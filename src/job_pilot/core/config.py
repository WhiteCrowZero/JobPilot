from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from defaults, .env and environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "JobPilot"
    APP_ENV: Literal["local", "dev", "test", "prod"] = "local"
    DEBUG: bool = True
    API_PREFIX: str = "/api"
    API_VERSION: str = "v1"

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    SECRET_KEY: str = Field(default="please-change-this-secret-key")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    ALGORITHM: str = "HS256"

    DATABASE_URL: str = "postgresql+asyncpg://jobpilot:jobpilot@localhost:5432/jobpilot"

    REDIS_URL: str = "redis://:jobpilot_redis@localhost:6389/0"
    CELERY_BROKER_URL: str = "redis://:jobpilot_redis@localhost:6389/1"
    CELERY_RESULT_BACKEND: str = "redis://:jobpilot_redis@localhost:6389/2"

    UPLOAD_DIR: Path = Path("./storage/uploads")
    MAX_UPLOAD_SIZE_MB: int = 20

    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
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

    @property
    def api_v1_prefix(self) -> str:
        return f"{self.API_PREFIX}/{self.API_VERSION}"

    @property
    def is_local(self) -> bool:
        return self.APP_ENV == "local"

    @property
    def is_prod(self) -> bool:
        return self.APP_ENV == "prod"

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
