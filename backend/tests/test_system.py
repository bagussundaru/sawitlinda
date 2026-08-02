def test_system_reports_mock_while_no_model_is_loaded(client):
    body = client.get("/api/system").json()

    assert body["inference_mode"] == "mock"
    assert body["model_loaded"] is False
    assert body["model_name"] is None


def test_system_reports_real_limits_and_vocabulary(client, settings):
    body = client.get("/api/system").json()

    assert body["max_upload_mb"] == settings.max_upload_mb
    assert body["condition_count"] == 4
    assert body["severities"] == ["sehat", "ringan", "sedang", "berat"]


def test_system_reports_a_model_once_the_file_exists(client, settings, tmp_path):
    model = tmp_path / "sawit_yolov8.pt"
    model.write_bytes(b"bukan model sungguhan, hanya berkas")
    settings.model_path = str(model)

    body = client.get("/api/system").json()

    assert body["inference_mode"] == "model"
    assert body["model_loaded"] is True
    assert body["model_name"] == "sawit_yolov8.pt"


def test_map_points_carry_the_capture_time(client, monkeypatch):
    import io

    from PIL import Image

    import app.routers.results as results_router

    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), "green").save(buffer, format="JPEG")
    uploaded = client.post(
        "/api/upload", files={"files": ("blok.jpg", buffer.getvalue(), "image/jpeg")}
    )
    image_id = uploaded.json()["images"][0]["image_id"]

    real = results_router.run_inference
    monkeypatch.setattr(
        results_router,
        "run_inference",
        lambda path, gps=None: real(path, (-0.78912, 101.41233)),
    )
    client.post(f"/api/analyze/{image_id}")

    points = client.get("/api/map").json()

    assert points
    # No EXIF on a generated image, so the field is present but empty.
    assert "captured_at" in points[0]
