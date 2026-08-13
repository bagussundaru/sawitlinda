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
        label="Healthy",
        appearance="Dense green crown, normal frond size",
        interpretation="Healthy plant",
        action="No action needed",
    ),
    Condition(
        key="yellow",
        label="Yellowing",
        appearance="Crown dominated by yellow or pale green",
        interpretation="Suspected nutrient deficiency",
        action="Check soil nutrients, apply follow-up fertiliser (N/Mg/K)",
    ),
    Condition(
        key="dead",
        label="Dead / stressed",
        appearance="Crown dried out, brown, fronds dead",
        interpretation="Fronds have died or the plant is severely stressed",
        action="Prune, or carry out a closer field inspection",
    ),
    Condition(
        key="small",
        label="Stunted",
        appearance="Crown noticeably smaller than surrounding plants",
        interpretation="Growth is being held back",
        action="Review fertilisation and assess soil condition",
    ),
)

BY_KEY = {condition.key: condition for condition in CONDITIONS}
BY_LABEL = {condition.label: condition for condition in CONDITIONS}

#: Model class name -> label yang ditampilkan di UI.
CLASS_LABELS = {condition.key: condition.label for condition in CONDITIONS}

#: Urutan tampilan kelas pada layar: sehat lebih dulu, lalu dari yang paling
#: ringan ke yang paling berat. Empat kelas ini SALING LEPAS dan mencakup seluruh
#: pohon, sehingga persentasenya berjumlah 100%.
DISPLAY_ORDER = ("healthy", "yellow", "small", "dead")

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
