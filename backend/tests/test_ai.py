"""Tes lapisan analisis AI.

Seluruh panggilan HTTP ditiru; tidak ada kunci API sungguhan yang dipakai dan
tidak ada permintaan yang benar-benar keluar ke Nebius.
"""

import io
import json

import httpx
import pytest
from PIL import Image

from app.inference import nebius


def _jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), "green").save(buffer, format="JPEG")
    return buffer.getvalue()


def _jawaban(isi: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": isi}}]},
        request=httpx.Request("POST", "https://contoh/v1/chat/completions"),
    )


ISI_SAH = json.dumps(
    {
        "dominant_condition": "Menguning",
        "affected_share": 0.35,
        "confidence": 0.8,
        "summary": "Sebagian tajuk tampak pucat kekuningan di sisi utara petak.",
        "recommendation": "Periksa unsur hara dan lakukan pemupukan susulan.",
        "notes": ["Sebagian citra tertutup bayangan awan tipis."],
    }
)


@pytest.fixture
def gambar(tmp_path):
    path = tmp_path / "uav.jpg"
    path.write_bytes(_jpeg())
    return str(path)


@pytest.fixture
def settings_ai(settings):
    settings.nebius_api_key = "kunci-uji-bukan-sungguhan"
    return settings


def test_fitur_mati_tanpa_kunci(settings, gambar):
    assert settings.ai_enabled is False
    with pytest.raises(nebius.NebiusError, match="NEBIUS_API_KEY"):
        nebius.assess_image(gambar, settings)


def test_penilaian_dibaca_dari_jawaban_model(monkeypatch, settings_ai, gambar):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _jawaban(ISI_SAH))

    hasil = nebius.assess_image(gambar, settings_ai)

    assert hasil.dominant_condition == "Menguning"
    assert hasil.affected_share == 0.35
    assert hasil.confidence == 0.8
    assert "kekuningan" in hasil.summary
    assert hasil.notes == ["Sebagian citra tertutup bayangan awan tipis."]
    assert hasil.model == settings_ai.nebius_model


def test_json_berpagar_backtick_tetap_terbaca(monkeypatch, settings_ai, gambar):
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: _jawaban(f"Tentu.\n```json\n{ISI_SAH}\n```")
    )

    assert nebius.assess_image(gambar, settings_ai).dominant_condition == "Menguning"


def test_kondisi_di_luar_daftar_ditolak(monkeypatch, settings_ai, gambar):
    palsu = json.dumps({**json.loads(ISI_SAH), "dominant_condition": "Ganoderma"})
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _jawaban(palsu))

    with pytest.raises(nebius.NebiusError, match="di luar daftar"):
        nebius.assess_image(gambar, settings_ai)


def test_jawaban_bukan_json_ditolak(monkeypatch, settings_ai, gambar):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _jawaban("maaf, tidak bisa"))

    with pytest.raises(nebius.NebiusError, match="bukan JSON"):
        nebius.assess_image(gambar, settings_ai)


def test_galat_jaringan_dibungkus(monkeypatch, settings_ai, gambar):
    def gagal(*a, **k):
        raise httpx.ConnectError("koneksi ditolak")

    monkeypatch.setattr(httpx, "post", gagal)

    with pytest.raises(nebius.NebiusError, match="Tidak dapat menghubungi"):
        nebius.assess_image(gambar, settings_ai)


def test_nilai_di_luar_rentang_dijepit(monkeypatch, settings_ai, gambar):
    aneh = json.dumps(
        {**json.loads(ISI_SAH), "confidence": 5, "affected_share": -2}
    )
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _jawaban(aneh))

    hasil = nebius.assess_image(gambar, settings_ai)

    assert hasil.confidence == 1.0
    assert hasil.affected_share == 0.0


def test_kunci_tidak_pernah_muncul_di_payload(monkeypatch, settings_ai, gambar):
    terekam = {}

    def rekam(url, **kwargs):
        terekam["json"] = kwargs["json"]
        terekam["headers"] = kwargs["headers"]
        return _jawaban(ISI_SAH)

    monkeypatch.setattr(httpx, "post", rekam)
    nebius.assess_image(gambar, settings_ai)

    # Kunci hanya boleh ada di header Authorization, tidak di badan permintaan.
    assert settings_ai.nebius_api_key not in json.dumps(terekam["json"])
    assert terekam["headers"]["Authorization"].endswith(settings_ai.nebius_api_key)


# --- Endpoint ---


def _unggah_dan_analisis(client) -> str:
    unggah = client.post(
        "/api/upload", files={"files": ("blok.jpg", _jpeg(), "image/jpeg")}
    )
    image_id = unggah.json()["images"][0]["image_id"]
    client.post(f"/api/analyze/{image_id}")
    return image_id


def test_endpoint_menolak_saat_fitur_mati(client):
    image_id = _unggah_dan_analisis(client)

    response = client.post(f"/api/analyze/{image_id}/ai")

    assert response.status_code == 503
    assert "NEBIUS_API_KEY" in response.json()["detail"]


def test_endpoint_menyimpan_penilaian(client, settings_ai, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _jawaban(ISI_SAH))
    image_id = _unggah_dan_analisis(client)

    response = client.post(f"/api/analyze/{image_id}/ai")

    assert response.status_code == 200
    ai = response.json()["ai"]
    assert ai["dominant_condition"] == "Menguning"
    assert ai["recommendation"].startswith("Periksa unsur hara")
    assert ai["model"] == settings_ai.nebius_model

    # Tersimpan, jadi terbaca lagi tanpa memanggil model dua kali.
    assert client.get(f"/api/results/{image_id}").json()["ai"]["confidence"] == 0.8


def test_selisih_dengan_hasil_deteksi_dihitung(client, settings_ai, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _jawaban(ISI_SAH))
    image_id = _unggah_dan_analisis(client)

    body = client.post(f"/api/analyze/{image_id}/ai").json()

    terdeteksi = body["summary"]["infected"] / body["summary"]["total"]
    diharapkan = round(abs(0.35 - terdeteksi) * 100, 1)
    assert body["ai"]["disagreement_pp"] == diharapkan


def test_kegagalan_model_tidak_merusak_hasil_deteksi(client, settings_ai, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _jawaban("bukan json"))
    image_id = _unggah_dan_analisis(client)

    response = client.post(f"/api/analyze/{image_id}/ai")

    assert response.status_code == 502
    # Deteksi per pohon tetap utuh.
    hasil = client.get(f"/api/results/{image_id}").json()
    assert hasil["detections"]
    assert hasil["ai"] is None


def test_status_sistem_melaporkan_lapisan_ai(client, settings_ai):
    body = client.get("/api/system").json()

    assert body["ai_enabled"] is True
    assert body["ai_model"] == settings_ai.nebius_model
