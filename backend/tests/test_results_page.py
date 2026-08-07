"""Riwayat berhalaman: paging, pengurutan, dan penyaringan.

Ini yang menahan aplikasi tetap dapat dipakai saat citra bertambah menjadi
ribuan. Cara lama mengembalikan seluruh riwayat sekaligus, lengkap dengan setiap
baris deteksi hanya untuk menghitung ringkasannya.
"""

import io

import pytest
from PIL import Image


def _jpeg() -> io.BytesIO:
    buf = io.BytesIO()
    Image.new("RGB", (48, 36), "green").save(buf, "JPEG")
    buf.seek(0)
    return buf


@pytest.fixture
def terisi(client):
    """Lima citra berlabel; tiga di antaranya dianalisis."""
    label = ["Delta", "Alfa", "Charlie", "Bravo", "Echo"]
    ids = []
    for nama in label:
        r = client.post(
            "/api/upload",
            files=[("files", (f"{nama}.jpg", _jpeg(), "image/jpeg"))],
            data={"labels": [nama]},
        )
        ids.append(r.json()["images"][0]["image_id"])
    for image_id in ids[:3]:
        client.post(f"/api/analyze/{image_id}")
    return ids


class TestPaging:
    def test_amplop_memuat_total_dan_batas(self, client, terisi):
        badan = client.get("/api/results?limit=2").json()

        assert badan["total"] == 5
        assert badan["limit"] == 2
        assert badan["offset"] == 0
        assert len(badan["items"]) == 2

    def test_halaman_berikutnya_tidak_mengulang_isi(self, client, terisi):
        a = client.get("/api/results?limit=2&offset=0").json()["items"]
        b = client.get("/api/results?limit=2&offset=2").json()["items"]

        id_a = {x["image_id"] for x in a}
        id_b = {x["image_id"] for x in b}
        assert not (id_a & id_b)

    def test_seluruh_halaman_menutup_seluruh_data_tanpa_duplikat(self, client, terisi):
        """Tanpa kunci urut kedua yang unik, baris bernilai sama dapat bertukar
        tempat antarhalaman dan satu citra muncul dua kali."""
        terkumpul = []
        for offset in range(0, 5, 2):
            terkumpul += [
                x["image_id"]
                for x in client.get(f"/api/results?limit=2&offset={offset}").json()["items"]
            ]

        assert len(terkumpul) == 5
        assert len(set(terkumpul)) == 5

    def test_batas_atas_halaman_ditegakkan(self, client):
        """Batas ini yang mencegah satu permintaan menarik seluruh riwayat."""
        assert client.get("/api/results?limit=5000").status_code == 422

    def test_offset_melewati_akhir_menghasilkan_halaman_kosong(self, client, terisi):
        badan = client.get("/api/results?offset=99").json()

        assert badan["items"] == []
        assert badan["total"] == 5


class TestPengurutan:
    def test_bawaan_terbaru_dulu(self, client, terisi):
        items = client.get("/api/results").json()["items"]

        assert [x["label"] for x in items][0] == "Echo"

    def test_urut_label_menaik(self, client, terisi):
        items = client.get("/api/results?sort=label&order=asc").json()["items"]

        assert [x["label"] for x in items] == [
            "Alfa",
            "Bravo",
            "Charlie",
            "Delta",
            "Echo",
        ]

    def test_urut_jumlah_pohon(self, client, terisi):
        items = client.get("/api/results?sort=trees&order=desc").json()["items"]

        jumlah = [(x["summary"] or {}).get("total", 0) for x in items]
        assert jumlah == sorted(jumlah, reverse=True)

    def test_citra_belum_dianalisis_dihitung_nol_pohon_bukan_dibuang(
        self, client, terisi
    ):
        items = client.get("/api/results?sort=trees&order=asc").json()["items"]

        assert len(items) == 5
        assert items[0]["summary"] is None

    def test_kolom_urut_asing_ditolak(self, client):
        """Nilai dari klien tidak pernah menjadi bagian kueri."""
        r = client.get("/api/results?sort=password")

        assert r.status_code == 400
        assert "Pengurutan tidak dikenal" in r.json()["detail"]


class TestPenyaringan:
    def test_pencarian_label(self, client, terisi):
        badan = client.get("/api/results?q=alfa").json()

        assert badan["total"] == 1
        assert badan["items"][0]["label"] == "Alfa"

    def test_pencarian_ikut_menyesuaikan_total(self, client, terisi):
        """Total harus mengikuti penyaringan; kalau tidak, jumlah halaman salah."""
        assert client.get("/api/results?q=zzz").json()["total"] == 0

    def test_saring_status(self, client, terisi):
        assert client.get("/api/results?status=analyzed").json()["total"] == 3
        assert client.get("/api/results?status=uploaded").json()["total"] == 2


class TestRingkasan:
    def test_ringkasan_dihitung_di_database_dan_nilainya_benar(self, client, terisi):
        """Angkanya harus sama dengan yang dihitung dari hasil lengkap."""
        item = next(
            x
            for x in client.get("/api/results?status=analyzed").json()["items"]
        )
        lengkap = client.get(f"/api/results/{item['image_id']}").json()

        assert item["summary"] == lengkap["summary"]
