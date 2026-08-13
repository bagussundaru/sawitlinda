import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app import mappers, models, schemas
from app.config import get_settings
from app.db import get_db
from app import villages
from app.services import exif

router = APIRouter(prefix="/api", tags=["upload"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


CHUNK_SIZE = 1024 * 1024


def _store_file(upload: UploadFile, destination: Path, max_bytes: int) -> None:
    """Stream the upload to disk, stopping if it exceeds the configured limit.

    Streaming in chunks keeps a large UAV frame from being held in memory whole,
    and the running total means an oversized file is rejected part-way rather than
    after the whole thing has landed on disk.
    """
    written = 0
    with destination.open("wb") as target:
        while chunk := upload.file.read(CHUNK_SIZE):
            written += len(chunk)
            if written > max_bytes:
                raise HTTPException(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    f"Berkas {upload.filename or '(tanpa nama)'} melebihi batas "
                    f"{max_bytes // (1024 * 1024)} MB.",
                )
            target.write(chunk)


@router.post("/upload", response_model=schemas.UploadResponse, status_code=status.HTTP_201_CREATED)
def upload_images(
    files: list[UploadFile] = File(..., description="Satu atau beberapa citra"),
    labels: list[str] = Form(
        default=[],
        description="Label tiap citra, berurutan sesuai daftar berkas. "
        "Boleh lebih pendek dari daftar berkas; sisanya memakai nama berkas.",
    ),
    village: str | None = Form(
        None,
        description="Desa asal citra; berlaku untuk seluruh berkas pada kiriman ini.",
    ),
    db: Session = Depends(get_db),
) -> schemas.UploadResponse:
    """Terima satu atau beberapa citra beserta labelnya, lalu simpan.

    Label diisi sendiri oleh pengunggah — itulah yang menjadi identitas citra di
    seluruh aplikasi. Bila dikosongkan, nama berkas dipakai apa adanya, sehingga
    citra tidak pernah berakhir tanpa nama.

    Waktu pengambilan dan koordinat masih dibaca dari EXIF bila ada dan tetap
    disimpan, meski tidak lagi ditampilkan sebagai peta.

    Seluruh batch ditolak bila ada satu berkas berformat tidak didukung, supaya
    pengguna tidak perlu menebak berkas mana yang lolos.
    """
    if village is not None and village.strip() and not villages.is_valid(village.strip()):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Desa tidak dikenal. Pilihan: {', '.join(v.key for v in villages.VILLAGES)}.",
        )
    desa = village.strip() if village and village.strip() else None

    if not files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Tidak ada berkas yang diunggah.")

    for upload in files:
        extension = Path(upload.filename or "").suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Format berkas tidak didukung: {upload.filename or '(tanpa nama)'}. "
                f"Gunakan: {', '.join(sorted(ALLOWED_EXTENSIONS))}.",
            )

    settings = get_settings()
    storage_path = settings.storage_path
    created: list[models.Image] = []
    written: list[Path] = []

    def _label(index: int, nama_berkas: str) -> str:
        """Label pilihan pengguna, atau nama berkas bila tidak diisi."""
        if index < len(labels) and labels[index].strip():
            return labels[index].strip()[:200]
        return nama_berkas

    try:
        for index, upload in enumerate(files):
            image_id = uuid.uuid4()
            extension = Path(upload.filename or "").suffix.lower()
            destination = storage_path / f"{image_id}{extension}"

            # Recorded before writing: a file rejected part-way through still
            # exists on disk and has to be cleaned up.
            written.append(destination)
            _store_file(upload, destination, settings.max_upload_bytes)

            metadata = exif.extract(destination)
            image = models.Image(
                id=image_id,
                filename=upload.filename or destination.name,
                storage_path=str(destination),
                label=_label(index, upload.filename or destination.name),
                village=desa,
                captured_at=metadata.captured_at,
                gps_lat=metadata.lat,
                gps_lng=metadata.lng,
                status="uploaded",
            )
            db.add(image)
            created.append(image)

        db.commit()
    except Exception:
        # Do not leave orphaned files behind when the transaction fails.
        db.rollback()
        for path in written:
            path.unlink(missing_ok=True)
        raise

    for image in created:
        db.refresh(image)

    return schemas.UploadResponse(images=[mappers.image_out(image) for image in created])
