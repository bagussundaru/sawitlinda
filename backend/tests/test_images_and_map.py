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


def test_map_is_empty_without_analysis(client, uploaded_id):
    assert client.get("/api/map").json() == []


def test_map_skips_detections_without_coordinates(client, uploaded_id):
    # A generated image carries no EXIF, so the mock cannot geo-reference anything.
    client.post(f"/api/analyze/{uploaded_id}")

    assert client.get("/api/map").json() == []


def test_map_returns_points_for_geo_referenced_detections(client, uploaded_id, monkeypatch):
    import app.routers.results as results_router

    real = results_router.run_inference
    monkeypatch.setattr(
        results_router,
        "run_inference",
        lambda path, gps=None: real(path, (-0.78912, 101.41233)),
    )
    analyzed = client.post(f"/api/analyze/{uploaded_id}").json()

    points = client.get("/api/map").json()

    assert len(points) == len(analyzed["detections"])
    assert points[0]["filename"] == "blok_a3_001.jpg"
    assert points[0]["image_id"] == uploaded_id
    assert all(-90 <= p["gps"]["lat"] <= 90 for p in points)
