import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app import mappers, models, schemas
from app.config import get_settings
from app.db import get_db
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
    files: list[UploadFile] = File(..., description="Satu atau beberapa citra UAV"),
    block: str | None = Form(None, description="Blok kebun, mis. A-3"),
    area_ha: float | None = Form(None, description="Luas area yang tercakup (hektar)"),
    lat: float | None = Form(None, description="Lintang, dipakai bila EXIF tidak memuatnya"),
    lng: float | None = Form(None, description="Bujur, dipakai bila EXIF tidak memuatnya"),
    db: Session = Depends(get_db),
) -> schemas.UploadResponse:
    """Accept one or more UAV images, extract EXIF GPS/timestamp, and store them.

    Block and covered area cannot be derived from the image or its metadata, so the
    operator supplies them here; they apply to every file in the batch. Manual
    coordinates are a fallback used only when the frame carries no EXIF GPS — real
    metadata always wins, so a correct frame is never overwritten by a typo.

    Rejects the whole batch if any file has an unsupported extension, so the user
    is never left guessing which of their files made it through.
    """
    if (lat is None) != (lng is None):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Lintang dan bujur harus diisi berpasangan.",
        )
    if lat is not None and not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Koordinat di luar rentang yang sah.",
        )
    if area_ha is not None and area_ha <= 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Luas area harus lebih besar dari nol."
        )

    block = block.strip() if block and block.strip() else None
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

    try:
        for upload in files:
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
                captured_at=metadata.captured_at,
                block=block,
                area_ha=area_ha,
                # EXIF wins; the manual pair only fills a gap.
                gps_lat=metadata.lat if metadata.lat is not None else lat,
                gps_lng=metadata.lng if metadata.lng is not None else lng,
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
