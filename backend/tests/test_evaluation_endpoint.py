"""Tes endpoint evaluasi ujung-ke-ujung."""

import io
import json
import zipfile

import pytest
from PIL import Image

DATA_YAML = "names: ['healthy', 'yellow', 'dead', 'small']\nnc: 4\n"


def _jpeg(size=(1000, 500)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, "green").save(buffer, format="JPEG")
    return buffer.getvalue()


def _zip(berkas: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as arsip:
        for nama, isi in berkas.items():
            arsip.writestr(nama, isi)
    return buffer.getvalue()


@pytest.fixture
def citra_dianalisis(client):
    """Satu citra terunggah dan teranalisis; kembalikan hasil deteksinya."""
    unggah = client.post(
        "/api/upload", files={"files": ("DJI_4101.jpg", _jpeg(), "image/jpeg")}
    )
    image_id = unggah.json()["images"][0]["image_id"]
    return client.post(f"/api/analyze/{image_id}").json()


def _anotasi_dari_deteksi(hasil, ukuran=(1000, 500), ambil=None) -> bytes:
    """Bangun anotasi YOLO yang persis menyalin deteksi sistem.

    Dipakai untuk membuktikan bahwa evaluator memberi skor sempurna ketika
    prediksi dan acuan memang identik.
    """
    lebar, tinggi = ukuran
    indeks = {"Sehat": 0, "Menguning": 1, "Mati/stres": 2, "Kerdil": 3}
    baris = []
    for d in hasil["detections"][:ambil] if ambil else hasil["detections"]:
        x, y, w, h = d["bbox"]
        baris.append(
            f"{indeks[d['condition']]} {(x + w / 2) / lebar} {(y + h / 2) / tinggi} "
            f"{w / lebar} {h / tinggi}"
        )
    return _zip({"data.yaml": DATA_YAML, "labels/DJI_4101.txt": "\n".join(baris)})


def test_anotasi_identik_menghasilkan_skor_sempurna(client, citra_dianalisis):
    anotasi = _anotasi_dari_deteksi(citra_dianalisis)

    response = client.post(
        "/api/evaluate", files={"file": ("gt.zip", anotasi, "application/zip")}
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["map50"] == pytest.approx(1.0)
    assert body["micro_precision"] == pytest.approx(1.0)
    assert body["micro_recall"] == pytest.approx(1.0)
    assert body["ground_truths"] == body["predictions"]


def test_anotasi_separuh_menurunkan_recall_bukan_presisi(client, citra_dianalisis):
    """Ground truth hanya separuh: sisanya jadi positif palsu, recall tetap 1."""
    total = len(citra_dianalisis["detections"])
    anotasi = _anotasi_dari_deteksi(citra_dianalisis, ambil=total // 2)

    body = client.post(
        "/api/evaluate", files={"file": ("gt.zip", anotasi, "application/zip")}
    ).json()

    assert body["micro_recall"] == pytest.approx(1.0)
    assert body["micro_precision"] < 1.0


def test_hasil_mencatat_mode_inference(client, citra_dianalisis):
    """Angka dari mock harus terbaca sebagai mock selamanya."""
    anotasi = _anotasi_dari_deteksi(citra_dianalisis)

    body = client.post(
        "/api/evaluate", files={"file": ("gt.zip", anotasi, "application/zip")}
    ).json()

    assert body["inference_mode"] == "mock"
    assert body["model_name"] is None


def test_confusion_matrix_lengkap(client, citra_dianalisis):
    anotasi = _anotasi_dari_deteksi(citra_dianalisis)

    body = client.post(
        "/api/evaluate", files={"file": ("gt.zip", anotasi, "application/zip")}
    ).json()

    kelas_hadir = {m["label"] for m in body["per_class"] if m["support"] > 0}
    for kelas in kelas_hadir:
        assert body["confusion"][kelas][kelas] > 0


def test_hasil_tersimpan_dan_dapat_dibuka_kembali(client, citra_dianalisis):
    anotasi = _anotasi_dari_deteksi(citra_dianalisis)
    dibuat = client.post(
        "/api/evaluate", files={"file": ("gt.zip", anotasi, "application/zip")}
    ).json()

    daftar = client.get("/api/evaluations").json()
    satu = client.get(f"/api/evaluations/{dibuat['id']}").json()

    assert len(daftar) == 1
    assert satu["map50"] == dibuat["map50"]
    assert satu["source_filename"] == "gt.zip"


def test_ambang_iou_dapat_diatur(client, citra_dianalisis):
    anotasi = _anotasi_dari_deteksi(citra_dianalisis)

    body = client.post(
        "/api/evaluate",
        files={"file": ("gt.zip", anotasi, "application/zip")},
        data={"iou_threshold": "0.9"},
    ).json()

    assert body["iou_threshold"] == 0.9
    assert body["map50"] == pytest.approx(1.0)  # kotaknya identik


def test_tanpa_citra_teranalisis_ditolak(client):
    anotasi = _zip({"data.yaml": DATA_YAML, "labels/DJI_4101.txt": "0 0.5 0.5 0.1 0.1"})

    response = client.post(
        "/api/evaluate", files={"file": ("gt.zip", anotasi, "application/zip")}
    )

    assert response.status_code == 409
    assert "belum ada citra" in response.json()["detail"].lower()


def test_anotasi_rusak_ditolak_dengan_pesan_jelas(client, citra_dianalisis):
    response = client.post(
        "/api/evaluate", files={"file": ("gt.zip", b"bukan zip", "application/zip")}
    )

    assert response.status_code == 400
    assert "zip" in response.json()["detail"].lower()


def test_format_tidak_didukung_ditolak(client, citra_dianalisis):
    response = client.post(
        "/api/evaluate", files={"file": ("gt.xml", b"<x/>", "application/xml")}
    )

    assert response.status_code == 400
    assert "tidak didukung" in response.json()["detail"]


def test_coco_juga_diterima(client, citra_dianalisis):
    d = citra_dianalisis["detections"][0]
    x, y, w, h = d["bbox"]
    coco = json.dumps(
        {
            "images": [{"id": 1, "file_name": "DJI_4101.jpg"}],
            "categories": [{"id": 1, "name": d["condition"]}],
            "annotations": [
                {"id": 1, "image_id": 1, "category_id": 1, "bbox": [x, y, w, h]}
            ],
        }
    ).encode()

    body = client.post(
        "/api/evaluate", files={"file": ("gt.json", coco, "application/json")}
    ).json()

    assert body["ground_truths"] == 1
    assert body["micro_recall"] == pytest.approx(1.0)


def test_citra_tanpa_anotasi_tidak_menekan_presisi(client, citra_dianalisis):
    """Citra kedua tanpa anotasi tidak boleh menjadikan deteksinya positif palsu."""
    kedua = client.post(
        "/api/upload", files={"files": ("DJI_9999.jpg", _jpeg(), "image/jpeg")}
    )
    client.post(f"/api/analyze/{kedua.json()['images'][0]['image_id']}")

    anotasi = _anotasi_dari_deteksi(citra_dianalisis)
    body = client.post(
        "/api/evaluate", files={"file": ("gt.zip", anotasi, "application/zip")}
    ).json()

    assert body["images"] == 1
    assert body["micro_precision"] == pytest.approx(1.0)
