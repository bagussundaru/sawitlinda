import io

from PIL import Image


def _jpeg_bytes(color: str = "green") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), color).save(buffer, format="JPEG")
    return buffer.getvalue()


def _upload_and_analyze(client, name: str, color: str = "green") -> dict:
    uploaded = client.post("/api/upload", files={"files": (name, _jpeg_bytes(color), "image/jpeg")})
    image_id = uploaded.json()["images"][0]["image_id"]
    return client.post(f"/api/analyze/{image_id}").json()


def test_dashboard_is_empty_without_data(client):
    body = client.get("/api/dashboard").json()

    assert body["images_total"] == 0
    assert body["images_analyzed"] == 0
    assert body["summary"]["total"] == 0
    assert body["by_disease"] == []


def test_dashboard_keeps_every_severity_level_even_when_unused(client):
    body = client.get("/api/dashboard").json()

    assert [item["label"] for item in body["by_severity"]] == [
        "sehat",
        "ringan",
        "sedang",
        "berat",
    ]


def test_dashboard_counts_only_analyzed_images(client):
    client.post("/api/upload", files={"files": ("belum.jpg", _jpeg_bytes(), "image/jpeg")})
    _upload_and_analyze(client, "sudah.jpg")

    body = client.get("/api/dashboard").json()

    assert body["images_total"] == 2
    assert body["images_analyzed"] == 1


def test_dashboard_totals_match_the_sum_of_each_image(client):
    first = _upload_and_analyze(client, "a.jpg", "green")
    second = _upload_and_analyze(client, "b.jpg", "red")

    body = client.get("/api/dashboard").json()

    assert body["summary"]["total"] == first["summary"]["total"] + second["summary"]["total"]
    assert body["summary"]["severe"] == first["summary"]["severe"] + second["summary"]["severe"]
    assert sum(item["count"] for item in body["by_disease"]) == body["summary"]["total"]
    assert sum(item["count"] for item in body["by_severity"]) == body["summary"]["total"]
