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

    # --- Nebius Token Factory (lapisan analisis AI) ---
    #: Kosong berarti fitur analisis AI mati; aplikasi tetap berjalan penuh.
    nebius_api_key: str = ""
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1"
    #: Model dengan kemampuan vision.
    nebius_model: str = "Qwen/Qwen2-VL-72B-Instruct"
    nebius_timeout_s: float = 90.0

    @property
    def model_file(self) -> Path | None:
        """Lokasi berkas model, tidak bergantung direktori kerja.

        Path relatif diselesaikan terhadap backend/, karena uvicorn, pytest, dan
        container menjalankan proses dari direktori yang berbeda-beda.
        """
        if not self.model_path.strip():
            return None
        path = Path(self.model_path)
        return path if path.is_absolute() else BACKEND_ROOT / path

    @property
    def ai_enabled(self) -> bool:
        return bool(self.nebius_api_key.strip())

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
