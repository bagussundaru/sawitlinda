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


@pytest.fixture(autouse=True)
def citra_nyata(tmp_path, monkeypatch):
    """Berkas citra sungguhan di direktori kerja tes.

    `run()` membuka citra untuk mengukur sisinya — itu yang menentukan citra
    dipotong menjadi ubin atau tidak. Berkasnya sengaja kecil supaya jalur yang
    diuji di berkas ini adalah jalur tanpa pemotongan; ukuran bingkai yang
    dipakai perhitungan tetap datang dari `orig_shape` milik model tiruan.
    """
    from PIL import Image

    monkeypatch.chdir(tmp_path)
    for nama in ("citra.jpg", "c.jpg"):
        Image.new("RGB", (320, 240), "green").save(tmp_path / nama)


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


class TestPemotonganUbin:
    """Bingkai besar dipotong menjadi ubin seukuran data pelatihan.

    Tanpa ini ultralytics mengecilkan seluruh bingkai ke satu ukuran masukan.
    Pada bingkai UAV 4000 px tajuk menyusut lebih dari enam kali dan nyaris tak
    ada yang terdeteksi — terukur di produksi: satu bingkai menghasilkan 3
    deteksi dengan cara lama, dan 135 setelah dipotong.
    """

    def test_ubin_menutupi_seluruh_bingkai(self):
        potong = yolo._tile_boxes(4000, 2250)

        assert max(k[2] for k in potong) == 4000
        assert max(k[3] for k in potong) == 2250

    def test_ubin_saling_bertumpang_tindih(self):
        """Tajuk yang terpotong garis batas harus utuh di ubin tetangga."""
        potong = yolo._tile_boxes(2000, 512)
        kiri = sorted({k[0] for k in potong})

        langkah = kiri[1] - kiri[0]
        assert langkah < yolo.TILE_SIZE

    def test_citra_seukuran_ubin_tidak_dipotong(self):
        """Ubin dataset 512 px diproses utuh, sehingga angka evaluasi terhadap
        dataset tidak berubah oleh penambahan pemotongan ini."""
        assert len(yolo._tile_boxes(512, 512)) == 1

    def test_nms_menggabungkan_kotak_kembar_dari_ubin_bertetangga(self):
        """Satu pohon di daerah tumpang tindih terdeteksi dua kali."""
        kembar = [
            {"_xyxy": (100.0, 100.0, 200.0, 200.0), "_conf": 0.9},
            {"_xyxy": (104.0, 104.0, 204.0, 204.0), "_conf": 0.7},
        ]

        assert len(yolo._nms(kembar)) == 1

    def test_nms_mempertahankan_pohon_yang_berbeda(self):
        terpisah = [
            {"_xyxy": (0.0, 0.0, 50.0, 50.0), "_conf": 0.9},
            {"_xyxy": (400.0, 400.0, 450.0, 450.0), "_conf": 0.8},
        ]

        assert len(yolo._nms(terpisah)) == 2

    def test_nms_menyimpan_yang_keyakinannya_tertinggi(self):
        kembar = [
            {"_xyxy": (100.0, 100.0, 200.0, 200.0), "_conf": 0.4},
            {"_xyxy": (102.0, 102.0, 202.0, 202.0), "_conf": 0.95},
        ]

        assert yolo._nms(kembar)[0]["_conf"] == 0.95

    def test_citra_sangat_besar_ditolak_dengan_pesan_jelas(self, monkeypatch, tmp_path):
        """Menggantung berjam-jam lebih buruk daripada menolak."""
        from PIL import Image

        monkeypatch.setattr(yolo, "MAX_TILES", 4)
        besar = tmp_path / "besar.jpg"
        Image.new("RGB", (4000, 2250), "green").save(besar)

        with pytest.raises(yolo.ModelError, match="terlalu besar"):
            yolo._predict_tiled(_Model([]), str(besar))

    def test_hasil_diurutkan_mengikuti_pembacaan_citra(self, monkeypatch):
        """Nomor deteksi pada laporan tidak boleh melompat-lompat."""
        kotak = [
            _Kotak((500, 400, 520, 420), 1, 0.5),
            _Kotak((100, 100, 120, 120), 1, 0.9),
            _Kotak((300, 100, 320, 120), 1, 0.7),
        ]
        _pasang(monkeypatch, _Model(kotak))

        hasil = yolo.run("c.jpg", model_path="m.pt")["detections"]
        posisi = [(d["bbox"][1], d["bbox"][0]) for d in hasil]

        assert posisi == sorted(posisi)
