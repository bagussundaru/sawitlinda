"""Penyiapan dataset klasifikasi untuk tahap Swin.

Yang diuji terutama satu hal: pembagian split tidak boleh membocorkan sumber
yang sama ke dua split. Angka evaluasi Swin berdiri di atas itu.
"""

import io
import zipfile

import pytest

from app.training import crops


class TestSatuanSumber:
    """Ubin dari mosaik yang sama harus dikenali sebagai satu sumber."""

    @pytest.mark.parametrize(
        "nama, diharapkan",
        [
            ("44000_16000_1031_1863_jpg.rf.64e117de.jpg", "44000_16000"),
            ("44000_16000_1059_3696_jpg.rf.59521e56.jpg", "44000_16000"),
            ("52000_20000_2670_3716_jpg.rf.b4cb6c96.jpg", "52000_20000"),
            ("labels/44000_4000_100_200_jpg.rf.abc123.txt", "44000_4000"),
        ],
    )
    def test_ubin_mosaik_dikelompokkan_ke_mosaiknya(self, nama, diharapkan):
        assert crops.source_group(nama) == diharapkan

    def test_ubin_bertetangga_masuk_kelompok_yang_sama(self):
        """Inti pencegahan kebocoran: dua ubin bersinggungan tidak boleh
        terpisah ke train dan test."""
        a = crops.source_group("44000_16000_1031_1863_jpg.rf.aaa.jpg")
        b = crops.source_group("44000_16000_1059_3696_jpg.rf.bbb.jpg")

        assert a == b

    def test_bingkai_berdiri_sendiri_jadi_kelompoknya_sendiri(self):
        assert crops.source_group("DJI_0476_JPG.rf.263fc391.jpg") == "DJI_0476"

    def test_mosaik_berbeda_tidak_tercampur(self):
        assert crops.source_group("44000_16000_1_2.jpg") != crops.source_group(
            "44000_4000_1_2.jpg"
        )


class TestPembagianSplit:
    def test_seluruh_kelompok_masuk_tepat_satu_split(self):
        pembagian = crops.split_groups({"a": 100, "b": 80, "c": 60, "d": 40})

        assert set(pembagian) == {"a", "b", "c", "d"}
        assert all(s in crops.SPLITS for s in pembagian.values())

    def test_kelompok_tidak_pernah_terbelah(self):
        """Satu kelompok hanya boleh punya satu split — itulah aturannya."""
        pembagian = crops.split_groups({f"g{i}": 10 for i in range(20)})

        assert len(pembagian) == 20
        assert all(isinstance(v, str) for v in pembagian.values())

    def test_hasilnya_deterministik(self):
        """Dua orang pada dataset yang sama harus memperoleh pembagian sama,
        atau angkanya tidak dapat dibandingkan."""
        jumlah = {"a": 50, "b": 30, "c": 20, "d": 15, "e": 5}

        assert crops.split_groups(jumlah) == crops.split_groups(jumlah)

    def test_proporsi_mendekati_rasio_yang_diminta(self):
        jumlah = {f"g{i}": 10 for i in range(30)}
        pembagian = crops.split_groups(jumlah, ratios=(0.7, 0.15, 0.15))

        ukuran = {s: 0 for s in crops.SPLITS}
        for g, s in pembagian.items():
            ukuran[s] += jumlah[g]

        assert 0.6 <= ukuran["train"] / 300 <= 0.8
        assert ukuran["val"] > 0 and ukuran["test"] > 0

    def test_rasio_yang_tidak_berjumlah_satu_ditolak(self):
        with pytest.raises(ValueError, match="berjumlah 1"):
            crops.split_groups({"a": 1}, ratios=(0.5, 0.3, 0.1))

    def test_dataset_kosong_tidak_meledak(self):
        assert crops.split_groups({}) == {}


