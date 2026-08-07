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


def test_berkas_model_palsu_tidak_dilaporkan_sebagai_model_siap(client, settings, tmp_path):
    """Berkas yang ada tapi tidak dapat dimuat harus tetap terbaca sebagai mock.

    Sebelumnya endpoint ini hanya memeriksa keberadaan berkas, sehingga mesin
    yang rusak tersembunyi di balik status yang terlihat sehat.
    """
    model = tmp_path / "sawit_yolov8.pt"
    model.write_bytes(b"bukan model sungguhan, hanya berkas")
    settings.model_path = str(model)

    body = client.get("/api/system").json()

    assert body["inference_mode"] == "mock"
    assert body["model_loaded"] is False
    assert body["model_error"]


