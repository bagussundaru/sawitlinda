"""Mock detection generator.

Stands in for the trained model until it is delivered. Output is deterministic per
image so that re-analysing the same file gives a stable result during demos.

Nothing outside `engine.py` should import this module.
"""

import hashlib
import random
from pathlib import Path

from PIL import Image

from app.inference.diseases import AFFECTED_CLASSES, CLASS_LABELS, HEALTHY_CLASS

#: Palms are planted on a roughly triangular grid ~9 m apart; at typical UAV
#: altitude that lands somewhere around this many trees per frame.
MIN_TREES = 18
MAX_TREES = 45

#: Roughly 9 m between palms, expressed in degrees near the equator.
TREE_SPACING_DEG = 8.1e-5

DEFAULT_IMAGE_SIZE = (4000, 3000)


def _image_size(image_path: str) -> tuple[int, int]:
    try:
        with Image.open(image_path) as img:
            return img.size
    except Exception:
        return DEFAULT_IMAGE_SIZE


def _seed_for(image_path: str) -> int:
    # hashlib rather than hash(): the latter is salted per process, which would
    # make a re-analysis after a restart return a different result.
    digest = hashlib.sha256(Path(image_path).stem.encode()).digest()
    return int.from_bytes(digest[:4], "big")


def _severity_for(condition: str, rng: random.Random) -> str:
    """Stand-in for the Swin + MTL severity head.

    A dead tree is by definition the worst case; the rest are spread across levels.
    """
    if condition == HEALTHY_CLASS:
        return "sehat"
    if condition == "dead":
        return "berat"
    return rng.choices(["ringan", "sedang", "berat"], weights=[5, 3, 2])[0]


def generate(image_path: str, gps: tuple[float, float] | None = None) -> dict:
    """Produce a detection payload for one image.

    `gps` is the image centre from EXIF, used to scatter plausible per-tree
    coordinates around it. Without it, detections carry no coordinates.
    """
    rng = random.Random(_seed_for(image_path))
    width, height = _image_size(image_path)

    tree_count = rng.randint(MIN_TREES, MAX_TREES)
    # Lay trees out on a grid so the mock looks like a real plantation block.
    columns = max(1, int(tree_count**0.5))
    rows = (tree_count + columns - 1) // columns
    cell_w = width / columns
    cell_h = height / rows

    box_w = cell_w * 0.55
    box_h = cell_h * 0.55

    detections = []
    for index in range(tree_count):
        column, row = index % columns, index // columns

        jitter_x = rng.uniform(-0.08, 0.08) * cell_w
        jitter_y = rng.uniform(-0.08, 0.08) * cell_h
        x = column * cell_w + (cell_w - box_w) / 2 + jitter_x
        y = row * cell_h + (cell_h - box_h) / 2 + jitter_y

        # Most trees in a block are healthy; severe cases are rare.
        if rng.random() < 0.72:
            condition = HEALTHY_CLASS
        else:
            condition = rng.choice(AFFECTED_CLASSES)
        severity = _severity_for(condition, rng)
        disease = CLASS_LABELS[condition]

        detection_gps = None
        if gps is not None:
            lat, lng = gps
            detection_gps = {
                "lat": lat + (row - rows / 2) * TREE_SPACING_DEG,
                "lng": lng + (column - columns / 2) * TREE_SPACING_DEG,
            }

        detections.append(
            {
                "bbox": [
                    round(max(0.0, x), 1),
                    round(max(0.0, y), 1),
                    round(box_w, 1),
                    round(box_h, 1),
                ],
                "disease": disease,
                "severity": severity,
                "confidence": round(rng.uniform(0.71, 0.98), 2),
                "gps": detection_gps,
            }
        )

    return {"detections": detections}