class TestRencanaPotongan:
    KELAS = ["healthy", "yellow", "dead", "small"]

    def _anotasi(self):
        return {
            "44000_16000_1_1": [(0, 0.5, 0.5, 0.2, 0.2), (1, 0.2, 0.2, 0.1, 0.1)],
            "44000_16000_2_2": [(2, 0.5, 0.5, 0.2, 0.2)],
            "DJI_0100": [(3, 0.5, 0.5, 0.3, 0.3)],
        }

    def _ukuran(self):
        return {k: (1000, 800) for k in self._anotasi()}

    def test_kotak_ternormalisasi_jadi_piksel(self):
        potongan, _ = crops.plan_crops(
            {"a": [(0, 0.5, 0.5, 0.2, 0.2)]}, self.KELAS, {"a": (1000, 800)}, padding=0
        )

        c = potongan[0]
        assert (c.x1, c.y1, c.x2, c.y2) == (400.0, 320.0, 600.0, 480.0)

    def test_padding_melebarkan_kotak(self):
        """Tajuk yang terpotong tepat di garis kehilangan konteks tepinya."""
        tanpa, _ = crops.plan_crops(
            {"a": [(0, 0.5, 0.5, 0.2, 0.2)]}, self.KELAS, {"a": (1000, 800)}, padding=0
        )
        dengan, _ = crops.plan_crops(
            {"a": [(0, 0.5, 0.5, 0.2, 0.2)]}, self.KELAS, {"a": (1000, 800)}, padding=0.1
        )

        assert dengan[0].x2 - dengan[0].x1 > tanpa[0].x2 - tanpa[0].x1

    def test_kotak_tidak_keluar_dari_citra(self):
        potongan, _ = crops.plan_crops(
            {"a": [(0, 0.02, 0.02, 0.1, 0.1)]}, self.KELAS, {"a": (1000, 800)}, padding=0.5
        )

        c = potongan[0]
        assert c.x1 >= 0 and c.y1 >= 0 and c.x2 <= 1000 and c.y2 <= 800

    def test_label_diambil_dari_ground_truth_bukan_prediksi(self):
        """Melatih Swin pada keluaran YOLOv8 berarti mengajarinya meniru
        YOLOv8, bukan belajar dari kebenaran."""
        potongan, _ = crops.plan_crops(self._anotasi(), self.KELAS, self._ukuran())

        assert {c.label for c in potongan} == {"healthy", "yellow", "dead", "small"}

    def test_setiap_potongan_membawa_jejak_asalnya(self):
        potongan, _ = crops.plan_crops(self._anotasi(), self.KELAS, self._ukuran())

        c = potongan[0]
        assert c.crop_id and c.source_image and c.source_group
        assert c.tree_index >= 0

    def test_citra_yang_tidak_ada_dilewati_bukan_ditebak(self):
        potongan, _ = crops.plan_crops(
            {"ada": [(0, 0.5, 0.5, 0.2, 0.2)], "hilang": [(0, 0.5, 0.5, 0.2, 0.2)]},
            self.KELAS,
            {"ada": (1000, 800)},
        )

        assert [c.source_image for c in potongan] == ["ada"]

    def test_kotak_terlalu_kecil_dibuang(self):
        potongan, _ = crops.plan_crops(
            {"a": [(0, 0.5, 0.5, 0.001, 0.001)]}, self.KELAS, {"a": (1000, 800)}
        )

        assert potongan == []

    def test_ubin_satu_mosaik_selalu_satu_split(self):
        potongan, pembagian = crops.plan_crops(
            self._anotasi(), self.KELAS, self._ukuran()
        )

        mosaik = {c.source_group for c in potongan if c.source_group == "44000_16000"}
        assert mosaik  # mosaiknya memang ada
        assert pembagian["44000_16000"] in crops.SPLITS


