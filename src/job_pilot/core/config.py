from __future__ import annotations

from functools import lru_cache
from os import getenv
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["local", "dev", "test", "prod"]
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def resolve_env_file(app_env: str | None = None) -> Path:
    selected_app_env = (app_env or getenv("APP_ENV") or "local").strip().lower()
    if selected_app_env == "local":
        return PROJECT_ROOT / ".env"
    if selected_app_env in {"dev", "test", "prod"}:
        return PROJECT_ROOT / f".env.{selected_app_env}"
    return PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """应用配置，统一从默认值、.env 文件和环境变量读取。"""

    model_config = SettingsConfigDict(
        env_file=resolve_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "JobPilot"
    APP_ENV: AppEnv = "local"
    DEBUG: bool = False
    API_PREFIX: str = "/api"
    API_VERSION: str = "v1"

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    SECRET_KEY: str = Field(default="change-me-secret")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    JWT_ALGORITHM: str = "HS256"

    DATABASE_URL: str = "postgresql+asyncpg://jobpilot:jobpilot@127.0.0.1:5432/jobpilot"
    TEST_DATABASE_URL: str = "postgresql+asyncpg://jobpilot:jobpilot@127.0.0.1:5433/jobpilot_test"
    DATABASE_ECHO: bool = False

    REDIS_URL: str = "redis://:jobpilot_redis@127.0.0.1:6479/0"
    CELERY_BROKER_URL: str = "redis://:jobpilot_redis@127.0.0.1:6479/1"
    CELERY_RESULT_BACKEND: str = "redis://:jobpilot_redis@127.0.0.1:6479/2"

    UPLOAD_DIR: Path = Path("./storage/uploads")
    MAX_UPLOAD_SIZE_MB: int = 20

    BACKEND_CORS_ORIGINS: list[str] = [
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5173",
    ]

    LOG_LEVEL: str = "INFO"

    @field_validator("API_PREFIX")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("API_PREFIX must start with '/'")
        return value.rstrip("/") or "/api"

    @field_validator("API_VERSION")
    @classmethod
    def validate_api_version(cls, value: str) -> str:
        return value.strip("/")

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        if len(value) < 20:
            raise ValueError("SECRET_KEY must be at least 20 characters long")
        return value

    @property
    def is_local(self) -> bool:
        return self.APP_ENV == "local"

    @property
    def is_test(self) -> bool:
        return self.APP_ENV == "test"

    @property
    def is_prod(self) -> bool:
        return self.APP_ENV == "prod"

    @property
    def effective_database_url(self) -> str:
        if self.is_test:
            return self.TEST_DATABASE_URL
        return self.DATABASE_URL

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
