from datetime import timezone

from PIL import Image

from app.services import exif


def test_to_degrees_converts_dms_to_decimal():
    assert exif._to_degrees((101, 24, 44.4)) == 101 + 24 / 60 + 44.4 / 3600


def test_to_degrees_rejects_malformed_value():
    assert exif._to_degrees("bukan koordinat") is None


def test_parse_gps_applies_south_and_west_references():
    lat, lng = exif._parse_gps(
        {
            1: "S",  # GPSLatitudeRef
            2: (0, 47, 20.8),  # GPSLatitude
            3: "E",  # GPSLongitudeRef
            4: (101, 24, 44.4),  # GPSLongitude
        }
    )
    assert lat is not None and lat < 0  # southern hemisphere
    assert lng is not None and lng > 0


def test_parse_gps_rejects_out_of_range_coordinates():
    assert exif._parse_gps({1: "N", 2: (200, 0, 0), 3: "E", 4: (0, 0, 0)}) == (None, None)


def test_extract_returns_empty_data_for_image_without_exif(tmp_path):
    path = tmp_path / "polos.jpg"
    Image.new("RGB", (10, 10), "green").save(path)

    data = exif.extract(path)

    assert data.captured_at is None
    assert data.lat is None and data.lng is None


def test_extract_returns_empty_data_for_unreadable_file(tmp_path):
    path = tmp_path / "rusak.jpg"
    path.write_bytes(b"bukan gambar")

    data = exif.extract(path)

    assert data.lat is None and data.captured_at is None


def test_extract_reads_capture_time(tmp_path):
    path = tmp_path / "berwaktu.jpg"
    image = Image.new("RGB", (10, 10), "green")
    metadata = Image.Exif()
    metadata[0x0132] = "2026:07:21 08:12:00"  # DateTime
    image.save(path, exif=metadata)

    data = exif.extract(path)

    assert data.captured_at is not None
    assert data.captured_at.year == 2026
    assert data.captured_at.hour == 8
    assert data.captured_at.tzinfo == timezone.utc
