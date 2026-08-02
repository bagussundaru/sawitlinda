import io
import uuid

import pytest
from PIL import Image


def _jpeg_bytes(color: str = "green") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), color).save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture
def uploaded_id(client) -> str:
    response = client.post(
        "/api/upload",
        files={"files": ("blok_a3_001.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    return response.json()["images"][0]["image_id"]


def test_analyze_returns_result_matching_the_contract(client, uploaded_id):
    response = client.post(f"/api/analyze/{uploaded_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["image_id"] == uploaded_id
    assert body["filename"] == "blok_a3_001.jpg"
    assert body["detections"]

    summary = body["summary"]
    assert summary["total"] == len(body["detections"])
    assert summary["healthy"] + summary["infected"] == summary["total"]
    assert summary["severe"] <= summary["infected"]


def test_analyze_marks_the_image_analyzed(client, uploaded_id):
    client.post(f"/api/analyze/{uploaded_id}")

    listed = client.get("/api/results").json()
    assert listed[0]["status"] == "analyzed"
    assert listed[0]["summary"] is not None


def test_reanalyzing_replaces_detections_instead_of_adding(client, uploaded_id):
    first = client.post(f"/api/analyze/{uploaded_id}").json()
    second = client.post(f"/api/analyze/{uploaded_id}").json()

    assert second["summary"]["total"] == first["summary"]["total"]


def test_analyze_rejects_unknown_image(client):
    assert client.post(f"/api/analyze/{uuid.uuid4()}").status_code == 404


def test_get_result_returns_the_stored_analysis(client, uploaded_id):
    analyzed = client.post(f"/api/analyze/{uploaded_id}").json()

    fetched = client.get(f"/api/results/{uploaded_id}").json()

    assert fetched == analyzed


def test_get_result_reports_an_unanalyzed_image_clearly(client, uploaded_id):
    response = client.get(f"/api/results/{uploaded_id}")

    assert response.status_code == 409
    assert "belum dianalisis" in response.json()["detail"]


def test_get_result_rejects_unknown_image(client):
    assert client.get(f"/api/results/{uuid.uuid4()}").status_code == 404


def test_results_list_is_empty_at_first(client):
    assert client.get("/api/results").json() == []


def test_unanalyzed_image_has_no_summary(client, uploaded_id):
    listed = client.get("/api/results").json()

    assert listed[0]["status"] == "uploaded"
    assert listed[0]["summary"] is None
