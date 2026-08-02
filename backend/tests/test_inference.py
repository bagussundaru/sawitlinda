from PIL import Image

from app.inference import engine
from app.inference.diseases import HEALTHY, SEVERITIES


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
        assert (detection["disease"] == HEALTHY) == (detection["severity"] == "sehat")


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
