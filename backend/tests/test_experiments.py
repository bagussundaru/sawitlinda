"""Catatan eksperimen dan penjagaan test set.

Aturan yang diuji di sini bersifat metodologis: hipotesis dicatat sebelum
hasilnya, hasil hanya dapat dilampirkan sekali, dan test set tidak dapat
dipakai ulang pada model yang sama tanpa disengaja.
"""

import pytest

HASH_TEST = "c0a514696760854c3de3cbdfb8feffc3" * 2
HASH_TEST_LAIN = "f" * 64
MODEL_A = "a" * 64
MODEL_B = "b" * 64


def _catatan(**ubah):
    dasar = {
        "experiment_id": "B1-dji-only",
        "kind": "test",
        "dataset_name": "B1-dji-only",
        "dataset_test_hash": HASH_TEST,
        "dataset_val_hash": "v" * 64,
        "hypothesis": "B2 akan lebih buruk di test meski datanya lebih banyak.",
        "training_config": {"epochs": 50, "base_model": "yolov8m.pt"},
    }
    dasar.update(ubah)
    return dasar


class TestPencatatan:
    def test_eksperimen_tercatat_beserta_hipotesisnya(self, client):
        r = client.post("/api/experiments", json=_catatan())

        assert r.status_code == 201
        badan = r.json()
        assert badan["experiment_id"] == "B1-dji-only"
        assert badan["hypothesis"].startswith("B2 akan lebih buruk")
        assert badan["created_by"] == "tester"

    def test_hasil_belum_ada_saat_dicatat(self, client):
        """Hipotesis yang ditulis setelah melihat angkanya tidak membuktikan
        apa pun."""
        r = client.post("/api/experiments", json=_catatan())

        assert r.json()["metrics"] is None
        assert r.json()["results_at"] is None

    def test_identitas_ganda_ditolak(self, client):
        client.post("/api/experiments", json=_catatan())

        kedua = client.post("/api/experiments", json=_catatan())

        assert kedua.status_code == 409
        assert "immutable" in kedua.json()["detail"]

    def test_hash_test_ikut_tersimpan(self, client):
        """Enam bulan kemudian, inilah satu-satunya cara memastikan angkanya
        diukur pada test set yang sama."""
        r = client.post("/api/experiments", json=_catatan())

        assert r.json()["dataset_test_hash"] == HASH_TEST

    def test_jenis_di_luar_daftar_ditolak(self, client):
        r = client.post("/api/experiments", json=_catatan(kind="produksi"))

        assert r.status_code == 422


class TestPenjagaanTestSet:
    def test_model_berbeda_pada_test_yang_sama_diperbolehkan(self, client):
        """Itu justru tujuan test set — membandingkan model."""
        client.post("/api/experiments", json=_catatan(model_id=MODEL_A))

        r = client.post(
            "/api/experiments",
            json=_catatan(experiment_id="B2-dji-plus-mosaic", model_id=MODEL_B),
        )

        assert r.status_code == 201

    def test_model_sama_pada_test_yang_sama_ditolak(self, client):
        """Di sinilah penyetelan diam-diam berdasarkan hasil test bermula."""
        client.post("/api/experiments", json=_catatan(model_id=MODEL_A))

        r = client.post(
            "/api/experiments",
            json=_catatan(experiment_id="B1-ulang", model_id=MODEL_A),
        )

        assert r.status_code == 409
        pesan = r.json()["detail"]
        assert "already evaluated" in pesan
        assert "B1-dji-only" in pesan  # menyebut catatan yang mana

    def test_pengulangan_yang_disengaja_diperbolehkan_dan_tetap_tercatat(self, client):
        client.post("/api/experiments", json=_catatan(model_id=MODEL_A))

        r = client.post(
            "/api/experiments",
            json=_catatan(
                experiment_id="B1-ulang", model_id=MODEL_A, confirm_repeat=True
            ),
        )

        assert r.status_code == 201
        assert len(client.get("/api/experiments").json()) == 2

    def test_model_sama_pada_test_BERBEDA_diperbolehkan(self, client):
        """Dataset yang berubah adalah eksperimen yang berbeda."""
        client.post("/api/experiments", json=_catatan(model_id=MODEL_A))

        r = client.post(
            "/api/experiments",
            json=_catatan(
                experiment_id="B1-dataset-v4",
                model_id=MODEL_A,
                dataset_test_hash=HASH_TEST_LAIN,
            ),
        )

        assert r.status_code == 201

    def test_validation_boleh_diulang_tanpa_batas(self, client):
        """Validation memang dipakai berkali-kali selama pengembangan."""
        for i in range(3):
            r = client.post(
                "/api/experiments",
                json=_catatan(experiment_id=f"B1-val-{i}", kind="validation"),
            )
            assert r.status_code == 201


