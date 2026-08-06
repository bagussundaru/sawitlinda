"""Proxy training ke Modal.

Mesin Modal ditiru: tes tidak boleh memicu training GPU sungguhan — itu berbiaya
nyata dan memakan waktu berjam-jam.
"""

import io
import zipfile

import pytest

from app.routers import training as training_router
from app.services import app_settings, training_engine


def _zip(nama="dataset.zip") -> tuple[str, io.BytesIO, str]:
    penyangga = io.BytesIO()
    with zipfile.ZipFile(penyangga, "w") as zf:
        zf.writestr("data.yaml", "train: train/images\nnc: 4\n")
    penyangga.seek(0)
    return (nama, penyangga, "application/zip")


@pytest.fixture
def mesin(monkeypatch, settings):
    """Mesin training palsu, plus konfigurasi yang menyatakan mesin tersedia."""
    settings.modal_training_url = "https://contoh.modal.run"
    settings.modal_training_token = "token-uji"

    keadaan = {"status": "queued", "epoch": 0, "history": []}
    dikirim = {}

    async def start(_settings, **kwargs):
        dikirim.update(kwargs)
        return {"job_id": "job123", "status": "queued", "run_name": kwargs["run_name"]}

    async def status_of(_settings, job_id):
        return {"job_id": job_id, "total_epochs": 5, **keadaan}

    async def download_weights(_settings, job_id):
        return b"bobot-palsu"

    monkeypatch.setattr(training_engine, "start", start)
    monkeypatch.setattr(training_engine, "status_of", status_of)
    monkeypatch.setattr(training_engine, "download_weights", download_weights)
    return {"keadaan": keadaan, "dikirim": dikirim}


class TestMemulai:
    def test_dataset_sah_menghasilkan_job(self, client, mesin):
        r = client.post(
            "/api/train",
            files={"dataset": _zip()},
            data={"epochs": "5", "base_model": "yolov8m.pt", "run_name": "uji coba"},
        )

        assert r.status_code == 202
        badan = r.json()
        assert badan["job_id"] == "job123"
        assert badan["status"] == "queued"
        assert badan["started_by"] == "tester"

    def test_nama_run_dibersihkan(self, client, mesin):
        """Nama run menjadi bagian nama berkas bobot."""
        client.post(
            "/api/train",
            files={"dataset": _zip()},
            data={"epochs": "5", "run_name": "../../etc/passwd"},
        )

        assert "/" not in mesin["dikirim"]["run_name"]
        assert ".." not in mesin["dikirim"]["run_name"]

    def test_model_dasar_di_luar_daftar_ditolak(self, client, mesin):
        r = client.post(
            "/api/train",
            files={"dataset": _zip()},
            data={"epochs": "5", "base_model": "sesuatu.pt"},
        )

        assert r.status_code == 400

    @pytest.mark.parametrize("epochs", ["0", "-3", "9999"])
    def test_epoch_di_luar_batas_ditolak(self, client, mesin, epochs):
        r = client.post("/api/train", files={"dataset": _zip()}, data={"epochs": epochs})

        assert r.status_code == 400

    def test_berkas_bukan_zip_ditolak(self, client, mesin):
        r = client.post(
            "/api/train",
            files={"dataset": ("citra.jpg", io.BytesIO(b"bukan zip"), "image/jpeg")},
            data={"epochs": "5"},
        )

        assert r.status_code == 400

    def test_tanpa_konfigurasi_mesin_dilaporkan_jelas(self, client, settings):
        settings.modal_training_url = ""
        settings.modal_training_token = ""

        r = client.get("/api/train/config")

        assert r.status_code == 200
        assert r.json()["configured"] is False


