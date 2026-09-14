from __future__ import annotations

import pytest
from pydantic import ValidationError

from settings import Settings


def test_production_settings_require_strong_secret_and_auth(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("SESSION_SECRET", "short")
    monkeypatch.setenv("AUTH_USERNAME", "")
    monkeypatch.setenv("AUTH_PASSWORD", "")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_production_settings_accept_valid_config(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "strong-password-123")

    settings = Settings(_env_file=None)
    assert settings.auth_enabled is True
    assert settings.expose_openapi is False


def test_debug_without_insecure_flag_requires_auth(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("AUTH_USERNAME", "")
    monkeypatch.setenv("AUTH_PASSWORD", "")
    monkeypatch.delenv("ALLOW_INSECURE_DEBUG", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_insecure_debug_allows_open_local_loop(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("ALLOW_INSECURE_DEBUG", "true")
    monkeypatch.setenv("AUTH_USERNAME", "")
    monkeypatch.setenv("AUTH_PASSWORD", "")

    settings = Settings(_env_file=None)
    assert settings.expose_openapi is True
    assert settings.auth_enabled is False


def test_debug_does_not_disable_auth_when_credentials_set(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "strong-password-123")

    settings = Settings(_env_file=None)
    assert settings.auth_enabled is True
    assert settings.expose_openapi is True
