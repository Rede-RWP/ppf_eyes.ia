from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = ROOT_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_secret_key: str = "change-me-to-a-long-random-string"
    admin_username: str = "admin"
    admin_password: str = "admin123"
    encryption_key: str = ""

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    default_ai_provider: str = "openai"
    openai_api_key: str = ""
    gemini_api_key: str = ""
    anthropic_api_key: str = ""

    data_dir: str = str(DEFAULT_DATA_DIR)
    database_url: str = ""

    # MySQL (usado se DATABASE_URL estiver vazio)
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "ppf_eyes"
    mysql_password: str = "ppf_eyes"
    mysql_database: str = "ppf_eyes"

    access_token_expire_minutes: int = 60 * 8
    auth_cookie_name: str = "ppf_eyes_session"
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"  # lax | strict | none
    auth_max_failed_attempts: int = 5
    auth_lockout_minutes: int = 15
    auth_rate_limit_window_sec: int = 60
    auth_rate_limit_max: int = 10
    # Imagens de alerta (não favoritas) expiram após N horas
    snapshot_retention_hours: int = 24
    # Fuso para horário de funcionamento das lojas
    app_timezone: str = "America/Sao_Paulo"

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def data_path(self) -> Path:
        path = Path(self.data_dir)
        if not path.is_absolute():
            path = (ROOT_DIR / path).resolve()
        return path

    @property
    def snapshots_path(self) -> Path:
        return self.data_path / "snapshots"

    @property
    def favorites_path(self) -> Path:
        return self.data_path / "favorites"

    def build_database_url(self) -> str:
        if self.database_url.strip():
            return self.database_url.strip()
        user = quote_plus(self.mysql_user)
        password = quote_plus(self.mysql_password)
        return (
            f"mysql+pymysql://{user}:{password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            "?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    data = s.data_path
    data.mkdir(parents=True, exist_ok=True)
    (data / "snapshots").mkdir(parents=True, exist_ok=True)
    (data / "favorites").mkdir(parents=True, exist_ok=True)
    object.__setattr__(s, "database_url", s.build_database_url())
    return s
