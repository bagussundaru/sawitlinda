import io
import uuid
from pathlib import Path

import pytest
from PIL import Image


def _jpeg_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), "green").save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture
def uploaded_id(client) -> str:
    response = client.post(
        "/api/upload", files={"files": ("blok_a3_001.jpg", _jpeg_bytes(), "image/jpeg")}
    )
    return response.json()["images"][0]["image_id"]


def test_image_file_is_served_back(client, uploaded_id):
    response = client.get(f"/api/images/{uploaded_id}/file")

    assert response.status_code == 200
    assert response.content == _jpeg_bytes()


def test_image_file_rejects_unknown_image(client):
    assert client.get(f"/api/images/{uuid.uuid4()}/file").status_code == 404


def test_image_file_reports_a_missing_file_distinctly(client, uploaded_id, settings):
    for path in settings.storage_path.iterdir():
        Path(path).unlink()

    response = client.get(f"/api/images/{uploaded_id}/file")

    assert response.status_code == 410
    assert "tidak lagi tersedia" in response.json()["detail"]


