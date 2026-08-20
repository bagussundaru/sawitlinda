"""Pemetaan spasial: pengelompokan desa dan penanda per citra."""

import io

import pytest
from PIL import Image

from app import villages


def _jpeg() -> io.BytesIO:
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), "green").save(buf, "JPEG")
    buf.seek(0)
    return buf


def _unggah(client, nama, label, village=None):
    data = {"labels": [label]}
    if village:
        data["village"] = village
    return client.post(
        "/api/upload",
        files=[("files", (nama, _jpeg(), "image/jpeg"))],
        data=data,
    )


def _beri_koordinat(image_id, lat, lng):
    """Isi koordinat langsung di database — citra uji tidak punya EXIF."""
    from app import models
    from app.db import get_db
    from app.main import app as fastapi_app

    db = next(fastapi_app.dependency_overrides[get_db]())
    citra = db.get(models.Image, __import__("uuid").UUID(image_id))
    citra.gps_lat, citra.gps_lng = lat, lng
    db.commit()


class TestDaftarDesa:
    def test_kelima_desa_selalu_ada(self, client):
        """Desa yang hilang dari layar akan terbaca seolah tidak termasuk
        penelitian, walau kebetulan belum punya citra."""
        daftar = client.get("/api/villages").json()

        assert len(daftar) == 5
        assert {d["key"] for d in daftar} == {v.key for v in villages.VILLAGES}

    def test_desa_kosong_dilaporkan_nol_bukan_disembunyikan(self, client):
        daftar = client.get("/api/villages").json()

        assert all(d["images"] == 0 for d in daftar)

    def test_jumlah_citra_dihitung_per_desa(self, client):
        for nama, desa in [("a.jpg", "samuda"), ("b.jpg", "samuda"), ("c.jpg", "bapeang")]:
            image_id = _unggah(client, nama, nama, desa).json()["images"][0]["image_id"]
            client.post(f"/api/analyze/{image_id}")

        per_desa = {d["key"]: d for d in client.get("/api/villages").json()}

        assert per_desa["samuda"]["images"] == 2
        assert per_desa["bapeang"]["images"] == 1
        assert per_desa["terantang"]["images"] == 0

    def test_pohon_dan_yang_bermasalah_ikut_dijumlahkan(self, client):
        image_id = _unggah(client, "a.jpg", "Petak", "kota-besi").json()["images"][0]["image_id"]
        client.post(f"/api/analyze/{image_id}")

        desa = next(d for d in client.get("/api/villages").json() if d["key"] == "kota-besi")

        assert desa["trees"] > 0
        assert desa["affected"] <= desa["trees"]


class TestPelabelanDesa:
    def test_desa_disimpan_dan_dikembalikan_dengan_namanya(self, client):
        r = _unggah(client, "a.jpg", "Petak 1", "parenggean")
        citra = r.json()["images"][0]

        assert citra["village"] == "parenggean"
        assert citra["village_name"] == "Karang Tunggal / Parenggean"

    def test_desa_di_luar_daftar_ditolak(self, client):
        """Daftar tertutup: nilai bebas akan membuat pengelompokan berantakan."""
        r = _unggah(client, "a.jpg", "Petak", "jakarta")

        assert r.status_code == 400
        assert "Desa tidak dikenal" in r.json()["detail"]

    def test_desa_boleh_dikosongkan(self, client):
        r = _unggah(client, "a.jpg", "Petak")

        assert r.status_code == 201
        assert r.json()["images"][0]["village"] is None


