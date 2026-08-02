"""Vocabulary of plant conditions, with the agronomic reading of each one.

Kept in one module so that swapping in the real model means aligning names with the
trained label set in exactly one place.

SOURCE: dataset klien di Roboflow Universe,
`heras-workspace/oil-palm-central-kalimantan` (Object Detection, 1.007 citra),
4 kelas: `healthy`, `yellow`, `dead`, `small`. Interpretasi & tindakan berasal dari
tabel kategori kelas yang diberikan klien.

CATATAN — kelas dataset adalah **kondisi pohon**, bukan diagnosis penyakit.
Lihat docs/SWAP_MODEL.md.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Condition:
    """One tree condition as the field team reads it."""

    #: Class name emitted by the model. Must match the trained label exactly.
    key: str
    #: Label shown in the UI.
    label: str
    #: What it looks like from above.
    appearance: str
    #: What it most likely means.
    interpretation: str
    #: What the operator should do about it.
    action: str


CONDITIONS: tuple[Condition, ...] = (
    Condition(
        key="healthy",
        label="Sehat",
        appearance="Tajuk hijau rapat, ukuran pelepah normal",
        interpretation="Tanaman sehat",
        action="Tidak ada tindakan",
    ),
    Condition(
        key="yellow",
        label="Menguning",
        appearance="Tajuk didominasi warna kuning atau hijau pucat",
        interpretation="Dugaan defisiensi nutrisi",
        action="Periksa unsur hara, lakukan pemupukan susulan (N/Mg/K)",
    ),
    Condition(
        key="dead",
        label="Mati/stres",
        appearance="Tajuk mengering, berwarna cokelat, pelepah mati",
        interpretation="Pelepah telah mati atau tanaman mengalami stres berat",
        action="Lakukan pemangkasan atau inspeksi lapangan lebih lanjut",
    ),
    Condition(
        key="small",
        label="Kerdil",
        appearance="Tajuk berukuran lebih kecil dibanding tanaman sekitar",
        interpretation="Pertumbuhan tanaman terhambat",
        action="Review kembali pemupukan dan evaluasi kondisi tanah",
    ),
)

BY_KEY = {condition.key: condition for condition in CONDITIONS}
BY_LABEL = {condition.label: condition for condition in CONDITIONS}

#: Model class name -> label yang ditampilkan di UI.
CLASS_LABELS = {condition.key: condition.label for condition in CONDITIONS}

#: The one class that means "nothing wrong with this tree".
HEALTHY_CLASS = "healthy"
HEALTHY = CLASS_LABELS[HEALTHY_CLASS]

#: Conditions that count as a finding, in the order they are shown.
AFFECTED_CLASSES = [key for key in CLASS_LABELS if key != HEALTHY_CLASS]

#: Every value the `severity` field may take. "sehat" marks a tree with no finding.
#:
#: Keparahan berasal dari kepala klasifikasi terpisah (Swin + MTL), bukan dari kelas
#: deteksi — dataset tidak memuat label keparahan, dan proposal §5 mencatat definisi
#: keparahan sebagai hal yang masih perlu disepakati.
SEVERITIES = ["sehat", "ringan", "sedang", "berat"]
