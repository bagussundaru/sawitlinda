import io

import pytest
from PIL import Image
from sqlalchemy.exc import OperationalError


def test_health_reports_the_database(client):
    body = client.get("/health").json()

    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_health_degrades_when_the_database_is_unreachable(client, monkeypatch):
    def explode(*args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("koneksi putus"))

    monkeypatch.setattr("sqlalchemy.orm.Session.execute", explode)

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["database"] == "unreachable"


def test_validation_errors_are_reported_in_indonesian(client):
    response = client.post("/api/upload")

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Permintaan tidak valid. Periksa kembali data yang dikirim."
    }


def test_oversized_upload_is_rejected_and_leaves_no_file(client, settings):
    settings.max_upload_mb = 0  # anything above zero bytes is too large

    buffer = io.BytesIO()
    Image.new("RGB", (200, 200), "green").save(buffer, format="JPEG")
    response = client.post(
        "/api/upload", files={"files": ("besar.jpg", buffer.getvalue(), "image/jpeg")}
    )

    assert response.status_code == 413
    assert "melebihi batas" in response.json()["detail"]
    assert list(settings.storage_path.iterdir()) == []


@pytest.mark.parametrize("path", ["/api/dashboard", "/api/results"])
def test_database_failures_return_a_service_unavailable(client, monkeypatch, path):
    def explode(*args, **kwargs):
        raise OperationalError("SELECT", {}, Exception("koneksi putus"))

    monkeypatch.setattr("sqlalchemy.orm.Session.execute", explode)

    response = client.get(path)

    assert response.status_code == 503
    assert "Database" in response.json()["detail"]
