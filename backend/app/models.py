import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Image(Base):
    """One uploaded UAV image."""

    __tablename__ = "images"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(512))
    #: Nama yang diberikan pengunggah — identitas citra di seluruh aplikasi.
    #: Kosong hanya mungkin pada baris lama sebelum migrasi 0008.
    label: Mapped[str | None] = mapped_column(String(200), index=True)
    #: Desa asal citra — pengelompokan pada peta. Salah satu kunci di
    #: app/villages.py, atau None bila tidak dicatat.
    village: Mapped[str | None] = mapped_column(String(64), index=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # --- Peninggalan konsep pemetaan. Tidak lagi diisi maupun ditampilkan,
    #     tetapi sengaja dipertahankan: data yang sudah terkumpul tetap utuh dan
    #     fitur peta dapat dihidupkan lagi tanpa memulihkan apa pun. ---
    block: Mapped[str | None] = mapped_column(String(64), index=True)
    area_ha: Mapped[float | None] = mapped_column(Float)
    gps_lat: Mapped[float | None] = mapped_column(Float)
    gps_lng: Mapped[float | None] = mapped_column(Float)
    # uploaded | analyzed
    status: Mapped[str] = mapped_column(String(16), default="uploaded")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # --- Penilaian tingkat citra dari model vision (opsional, lihat
    #     app/inference/nebius.py). Semua nullable: fitur boleh dimatikan. ---
    ai_summary: Mapped[str | None] = mapped_column(Text)
    ai_recommendation: Mapped[str | None] = mapped_column(Text)
    ai_dominant_condition: Mapped[str | None] = mapped_column(String(128))
    ai_confidence: Mapped[float | None] = mapped_column(Float)
    ai_affected_share: Mapped[float | None] = mapped_column(Float)
    #: Catatan keterbatasan dari model, dipisah baris baru.
    ai_notes: Mapped[str | None] = mapped_column(Text)
    ai_model: Mapped[str | None] = mapped_column(String(128))
    ai_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    detections: Mapped[list["Detection"]] = relationship(
        back_populates="image",
        cascade="all, delete-orphan",
        order_by="Detection.id",
    )


class Detection(Base):
    """One detected palm tree within an image."""

    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    image_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("images.id", ondelete="CASCADE"), index=True
    )
    bbox_x: Mapped[float] = mapped_column(Float)
    bbox_y: Mapped[float] = mapped_column(Float)
    bbox_w: Mapped[float] = mapped_column(Float)
    bbox_h: Mapped[float] = mapped_column(Float)
    condition: Mapped[str] = mapped_column(String(128))
    # ringan | sedang | berat
    severity: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float] = mapped_column(Float)
    gps_lat: Mapped[float | None] = mapped_column(Float)
    gps_lng: Mapped[float | None] = mapped_column(Float)

    image: Mapped[Image] = relationship(back_populates="detections")


class Evaluation(Base):
    """Satu kali evaluasi terhadap anotasi ground truth.

    Disimpan agar angkanya dapat dibuka kembali dan dibandingkan antarwaktu —
    tanpa itu, metrik disertasi hanya ada di layar sekali jalan.
    """

    __tablename__ = "evaluations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    source_filename: Mapped[str] = mapped_column(String(255))
    iou_threshold: Mapped[float] = mapped_column(Float)

    #: Keadaan sistem saat evaluasi dijalankan — supaya angka mock tidak pernah
    #: tertukar dengan angka model sungguhan di kemudian hari.
    inference_mode: Mapped[str] = mapped_column(String(16))
    model_name: Mapped[str | None] = mapped_column(String(128))

    images: Mapped[int] = mapped_column(Integer)
    ground_truths: Mapped[int] = mapped_column(Integer)
    predictions: Mapped[int] = mapped_column(Integer)

    map50: Mapped[float] = mapped_column(Float)
    micro_precision: Mapped[float] = mapped_column(Float)
    micro_recall: Mapped[float] = mapped_column(Float)
    micro_f1: Mapped[float] = mapped_column(Float)

    per_class: Mapped[list] = mapped_column(JSON)
    confusion: Mapped[dict] = mapped_column(JSON)