class TestProgres:
    def test_status_diteruskan_dari_mesin(self, client, mesin):
        client.post("/api/train", files={"dataset": _zip()}, data={"epochs": "5"})
        mesin["keadaan"].update(
            status="running",
            epoch=3,
            history=[{"epoch": 1, "map50": 0.1}, {"epoch": 2, "map50": 0.3}],
        )

        badan = client.get("/api/train/job123/status").json()

        assert badan["status"] == "running"
        assert badan["epoch"] == 3
        assert len(badan["history"]) == 2

    def test_hasil_akhir_disalin_ke_database(self, client, mesin):
        """Catatan di Modal Dict tidak permanen; angka akhir harus bertahan."""
        client.post("/api/train", files={"dataset": _zip()}, data={"epochs": "5"})
        mesin["keadaan"].update(
            status="done", epoch=5, final={"map50": 0.61, "map50_95": 0.34}
        )
        client.get("/api/train/job123/status")

        run = next(r for r in client.get("/api/train/runs").json() if r["job_id"] == "job123")

        assert run["status"] == "done"
        assert run["final_map50"] == 0.61
        assert run["final_map50_95"] == 0.34

    def test_run_selesai_tidak_menanyai_mesin_lagi(self, client, mesin, monkeypatch):
        client.post("/api/train", files={"dataset": _zip()}, data={"epochs": "5"})
        mesin["keadaan"].update(status="done", final={"map50": 0.5})
        client.get("/api/train/job123/status")

        async def meledak(*a, **k):
            raise AssertionError("mesin tidak boleh ditanya lagi")

        monkeypatch.setattr(training_engine, "status_of", meledak)

        assert client.get("/api/train/job123/status").json()["status"] == "done"

    def test_kegagalan_dicatat_bukan_menggantung(self, client, mesin):
        """Tanpa ini, job gagal memutar spinner tanpa akhir di layar."""
        client.post("/api/train", files={"dataset": _zip()}, data={"epochs": "5"})
        mesin["keadaan"].update(status="failed", error="CUDA out of memory")
        client.get("/api/train/job123/status")

        run = client.get("/api/train/runs").json()[0]

        assert run["status"] == "failed"
        assert "CUDA" in run["error"]

    def test_job_tak_dikenal_404(self, client, mesin):
        assert client.get("/api/train/tidakada/status").status_code == 404


class TestJadikanAktif:
    def _selesaikan(self, client, mesin):
        client.post("/api/train", files={"dataset": _zip()}, data={"epochs": "5"})
        mesin["keadaan"].update(status="done", epoch=5, final={"map50": 0.61})
        client.get("/api/train/job123/status")

    def test_bobot_disimpan_dan_menjadi_model_aktif(self, client, mesin, settings):
        self._selesaikan(client, mesin)

        r = client.post("/api/train/job123/activate")

        assert r.status_code == 200
        assert r.json()["is_active"] is True

        badan = client.get("/api/system").json()
        assert badan["inference_mode"] in {"model", "mock"}  # berkas palsu -> mock
        # Yang penting: penunjuknya benar-benar berpindah.
        assert client.get("/api/train/config").json()["active_model"].endswith(".pt")

    def test_berkas_bobot_benar_benar_ditulis(self, client, mesin, settings):
        self._selesaikan(client, mesin)
        client.post("/api/train/job123/activate")

        folder = settings.storage_path / "models"
        berkas = list(folder.glob("*.pt"))

        assert berkas and berkas[0].read_bytes() == b"bobot-palsu"
        # Berkas sementara tidak boleh tertinggal.
        assert not list(folder.glob("*.part"))

    def test_training_belum_selesai_tidak_dapat_diaktifkan(self, client, mesin):
        client.post("/api/train", files={"dataset": _zip()}, data={"epochs": "5"})

        r = client.post("/api/train/job123/activate")

        assert r.status_code == 409

    def test_model_aktif_dipakai_inference_tanpa_restart(self, client, mesin, settings):
        """Inti dari tombol ini: pointer model dibaca ulang tiap permintaan."""
        self._selesaikan(client, mesin)
        client.post("/api/train/job123/activate")

        from app.db import get_db
        from app.main import app as fastapi_app

        db = next(fastapi_app.dependency_overrides[get_db]())
        efektif = app_settings.effective_settings(db, settings)

        assert efektif.model_file is not None
        assert efektif.model_file.name.endswith(".pt")
        assert efektif.model_file != settings.model_file


class TestKeamanan:
    def test_token_modal_tidak_pernah_muncul_di_respons(self, client, mesin):
        """Token itu memicu biaya GPU; ia tidak boleh sampai ke peramban."""
        r1 = client.get("/api/train/config")
        r2 = client.post("/api/train", files={"dataset": _zip()}, data={"epochs": "5"})

        assert "token-uji" not in r1.text
        assert "token-uji" not in r2.text

    def test_nama_run_tidak_dapat_menulis_di_luar_folder_model(
        self, client, mesin, settings
    ):
        client.post(
            "/api/train",
            files={"dataset": _zip()},
            data={"epochs": "5", "run_name": "../../../keluar"},
        )
        mesin["keadaan"].update(status="done", final={"map50": 0.5})
        client.get("/api/train/job123/status")
        client.post("/api/train/job123/activate")

        folder = settings.storage_path / "models"
        berkas = list(folder.glob("*.pt"))

        assert len(berkas) == 1
        assert berkas[0].parent == folder
