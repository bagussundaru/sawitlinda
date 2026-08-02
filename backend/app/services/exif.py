"""Extract capture time and GPS coordinates from image EXIF metadata.

UAV imagery normally carries both. Everything here degrades to None rather than
raising — an image without EXIF is still a valid upload.
"""

from datetime import datetime, timezone
from pathlib import Path

from PIL import Image as PILImage
from PIL.ExifTags import GPSTAGS, TAGS


class ExifData:
    def __init__(
        self,
        captured_at: datetime | None = None,
        lat: float | None = None,
        lng: float | None = None,
    ) -> None:
        self.captured_at = captured_at
        self.lat = lat
        self.lng = lng


def _to_degrees(value) -> float | None:
    """Convert EXIF (degrees, minutes, seconds) rationals to decimal degrees."""
    try:
        degrees, minutes, seconds = (float(part) for part in value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return degrees + minutes / 60 + seconds / 3600


def _parse_gps(gps_info: dict) -> tuple[float | None, float | None]:
    tags = {GPSTAGS.get(key, key): val for key, val in gps_info.items()}

    lat = _to_degrees(tags.get("GPSLatitude"))
    lng = _to_degrees(tags.get("GPSLongitude"))
    if lat is None or lng is None:
        return None, None

    # Southern and western hemispheres are stored as positive values plus a reference.
    if str(tags.get("GPSLatitudeRef", "N")).upper().startswith("S"):
        lat = -lat
    if str(tags.get("GPSLongitudeRef", "E")).upper().startswith("W"):
        lng = -lng

    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None, None
    return lat, lng


def _parse_datetime(raw: str) -> datetime | None:
    try:
        parsed = datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
    except (TypeError, ValueError):
        return None
    return parsed.replace(tzinfo=timezone.utc)


def extract(image_path: str | Path) -> ExifData:
    """Read EXIF from `image_path`. Never raises on malformed or missing metadata."""
    try:
        with PILImage.open(image_path) as img:
            exif = img.getexif()
    except Exception:
        return ExifData()

    if not exif:
        return ExifData()

    tags = {TAGS.get(key, key): val for key, val in exif.items()}

    captured_at = None
    for tag in ("DateTimeOriginal", "DateTime", "DateTimeDigitized"):
        if tag in tags:
            captured_at = _parse_datetime(tags[tag])
            if captured_at:
                break

    lat = lng = None
    try:
        gps_info = exif.get_ifd(0x8825)
    except Exception:
        gps_info = None
    if gps_info:
        lat, lng = _parse_gps(gps_info)

    return ExifData(captured_at=captured_at, lat=lat, lng=lng)