def _sampai_siap(client, experiment_id="B1-dji-only", model_id=MODEL_A):
    """Jalankan siklus sampai model dinyatakan final."""
    for tahap in ("locked", "training"):
        client.post(f"/api/experiments/{experiment_id}/status", json={"status": tahap})
    client.post(
        f"/api/experiments/{experiment_id}/status",
        json={"status": "ready_for_final_test", "model_id": model_id},
    )


class TestHasilTidakDapatDitimpa:
    def _buat(self, client):
        client.post("/api/experiments", json=_catatan())
        _sampai_siap(client)

    def test_hasil_dilampirkan_sekali(self, client):
        self._buat(client)

        r = client.post(
            "/api/experiments/B1-dji-only/results",
            json={"metrics": {"map50": 0.61, "map50_95": 0.34}},
        )

        assert r.status_code == 200
        assert r.json()["metrics"]["map50"] == 0.61
        assert r.json()["results_at"]

    def test_percobaan_kedua_ditolak(self, client):
        """Catatan yang hasilnya dapat ditimpa tidak membuktikan apa pun."""
        self._buat(client)
        client.post(
            "/api/experiments/B1-dji-only/results", json={"metrics": {"map50": 0.61}}
        )

        r = client.post(
            "/api/experiments/B1-dji-only/results", json={"metrics": {"map50": 0.99}}
        )

        assert r.status_code == 409
        assert "immutable" in r.json()["detail"]

    def test_hasil_pertama_tetap_utuh_setelah_percobaan_kedua(self, client):
        self._buat(client)
        client.post(
            "/api/experiments/B1-dji-only/results", json={"metrics": {"map50": 0.61}}
        )
        client.post(
            "/api/experiments/B1-dji-only/results", json={"metrics": {"map50": 0.99}}
        )

        tercatat = client.get("/api/experiments").json()[0]
        assert tercatat["metrics"]["map50"] == 0.61

    def test_eksperimen_tak_dikenal_404(self, client):
        r = client.post("/api/experiments/tidak-ada/results", json={"metrics": {}})

        assert r.status_code == 404

    def test_tidak_ada_cara_menghapus_atau_menyunting(self, client):
        """Yang diuji sifatnya, bukan kode statusnya: catatan harus tetap ada.

        Tanpa route sama sekali FastAPI menjawab 404, bukan 405 — keduanya
        sama-sama berarti tidak ada jalan menghapusnya, dan menuntut salah
        satunya hanya menguji detail kerangka kerja.
        """
        self._buat(client)

        assert client.delete("/api/experiments/B1-dji-only").status_code >= 400
        assert client.put("/api/experiments/B1-dji-only", json={}).status_code >= 400

        assert len(client.get("/api/experiments").json()) == 1


class TestPenyaringan:
    def test_dapat_disaring_per_jenis(self, client):
        client.post("/api/experiments", json=_catatan(experiment_id="v", kind="validation"))
        client.post("/api/experiments", json=_catatan(experiment_id="t", kind="test"))

        assert len(client.get("/api/experiments?kind=test").json()) == 1
        assert len(client.get("/api/experiments?kind=validation").json()) == 1


