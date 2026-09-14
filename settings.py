from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent
WEAK_SESSION_SECRETS = frozenset({"change-me-in-production", "test-secret", "secret", "changeme"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    debug: bool = Field(
        default=False,
        validation_alias=AliasChoices("DEBUG", "OPOP_DEBUG"),
    )
    app_host: str = Field(
        default="0.0.0.0",
        validation_alias=AliasChoices("APP_HOST", "OPOP_APP_HOST"),
    )
    app_port: int = Field(
        default=8000,
        validation_alias=AliasChoices("APP_PORT", "OPOP_APP_PORT"),
    )
    session_secret: str = Field(
        default="change-me-in-production",
        validation_alias=AliasChoices("SESSION_SECRET", "OPOP_SESSION_SECRET"),
    )
    auth_username: str = Field(
        default="",
        validation_alias=AliasChoices("AUTH_USERNAME", "OPOP_AUTH_USERNAME"),
    )
    auth_password: str = Field(
        default="",
        validation_alias=AliasChoices("AUTH_PASSWORD", "OPOP_AUTH_PASSWORD"),
    )
    allow_insecure_debug: bool = Field(
        default=False,
        validation_alias=AliasChoices("ALLOW_INSECURE_DEBUG", "OPOP_ALLOW_INSECURE_DEBUG"),
    )
    auth_lockout_attempts: int = Field(
        default=5,
        validation_alias=AliasChoices("AUTH_LOCKOUT_ATTEMPTS", "OPOP_AUTH_LOCKOUT_ATTEMPTS"),
    )
    auth_lockout_window_seconds: int = Field(
        default=300,
        validation_alias=AliasChoices(
            "AUTH_LOCKOUT_WINDOW_SECONDS",
            "OPOP_AUTH_LOCKOUT_WINDOW_SECONDS",
        ),
    )
    max_upload_bytes: int = Field(
        default=52_428_800,
        validation_alias=AliasChoices("MAX_UPLOAD_BYTES", "OPOP_MAX_UPLOAD_BYTES"),
    )
    upload_rate_limit_per_minute: int = Field(
        default=10,
        validation_alias=AliasChoices("UPLOAD_RATE_LIMIT_PER_MINUTE", "OPOP_UPLOAD_RATE_LIMIT_PER_MINUTE"),
    )
    trusted_proxy_ips: str = Field(
        default="",
        validation_alias=AliasChoices("TRUSTED_PROXY_IPS", "OPOP_TRUSTED_PROXY_IPS"),
    )
    allowed_hosts: str = Field(
        default="localhost,127.0.0.1,testserver",
        validation_alias=AliasChoices("ALLOWED_HOSTS", "OPOP_ALLOWED_HOSTS"),
    )
    xlsx_max_archive_entries: int = Field(
        default=20_000,
        validation_alias=AliasChoices("XLSX_MAX_ARCHIVE_ENTRIES", "OPOP_XLSX_MAX_ARCHIVE_ENTRIES"),
    )
    xlsx_max_uncompressed_bytes: int = Field(
        default=262_144_000,
        validation_alias=AliasChoices("XLSX_MAX_UNCOMPRESSED_BYTES", "OPOP_XLSX_MAX_UNCOMPRESSED_BYTES"),
    )
    xlsx_max_compression_ratio: int = Field(
        default=100,
        validation_alias=AliasChoices("XLSX_MAX_COMPRESSION_RATIO", "OPOP_XLSX_MAX_COMPRESSION_RATIO"),
    )
    xlsx_max_sheets: int = Field(
        default=50,
        validation_alias=AliasChoices("XLSX_MAX_SHEETS", "OPOP_XLSX_MAX_SHEETS"),
    )
    xlsx_max_rows_per_sheet: int = Field(
        default=100_000,
        validation_alias=AliasChoices("XLSX_MAX_ROWS_PER_SHEET", "OPOP_XLSX_MAX_ROWS_PER_SHEET"),
    )
    xlsx_validation_timeout_seconds: int = Field(
        default=30,
        validation_alias=AliasChoices(
            "XLSX_VALIDATION_TIMEOUT_SECONDS",
            "OPOP_XLSX_VALIDATION_TIMEOUT_SECONDS",
        ),
    )
    max_upload_storage_bytes: int = Field(
        default=1_073_741_824,
        validation_alias=AliasChoices("MAX_UPLOAD_STORAGE_BYTES", "OPOP_MAX_UPLOAD_STORAGE_BYTES"),
    )
    max_upload_files: int = Field(
        default=100,
        validation_alias=AliasChoices("MAX_UPLOAD_FILES", "OPOP_MAX_UPLOAD_FILES"),
    )
    log_max_bytes: int = Field(
        default=10_485_760,
        validation_alias=AliasChoices("LOG_MAX_BYTES", "OPOP_LOG_MAX_BYTES"),
    )
    log_backup_count: int = Field(
        default=10,
        validation_alias=AliasChoices("LOG_BACKUP_COUNT", "OPOP_LOG_BACKUP_COUNT"),
    )

    data_dir: Path = Field(
        default=Path("data"),
        validation_alias=AliasChoices("DATA_DIR", "OPOP_DATA_DIR"),
    )
    uploads_dir: Path = Field(
        default=Path("uploads"),
        validation_alias=AliasChoices("UPLOADS_DIR", "OPOP_UPLOADS_DIR"),
    )
    database_path: Path = Field(
        default=Path("runtime/dashboard.sqlite3"),
        validation_alias=AliasChoices("DATABASE_PATH", "OPOP_DATABASE_PATH"),
    )
    logs_dir: Path = Field(
        default=Path("logs"),
        validation_alias=AliasChoices("LOGS_DIR", "OPOP_LOGS_DIR"),
    )
    active_default_file: str = Field(
        default="data.xlsx",
        validation_alias=AliasChoices("ACTIVE_DEFAULT_FILE", "OPOP_ACTIVE_DEFAULT_FILE"),
    )

    @property
    def auth_enabled(self) -> bool:
        return bool(self.auth_username and self.auth_password)

    @property
    def expose_openapi(self) -> bool:
        return self.debug

    @property
    def trusted_proxy_host_list(self) -> list[str]:
        if not self.trusted_proxy_ips.strip():
            return []
        return [item.strip() for item in self.trusted_proxy_ips.split(",") if item.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_hosts.split(",") if item.strip()]

    def resolve_path(self, path: Path) -> Path:
        if path.is_absolute():
            return path
        return BASE_DIR / path

    @property
    def resolved_data_dir(self) -> Path:
        return self.resolve_path(self.data_dir)

    @property
    def resolved_uploads_dir(self) -> Path:
        return self.resolve_path(self.uploads_dir)

    @property
    def resolved_database_path(self) -> Path:
        return self.resolve_path(self.database_path)

    @property
    def resolved_logs_dir(self) -> Path:
        return self.resolve_path(self.logs_dir)

    @property
    def default_excel_path(self) -> Path:
        return self.resolved_data_dir / self.active_default_file

    def ensure_runtime_dirs(self) -> None:
        self.resolved_data_dir.mkdir(parents=True, exist_ok=True)
        self.resolved_uploads_dir.mkdir(parents=True, exist_ok=True)
        self.resolved_database_path.parent.mkdir(parents=True, exist_ok=True)
        self.resolved_logs_dir.mkdir(parents=True, exist_ok=True)

    @model_validator(mode="after")
    def validate_security(self) -> Settings:
        positive_limits = {
            "MAX_UPLOAD_BYTES": self.max_upload_bytes,
            "XLSX_MAX_ARCHIVE_ENTRIES": self.xlsx_max_archive_entries,
            "XLSX_MAX_UNCOMPRESSED_BYTES": self.xlsx_max_uncompressed_bytes,
            "XLSX_MAX_COMPRESSION_RATIO": self.xlsx_max_compression_ratio,
            "XLSX_MAX_SHEETS": self.xlsx_max_sheets,
            "XLSX_MAX_ROWS_PER_SHEET": self.xlsx_max_rows_per_sheet,
            "XLSX_VALIDATION_TIMEOUT_SECONDS": self.xlsx_validation_timeout_seconds,
            "MAX_UPLOAD_STORAGE_BYTES": self.max_upload_storage_bytes,
            "MAX_UPLOAD_FILES": self.max_upload_files,
            "LOG_MAX_BYTES": self.log_max_bytes,
            "LOG_BACKUP_COUNT": self.log_backup_count,
            "AUTH_LOCKOUT_ATTEMPTS": self.auth_lockout_attempts,
            "AUTH_LOCKOUT_WINDOW_SECONDS": self.auth_lockout_window_seconds,
        }
        invalid = [name for name, value in positive_limits.items() if value <= 0]
        if invalid:
            raise ValueError(f"Security limits must be greater than 0: {', '.join(invalid)}")
        if not self.allowed_host_list:
            raise ValueError("ALLOWED_HOSTS must contain at least one host")
        if self.allow_insecure_debug and not self.debug:
            raise ValueError("ALLOW_INSECURE_DEBUG requires DEBUG=true")
        if self.allow_insecure_debug:
            return self
        if self.debug and not self.auth_enabled:
            raise ValueError(
                "AUTH_USERNAME and AUTH_PASSWORD are required when DEBUG=true "
                "unless ALLOW_INSECURE_DEBUG=true"
            )
        if self.debug:
            return self

        if len(self.session_secret) < 32 or self.session_secret in WEAK_SESSION_SECRETS:
            raise ValueError(
                "SESSION_SECRET must be a random string with at least 32 characters when DEBUG=false"
            )
        if not self.auth_enabled:
            raise ValueError("AUTH_USERNAME and AUTH_PASSWORD are required when DEBUG=false")
        if len(self.auth_password) < 16:
            raise ValueError("AUTH_PASSWORD must contain at least 16 characters when DEBUG=false")
        return self


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_runtime_dirs()
    return settings
