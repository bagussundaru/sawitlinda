import csv
import io
import uuid

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


@pytest.fixture
def analyzed(client, uploaded_id) -> dict:
    return client.post(f"/api/analyze/{uploaded_id}").json()


def test_csv_has_one_row_per_detection(client, analyzed):
    response = client.get(f"/api/results/{analyzed['image_id']}/export.csv")

    assert response.status_code == 200
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows[0][0] == "no"
    assert len(rows) - 1 == len(analyzed["detections"])


def test_csv_content_matches_the_api_result(client, analyzed):
    response = client.get(f"/api/results/{analyzed['image_id']}/export.csv")

    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    for row, detection in zip(rows, analyzed["detections"]):
        assert row["kondisi"] == detection["condition"]
        assert row["keparahan"] == detection["severity"]
        assert row["nama_berkas"] == "blok_a3_001.jpg"
        assert "blok" in row


def test_csv_starts_with_a_bom_so_excel_reads_it(client, analyzed):
    response = client.get(f"/api/results/{analyzed['image_id']}/export.csv")

    assert response.content.startswith(b"\xef\xbb\xbf")


def test_csv_is_offered_as_a_named_download(client, analyzed):
    response = client.get(f"/api/results/{analyzed['image_id']}/export.csv")

    assert 'filename="laporan_blok_a3_001.csv"' in response.headers["content-disposition"]


def test_pdf_is_a_valid_document(client, analyzed):
    response = client.get(f"/api/results/{analyzed['image_id']}/export.pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
    assert response.content.rstrip().endswith(b"%%EOF")
    assert len(response.content) > 1000


def test_pdf_lists_the_recommended_action_for_each_condition_found(client, analyzed):
    from pypdf import PdfReader

    from app.inference.conditions import BY_LABEL, HEALTHY

    response = client.get(f"/api/results/{analyzed['image_id']}/export.pdf")
    text = "".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(response.content)).pages)

    found = {d["condition"] for d in analyzed["detections"] if d["condition"] != HEALTHY}
    assert found, "citra contoh seharusnya memuat setidaknya satu temuan"
    assert "Rekomendasi tindakan" in text
    for label in found:
        assert " ".join(BY_LABEL[label].action.split()[:2]) in text


def test_pdf_is_offered_as_a_named_download(client, analyzed):
    response = client.get(f"/api/results/{analyzed['image_id']}/export.pdf")

    assert 'filename="laporan_blok_a3_001.pdf"' in response.headers["content-disposition"]


@pytest.mark.parametrize("extension", ["csv", "pdf"])
def test_export_refuses_an_unanalyzed_image(client, uploaded_id, extension):
    response = client.get(f"/api/results/{uploaded_id}/export.{extension}")

    assert response.status_code == 409
    assert "belum dianalisis" in response.json()["detail"]


@pytest.mark.parametrize("extension", ["csv", "pdf"])
def test_export_rejects_unknown_image(client, extension):
    assert client.get(f"/api/results/{uuid.uuid4()}/export.{extension}").status_code == 404
