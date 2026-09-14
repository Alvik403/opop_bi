from __future__ import annotations

import base64
import ipaddress
import logging
import secrets
import time
from collections import defaultdict
from threading import Lock
from urllib.parse import urlsplit

from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

PUBLIC_PATHS = frozenset({"/health", "/ready"})
UPLOAD_PATHS = frozenset({"/api/files/upload", "/api/excel/save-version"})
EXCEL_EDITOR_PREFIX = "/dashboard/excel"
CSRF_SESSION_KEY = "csrf_token"
logger = logging.getLogger("opop_bi.security")


def _strict_csp(nonce: str) -> str:
    return (
        "default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "worker-src 'self'; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
    )


def _excel_csp(nonce: str) -> str:
    return (
        "default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}' 'unsafe-eval' blob:; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "worker-src 'self' blob:; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
    )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.csp_nonce = secrets.token_urlsafe(18)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        csp = (
            _excel_csp(request.state.csp_nonce)
            if request.url.path.startswith(EXCEL_EDITOR_PREFIX)
            else _strict_csp(request.state.csp_nonce)
        )
        response.headers.setdefault("Content-Security-Policy", csp)
        if request.url.path.startswith(("/api/", "/dashboard", "/debug")):
            response.headers.setdefault("Cache-Control", "no-store")
        return response


class AuthLockout:
    def __init__(self, max_attempts: int = 5, window_seconds: float = 300.0):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._failures: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def _prune(self, key: str, now: float) -> list[float]:
        window_start = now - self.window_seconds
        recent = [stamp for stamp in self._failures.get(key, []) if stamp >= window_start]
        if recent:
            self._failures[key] = recent
        else:
            self._failures.pop(key, None)
        return recent

    def is_locked(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            return len(self._prune(key, now)) >= self.max_attempts

    def register_failure(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            recent = self._prune(key, now)
            recent.append(now)
            self._failures[key] = recent

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)


def request_is_https(request: Request) -> bool:
    if request.url.scheme == "https":
        return True
    proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    return proto == "https"


class BasicAuthMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        username: str,
        password: str,
        require_https: bool = True,
        lockout: AuthLockout | None = None,
    ):
        super().__init__(app)
        self.username = username
        self.password = password
        self.require_https = require_https
        self.lockout = lockout or AuthLockout()

    async def dispatch(self, request: Request, call_next):
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)
        if self.require_https and not request_is_https(request):
            logger.error(
                "insecure_auth_transport_blocked",
                extra={"path": request.url.path, "client_ip": client_key(request)},
            )
            return Response(status_code=400, content="HTTPS is required")

        key = client_key(request)
        if self.lockout.is_locked(key):
            logger.warning(
                "authentication_lockout",
                extra={"path": request.url.path, "client_ip": key},
            )
            return Response(status_code=429, content="Too many failed authentication attempts")

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Basic "):
            return self._unauthorized(request, "missing")

        try:
            decoded = base64.b64decode(auth_header[6:], validate=True).decode("utf-8")
            username, separator, password = decoded.partition(":")
            if not separator:
                self.lockout.register_failure(key)
                return self._unauthorized(request, "malformed")
        except (ValueError, UnicodeDecodeError):
            self.lockout.register_failure(key)
            return self._unauthorized(request, "malformed")

        if not (
            secrets.compare_digest(username, self.username)
            and secrets.compare_digest(password, self.password)
        ):
            self.lockout.register_failure(key)
            return self._unauthorized(request, "invalid")

        self.lockout.reset(key)
        return await call_next(request)

    @staticmethod
    def _unauthorized(request: Request, reason: str) -> Response:
        logger.warning(
            "authentication_failed",
            extra={
                "request_id": getattr(request.state, "request_id", None),
                "client_ip": request.client.host if request.client else "unknown",
                "path": request.url.path,
                "reason": reason,
            },
        )
        return Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="OPOP BI"'},
            content="Authentication required",
        )


class UploadRateLimiter:
    def __init__(self, limit_per_minute: int):
        self.limit_per_minute = limit_per_minute
        self._events: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, client_key: str) -> None:
        if self.limit_per_minute <= 0:
            return

        now = time.monotonic()
        window_start = now - 60.0

        with self._lock:
            stale_keys = [
                key
                for key, stamps in self._events.items()
                if key != client_key and not any(stamp >= window_start for stamp in stamps)
            ]
            for key in stale_keys:
                self._events.pop(key, None)

            recent = [stamp for stamp in self._events[client_key] if stamp >= window_start]
            if len(recent) >= self.limit_per_minute:
                if recent:
                    self._events[client_key] = recent
                else:
                    self._events.pop(client_key, None)
                raise RateLimitExceeded()
            recent.append(now)
            self._events[client_key] = recent


class RateLimitExceeded(Exception):
    pass


def _is_private_or_loopback(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_private or address.is_loopback


def trusted_proxy_hosts(request: Request) -> list[str]:
    return list(getattr(request.app.state, "trusted_proxy_hosts", []) or [])


def client_key(request: Request) -> str:
    remote = request.client.host if request.client else "unknown"
    trusted = trusted_proxy_hosts(request)
    peer_trusted = "*" in trusted or remote in trusted or _is_private_or_loopback(remote)
    if peer_trusted:
        real_ip = (request.headers.get("x-real-ip") or "").split(",")[0].strip()
        if real_ip:
            return real_ip
    return remote


def enforce_upload_rate_limit(request: Request, limiter: UploadRateLimiter) -> None:
    if request.url.path not in UPLOAD_PATHS:
        return
    limiter.check(client_key(request))


def get_or_create_csrf_token(request: Request) -> str:
    token = request.session.get(CSRF_SESSION_KEY)
    if not isinstance(token, str) or len(token) < 32:
        token = secrets.token_urlsafe(32)
        request.session[CSRF_SESSION_KEY] = token
    return token


def _host_allowed(netloc: str, allowed_hosts: list[str]) -> bool:
    host = (netloc or "").split("@")[-1].lower()
    hostname = host.split(":")[0]
    allowed = {item.lower() for item in allowed_hosts}
    return host in allowed or hostname in allowed or "*" in allowed


def enforce_csrf(request: Request, allowed_hosts: list[str] | None = None) -> None:
    expected = request.session.get(CSRF_SESSION_KEY)
    supplied = request.headers.get("x-csrf-token", "")
    if not (
        isinstance(expected, str)
        and supplied
        and secrets.compare_digest(expected, supplied)
    ):
        raise HTTPException(status_code=403, detail="Недействительный CSRF-токен")

    source = request.headers.get("origin") or request.headers.get("referer")
    if not source:
        raise HTTPException(status_code=403, detail="Недопустимый источник запроса")
    source_url = urlsplit(source)
    hosts = allowed_hosts if allowed_hosts is not None else list(
        getattr(request.app.state, "allowed_hosts", []) or []
    )
    if not hosts:
        hosts = [request.url.hostname or ""]
    if not _host_allowed(source_url.netloc, hosts):
        raise HTTPException(status_code=403, detail="Недопустимый источник запроса")
