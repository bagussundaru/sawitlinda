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
    #: Model bawaan. Harus ada di daftar model Nebius — Qwen2-VL (tanpa .5)
    #: TIDAK tersedia di sana, dan memakainya membuat setiap analisis gagal.
    #: Per Agustus 2026 satu-satunya model vision di Nebius adalah Qwen2.5-VL;
    #: moonshotai/Kimi-K3 juga menerima gambar.
    nebius_model: str = "Qwen/Qwen2.5-VL-72B-Instruct"
    nebius_timeout_s: float = 90.0

    #: Nyalakan pekerja latar di proses ini. Dimatikan saat pengujian — pekerja
    #: memakai koneksi database sendiri, di luar jangkauan penggantian
    #: dependency, sehingga ia akan mencoba menghubungi database sungguhan.
    #: Juga berguna bila kelak aplikasi dijalankan lebih dari satu replika dan
    #: hanya satu di antaranya yang boleh mengerjakan antrean.
    worker_enabled: bool = True

    # --- Autentikasi ---
    #: Umur sesi login. Setelah ini pengguna harus masuk lagi.
    session_hours: int = 12
    #: Kirim cookie hanya lewat HTTPS. WAJIB true di produksi; false hanya untuk
    #: pengembangan lokal yang berjalan di http://localhost.
    cookie_secure: bool = False

    # --- Mesin training (Modal) ---
    #: URL endpoint web Modal, mis. https://<workspace>--sawitscan-training-web.modal.run
    #: Kosong berarti menu Training melapor "belum dikonfigurasi"; sisa aplikasi
    #: tetap berjalan penuh.
    modal_training_url: str = ""
    #: Token bearer yang sama dengan secret sawitscan-training-token di Modal.
    #: JANGAN pernah sampai ke peramban — hanya dipakai server ke server.
    modal_training_token: str = ""
    #: Training memakan waktu lama, tapi permintaan HTTP ke Modal tidak: yang
    #: lama adalah unggah dataset dan unduh bobot.
    modal_timeout_s: float = 900.0

    # --- Mesin inference GPU (Modal) ---
    #: Kosong berarti deteksi dijalankan di CPU VM ini. Mengisinya memindahkan
    #: bagian beratnya ke GPU; sisanya — penggabungan, keparahan, georeferensi —
    #: tetap dihitung di sini.
    modal_inference_url: str = ""
    modal_inference_token: str = ""
    #: Container GPU perlu menyala lebih dulu pada permintaan pertama.
    modal_inference_timeout_s: float = 300.0

    @property
    def gpu_inference_enabled(self) -> bool:
        return bool(
            self.modal_inference_url.strip() and self.modal_inference_token.strip()
        )

    @property
    def training_enabled(self) -> bool:
        return bool(self.modal_training_url.strip() and self.modal_training_token.strip())

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
