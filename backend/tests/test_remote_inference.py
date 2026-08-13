"""Jalur inference GPU di Modal.

Mesin GPU ditiru: tes tidak boleh memanggil layanan berbayar, dan harus tetap
berjalan tanpa jaringan.
"""

import pytest
from PIL import Image

from app.inference import yolo
from app.services import remote_inference


@pytest.fixture
def citra(tmp_path):
    """Bingkai yang cukup besar untuk memicu pemotongan ubin."""
    path = tmp_path / "bingkai.jpg"
    Image.new("RGB", (2000, 1500), "green").save(path)
    return str(path)


@pytest.fixture
def bobot(tmp_path):
    path = tmp_path / "best.pt"
    path.write_bytes(b"bobot-palsu")
    return str(path)


@pytest.fixture
def gpu(settings, monkeypatch):
    """Konfigurasi yang menyatakan mesin GPU tersedia, plus mesin tiruannya."""
    settings.modal_inference_url = "https://contoh.modal.run"
    settings.modal_inference_token = "token-gpu"

    panggilan = {}

    def detect(_settings, *, image_path, tiles, model_path, imgsz, conf, iou):
        panggilan.update(
            tiles=tiles, imgsz=imgsz, conf=conf, iou=iou, model_path=model_path
        )
        # Dua kotak dari ubin berbeda yang menunjuk pohon yang sama.
        return [
            (100.0, 100.0, 200.0, 200.0, "healthy", 0.9),
            (104.0, 104.0, 204.0, 204.0, "healthy", 0.7),
            (900.0, 800.0, 980.0, 880.0, "yellow", 0.6),
        ]

    monkeypatch.setattr(remote_inference, "detect", detect)
    return panggilan


class TestJalurGpu:
    def test_deteksi_dijalankan_di_gpu_saat_dikonfigurasi(
        self, settings, gpu, citra, bobot, monkeypatch
    ):
        def jangan_dipanggil(*a, **k):
            raise AssertionError("model lokal tidak boleh dimuat")

        monkeypatch.setattr(yolo, "load", jangan_dipanggil)

        hasil = yolo.run(citra, model_path=bobot, settings=settings)

        assert len(hasil["detections"]) == 2  # dua kembar digabung jadi satu

    def test_geometri_ubin_ditentukan_di_sini_bukan_di_gpu(
        self, settings, gpu, citra, bobot
    ):
        """Mesin GPU tidak boleh memutuskan apa pun tentang cara citra dibaca."""
        yolo.run(citra, model_path=bobot, settings=settings)

        assert gpu["tiles"], "daftar ubin harus dikirim bersama citra"
        assert gpu["imgsz"] == yolo.TILE_SIZE
        assert gpu["conf"] == yolo.CONF_THRESHOLD
        # Ubin harus menutupi seluruh bingkai 2000x1500.
        assert max(t[2] for t in gpu["tiles"]) == 2000
        assert max(t[3] for t in gpu["tiles"]) == 1500

    def test_penggabungan_dan_keparahan_tetap_dihitung_di_sini(
        self, settings, gpu, citra, bobot
    ):
        hasil = yolo.run(citra, model_path=bobot, settings=settings)["detections"]

        assert [d["condition"] for d in hasil] == ["Healthy", "Yellowing"]
        assert [d["severity"] for d in hasil] == ["sehat", "ringan"]

    def test_hasil_tetap_terurut_mengikuti_pembacaan_citra(
        self, settings, gpu, citra, bobot
    ):
        hasil = yolo.run(citra, model_path=bobot, settings=settings)["detections"]
        posisi = [(d["bbox"][1], d["bbox"][0]) for d in hasil]

        assert posisi == sorted(posisi)

    def test_kegagalan_gpu_diulang_di_cpu_bukan_menggagalkan_permintaan(
        self, settings, gpu, citra, bobot, monkeypatch
    ):
        """Mesin GPU yang mati tidak boleh membuat aplikasi berhenti bekerja."""

        def gagal(*a, **k):
            raise remote_inference.RemoteError("jaringan putus")

        monkeypatch.setattr(remote_inference, "detect", gagal)

        dipakai = {"cpu": False}

        def cpu(model, image_path):
            dipakai["cpu"] = True
            return [(10.0, 10.0, 50.0, 50.0, "healthy", 0.8)], 2000, 1500

        monkeypatch.setattr(yolo, "load", lambda p: object())
        monkeypatch.setattr(yolo, "_predict_tiled", cpu)

        hasil = yolo.run(citra, model_path=bobot, settings=settings)

        assert dipakai["cpu"] is True
        assert len(hasil["detections"]) == 1

    def test_tanpa_konfigurasi_gpu_langsung_memakai_cpu(
        self, settings, citra, bobot, monkeypatch
    ):
        settings.modal_inference_url = ""
        settings.modal_inference_token = ""

        def jangan_dipanggil(*a, **k):
            raise AssertionError("mesin GPU tidak boleh dihubungi")

        monkeypatch.setattr(remote_inference, "detect", jangan_dipanggil)
        monkeypatch.setattr(yolo, "load", lambda p: object())
        monkeypatch.setattr(
            yolo, "_predict_tiled", lambda m, p: ([], 2000, 1500)
        )

        assert yolo.run(citra, model_path=bobot, settings=settings) == {"detections": []}


class TestSidikBobot:
    def test_hash_berubah_saat_berkas_diganti(self, tmp_path):
        """Berkas yang diganti di tempat tidak boleh memakai hash lama —
        mesin GPU akan menjalankan model yang keliru."""
        path = tmp_path / "best.pt"
        path.write_bytes(b"model versi satu")
        pertama = remote_inference._sha(str(path))

        path.write_bytes(b"model versi dua yang berbeda panjangnya")
        kedua = remote_inference._sha(str(path))

        assert pertama != kedua

    def test_berkas_sama_menghasilkan_hash_sama(self, tmp_path):
        """Kalau tidak, bobot 50 MB akan diunggah ulang tiap citra."""
        path = tmp_path / "best.pt"
        path.write_bytes(b"model")

        assert remote_inference._sha(str(path)) == remote_inference._sha(str(path))


class TestKeamanan:
    def test_token_gpu_tidak_pernah_muncul_di_respons_api(self, client, settings):
        settings.modal_inference_url = "https://contoh.modal.run"
        settings.modal_inference_token = "token-rahasia-gpu"

        badan = client.get("/api/system").text + client.get("/api/train/config").text

        assert "token-rahasia-gpu" not in badan
