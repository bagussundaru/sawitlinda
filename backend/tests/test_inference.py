from PIL import Image

from app.inference import engine
from app.inference.conditions import CLASS_LABELS, HEALTHY, SEVERITIES


def _image(tmp_path, name="blok.jpg", size=(800, 600)):
    path = tmp_path / name
    Image.new("RGB", size, "green").save(path)
    return str(path)


def test_run_inference_returns_valid_detections(tmp_path):
    result = engine.run_inference(_image(tmp_path))

    assert result["detections"]
    for detection in result["detections"]:
        assert len(detection["bbox"]) == 4
        assert detection["severity"] in SEVERITIES
        assert 0 < detection["confidence"] <= 1
        assert detection["condition"] in CLASS_LABELS.values()
        assert (detection["condition"] == HEALTHY) == (detection["severity"] == "sehat")


def test_dead_trees_are_always_reported_as_severe(tmp_path):
    result = engine.run_inference(_image(tmp_path))

    dead = [d for d in result["detections"] if d["condition"] == CLASS_LABELS["dead"]]
    assert all(d["severity"] == "berat" for d in dead)


def test_bboxes_stay_inside_the_image(tmp_path):
    width, height = 800, 600
    result = engine.run_inference(_image(tmp_path, size=(width, height)))

    for x, y, w, h in (d["bbox"] for d in result["detections"]):
        assert x >= 0 and y >= 0
        assert x + w <= width and y + h <= height


def test_result_is_stable_for_the_same_image(tmp_path):
    path = _image(tmp_path)

    assert engine.run_inference(path) == engine.run_inference(path)


def test_different_images_give_different_results(tmp_path):
    first = engine.run_inference(_image(tmp_path, "a.jpg"))
    second = engine.run_inference(_image(tmp_path, "b.jpg"))

    assert first != second


def test_detections_carry_no_coordinates_without_image_gps(tmp_path):
    result = engine.run_inference(_image(tmp_path))

    assert all(detection["gps"] is None for detection in result["detections"])


def test_detections_are_scattered_around_the_image_gps(tmp_path):
    lat, lng = -0.78912, 101.41233
    result = engine.run_inference(_image(tmp_path), (lat, lng))

    points = [detection["gps"] for detection in result["detections"]]
    assert all(point is not None for point in points)
    # Plausibly within one plantation block, not all stacked on one spot.
    assert all(abs(point["lat"] - lat) < 0.01 for point in points)
    assert len({(point["lat"], point["lng"]) for point in points}) > 1


def test_missing_file_falls_back_instead_of_raising(tmp_path):
    result = engine.run_inference(str(tmp_path / "tidak-ada.jpg"))

    assert result["detections"]


def test_trees_sit_on_a_triangular_grid(tmp_path):
    """Baris berselang-seling setengah langkah, seperti tata tanam sawit."""
    result = engine.run_inference(_image(tmp_path), (-0.78912, 101.41233))
    points = [d["gps"] for d in result["detections"]]

    # Kelompokkan per baris berdasarkan lintang yang sama.
    rows: dict[float, list[float]] = {}
    for point in points:
        rows.setdefault(round(point["lat"], 6), []).append(point["lng"])

    assert len(rows) >= 4, "harus ada beberapa baris tanam"
    urut = [sorted(v) for _, v in sorted(rows.items())]
    # Baris bersebelahan tidak boleh sejajar persis — itu ciri kisi persegi.
    assert urut[0][0] != urut[1][0]


def test_planting_density_is_plausible(tmp_path):
    """Tetangga terdekat tiap pohon berjarak sekitar 9 m — jarak tanam sawit.

    Diukur lewat tetangga terdekat, bukan per baris: jitter posisi membuat
    pengelompokan baris rapuh, sedangkan kerapatan tanam justru yang ingin diuji.
    """
    import math

    result = engine.run_inference(_image(tmp_path), (-0.78912, 101.41233))
    lat0 = -0.78912
    m_per_lng = 111_320.0 * math.cos(math.radians(lat0))

    titik = [
        ((d["gps"]["lat"] - lat0) * 111_320.0, (d["gps"]["lng"] - 101.41233) * m_per_lng)
        for d in result["detections"]
    ]
    assert len(titik) > 8

    terdekat = [
        min(math.dist(a, b) for j, b in enumerate(titik) if j != i)
        for i, a in enumerate(titik)
    ]
    rerata = sum(terdekat) / len(terdekat)

    assert 6 < rerata < 12, f"kerapatan tanam tidak wajar: {rerata:.1f} m"


def test_problems_cluster_instead_of_scattering(tmp_path):
    """Pohon bermasalah harus mengelompok, bukan tersebar merata.

    Diuji dengan membandingkan jarak rata-rata antar-pohon bermasalah terhadap
    jarak rata-rata seluruh pohon: kalau mengelompok, angkanya lebih kecil.
    """
    import math
    from statistics import mean

    def rerata_jarak(titik):
        pasangan = [
            math.dist(a, b)
            for i, a in enumerate(titik)
            for b in titik[i + 1 :]
        ]
        return mean(pasangan) if pasangan else 0.0

    # Beberapa citra, karena satu citra bisa kebetulan tidak punya bercak.
    lebih_rapat = 0
    diperiksa = 0
    for i in range(6):
        result = engine.run_inference(_image(tmp_path, f"kebun-{i}.jpg"))
        semua = [(d["bbox"][0], d["bbox"][1]) for d in result["detections"]]
        sakit = [
            (d["bbox"][0], d["bbox"][1])
            for d in result["detections"]
            if d["severity"] != "sehat"
        ]
        if len(sakit) < 3:
            continue
        diperiksa += 1
        if rerata_jarak(sakit) < rerata_jarak(semua):
            lebih_rapat += 1

    assert diperiksa >= 3, "citra contoh harus menghasilkan cukup temuan"
    assert lebih_rapat >= diperiksa - 1, "temuan tidak mengelompok"
