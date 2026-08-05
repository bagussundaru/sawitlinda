"""Tes lapisan inference model terlatih.

Model YOLO ditiru, sehingga tes tetap cepat dan berjalan tanpa berkas model
maupun torch. Yang diuji adalah bagian yang benar-benar ditulis di sini:
pemetaan keluaran model ke kontrak JSON, aturan keparahan, dan georeferensi.
"""

import math
from types import SimpleNamespace

import pytest

from app.inference import engine, yolo


class _Kotak:
    """Peniru objek Boxes milik ultralytics."""

    def __init__(self, xyxy, cls, conf):
        self.xyxy = [SimpleNamespace(tolist=lambda v=xyxy: list(v))]
        self.cls = SimpleNamespace(item=lambda v=cls: v)
        self.conf = SimpleNamespace(item=lambda v=conf: v)


class _Model:
    def __init__(self, kotak, names=None, shape=(1000, 2000)):
        # ultralytics memakai urutan (tinggi, lebar).
        self._hasil = [SimpleNamespace(orig_shape=shape, boxes=kotak)]
        self.names = names or {0: "dead", 1: "healthy", 2: "small", 3: "yellow"}

    def predict(self, **kwargs):
        return self._hasil


@pytest.fixture(autouse=True)
def bersihkan_cache():
    yolo._model = None
    yolo._model_path = None
    yield
    yolo._model = None
    yolo._model_path = None


def _pasang(monkeypatch, model):
    monkeypatch.setattr(yolo, "load", lambda path: model)


class TestPemetaanKeluaran:
    def test_kotak_xyxy_jadi_xywh(self, monkeypatch):
        _pasang(monkeypatch, _Model([_Kotak((100, 200, 340, 500), 1, 0.91)]))

        d = yolo.run("citra.jpg", model_path="model.pt")["detections"][0]

        assert d["bbox"] == [100.0, 200.0, 240.0, 300.0]
        assert d["condition"] == "Sehat"
        assert d["confidence"] == 0.91

    def test_indeks_kelas_dibaca_dari_model_bukan_diasumsikan(self, monkeypatch):
        """Urutan kelas model ini alfabetis; mengasumsikan urutan lain akan salah."""
        kotak = [
            _Kotak((0, 0, 10, 10), 0, 0.9),
            _Kotak((20, 0, 30, 10), 1, 0.9),
            _Kotak((40, 0, 50, 10), 2, 0.9),
            _Kotak((60, 0, 70, 10), 3, 0.9),
        ]
        _pasang(monkeypatch, _Model(kotak))

        label = [d["condition"] for d in yolo.run("c.jpg", model_path="m.pt")["detections"]]

        assert label == ["Mati/stres", "Sehat", "Kerdil", "Menguning"]

    def test_kelas_asing_diabaikan(self, monkeypatch):
        _pasang(
            monkeypatch,
            _Model([_Kotak((0, 0, 10, 10), 0, 0.9)], names={0: "ganoderma"}),
        )

        assert yolo.run("c.jpg", model_path="m.pt")["detections"] == []


class TestAturanKeparahan:
    @pytest.mark.parametrize(
        "kelas, indeks, keparahan",
        [("healthy", 1, "sehat"), ("yellow", 3, "ringan"), ("small", 2, "sedang"), ("dead", 0, "berat")],
    )
    def test_keparahan_mengikuti_aturan_tetap(self, monkeypatch, kelas, indeks, keparahan):
        _pasang(monkeypatch, _Model([_Kotak((0, 0, 10, 10), indeks, 0.9)]))

        assert yolo.run("c.jpg", model_path="m.pt")["detections"][0]["severity"] == keparahan

    def test_setiap_kelas_punya_aturan(self):
        from app.inference.conditions import CLASS_LABELS

        assert set(yolo.SEVERITY_RULE) == set(CLASS_LABELS)


