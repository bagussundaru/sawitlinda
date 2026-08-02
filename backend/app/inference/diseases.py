"""Vocabulary of tree conditions.

Kept in one module so that swapping in the real model means aligning names with the
trained label set in exactly one place.

SOURCE: dataset klien di Roboflow Universe,
`heras-workspace/oil-palm-central-kalimantan` (Object Detection, 1.007 citra),
dengan 4 kelas: `yellow`, `healthy`, `dead`, `small`.

CATATAN PENTING — kelas dataset adalah **kondisi pohon**, bukan nama penyakit.
Daftar penyakit di CLAUDE.md (Ganoderma, karat daun, bercak daun, defisiensi hara)
tidak ada di dataset ini. Sampai klien menyediakan label penyakit, sistem melaporkan
kondisi pohon apa adanya — lihat docs/SWAP_MODEL.md.
"""

#: Model class name -> label yang ditampilkan di UI (Bahasa Indonesia).
CLASS_LABELS = {
    "healthy": "Sehat",
    "yellow": "Daun menguning",
    "dead": "Pohon mati",
    "small": "Pertumbuhan kerdil",
}

#: The one class that means "nothing wrong with this tree".
HEALTHY_CLASS = "healthy"
HEALTHY = CLASS_LABELS[HEALTHY_CLASS]

#: Conditions that count as a finding, in the order they are shown.
AFFECTED_CLASSES = [name for name in CLASS_LABELS if name != HEALTHY_CLASS]

#: Every value the `severity` field may take. "sehat" marks a tree with no finding.
#:
#: Keparahan berasal dari kepala klasifikasi terpisah (Swin + MTL), bukan dari
#: kelas deteksi — dataset di atas tidak memuat label keparahan.
SEVERITIES = ["sehat", "ringan", "sedang", "berat"]
