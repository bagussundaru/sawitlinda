import io

import pytest
from PIL import Image


def _jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), "green").save(buffer, format="JPEG")
    return buffer.getvalue()


def _upload(client, name: str, **fields) -> str:
    response = client.post(
        "/api/upload",
        files={"files": (name, _jpeg(), "image/jpeg")},
        data=fields or None,
    )
    assert response.status_code == 201, response.text
    return response.json()["images"][0]["image_id"]


def test_upload_records_block_and_area(client):
    image_id = _upload(client, "a.jpg", block="A-3", area_ha="4.5")

    item = next(i for i in client.get("/api/results").json() if i["image_id"] == image_id)
    assert item["block"] == "A-3"
    assert item["area_ha"] == 4.5


def test_block_is_optional(client):
    _upload(client, "tanpa-blok.jpg")

    assert client.get("/api/results").json()[0]["block"] is None


def test_blank_block_is_stored_as_empty_not_whitespace(client):
    _upload(client, "spasi.jpg", block="   ")

    assert client.get("/api/results").json()[0]["block"] is None


def test_manual_coordinates_fill_in_for_an_image_without_exif(client):
    _upload(client, "manual.jpg", block="B-1", lat="-0.78912", lng="101.41233")

    item = client.get("/api/results").json()[0]
    assert item["gps"]["lat"] == pytest.approx(-0.78912)
    assert item["gps"]["lng"] == pytest.approx(101.41233)


def test_coordinates_must_be_supplied_as_a_pair(client):
    response = client.post(
        "/api/upload", files={"files": ("x.jpg", _jpeg(), "image/jpeg")}, data={"lat": "-0.7"}
    )

    assert response.status_code == 400
    assert "berpasangan" in response.json()["detail"]


def test_coordinates_outside_the_valid_range_are_rejected(client):
    response = client.post(
        "/api/upload",
        files={"files": ("x.jpg", _jpeg(), "image/jpeg")},
        data={"lat": "200", "lng": "0"},
    )

    assert response.status_code == 400
    assert "rentang" in response.json()["detail"]


def test_area_must_be_positive(client):
    response = client.post(
        "/api/upload",
        files={"files": ("x.jpg", _jpeg(), "image/jpeg")},
        data={"area_ha": "0"},
    )

    assert response.status_code == 400
    assert "lebih besar dari nol" in response.json()["detail"]


def test_blocks_endpoint_summarises_each_block(client):
    first = _upload(client, "a1.jpg", block="A-3", area_ha="4")
    _upload(client, "a2.jpg", block="A-3", area_ha="2")
    _upload(client, "b1.jpg", block="B-7", area_ha="3")
    client.post(f"/api/analyze/{first}")

    blocks = {b["block"]: b for b in client.get("/api/blocks").json()}

    assert blocks["A-3"]["images"] == 2
    assert blocks["A-3"]["analyzed"] == 1
    assert blocks["A-3"]["area_ha"] == 6
    assert blocks["A-3"]["trees"] > 0
    assert blocks["B-7"]["trees"] == 0


def test_unlabelled_uploads_are_listed_last(client):
    _upload(client, "tanpa.jpg")
    _upload(client, "berlabel.jpg", block="A-1")

    blocks = client.get("/api/blocks").json()

    assert blocks[0]["block"] == "A-1"
    assert blocks[-1]["block"] is None


def test_dashboard_can_be_narrowed_to_one_block(client):
    a = _upload(client, "a.jpg", block="A-3")
    b = _upload(client, "b.jpg", block="B-7")
    client.post(f"/api/analyze/{a}")
    client.post(f"/api/analyze/{b}")

    everything = client.get("/api/dashboard").json()
    only_a = client.get("/api/dashboard", params={"block": "A-3"}).json()

    assert only_a["images_total"] == 1
    assert only_a["summary"]["total"] < everything["summary"]["total"]
    assert only_a["summary"]["healthy"] + only_a["summary"]["infected"] == only_a["summary"]["total"]


def test_map_can_be_narrowed_to_one_block(client, monkeypatch):
    import app.routers.results as results_router

    real = results_router.run_inference
    monkeypatch.setattr(
        results_router,
        "run_inference",
        lambda path, gps=None, area_ha=None: real(path, (-0.78912, 101.41233)),
    )
    a = _upload(client, "a.jpg", block="A-3")
    b = _upload(client, "b.jpg", block="B-7")
    client.post(f"/api/analyze/{a}")
    client.post(f"/api/analyze/{b}")

    points = client.get("/api/map", params={"block": "A-3"}).json()

    assert points
    assert {point["block"] for point in points} == {"A-3"}
