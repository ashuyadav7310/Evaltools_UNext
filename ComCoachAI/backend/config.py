# backend/config.py
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "development"

    # Database
    DATABASE_URL: str = "sqlite:///./comcoachai.db"

    # OpenAI
    OPENAI_API_KEY: str = ""

    # Admin
    ADMIN_TOKEN: str = "change-me-admin-token"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Public URLs
    BACKEND_BASE_URL: str = "http://127.0.0.1:8000"
    FRONTEND_BASE_URL: str = "http://127.0.0.1:3000"
    CORS_ORIGINS: str = "*"

    # Paths
    UPLOAD_DIR: str = "uploads"
    REPORT_DIR: str = "reports"

    # AWS / S3
    AWS_REGION: str = "ap-south-1"
    S3_ENABLED: bool = False
    S3_BUCKET_NAME: str = ""
    S3_AUDIO_PREFIX: str = "audio"
    S3_REPORT_PREFIX: str = "reports"
    S3_PRESIGNED_URL_EXPIRE_SECONDS: int = 3600

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parent.parent

    @property
    def upload_dir_path(self) -> Path:
        return (self.project_root / self.UPLOAD_DIR).resolve()

    @property
    def report_dir_path(self) -> Path:
        return (self.project_root / self.REPORT_DIR).resolve()

    @property
    def cors_origins_list(self) -> list[str]:
        raw_value = (self.CORS_ORIGINS or "*").strip()
        if raw_value == "*":
            return ["*"]
        return [origin.strip() for origin in raw_value.split(",") if origin.strip()]


@lru_cache()
def get_settings():
    return Settings()