class User(Base):
    """Operator yang boleh memakai aplikasi.

    Password tidak pernah disimpan, hanya turunannya (scrypt + salt acak).
    Lihat app/services/auth.py.
    """

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(64), primary_key=True)
    #: Format: scrypt$<n>$<r>$<p>$<salt_hex>$<hash_hex>
    password_hash: Mapped[str] = mapped_column(String(512))
    full_name: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SessionToken(Base):
    """Sesi login yang sedang berjalan.

    Yang disimpan adalah SHA-256 dari token, bukan tokennya. Bocornya isi tabel
    ini karena itu tidak cukup untuk menyamar sebagai pengguna.
    """

    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(
        ForeignKey("users.username", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class TrainingRun(Base):
    """Satu kali training di mesin GPU Modal.

    Disimpan di PostgreSQL, bukan hanya di modal.Dict: Dict tidak dirancang
    sebagai penyimpanan permanen, sementara riwayat training adalah bagian dari
    catatan penelitian yang harus bertahan.
    """

    __tablename__ = "training_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    #: job_id dari mesin Modal — kunci untuk menanyakan progres.
    job_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    run_name: Mapped[str] = mapped_column(String(128))
    base_model: Mapped[str] = mapped_column(String(64))
    epochs: Mapped[int] = mapped_column(Integer)
    dataset_filename: Mapped[str | None] = mapped_column(String(255))

    # queued | running | done | failed
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    started_by: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    #: Metrik epoch terakhir, diisi saat training selesai.
    final_map50: Mapped[float | None] = mapped_column(Float)
    final_map50_95: Mapped[float | None] = mapped_column(Float)
    last_epoch: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)

    #: Terisi setelah bobot diunduh dan dijadikan model aktif.
    weights_path: Mapped[str | None] = mapped_column(String(512))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Job(Base):
    """Pekerjaan yang berjalan di latar belakang.

    Disimpan sebagai baris database, bukan di memori: pekerjaan yang hanya ada
    di memori hilang begitu container restart, dan tidak ada cara mengetahui
    apakah ia pernah selesai. Antreannya pun cukup satu tabel — beban aplikasi
    ini satu operator dengan pekerjaan berurutan, dan VM-nya sudah padat oleh
    aplikasi lain.
    """

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    #: roboflow_evaluate | reanalyse
    kind: Mapped[str] = mapped_column(String(32), index=True)
    # queued | running | done | failed | cancelled
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)

    #: Masukan pekerjaan, bentuknya bergantung `kind`.
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    #: {"current": n, "total": n, "message": "..."} — dibaca layar saat memantau.
    progress: Mapped[dict] = mapped_column(JSON, default=dict)
    #: Hasil akhir; untuk evaluasi berisi id evaluasinya.
    result: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)

    created_by: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Experiment(Base):
    """Satu evaluasi yang tercatat permanen.

    Dibuat sebagai catatan yang TIDAK dapat diubah: tidak ada endpoint yang
    menyunting atau menghapusnya, dan hasilnya hanya boleh dilampirkan sekali.
    Catatan eksperimen yang dapat disunting setelah hasilnya terlihat bukan
    catatan eksperimen.

    Hipotesis dicatat SEBELUM hasil dilampirkan. Hipotesis yang ditulis setelah
    melihat angkanya tidak membuktikan apa pun.
    """

    __tablename__ = "experiments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    #: Nama yang dibaca manusia, mis. "EXP-2026-001" atau "B1-dji-only".
    experiment_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    #: validation | test
    #:
    #: `validation` boleh dijalankan berkali-kali selama pengembangan.
    #: `test` dimaksudkan sekali, setelah model final dibekukan.
    kind: Mapped[str] = mapped_column(String(16), index=True)

    #: draft | locked | training | ready_for_final_test | final_tested
    #:
    #: Hanya maju, tidak pernah mundur. Sejak `locked`, hipotesis dan identitas
    #: dataset tidak dapat diubah lagi — itulah yang membuat "dibekukan" berarti
    #: sesuatu, bukan sekadar kesepakatan lisan.
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)

    #: sha256 berkas bobot. Model yang berbeda boleh diuji pada test yang sama;
    #: model yang SAMA diuji dua kali pada test yang sama adalah keadaan yang
    #: harus disengaja, bukan terjadi begitu saja.
    model_id: Mapped[str] = mapped_column(String(64), index=True)
    model_name: Mapped[str | None] = mapped_column(String(128))

    dataset_name: Mapped[str] = mapped_column(String(128))
    #: sha256 isi split test. Enam bulan kemudian, inilah satu-satunya cara
    #: memastikan angka yang dilaporkan diukur pada test set yang sama.
    dataset_test_hash: Mapped[str] = mapped_column(String(64), index=True)
    dataset_val_hash: Mapped[str | None] = mapped_column(String(64))

    #: Ditulis sebelum hasilnya ada.
    hypothesis: Mapped[str | None] = mapped_column(Text)
    training_config: Mapped[dict] = mapped_column(JSON, default=dict)
    git_commit: Mapped[str | None] = mapped_column(String(64))

    #: Terisi sekali lewat endpoint hasil; percobaan kedua ditolak.
    metrics: Mapped[dict | None] = mapped_column(JSON)
    results_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_by: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AppSetting(Base):
    """Pengaturan yang dapat diubah saat aplikasi berjalan.

    Dipakai untuk nilai yang tidak boleh masuk repositori — mis. kunci API —
    sehingga operator dapat mengisinya lewat layar Pengaturan tanpa menyunting
    berkas .env dan tanpa restart container.

    Nilai di sini menimpa environment variable dengan nama yang setara.
    """

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
