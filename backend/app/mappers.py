"""ORM -> Pydantic conversion, kept in one place so the JSON contract is built
identically by every endpoint."""

from app import models, schemas


def gps_of(lat: float | None, lng: float | None) -> schemas.Gps | None:
    if lat is None or lng is None:
        return None
    return schemas.Gps(lat=lat, lng=lng)


def summarise(detections: list[models.Detection]) -> schemas.Summary:
    """Count trees by health. `infected` covers every non-healthy tree; `severe`
    is the subset needing urgent action, so the two deliberately overlap."""
    infected = [d for d in detections if d.severity != "sehat"]
    return schemas.Summary(
        total=len(detections),
        healthy=len(detections) - len(infected),
        infected=len(infected),
        severe=len([d for d in infected if d.severity == "berat"]),
    )


def detection_out(detection: models.Detection) -> schemas.DetectionOut:
    return schemas.DetectionOut(
        id=detection.id,
        bbox=[detection.bbox_x, detection.bbox_y, detection.bbox_w, detection.bbox_h],
        condition=detection.condition,
        severity=detection.severity,
        confidence=detection.confidence,
        gps=gps_of(detection.gps_lat, detection.gps_lng),
    )


def detection_result(image: models.Image) -> schemas.DetectionResult:
    return schemas.DetectionResult(
        image_id=image.id,
        filename=image.filename,
        captured_at=image.captured_at,
        block=image.block,
        area_ha=image.area_ha,
        gps=gps_of(image.gps_lat, image.gps_lng),
        summary=summarise(image.detections),
        detections=[detection_out(d) for d in image.detections],
    )


def image_out(image: models.Image) -> schemas.ImageOut:
    return schemas.ImageOut(
        image_id=image.id,
        filename=image.filename,
        captured_at=image.captured_at,
        block=image.block,
        area_ha=image.area_ha,
        gps=gps_of(image.gps_lat, image.gps_lng),
        status=image.status,
        created_at=image.created_at,
    )
