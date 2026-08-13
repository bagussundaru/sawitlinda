"""ORM -> Pydantic conversion, kept in one place so the JSON contract is built
identically by every endpoint."""

from app import models, schemas, villages


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
        label=image.label,
        village=image.village,
        village_name=villages.label(image.village),
        gps=gps_of(image.gps_lat, image.gps_lng),
        summary=summarise(image.detections),
        detections=[detection_out(d) for d in image.detections],
        ai=ai_assessment(image),
    )


def ai_assessment(image: models.Image) -> schemas.AiAssessmentOut | None:
    """Bentuk penilaian AI untuk API, sekaligus menghitung selisihnya dengan
    hasil deteksi supaya operator tahu kapan keduanya tidak sepakat."""
    if image.ai_created_at is None or not image.ai_model:
        return None

    disagreement = None
    if image.ai_affected_share is not None and image.detections:
        summary = summarise(image.detections)
        if summary.total:
            terdeteksi = summary.infected / summary.total
            disagreement = round(abs(image.ai_affected_share - terdeteksi) * 100, 1)

    return schemas.AiAssessmentOut(
        summary=image.ai_summary or "",
        recommendation=image.ai_recommendation or "",
        dominant_condition=image.ai_dominant_condition or "",
        confidence=image.ai_confidence or 0.0,
        affected_share=image.ai_affected_share or 0.0,
        notes=[n for n in (image.ai_notes or "").splitlines() if n.strip()],
        model=image.ai_model,
        created_at=image.ai_created_at,
        disagreement_pp=disagreement,
    )


def image_out(image: models.Image) -> schemas.ImageOut:
    return schemas.ImageOut(
        image_id=image.id,
        filename=image.filename,
        captured_at=image.captured_at,
        label=image.label,
        village=image.village,
        village_name=villages.label(image.village),
        gps=gps_of(image.gps_lat, image.gps_lng),
        status=image.status,
        created_at=image.created_at,
        has_ai=image.ai_created_at is not None,
    )