class TestGeoreferensi:
    def test_tanpa_luas_area_koordinat_dikosongkan(self, monkeypatch):
        """Menebak skala tanah akan menempatkan pohon di tempat yang salah."""
        _pasang(monkeypatch, _Model([_Kotak((0, 0, 10, 10), 1, 0.9)]))

        d = yolo.run("c.jpg", gps=(-0.789, 101.412), model_path="m.pt")["detections"][0]

        assert d["gps"] is None

    def test_tanpa_gps_citra_koordinat_dikosongkan(self, monkeypatch):
        _pasang(monkeypatch, _Model([_Kotak((0, 0, 10, 10), 1, 0.9)]))

        d = yolo.run("c.jpg", area_ha=1.0, model_path="m.pt")["detections"][0]

        assert d["gps"] is None

    def test_kotak_di_tengah_citra_memakai_koordinat_citra(self, monkeypatch):
        # Bingkai 2000x1000 piksel; kotak tepat di tengah.
        _pasang(monkeypatch, _Model([_Kotak((990, 490, 1010, 510), 1, 0.9)]))

        d = yolo.run(
            "c.jpg", gps=(-0.789, 101.412), area_ha=2.0, model_path="m.pt"
        )["detections"][0]

        assert d["gps"]["lat"] == pytest.approx(-0.789, abs=1e-6)
        assert d["gps"]["lng"] == pytest.approx(101.412, abs=1e-6)

    def test_pergeseran_piksel_jadi_pergeseran_meter_yang_benar(self, monkeypatch):
        """Luas 2 ha pada bingkai 2000x1000 -> 200 m x 100 m -> 0,1 m per piksel."""
        _pasang(monkeypatch, _Model([_Kotak((1490, 490, 1510, 510), 1, 0.9)]))

        d = yolo.run(
            "c.jpg", gps=(0.0, 0.0), area_ha=2.0, model_path="m.pt"
        )["detections"][0]

        # Bergeser 500 piksel ke kanan = 50 m timur.
        meter_per_derajat = 111_320.0 * math.cos(0.0)
        assert d["gps"]["lng"] == pytest.approx(50.0 / meter_per_derajat, rel=1e-3)
        assert d["gps"]["lat"] == pytest.approx(0.0, abs=1e-9)

    def test_skala_tanah_dihitung_dari_luas_dan_rasio_bingkai(self):
        # 2 ha = 20.000 m2 pada bingkai 2:1 -> 200 m x 100 m.
        x, y = yolo._ground_scale(2000, 1000, 2.0)

        assert x == pytest.approx(0.1)
        assert y == pytest.approx(0.1)

    def test_luas_nol_atau_kosong_tidak_menghasilkan_skala(self):
        assert yolo._ground_scale(2000, 1000, None) is None
        assert yolo._ground_scale(2000, 1000, 0) is None


class TestPemilihanMesin:
    def test_tanpa_model_memakai_mock(self, settings, tmp_path):
        from PIL import Image

        citra = tmp_path / "c.jpg"
        Image.new("RGB", (800, 600), "green").save(citra)
        settings.model_path = ""

        assert engine.model_is_available() is False
        assert engine.run_inference(str(citra))["detections"]

    def test_kegagalan_model_jatuh_ke_mock_bukan_menggagalkan_permintaan(
        self, settings, tmp_path, monkeypatch
    ):
        from PIL import Image

        citra = tmp_path / "c.jpg"
        Image.new("RGB", (800, 600), "green").save(citra)

        palsu = tmp_path / "model.pt"
        palsu.write_bytes(b"bukan model")
        settings.model_path = str(palsu)

        def meledak(*a, **k):
            raise yolo.ModelError("model rusak")

        monkeypatch.setattr(yolo, "run", meledak)

        hasil = engine.run_inference(str(citra))

        assert hasil["detections"], "harus tetap mengembalikan hasil dari mock"

    def test_path_relatif_diselesaikan_terhadap_backend(self, settings):
        settings.model_path = "models/best.pt"

        berkas = settings.model_file

        assert berkas is not None
        assert berkas.is_absolute()
        assert berkas.parent.name == "models"


class TestStatusMesin:
    def test_tanpa_berkas_model_status_mock_tanpa_galat(self, settings):
        settings.model_path = ""

        assert engine.engine_status() == ("mock", None)

    def test_berkas_ada_tapi_mesin_rusak_dilaporkan_apa_adanya(
        self, settings, tmp_path, monkeypatch
    ):
        """Kegagalan mesin tidak boleh bersembunyi di balik status sehat.

        Persis kasus yang terjadi di produksi: berkas model ada, tapi cv2 gagal
        diimpor karena pustaka X11 tidak terpasang di container.
        """
        palsu = tmp_path / "best.pt"
        palsu.write_bytes(b"bukan model")
        settings.model_path = str(palsu)

        def gagal(path):
            raise yolo.ModelError("libxcb.so.1: cannot open shared object file")

        monkeypatch.setattr(yolo, "load", gagal)

        mode, galat = engine.engine_status()

        assert mode == "mock"
        assert "libxcb" in galat

    def test_endpoint_system_ikut_melaporkan_galat_mesin(
        self, client, settings, tmp_path, monkeypatch
    ):
        palsu = tmp_path / "best.pt"
        palsu.write_bytes(b"bukan model")
        settings.model_path = str(palsu)
        monkeypatch.setattr(
            yolo, "load", lambda path: (_ for _ in ()).throw(yolo.ModelError("rusak"))
        )

        body = client.get("/api/system").json()

        assert body["inference_mode"] == "mock"
        assert body["model_loaded"] is False
        assert body["model_error"] == "rusak"
