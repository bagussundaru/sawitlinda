"""Disease vocabulary.

Kept in one module so that swapping in the real model means aligning these names
with the trained label set in exactly one place.

STATUS: acuan awal dari CLAUDE.md — belum dikonfirmasi ke klien dan belum
dicocokkan dengan label dataset Roboflow.
"""

HEALTHY = "Sehat"

DISEASES = [
    "Ganoderma (busuk pangkal batang)",
    "Karat daun",
    "Bercak daun (Curvularia)",
    "Defisiensi hara",
]

#: Every value the `severity` field may take. "sehat" marks a tree with no disease.
SEVERITIES = ["sehat", "ringan", "sedang", "berat"]