class TestSiklusStatus:
    def _buat(self, client, **ubah):
        return client.post("/api/experiments", json=_catatan(**ubah))

    def test_dimulai_sebagai_draft(self, client):
        assert self._buat(client).json()["status"] == "draft"

    def test_maju_selangkah_demi_selangkah(self, client):
        self._buat(client)

        for tahap in ("locked", "training"):
            r = client.post(
                "/api/experiments/B1-dji-only/status", json={"status": tahap}
            )
            assert r.status_code == 200
            assert r.json()["status"] == tahap

        r = client.post(
            "/api/experiments/B1-dji-only/status",
            json={"status": "ready_for_final_test", "model_id": MODEL_A},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "ready_for_final_test"

    def test_mundur_ditolak(self, client):
        """Catatan yang dapat dikembalikan ke draft setelah hasilnya terlihat
        bukan catatan yang dibekukan."""
        self._buat(client)
        client.post("/api/experiments/B1-dji-only/status", json={"status": "locked"})

        r = client.post(
            "/api/experiments/B1-dji-only/status", json={"status": "draft"}
        )

        assert r.status_code == 409
        assert "only moves forward" in r.json()["detail"]

    def test_final_tested_tidak_dapat_disetel_langsung(self, client):
        """Status itu hanya diperoleh dengan benar-benar melampirkan hasil."""
        self._buat(client)

        r = client.post(
            "/api/experiments/B1-dji-only/status", json={"status": "final_tested"}
        )

        assert r.status_code == 400
        assert "attaching results" in r.json()["detail"]

    def test_hipotesis_dapat_disunting_selagi_draft(self, client):
        self._buat(client)

        r = client.patch(
            "/api/experiments/B1-dji-only", json={"hypothesis": "hipotesis baru"}
        )

        assert r.status_code == 200
        assert r.json()["hypothesis"] == "hipotesis baru"

    def test_hipotesis_beku_setelah_dikunci(self, client):
        """Hipotesis yang masih dapat diubah setelah eksperimen berjalan tidak
        mengikat apa pun."""
        self._buat(client)
        client.post("/api/experiments/B1-dji-only/status", json={"status": "locked"})

        r = client.patch(
            "/api/experiments/B1-dji-only", json={"hypothesis": "diubah belakangan"}
        )

        assert r.status_code == 409
        assert "frozen" in r.json()["detail"]

    def test_hipotesis_asli_tetap_utuh_setelah_percobaan_sunting(self, client):
        self._buat(client)
        client.post("/api/experiments/B1-dji-only/status", json={"status": "locked"})
        client.patch("/api/experiments/B1-dji-only", json={"hypothesis": "diubah"})

        tercatat = client.get("/api/experiments").json()[0]
        assert tercatat["hypothesis"].startswith("B2 akan lebih buruk")

    def test_test_final_ditolak_sebelum_model_final(self, client):
        """Test set tidak boleh disentuh sebelum modelnya benar-benar final."""
        self._buat(client)
        client.post("/api/experiments/B1-dji-only/status", json={"status": "training"})

        r = client.post(
            "/api/experiments/B1-dji-only/results", json={"metrics": {"map50": 0.6}}
        )

        assert r.status_code == 409
        assert "ready_for_final_test" in r.json()["detail"]

    def test_status_menjadi_final_tested_setelah_hasil_dilampirkan(self, client):
        self._buat(client)
        _sampai_siap(client)

        r = client.post(
            "/api/experiments/B1-dji-only/results", json={"metrics": {"map50": 0.6}}
        )

        assert r.json()["status"] == "final_tested"

    def test_validation_tidak_dibatasi_siklus(self, client):
        """Validation memang dipakai berkali-kali selama pengembangan."""
        self._buat(client, experiment_id="B1-val", kind="validation")

        r = client.post(
            "/api/experiments/B1-val/results", json={"metrics": {"map50": 0.5}}
        )

        assert r.status_code == 200


class TestCheckpointDideklarasikanSekali:
    """Bobot belum ada saat mendaftar, sementara hipotesis harus sudah beku.

    Identitas checkpoint karena itu diisi belakangan — tepat di gerbang
    `ready_for_final_test`, saat "pilih checkpoint terbaik" benar-benar terjadi.
    """

    def _buat(self, client, **ubah):
        return client.post("/api/experiments", json=_catatan(**ubah))

    def _sampai_training(self, client):
        for tahap in ("locked", "training"):
            client.post("/api/experiments/B1-dji-only/status", json={"status": tahap})

    def test_boleh_mendaftar_tanpa_checkpoint(self, client):
        r = self._buat(client)

        assert r.status_code == 201
        assert r.json()["model_id"] is None

    def test_hipotesis_beku_sebelum_checkpoint_diketahui(self, client):
        """Inilah yang membuat kedua syarat dapat dipenuhi bersamaan."""
        self._buat(client)
        client.post("/api/experiments/B1-dji-only/status", json={"status": "locked"})

        r = client.patch("/api/experiments/B1-dji-only", json={"hypothesis": "diubah"})

        assert r.status_code == 409
        assert client.get("/api/experiments").json()[0]["model_id"] is None

    def test_checkpoint_dicatat_saat_maju_ke_siap(self, client):
        self._buat(client)
        self._sampai_training(client)

        r = client.post(
            "/api/experiments/B1-dji-only/status",
            json={
                "status": "ready_for_final_test",
                "model_id": MODEL_A,
                "model_name": "b1-best.pt",
            },
        )

        assert r.status_code == 200
        assert r.json()["model_id"] == MODEL_A
        assert r.json()["model_name"] == "b1-best.pt"

    def test_maju_ke_siap_tanpa_checkpoint_ditolak(self, client):
        """Test final yang tidak menyebut bobot mana tidak dapat diulang orang lain."""
        self._buat(client)
        self._sampai_training(client)

        r = client.post(
            "/api/experiments/B1-dji-only/status",
            json={"status": "ready_for_final_test"},
        )

        assert r.status_code == 400
        assert "sha256 of the weights" in r.json()["detail"]

    def test_checkpoint_tidak_dapat_ditukar(self, client):
        self._buat(client)
        _sampai_siap(client)

        r = client.post(
            "/api/experiments/B1-dji-only/status",
            json={"status": "final_tested", "model_id": MODEL_B},
        )

        assert r.status_code >= 400
        assert client.get("/api/experiments").json()[0]["model_id"] == MODEL_A

    def test_checkpoint_tidak_boleh_dideklarasikan_terlalu_dini(self, client):
        self._buat(client)

        r = client.post(
            "/api/experiments/B1-dji-only/status",
            json={"status": "locked", "model_id": MODEL_A},
        )

        assert r.status_code == 400
        assert "declared when advancing" in r.json()["detail"]

    def test_penjagaan_test_set_berlaku_di_gerbang_checkpoint(self, client):
        """Checkpoint yang sudah pernah diuji pada test set ini tetap ditolak,
        walau identitasnya baru muncul belakangan."""
        client.post("/api/experiments", json=_catatan(experiment_id="lama", model_id=MODEL_A))
        self._buat(client)
        self._sampai_training(client)

        r = client.post(
            "/api/experiments/B1-dji-only/status",
            json={"status": "ready_for_final_test", "model_id": MODEL_A},
        )

        assert r.status_code == 409
        assert "already evaluated" in r.json()["detail"]

    def test_validation_tidak_wajib_menyebut_checkpoint(self, client):
        self._buat(client, experiment_id="B1-val", kind="validation")
        for tahap in ("locked", "training"):
            client.post("/api/experiments/B1-val/status", json={"status": tahap})

        r = client.post(
            "/api/experiments/B1-val/status", json={"status": "ready_for_final_test"}
        )

        assert r.status_code == 200