class TestPeta:
    def _siapkan(self, client, desa="samuda", lat=-3.05, lng=112.95):
        image_id = _unggah(client, "a.jpg", "Petak", desa).json()["images"][0]["image_id"]
        client.post(f"/api/analyze/{image_id}")
        _beri_koordinat(image_id, lat, lng)
        return image_id

    def test_penanda_dipasang_per_citra_bukan_per_pohon(self, client):
        """Satu citra berisi puluhan pohon menghasilkan SATU penanda."""
        image_id = self._siapkan(client)

        titik = client.get("/api/map").json()["points"]

        assert len(titik) == 1
        assert titik[0]["image_id"] == image_id
        assert titik[0]["summary"]["total"] > 1

    def test_penanda_membawa_bagian_yang_bermasalah(self, client):
        """Dipakai mewarnai penanda; tanpa itu peta hanya titik seragam."""
        self._siapkan(client)

        titik = client.get("/api/map").json()["points"][0]

        assert 0.0 <= titik["affected_share"] <= 1.0
        assert titik["dominant_condition"]

    def test_peta_dapat_disaring_per_desa(self, client):
        self._siapkan(client, desa="samuda")
        self._siapkan(client, desa="bapeang")

        assert len(client.get("/api/map").json()["points"]) == 2
        assert len(client.get("/api/map?village=samuda").json()["points"]) == 1

    def test_citra_belum_dianalisis_tidak_muncul(self, client):
        """Penanda tanpa angka tidak memberi tahu apa pun."""
        image_id = _unggah(client, "a.jpg", "Petak", "samuda").json()["images"][0]["image_id"]
        _beri_koordinat(image_id, -3.0, 112.9)

        assert client.get("/api/map").json()["points"] == []


class TestDaftarDesaTetap:
    def test_koordinat_desa_hanya_perkiraan_pusat_wilayah(self):
        """Ditandai jelas di kode agar tidak pernah dikira titik survei."""
        import inspect

        sumber = inspect.getsource(villages)

        assert "TIDAK DIPAKAI UNTUK MENEMPATKAN CITRA" in sumber

    @pytest.mark.parametrize("v", villages.VILLAGES, ids=lambda v: v.key)
    def test_setiap_desa_punya_nama_dan_kecamatan(self, v):
        assert v.name and v.district
        assert -4 < v.lat < 0 and 110 < v.lng < 115  # masih di Kalimantan Tengah


class TestStatusGpsTidakTersedia:
    """Citra tanpa GPS harus DINYATAKAN, bukan dibuang diam-diam.

    Membuangnya membuat peta tampak sebagai gambaran lengkap padahal sebagian
    citra tidak terwakili — dan pembacanya tidak punya cara mengetahui itu.
    """

    def _analisis(self, client, nama="a.jpg", desa="samuda"):
        image_id = _unggah(client, nama, nama, desa).json()["images"][0]["image_id"]
        client.post(f"/api/analyze/{image_id}")
        return image_id

    def test_citra_tanpa_gps_dikembalikan_terpisah(self, client):
        image_id = self._analisis(client)

        badan = client.get("/api/map").json()

        assert badan["points"] == []
        assert [x["image_id"] for x in badan["without_gps"]] == [image_id]

    def test_jumlah_seluruh_citra_dianalisis_ikut_dilaporkan(self, client):
        """Tanpa angka ini, "26 penanda" tidak dapat dibandingkan dengan apa pun."""
        self._analisis(client, "a.jpg")
        self._analisis(client, "b.jpg")

        assert client.get("/api/map").json()["analyzed_total"] == 2

    def test_citra_tanpa_gps_tetap_membawa_angkanya(self, client):
        """Cukup untuk ditampilkan sebagai baris, bukan sekadar nama berkas."""
        self._analisis(client)

        tanpa = client.get("/api/map").json()["without_gps"][0]

        assert tanpa["summary"]["total"] > 0
        assert tanpa["label"]

    def test_penyaringan_desa_ikut_berlaku_pada_yang_tanpa_gps(self, client):
        self._analisis(client, "a.jpg", desa="samuda")
        self._analisis(client, "b.jpg", desa="bapeang")

        badan = client.get("/api/map?village=samuda").json()

        assert len(badan["without_gps"]) == 1
        assert badan["analyzed_total"] == 1

    def test_citra_belum_dianalisis_tidak_masuk_daftar_mana_pun(self, client):
        _unggah(client, "a.jpg", "belum dianalisis", "samuda")

        badan = client.get("/api/map").json()

        assert badan["points"] == []
        assert badan["without_gps"] == []
        assert badan["analyzed_total"] == 0
