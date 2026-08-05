"""Tes pengisian kunci API lewat aplikasi.

Yang paling penting diuji: kunci tidak pernah bisa dibaca kembali lewat API.
"""

import io
import json

import httpx
import pytest
from PIL import Image

KUNCI = "kunci-uji-abcdefgh1234"


def _jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), "green").save(buffer, format="JPEG")
    return buffer.getvalue()


def test_awalnya_belum_dikonfigurasi(client):
    body = client.get("/api/settings/ai").json()

    assert body["configured"] is False
    assert body["source"] is None
    assert body["key_hint"] is None


def test_kunci_dapat_disimpan_dan_langsung_berlaku(client):
    body = client.put("/api/settings/ai", json={"api_key": KUNCI}).json()

    assert body["configured"] is True
    assert body["source"] == "aplikasi"
    assert client.get("/api/system").json()["ai_enabled"] is True


def test_kunci_tidak_pernah_dikembalikan(client):
    client.put("/api/settings/ai", json={"api_key": KUNCI})

    for path in ["/api/settings/ai", "/api/system"]:
        teks = json.dumps(client.get(path).json())
        assert KUNCI not in teks, f"kunci bocor lewat {path}"


def test_hanya_empat_karakter_terakhir_yang_ditampilkan(client):
    client.put("/api/settings/ai", json={"api_key": KUNCI})

    hint = client.get("/api/settings/ai").json()["key_hint"]

    assert hint == "…1234"
    assert len(hint) < len(KUNCI)


def test_kunci_terlalu_pendek_ditolak(client):
    assert client.put("/api/settings/ai", json={"api_key": "abc"}).status_code == 422


def test_kunci_dapat_dihapus(client):
    client.put("/api/settings/ai", json={"api_key": KUNCI})

    body = client.delete("/api/settings/ai").json()

    assert body["configured"] is False
    assert client.get("/api/system").json()["ai_enabled"] is False


def test_kunci_dari_aplikasi_menimpa_environment(client, settings):
    settings.nebius_api_key = "kunci-dari-environment"

    sebelum = client.get("/api/settings/ai").json()
    client.put("/api/settings/ai", json={"api_key": KUNCI})
    sesudah = client.get("/api/settings/ai").json()

    assert sebelum["source"] == "environment"
    assert sesudah["source"] == "aplikasi"
    assert sesudah["key_hint"] == "…1234"


def test_menghapus_mengembalikan_nilai_environment(client, settings):
    settings.nebius_api_key = "kunci-dari-environment"
    client.put("/api/settings/ai", json={"api_key": KUNCI})

    body = client.delete("/api/settings/ai").json()

    assert body["configured"] is True
    assert body["source"] == "environment"


def test_analisis_ai_memakai_kunci_yang_diisi_lewat_aplikasi(client, monkeypatch):
    """Bukti bahwa kunci itu benar-benar dipakai, bukan sekadar tersimpan."""
    terpakai = {}

    def rekam(url, **kwargs):
        terpakai["auth"] = kwargs["headers"]["Authorization"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "dominant_condition": "Sehat",
                                    "affected_share": 0.1,
                                    "confidence": 0.9,
                                    "summary": "Tajuk tampak rapat dan hijau.",
                                    "recommendation": "Tidak ada tindakan.",
                                    "notes": [],
                                }
                            )
                        }
                    }
                ]
            },
            request=httpx.Request("POST", "https://contoh/v1/chat/completions"),
        )

    monkeypatch.setattr(httpx, "post", rekam)

    unggah = client.post("/api/upload", files={"files": ("a.jpg", _jpeg(), "image/jpeg")})
    image_id = unggah.json()["images"][0]["image_id"]
    client.post(f"/api/analyze/{image_id}")

    client.put("/api/settings/ai", json={"api_key": KUNCI})
    response = client.post(f"/api/analyze/{image_id}/ai")

    assert response.status_code == 200
    assert terpakai["auth"] == f"Bearer {KUNCI}"


def test_tanpa_kunci_analisis_ai_menolak_dengan_petunjuk_layar(client):
    unggah = client.post("/api/upload", files={"files": ("a.jpg", _jpeg(), "image/jpeg")})
    image_id = unggah.json()["images"][0]["image_id"]
    client.post(f"/api/analyze/{image_id}")

    response = client.post(f"/api/analyze/{image_id}/ai")

    assert response.status_code == 503
    assert "Pengaturan" in response.json()["detail"]
