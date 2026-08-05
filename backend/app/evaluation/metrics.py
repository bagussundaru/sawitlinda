"""Metrik evaluasi deteksi objek.

Inti matematis modul evaluasi: IoU, pencocokan prediksi terhadap ground truth,
presisi/recall/F1 per kelas, Average Precision, mAP, dan confusion matrix.

Seluruh fungsi di sini murni — tanpa database, tanpa berkas, tanpa jaringan —
supaya benar-benar dapat diuji. Konvensinya mengikuti praktik yang lazim dipakai
pada evaluasi COCO/Pascal VOC sehingga angkanya sebanding dengan literatur:

- Kotak dinyatakan sebagai (x, y, w, h) dalam piksel.
- Satu prediksi dianggap benar bila IoU >= ambang DAN kelasnya sama.
- Satu ground truth hanya boleh dipasangkan dengan satu prediksi; prediksi
  berikutnya yang menimpa kotak yang sama dihitung sebagai positif palsu.
- Prediksi diurutkan menurun berdasarkan confidence sebelum dipasangkan, karena
  Average Precision bergantung pada urutan itu.
"""

from __future__ import annotations

from dataclasses import dataclass, field

Box = tuple[float, float, float, float]


@dataclass(frozen=True)
class Prediction:
    box: Box
    label: str
    confidence: float
    #: Identitas citra; pencocokan tidak pernah melintasi citra.
    image: str = ""


@dataclass(frozen=True)
class GroundTruth:
    box: Box
    label: str
    image: str = ""


@dataclass
class ClassMetrics:
    label: str
    support: int
    """Jumlah ground truth untuk kelas ini."""
    predicted: int
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float
    f1: float
    average_precision: float


@dataclass
class EvaluationResult:
    iou_threshold: float
    images: int
    per_class: list[ClassMetrics]
    #: Rata-rata AP lintas kelas yang punya ground truth.
    map50: float
    micro_precision: float
    micro_recall: float
    micro_f1: float
    #: confusion[aktual][prediksi]; "(tidak terdeteksi)" dan "(latar)" mewakili
    #: ground truth yang terlewat dan prediksi yang tidak berpasangan.
    confusion: dict[str, dict[str, int]] = field(default_factory=dict)


MISSED = "(tidak terdeteksi)"
BACKGROUND = "(latar)"


def iou(a: Box, b: Box) -> float:
    """Intersection over Union dua kotak (x, y, w, h)."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    if aw <= 0 or ah <= 0 or bw <= 0 or bh <= 0:
        return 0.0

    x1 = max(ax, bx)
    y1 = max(ay, by)
    x2 = min(ax + aw, bx + bw)
    y2 = min(ay + ah, by + bh)
    if x2 <= x1 or y2 <= y1:
        return 0.0

    irisan = (x2 - x1) * (y2 - y1)
    gabungan = aw * ah + bw * bh - irisan
    return irisan / gabungan if gabungan > 0 else 0.0


def _average_precision(tp_flags: list[int], total_gt: int) -> float:
    """AP dengan interpolasi seluruh titik (gaya COCO/VOC 2010+).

    `tp_flags` berisi 1/0 untuk tiap prediksi, sudah urut menurun berdasarkan
    confidence.
    """
    if total_gt == 0:
        return 0.0

    tp = fp = 0
    titik: list[tuple[float, float]] = []  # (recall, precision)
    for benar in tp_flags:
        tp += benar
        fp += 1 - benar
        titik.append((tp / total_gt, tp / (tp + fp)))

    if not titik:
        return 0.0

    # Presisi dibuat monoton menurun dari kanan ke kiri, lalu diintegralkan.
    presisi_maks = 0.0
    halus: list[tuple[float, float]] = []
    for recall, presisi in reversed(titik):
        presisi_maks = max(presisi_maks, presisi)
        halus.append((recall, presisi_maks))
    halus.reverse()

    ap = 0.0
    recall_sebelum = 0.0
    for recall, presisi in halus:
        ap += (recall - recall_sebelum) * presisi
        recall_sebelum = recall
    return ap


def evaluate(
    predictions: list[Prediction],
    ground_truths: list[GroundTruth],
    iou_threshold: float = 0.5,
) -> EvaluationResult:
    """Bandingkan prediksi terhadap ground truth dan hitung metriknya."""
    labels = sorted({g.label for g in ground_truths} | {p.label for p in predictions})
    gambar = {g.image for g in ground_truths} | {p.image for p in predictions}

    confusion: dict[str, dict[str, int]] = {
        aktual: {prediksi: 0 for prediksi in labels + [MISSED]}
        for aktual in labels + [BACKGROUND]
    }

    # Pencocokan agnostik kelas lebih dulu, supaya kesalahan klasifikasi terlihat
    # sebagai salah kelas pada confusion matrix, bukan sekadar "tidak terdeteksi".
    per_kelas_tp: dict[str, list[int]] = {label: [] for label in labels}
    tp_total = fp_total = 0

    for nama in gambar:
        gt_gambar = [g for g in ground_truths if g.image == nama]
        pred_gambar = sorted(
            (p for p in predictions if p.image == nama),
            key=lambda p: -p.confidence,
        )
        terpakai: set[int] = set()

        for prediksi in pred_gambar:
            terbaik = -1
            skor_terbaik = 0.0
            for i, gt in enumerate(gt_gambar):
                if i in terpakai:
                    continue
                skor = iou(prediksi.box, gt.box)
                if skor > skor_terbaik:
                    skor_terbaik, terbaik = skor, i

            cocok = terbaik >= 0 and skor_terbaik >= iou_threshold
            if cocok:
                terpakai.add(terbaik)
                aktual = gt_gambar[terbaik].label
                confusion[aktual][prediksi.label] += 1
                benar = int(aktual == prediksi.label)
            else:
                confusion[BACKGROUND][prediksi.label] += 1
                benar = 0

            per_kelas_tp[prediksi.label].append(benar)
            tp_total += benar
            fp_total += 1 - benar

        for i, gt in enumerate(gt_gambar):
            if i not in terpakai:
                confusion[gt.label][MISSED] += 1

    hasil: list[ClassMetrics] = []
    for label in labels:
        support = sum(1 for g in ground_truths if g.label == label)
        flags = per_kelas_tp[label]
        tp = sum(flags)
        fp = len(flags) - tp
        fn = support - tp

        presisi = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * presisi * recall / (presisi + recall) if (presisi + recall) else 0.0

        hasil.append(
            ClassMetrics(
                label=label,
                support=support,
                predicted=len(flags),
                true_positive=tp,
                false_positive=fp,
                false_negative=max(fn, 0),
                precision=presisi,
                recall=recall,
                f1=f1,
                average_precision=_average_precision(flags, support),
            )
        )

    dengan_gt = [m for m in hasil if m.support > 0]
    map50 = sum(m.average_precision for m in dengan_gt) / len(dengan_gt) if dengan_gt else 0.0

    total_gt = len(ground_truths)
    mikro_presisi = tp_total / (tp_total + fp_total) if (tp_total + fp_total) else 0.0
    mikro_recall = tp_total / total_gt if total_gt else 0.0
    mikro_f1 = (
        2 * mikro_presisi * mikro_recall / (mikro_presisi + mikro_recall)
        if (mikro_presisi + mikro_recall)
        else 0.0
    )

    return EvaluationResult(
        iou_threshold=iou_threshold,
        images=len(gambar),
        per_class=hasil,
        map50=map50,
        micro_precision=mikro_presisi,
        micro_recall=mikro_recall,
        micro_f1=mikro_f1,
        confusion=confusion,
    )
