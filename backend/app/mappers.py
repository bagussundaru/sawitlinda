"""ORM -> Pydantic conversion, kept in one place so the JSON contract is built
identically by every endpoint."""

from app import models, schemas


def gps_of(lat: float | None, lng: float | None) -> schemas.Gps | None:
    if lat is None or lng is None:
        return None
    return schemas.Gps(lat=lat, lng=lng)


def image_out(image: models.Image) -> schemas.ImageOut:
    return schemas.ImageOut(
        image_id=image.id,
        filename=image.filename,
        captured_at=image.captured_at,
        gps=gps_of(image.gps_lat, image.gps_lng),
        status=image.status,
        created_at=image.created_at,
    )
