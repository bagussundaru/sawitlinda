"""Label per citra — identitas citra sejak konsep peta ditinggalkan."""

import io

from PIL import Image


def _jpeg(warna="green") -> io.BytesIO:
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), warna).save(buf, "JPEG")
    buf.seek(0)
    return buf


def _unggah(client, berkas, labels=None):
    return client.post(
        "/api/upload",
        files=[("files", (nama, _jpeg(), "image/jpeg")) for nama in berkas],
        data={"labels": list(labels)} if labels else None,
    )


class TestPelabelan:
    def test_label_disimpan_per_berkas(self, client):
        r = _unggah(client, ["a.jpg", "b.jpg"], ["Kebun utara", "Kebun selatan"])

        assert r.status_code == 201
        label = [citra["label"] for citra in r.json()["images"]]
        assert label == ["Kebun utara", "Kebun selatan"]

    def test_tanpa_label_memakai_nama_berkas(self, client):
        """Citra tidak boleh berakhir tanpa nama."""
        r = _unggah(client, ["DJI_0384.JPG"])

        assert r.json()["images"][0]["label"] == "DJI_0384.JPG"

    def test_label_kosong_diperlakukan_sebagai_tidak_diisi(self, client):
        r = _unggah(client, ["a.jpg"], ["   "])

        assert r.json()["images"][0]["label"] == "a.jpg"

    def test_label_lebih_sedikit_dari_berkas_tidak_menggagalkan_unggahan(self, client):
        """Sisa berkas memakai namanya sendiri, bukan menolak seluruh batch."""
        r = _unggah(client, ["a.jpg", "b.jpg", "c.jpg"], ["Petak 1"])

        label = [citra["label"] for citra in r.json()["images"]]
        assert label == ["Petak 1", "b.jpg", "c.jpg"]

    def test_label_panjang_dipotong_bukan_ditolak(self, client):
        r = _unggah(client, ["a.jpg"], ["x" * 500])

        assert len(r.json()["images"][0]["label"]) == 200

    def test_label_muncul_di_riwayat_dan_hasil(self, client):
        image_id = _unggah(client, ["a.jpg"], ["Petak Mawar"]).json()["images"][0]["image_id"]
        client.post(f"/api/analyze/{image_id}")

        assert client.get(f"/api/results/{image_id}").json()["label"] == "Petak Mawar"
        assert client.get("/api/results").json()["items"][0]["label"] == "Petak Mawar"


class TestPencarianLabel:
    def _siapkan(self, client):
        for nama, label in [("a.jpg", "Kebun Utara"), ("b.jpg", "Kebun Selatan")]:
            image_id = _unggah(client, [nama], [label]).json()["images"][0]["image_id"]
            client.post(f"/api/analyze/{image_id}")

    def test_dashboard_dapat_disaring_dengan_label(self, client):
        self._siapkan(client)

        semua = client.get("/api/dashboard").json()
        utara = client.get("/api/dashboard?q=utara").json()

        assert semua["images_analyzed"] == 2
        assert utara["images_analyzed"] == 1

    def test_pencarian_tidak_membedakan_huruf_besar_kecil(self, client):
        self._siapkan(client)

        assert client.get("/api/dashboard?q=UTARA").json()["images_analyzed"] == 1

    def test_kata_yang_tidak_cocok_menghasilkan_nol(self, client):
        self._siapkan(client)

        assert client.get("/api/dashboard?q=tidak-ada").json()["images_analyzed"] == 0


class TestPetaBerbasisCitra:
    def test_endpoint_blok_tetap_tidak_ada(self, client):
        """Blok kebun digantikan label; endpointnya tidak dihidupkan lagi."""
        assert client.get("/api/blocks").status_code == 404

    def test_peta_mengembalikan_penanda_per_citra(self, client):
        assert client.get("/api/map").status_code == 200

    def test_citra_tanpa_koordinat_tidak_muncul_di_peta(self, client):
        """Menempatkannya di titik tengah wilayah akan terlihat seperti data
        survei padahal bukan."""
        image_id = _unggah(client, ["a.jpg"], ["Tanpa EXIF"]).json()["images"][0]["image_id"]
        client.post(f"/api/analyze/{image_id}")

        assert client.get("/api/map").json()["points"] == []
