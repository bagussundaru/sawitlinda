import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app import mappers, models, schemas
from app.config import get_settings
from app.db import get_db
from app.services import exif

router = APIRouter(prefix="/api", tags=["upload"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def _store_file(upload: UploadFile, destination: Path) -> None:
    with destination.open("wb") as target:
        shutil.copyfileobj(upload.file, target)


@router.post("/upload", response_model=schemas.UploadResponse, status_code=status.HTTP_201_CREATED)
def upload_images(
    files: list[UploadFile] = File(..., description="Satu atau beberapa citra UAV"),
    db: Session = Depends(get_db),
) -> schemas.UploadResponse:
    """Accept one or more UAV images, extract EXIF GPS/timestamp, and store them.

    Rejects the whole batch if any file has an unsupported extension, so the user
    is never left guessing which of their files made it through.
    """
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

    storage_path = get_settings().storage_path
    created: list[models.Image] = []
    written: list[Path] = []

    try:
        for upload in files:
            image_id = uuid.uuid4()
            extension = Path(upload.filename or "").suffix.lower()
            destination = storage_path / f"{image_id}{extension}"

            _store_file(upload, destination)
            written.append(destination)

            metadata = exif.extract(destination)
            image = models.Image(
                id=image_id,
                filename=upload.filename or destination.name,
                storage_path=str(destination),
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
