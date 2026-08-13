"""Tes pembaca berkas anotasi ground truth."""

import io
import json
import zipfile

import pytest

from app.evaluation.parsers import AnnotationError, parse, parse_coco, parse_yolo_zip

SIZES = {"dji_4101": (1000, 500), "dji_4102": (800, 400)}

DATA_YAML = "train: ../train/images\nnames: ['healthy', 'yellow', 'dead', 'small']\nnc: 4\n"


def _zip(berkas: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as arsip:
        for nama, isi in berkas.items():
            arsip.writestr(nama, isi)
    return buffer.getvalue()


class TestYolo:
    def test_koordinat_ternormalisasi_jadi_piksel(self):
        # Titik tengah 0,5/0,5 dengan lebar 0,2 tinggi 0,4 pada citra 1000x500
        # -> x=400, y=150, w=200, h=200.
        isi = _zip({"data.yaml": DATA_YAML, "labels/DJI_4101.txt": "0 0.5 0.5 0.2 0.4\n"})

        hasil = parse_yolo_zip(isi, SIZES)

        assert len(hasil) == 1
        assert hasil[0].box == pytest.approx((400.0, 150.0, 200.0, 200.0))
        assert hasil[0].label == "Healthy"
        assert hasil[0].image == "dji_4101"

    def test_indeks_kelas_dipetakan_ke_label_sistem(self):
        isi = _zip(
            {
                "data.yaml": DATA_YAML,
                "labels/DJI_4101.txt": (
                    "0 0.1 0.1 0.1 0.1\n"
                    "1 0.2 0.2 0.1 0.1\n"
                    "2 0.3 0.3 0.1 0.1\n"
                    "3 0.4 0.4 0.1 0.1\n"
                ),
            }
        )

        label = [g.label for g in parse_yolo_zip(isi, SIZES)]

        assert label == ["Healthy", "Yellowing", "Dead / stressed", "Stunted"]

    def test_classes_txt_juga_diterima(self):
        isi = _zip(
            {
                "classes.txt": "healthy\nyellow\ndead\nsmall\n",
                "labels/DJI_4101.txt": "1 0.5 0.5 0.2 0.2\n",
            }
        )

        assert parse_yolo_zip(isi, SIZES)[0].label == "Yellowing"

    def test_names_bergaya_butir_juga_terbaca(self):
        yaml = "nc: 4\nnames:\n  - healthy\n  - yellow\n  - dead\n  - small\n"
        isi = _zip({"data.yaml": yaml, "labels/DJI_4101.txt": "2 0.5 0.5 0.2 0.2\n"})

        assert parse_yolo_zip(isi, SIZES)[0].label == "Dead / stressed"

    def test_beberapa_citra_terbaca_terpisah(self):
        isi = _zip(
            {
                "data.yaml": DATA_YAML,
                "labels/DJI_4101.txt": "0 0.5 0.5 0.2 0.2\n",
                "labels/DJI_4102.txt": "1 0.5 0.5 0.2 0.2\n",
            }
        )

        hasil = parse_yolo_zip(isi, SIZES)

        assert {g.image for g in hasil} == {"dji_4101", "dji_4102"}

    def test_citra_yang_tidak_ada_di_sistem_dilewati(self):
        isi = _zip(
            {
                "data.yaml": DATA_YAML,
                "labels/DJI_4101.txt": "0 0.5 0.5 0.2 0.2\n",
                "labels/TIDAK_ADA.txt": "0 0.5 0.5 0.2 0.2\n",
            }
        )

        hasil = parse_yolo_zip(isi, SIZES)

        assert len(hasil) == 1

    def test_baris_kosong_diabaikan(self):
        isi = _zip(
            {"data.yaml": DATA_YAML, "labels/DJI_4101.txt": "\n0 0.5 0.5 0.2 0.2\n\n"}
        )

        assert len(parse_yolo_zip(isi, SIZES)) == 1

    def test_tanpa_nama_kelas_ditolak(self):
        isi = _zip({"labels/DJI_4101.txt": "0 0.5 0.5 0.2 0.2\n"})

        with pytest.raises(AnnotationError, match="Nama kelas tidak ditemukan"):
            parse_yolo_zip(isi, SIZES)

    def test_kelas_asing_ditolak_dengan_nama_aslinya(self):
        isi = _zip({"data.yaml": "names: ['ganoderma']\n", "labels/DJI_4101.txt": ""})

        with pytest.raises(AnnotationError, match="ganoderma"):
            parse_yolo_zip(isi, SIZES)

    def test_kolom_kurang_ditolak(self):
        isi = _zip({"data.yaml": DATA_YAML, "labels/DJI_4101.txt": "0 0.5 0.5\n"})

        with pytest.raises(AnnotationError, match="butuh 5 kolom"):
            parse_yolo_zip(isi, SIZES)

    def test_indeks_kelas_di_luar_jangkauan_ditolak(self):
        isi = _zip({"data.yaml": DATA_YAML, "labels/DJI_4101.txt": "9 0.5 0.5 0.2 0.2\n"})

        with pytest.raises(AnnotationError, match="di luar jangkauan"):
            parse_yolo_zip(isi, SIZES)

    def test_zip_rusak_ditolak(self):
        with pytest.raises(AnnotationError, match="bukan arsip zip"):
            parse_yolo_zip(b"bukan zip", SIZES)

    def test_tidak_ada_yang_cocok_menyebutkan_nama_berkas(self):
        isi = _zip({"data.yaml": DATA_YAML, "labels/FOTO_LAIN.txt": "0 0.5 0.5 0.2 0.2\n"})

        with pytest.raises(AnnotationError, match="FOTO_LAIN"):
            parse_yolo_zip(isi, SIZES)


class TestCoco:
    def _coco(self, anotasi=None) -> bytes:
        isi = {
            "images": [{"id": 1, "file_name": "DJI_4101.JPG"}],
            "categories": [
                {"id": 1, "name": "healthy"},
                {"id": 2, "name": "yellow"},
            ],
            "annotations": anotasi
            if anotasi is not None
            else [{"id": 1, "image_id": 1, "category_id": 2, "bbox": [10, 20, 30, 40]}],
        }
        return json.dumps(isi).encode()

    def test_kotak_dipakai_apa_adanya(self):
        hasil = parse_coco(self._coco(), SIZES)

        assert hasil[0].box == (10.0, 20.0, 30.0, 40.0)
        assert hasil[0].label == "Yellowing"
        assert hasil[0].image == "dji_4101"

    def test_anotasi_citra_asing_dilewati(self):
        anotasi = [
            {"id": 1, "image_id": 1, "category_id": 1, "bbox": [1, 2, 3, 4]},
            {"id": 2, "image_id": 99, "category_id": 1, "bbox": [1, 2, 3, 4]},
        ]

        assert len(parse_coco(self._coco(anotasi), SIZES)) == 1

    def test_json_rusak_ditolak(self):
        with pytest.raises(AnnotationError, match="bukan JSON"):
            parse_coco(b"{rusak", SIZES)

    def test_tanpa_annotations_ditolak(self):
        with pytest.raises(AnnotationError, match="annotations"):
            parse_coco(json.dumps({"images": []}).encode(), SIZES)


class TestPemilihanFormat:
    def test_zip_dan_json_dikenali(self):
        isi = _zip({"data.yaml": DATA_YAML, "labels/DJI_4101.txt": "0 0.5 0.5 0.2 0.2\n"})

        assert parse("ekspor.zip", isi, SIZES)

    def test_format_lain_ditolak(self):
        with pytest.raises(AnnotationError, match="Format tidak didukung"):
            parse("anotasi.xml", b"<x/>", SIZES)
