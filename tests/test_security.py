from __future__ import annotations

import base64
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from conftest import csrf_headers, load_app


def _auth_headers(client: TestClient) -> dict[str, str]:
    token = base64.b64encode(b"admin:secret-password-123").decode("ascii")
    return csrf_headers(client, {"Authorization": f"Basic {token}"})


def test_basic_auth_blocks_dashboard_without_credentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with load_app(monkeypatch, tmp_path) as client:
        response = client.get("/dashboard")
        assert response.status_code == 401


def test_basic_auth_allows_dashboard_with_credentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    token = base64.b64encode(b"admin:secret-password-123").decode("ascii")
    headers = {"Authorization": f"Basic {token}"}

    with load_app(monkeypatch, tmp_path) as client:
        response = client.get("/dashboard", headers=headers)
        assert response.status_code == 200


def test_debug_with_credentials_still_requires_auth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with load_app(monkeypatch, tmp_path, DEBUG="true") as client:
        assert client.get("/dashboard").status_code == 401
        assert client.get("/debug").status_code == 401
        headers = _auth_headers(client)
        assert client.get("/debug", headers=headers).status_code == 200


def test_health_and_ready_stay_public_without_auth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with load_app(monkeypatch, tmp_path) as client:
        assert client.get("/health").status_code == 200
        response = client.get("/ready")
        assert response.status_code in {200, 503}
        checks = response.json()["checks"]
        assert "latest_file_path" not in checks
        assert "latest_file_id" not in checks
        assert "database_error" not in checks


def test_openapi_hidden_in_production(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    token = base64.b64encode(b"admin:secret-password-123").decode("ascii")
    headers = {"Authorization": f"Basic {token}"}

    with load_app(monkeypatch, tmp_path) as client:
        assert client.get("/api/docs", headers=headers).status_code == 404


def test_upload_rejects_oversized_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    payload = b"x" * 2048

    with load_app(monkeypatch, tmp_path) as client:
        headers = _auth_headers(client)
        response = client.post(
            "/api/files/upload",
            headers=headers,
            files={"file": ("big.xlsx", payload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert response.status_code == 413


def test_csrf_blocks_state_change_without_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    token = base64.b64encode(b"admin:secret-password-123").decode("ascii")
    headers = {"Authorization": f"Basic {token}"}
    with load_app(monkeypatch, tmp_path) as client:
        latest_id = client.get("/api/files", headers=headers).json()["latest_file_id"]
        response = client.post(f"/api/session/active-file/{latest_id}", headers=headers)
        assert response.status_code == 403


def test_csrf_blocks_missing_origin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    token = base64.b64encode(b"admin:secret-password-123").decode("ascii")
    with load_app(monkeypatch, tmp_path) as client:
        latest_id = client.get("/api/files", headers={"Authorization": f"Basic {token}"}).json()["latest_file_id"]
        csrf = client.get("/api/csrf-token", headers={"Authorization": f"Basic {token}"}).json()["csrf_token"]
        response = client.post(
            f"/api/session/active-file/{latest_id}",
            headers={"Authorization": f"Basic {token}", "X-CSRF-Token": csrf},
        )
        assert response.status_code == 403


def test_csrf_blocks_foreign_origin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with load_app(monkeypatch, tmp_path) as client:
        headers = _auth_headers(client)
        latest_id = client.get("/api/files", headers=headers).json()["latest_file_id"]
        headers["Origin"] = "https://evil.example"
        response = client.post(f"/api/session/active-file/{latest_id}", headers=headers)
        assert response.status_code == 403


def test_security_headers_include_csp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with load_app(monkeypatch, tmp_path) as client:
        headers = _auth_headers(client)
        response = client.get("/dashboard", headers=headers)
        assert response.status_code == 200
        csp = response.headers["content-security-policy"]
        assert "default-src 'self'" in csp
        assert "unsafe-eval" not in csp
        assert response.headers["x-frame-options"] == "DENY"
        assert 'nonce="' in response.text

        excel = client.get("/dashboard/excel", headers=headers)
        assert excel.status_code == 200
        assert "unsafe-eval" in excel.headers["content-security-policy"]


def test_malformed_basic_auth_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with load_app(monkeypatch, tmp_path) as client:
        response = client.get("/dashboard", headers={"Authorization": "Basic !!!"})
        assert response.status_code == 401


def test_production_auth_rejects_plain_http(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    secure_client = load_app(monkeypatch, tmp_path)
    with TestClient(secure_client.app, base_url="http://testserver") as client:
        response = client.get("/dashboard")
        assert response.status_code == 400


def test_x_forwarded_for_does_not_bypass_rate_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    payload = b"x" * 2048
    with load_app(monkeypatch, tmp_path) as client:
        headers = _auth_headers(client)
        statuses = []
        for index in range(3):
            request_headers = {**headers, "X-Forwarded-For": f"203.0.113.{index + 1}"}
            response = client.post(
                "/api/files/upload",
                headers=request_headers,
                files={"file": ("big.xlsx", payload, "application/octet-stream")},
            )
            statuses.append(response.status_code)
        assert statuses == [413, 413, 429]


def test_proxy_headers_xff_still_does_not_bypass_rate_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    payload = b"x" * 2048
    with load_app(monkeypatch, tmp_path, TRUSTED_PROXY_IPS="*") as client:
        headers = _auth_headers(client)
        statuses = []
        for index in range(3):
            request_headers = {**headers, "X-Forwarded-For": f"203.0.113.{index + 1}"}
            response = client.post(
                "/api/files/upload",
                headers=request_headers,
                files={"file": ("big.xlsx", payload, "application/octet-stream")},
            )
            statuses.append(response.status_code)
        assert statuses == [413, 413, 429]


def test_x_real_ip_from_trusted_proxy_is_used_for_rate_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    payload = b"x" * 2048
    with load_app(monkeypatch, tmp_path, TRUSTED_PROXY_IPS="*") as client:
        headers = _auth_headers(client)
        statuses = []
        for index in range(3):
            request_headers = {**headers, "X-Real-IP": f"203.0.113.{index + 1}"}
            response = client.post(
                "/api/files/upload",
                headers=request_headers,
                files={"file": ("big.xlsx", payload, "application/octet-stream")},
            )
            statuses.append(response.status_code)
        assert statuses == [413, 413, 413]


def test_auth_lockout_after_failed_attempts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    token = base64.b64encode(b"admin:wrong-password-123").decode("ascii")
    with load_app(monkeypatch, tmp_path, AUTH_LOCKOUT_ATTEMPTS="3") as client:
        statuses = [
            client.get("/dashboard", headers={"Authorization": f"Basic {token}"}).status_code
            for _ in range(4)
        ]
        assert statuses[:3] == [401, 401, 401]
        assert statuses[3] == 429
