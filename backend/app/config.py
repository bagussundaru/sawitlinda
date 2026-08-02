from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings, loaded from environment / backend/.env."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://sawitscan:sawitscan@localhost:5432/sawitscan"
    storage_dir: str = "storage"
    cors_origins: str = "http://localhost:3000"
    model_path: str = ""

    #: Largest single image accepted, in megabytes. UAV frames are big; this only
    #: guards against a runaway upload filling the disk.
    max_upload_mb: int = 50

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def storage_path(self) -> Path:
        path = BACKEND_ROOT / self.storage_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
