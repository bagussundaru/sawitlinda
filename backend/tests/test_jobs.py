"""Antrean pekerjaan latar dan penarikan dataset dari Roboflow.

Roboflow ditiru: tes tidak boleh menghubungi layanan luar, dan harus tetap
berjalan tanpa jaringan maupun kunci API.
"""

import io
import zipfile

import pytest
from PIL import Image

from app import models
from app.db import get_db
from app.main import app as fastapi_app
from app.services import app_settings, job_handlers, jobs, roboflow


def _db():
    return next(fastapi_app.dependency_overrides[get_db]())


def _jpeg(size=(64, 48)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, "green").save(buf, "JPEG")
    return buf.getvalue()


def _dataset_zip(names=("DJI_0001", "DJI_0002")) -> bytes:
    """Arsip ekspor Roboflow tiruan: test/images + test/labels + data.yaml."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("data.yaml", "names: ['healthy', 'yellow', 'dead', 'small']\n")
        for n in names:
            zf.writestr(f"test/images/{n}.jpg", _jpeg())
            # Satu kotak di tengah, kelas 0 (healthy).
            zf.writestr(f"test/labels/{n}.txt", "0 0.5 0.5 0.4 0.4\n")
    return buf.getvalue()


class TestAntrean:
    def test_pekerjaan_tak_dikenal_ditolak(self, client):
        with pytest.raises(ValueError, match="tidak dikenal"):
            jobs.enqueue(_db(), "tidak-ada", {})

    def test_pekerjaan_diantrekan_dan_terbaca_lewat_api(self, client):
        jobs.enqueue(_db(), "reanalyse", {"image_ids": None}, created_by="tester")

        daftar = client.get("/api/jobs").json()

        assert len(daftar) == 1
        assert daftar[0]["kind"] == "reanalyse"
        assert daftar[0]["status"] == "queued"
        assert daftar[0]["created_by"] == "tester"

    def test_hanya_satu_pekerjaan_berat_pada_satu_waktu(self, client):
        """VM ini berbagi dengan aplikasi lain; dua inference sekaligus akan
        memakan seluruh CPU."""
        assert client.post("/api/jobs/reanalyse", json={}).status_code == 202

        kedua = client.post("/api/jobs/reanalyse", json={})

        assert kedua.status_code == 409
        assert "already" in kedua.json()["detail"]

    def test_pekerjaan_diambil_sekali_saja(self, client):
        """Dua pekerja tidak boleh mengambil baris yang sama."""
        db = _db()
        jobs.enqueue(db, "reanalyse", {})

        pertama = jobs._claim(db)
        kedua = jobs._claim(db)

        assert pertama is not None
        assert kedua is None

    def test_pekerjaan_tertinggal_ditandai_gagal_saat_start(self, client, monkeypatch):
        """Dibiarkan "running", layar akan memutar spinner tanpa akhir."""
        db = _db()
        job = jobs.enqueue(db, "reanalyse", {})
        jobs._claim(db)

        monkeypatch.setattr(jobs, "SessionLocal", lambda: _db())
        jobs.reset_interrupted()

        db.refresh(job)
        assert job.status == "failed"
        assert "dijalankan ulang" in job.error

    def test_job_tak_dikenal_404(self, client):
        r = client.get("/api/jobs/00000000-0000-0000-0000-000000000000")

        assert r.status_code == 404


class TestAnalisisUlang:
    def test_menganalisis_ulang_seluruh_citra(self, client, settings):
        r = client.post(
            "/api/upload",
            files=[("files", ("a.jpg", io.BytesIO(_jpeg()), "image/jpeg"))],
            data={"labels": ["Petak"]},
        )
        image_id = r.json()["images"][0]["image_id"]

        db = _db()
        job = jobs.enqueue(db, "reanalyse", {"image_ids": None})
        hasil = job_handlers.reanalyse(db, job)

        assert hasil["images"] == 1
        assert hasil["detections"] > 0
        assert hasil["failed"] == 0
        assert client.get(f"/api/results/{image_id}").json()["summary"]["total"] > 0

    def test_citra_rusak_tidak_menghentikan_sisanya(self, client, settings, monkeypatch):
        for nama in ("a.jpg", "b.jpg"):
            client.post(
                "/api/upload",
                files=[("files", (nama, io.BytesIO(_jpeg()), "image/jpeg"))],
                data={"labels": [nama]},
            )

        panggilan = {"n": 0}

        def kadang_gagal(*a, **k):
            panggilan["n"] += 1
            if panggilan["n"] == 1:
                raise RuntimeError("berkas rusak")
            return {"detections": []}

        monkeypatch.setattr(job_handlers, "run_inference", kadang_gagal)

        db = _db()
        job = jobs.enqueue(db, "reanalyse", {"image_ids": None})
        hasil = job_handlers.reanalyse(db, job)

        assert hasil["failed"] == 1
        assert hasil["images"] == 2


class TestRoboflow:
    def test_nama_tidak_sah_ditolak_sebelum_menghubungi_apa_pun(self):
        """Nilai dari klien tidak pernah membentuk URL lain."""
        for buruk in ["../../etc", "a b", "https://jahat.example"]:
            with pytest.raises(roboflow.RoboflowError, match="tidak sah"):
                roboflow.download_version("kunci", buruk, "project", 1)

    def test_split_tidak_dikenal_ditolak(self):
        with pytest.raises(roboflow.RoboflowError, match="Split tidak dikenal"):
            roboflow.read_split(_dataset_zip(), "produksi")

    def test_citra_split_terbaca_dari_arsip(self):
        citra = roboflow.read_split(_dataset_zip(), "test")

        assert len(citra) == 2
        assert all(n.endswith(".jpg") for n, _ in citra)

    def test_arsip_anotasi_saja_membuang_citra(self):
        """Pembaca anotasi tidak perlu membaca ulang puluhan megabyte citra."""
        ringkas = roboflow.labels_only(_dataset_zip())

        isi = zipfile.ZipFile(io.BytesIO(ringkas)).namelist()
        assert any(n.endswith("data.yaml") for n in isi)
        assert any(n.endswith(".txt") for n in isi)
        assert not any(n.endswith(".jpg") for n in isi)

    def test_tanpa_kunci_api_endpoint_menolak_dengan_jelas(self, client):
        r = client.post(
            "/api/jobs/roboflow-evaluate",
            json={"workspace": "ws", "project": "proj", "version": 3},
        )

        assert r.status_code == 503
        assert "Roboflow API key" in r.json()["detail"]

    def test_kunci_disimpan_dan_tidak_dapat_dibaca_kembali(self, client):
        r = client.put("/api/settings/roboflow", json={"api_key": "rahasia-roboflow"})

        badan = r.json()
        assert badan["configured"] is True
        assert badan["key_hint"] == "…flow"
        assert "rahasia-roboflow" not in r.text

    def test_pekerjaan_diantrekan_setelah_kunci_diisi(self, client):
        client.put("/api/settings/roboflow", json={"api_key": "rahasia-roboflow"})

        r = client.post(
            "/api/jobs/roboflow-evaluate",
            json={"workspace": "ws", "project": "proj", "version": 3},
        )

        assert r.status_code == 202
        assert r.json()["kind"] == "roboflow_evaluate"

    def test_alur_penuh_menghasilkan_evaluasi(self, client, settings, monkeypatch):
        """Menarik, mendaftarkan, menganalisis, lalu menghitung metrik."""
        db = _db()
        app_settings.set_value(db, job_handlers.ROBOFLOW_KEY, "kunci-uji")
        monkeypatch.setattr(
            roboflow, "download_version", lambda *a, **k: _dataset_zip()
        )

        job = jobs.enqueue(
            db,
            "roboflow_evaluate",
            {"workspace": "ws", "project": "sawit", "version": 3, "split": "test"},
        )
        hasil = job_handlers.roboflow_evaluate(db, job)

        assert hasil["images_analysed"] == 2
        assert hasil["dataset"] == "ws/sawit v3 (test)"

        evaluasi = client.get("/api/evaluations").json()[0]
        # Versi dataset dicatat, bukan nama berkas sementara — inilah yang
        # membuat evaluasi dapat diulang orang lain.
        assert evaluasi["source_filename"] == "roboflow:ws/sawit/v3/test"

    def test_citra_yang_sudah_ada_tidak_digandakan(self, client, settings, monkeypatch):
        db = _db()
        app_settings.set_value(db, job_handlers.ROBOFLOW_KEY, "kunci-uji")
        monkeypatch.setattr(roboflow, "download_version", lambda *a, **k: _dataset_zip())

        muatan = {"workspace": "ws", "project": "sawit", "version": 3, "split": "test"}
        job_handlers.roboflow_evaluate(db, jobs.enqueue(db, "roboflow_evaluate", muatan))
        job_handlers.roboflow_evaluate(db, jobs.enqueue(db, "roboflow_evaluate", muatan))

        assert db.query(models.Image).count() == 2
