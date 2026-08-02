import io

from PIL import Image


def _jpeg_bytes(color: str = "green") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), color).save(buffer, format="JPEG")
    return buffer.getvalue()


def test_upload_single_image_stores_it(client, settings):
    response = client.post(
        "/api/upload",
        files={"files": ("blok_a3_001.jpg", _jpeg_bytes(), "image/jpeg")},
    )

    assert response.status_code == 201
    images = response.json()["images"]
    assert len(images) == 1
    assert images[0]["filename"] == "blok_a3_001.jpg"
    assert images[0]["status"] == "uploaded"
    assert images[0]["gps"] is None  # no EXIF in a generated image

    stored = list(settings.storage_path.iterdir())
    assert len(stored) == 1
    assert stored[0].name.startswith(images[0]["image_id"])


def test_upload_accepts_a_batch(client, settings):
    response = client.post(
        "/api/upload",
        files=[
            ("files", ("a.jpg", _jpeg_bytes("green"), "image/jpeg")),
            ("files", ("b.png", _jpeg_bytes("red"), "image/png")),
        ],
    )

    assert response.status_code == 201
    assert len(response.json()["images"]) == 2
    assert len(list(settings.storage_path.iterdir())) == 2


def test_upload_rejects_unsupported_extension_without_storing_anything(client, settings):
    response = client.post(
        "/api/upload",
        files=[
            ("files", ("baik.jpg", _jpeg_bytes(), "image/jpeg")),
            ("files", ("laporan.pdf", b"%PDF-1.4", "application/pdf")),
        ],
    )

    assert response.status_code == 400
    assert "tidak didukung" in response.json()["detail"]
    assert list(settings.storage_path.iterdir()) == []


def test_upload_requires_at_least_one_file(client):
    assert client.post("/api/upload").status_code == 422