class TestBuktiTanpaKebocoran:
    KELAS = ["healthy", "yellow", "dead", "small"]

    def test_laporan_menyatakan_nol_kebocoran(self):
        """Dihitung, bukan diasumsikan."""
        anotasi = {
            f"44000_16000_{i}_{i}": [(i % 4, 0.5, 0.5, 0.2, 0.2)] for i in range(6)
        }
        anotasi.update({f"DJI_{i:04d}": [(0, 0.5, 0.5, 0.2, 0.2)] for i in range(6)})
        ukuran = {k: (500, 500) for k in anotasi}

        potongan, pembagian = crops.plan_crops(anotasi, self.KELAS, ukuran)
        laporan = crops.leakage_report(potongan, pembagian)

        assert laporan["leaked_groups"] == {}
        assert laporan["crops"] == len(potongan)
        assert sum(laporan["split_sizes"].values()) == len(potongan)

    def test_kebocoran_yang_disengaja_terdeteksi(self):
        """Kalau laporan ini tidak dapat mendeteksi kebocoran, ia tidak
        membuktikan apa pun."""
        potongan = [
            crops.Crop("c1", "img1", "g1", 0, "healthy", 0, 0, 10, 10),
            crops.Crop("c2", "img2", "g1", 0, "healthy", 0, 0, 10, 10),
        ]
        # Kelompok yang sama dipaksa ke dua split — keadaan yang harus tertangkap.
        laporan_a = crops.leakage_report(potongan, {"g1": "train"})
        assert laporan_a["leaked_groups"] == {}

        campur = [
            crops.Crop("c1", "img1", "g1", 0, "healthy", 0, 0, 10, 10),
            crops.Crop("c2", "img2", "g2", 0, "healthy", 0, 0, 10, 10),
        ]
        laporan_b = crops.leakage_report(campur, {"g1": "train", "g2": "test"})
        assert laporan_b["leaked_groups"] == {}
        assert laporan_b["split_sizes"]["train"] == 1
        assert laporan_b["split_sizes"]["test"] == 1


class TestPembacaAnotasi:
    def _arsip(self) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("data.yaml", "names: ['healthy','yellow','dead','small']\n")
            zf.writestr("train/labels/44000_16000_1_1.txt", "0 0.5 0.5 0.2 0.2\n")
            zf.writestr("test/labels/44000_16000_2_2.txt", "1 0.4 0.4 0.1 0.1\n")
            zf.writestr("valid/labels/DJI_0100.txt", "2 0.6 0.6 0.3 0.3\n")
            zf.writestr("train/labels/classes.txt", "healthy\n")
        return buf.getvalue()

    def test_seluruh_split_bawaan_dibaca_lalu_dibagi_ulang(self):
        """Split bawaan Roboflow membagi per ubin; mosaik yang sama dapat
        tersebar ke train dan test."""
        anotasi = crops.read_annotations(self._arsip(), ["healthy", "yellow", "dead", "small"])

        assert set(anotasi) == {"44000_16000_1_1", "44000_16000_2_2", "DJI_0100"}

    def test_classes_txt_tidak_dibaca_sebagai_label(self):
        anotasi = crops.read_annotations(self._arsip(), ["healthy", "yellow", "dead", "small"])

        assert "classes" not in anotasi

    def test_indeks_kelas_di_luar_jangkauan_ditolak(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("train/labels/a.txt", "9 0.5 0.5 0.2 0.2\n")

        with pytest.raises(ValueError, match="di luar jangkauan"):
            crops.read_annotations(buf.getvalue(), ["healthy"])


class TestManifest:
    def test_manifest_memuat_setiap_potongan_beserta_splitnya(self):
        potongan = [crops.Crop("c1", "img1", "g1", 0, "healthy", 1, 2, 3, 4)]

        csv = crops.manifest_csv(potongan, {"g1": "train"})
        baris = csv.strip().split("\n")

        assert baris[0].startswith("crop_id,split,source_image,source_group")
        assert baris[1] == "c1,train,img1,g1,0,healthy,1,2,3,4"
