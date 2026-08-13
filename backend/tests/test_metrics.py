"""Tes inti matematis modul evaluasi.

Angka yang diharapkan dihitung tangan, bukan disalin dari keluaran program —
kalau tidak, tes hanya mengunci perilaku yang mungkin salah sejak awal.
"""

import pytest

from app.evaluation.metrics import (
    BACKGROUND,
    MISSED,
    GroundTruth,
    Prediction,
    evaluate,
    iou,
)


class TestIoU:
    def test_kotak_identik_bernilai_satu(self):
        assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0

    def test_kotak_terpisah_bernilai_nol(self):
        assert iou((0, 0, 10, 10), (20, 20, 10, 10)) == 0.0

    def test_bersentuhan_di_tepi_bernilai_nol(self):
        assert iou((0, 0, 10, 10), (10, 0, 10, 10)) == 0.0

    def test_tumpang_tindih_separuh(self):
        # Irisan 5x10=50; gabungan 100+100-50=150.
        assert iou((0, 0, 10, 10), (5, 0, 10, 10)) == pytest.approx(50 / 150)

    def test_kotak_di_dalam_kotak(self):
        # Irisan 25; gabungan 100.
        assert iou((0, 0, 10, 10), (0, 0, 5, 5)) == pytest.approx(0.25)

    def test_lebar_nol_bernilai_nol(self):
        assert iou((0, 0, 0, 10), (0, 0, 10, 10)) == 0.0


class TestPencocokan:
    def test_deteksi_sempurna(self):
        gt = [GroundTruth((0, 0, 10, 10), "Healthy", "a")]
        pred = [Prediction((0, 0, 10, 10), "Healthy", 0.9, "a")]

        hasil = evaluate(pred, gt)

        assert hasil.map50 == pytest.approx(1.0)
        assert hasil.micro_precision == 1.0
        assert hasil.micro_recall == 1.0
        sehat = hasil.per_class[0]
        assert (sehat.true_positive, sehat.false_positive, sehat.false_negative) == (1, 0, 0)

    def test_satu_ground_truth_hanya_dipasangkan_sekali(self):
        """Prediksi kedua di kotak yang sama adalah positif palsu, bukan bonus."""
        gt = [GroundTruth((0, 0, 10, 10), "Healthy", "a")]
        pred = [
            Prediction((0, 0, 10, 10), "Healthy", 0.9, "a"),
            Prediction((1, 1, 10, 10), "Healthy", 0.8, "a"),
        ]

        sehat = evaluate(pred, gt).per_class[0]

        assert sehat.true_positive == 1
        assert sehat.false_positive == 1

    def test_iou_di_bawah_ambang_tidak_dicocokkan(self):
        gt = [GroundTruth((0, 0, 10, 10), "Healthy", "a")]
        # Irisan 2x10=20; gabungan 180 -> IoU 0,111 < 0,5.
        pred = [Prediction((8, 0, 10, 10), "Healthy", 0.9, "a")]

        hasil = evaluate(pred, gt)

        assert hasil.per_class[0].true_positive == 0
        assert hasil.confusion[BACKGROUND]["Healthy"] == 1
        assert hasil.confusion["Healthy"][MISSED] == 1

    def test_pencocokan_tidak_melintasi_citra(self):
        gt = [GroundTruth((0, 0, 10, 10), "Healthy", "a")]
        pred = [Prediction((0, 0, 10, 10), "Healthy", 0.9, "b")]

        hasil = evaluate(pred, gt)

        assert hasil.per_class[0].true_positive == 0
        assert hasil.images == 2

    def test_kotak_bertumpang_dipasangkan_ke_yang_iou_terbesar(self):
        gt = [
            GroundTruth((0, 0, 10, 10), "Healthy", "a"),
            GroundTruth((6, 0, 10, 10), "Yellowing", "a"),
        ]
        pred = [Prediction((6, 0, 10, 10), "Yellowing", 0.9, "a")]

        hasil = evaluate(pred, gt)

        menguning = next(m for m in hasil.per_class if m.label == "Yellowing")
        assert menguning.true_positive == 1


class TestSalahKelas:
    def test_kotak_benar_kelas_salah_tercatat_di_confusion(self):
        gt = [GroundTruth((0, 0, 10, 10), "Yellowing", "a")]
        pred = [Prediction((0, 0, 10, 10), "Stunted", 0.9, "a")]

        hasil = evaluate(pred, gt)

        # Terlihat sebagai kekeliruan kelas, bukan sebagai objek yang terlewat.
        assert hasil.confusion["Yellowing"]["Stunted"] == 1
        assert hasil.confusion["Yellowing"][MISSED] == 0

        menguning = next(m for m in hasil.per_class if m.label == "Yellowing")
        kerdil = next(m for m in hasil.per_class if m.label == "Stunted")
        assert menguning.false_negative == 1
        assert kerdil.false_positive == 1
        assert hasil.micro_precision == 0.0


class TestAveragePrecision:
    def test_ap_satu_saat_semua_benar(self):
        gt = [GroundTruth((i * 100, 0, 10, 10), "Healthy", "a") for i in range(4)]
        pred = [
            Prediction((i * 100, 0, 10, 10), "Healthy", 0.9 - i * 0.1, "a") for i in range(4)
        ]

        assert evaluate(pred, gt).per_class[0].average_precision == pytest.approx(1.0)

    def test_ap_nol_tanpa_prediksi(self):
        gt = [GroundTruth((0, 0, 10, 10), "Healthy", "a")]

        hasil = evaluate([], gt)

        assert hasil.per_class[0].average_precision == 0.0
        assert hasil.per_class[0].false_negative == 1
        assert hasil.micro_recall == 0.0

    def test_urutan_confidence_mempengaruhi_ap(self):
        """Positif palsu berkeyakinan tinggi lebih merugikan daripada yang rendah."""
        gt = [GroundTruth((0, 0, 10, 10), "Healthy", "a")]

        salah_dulu = evaluate(
            [
                Prediction((500, 500, 10, 10), "Healthy", 0.95, "a"),
                Prediction((0, 0, 10, 10), "Healthy", 0.5, "a"),
            ],
            gt,
        )
        benar_dulu = evaluate(
            [
                Prediction((0, 0, 10, 10), "Healthy", 0.95, "a"),
                Prediction((500, 500, 10, 10), "Healthy", 0.5, "a"),
            ],
            gt,
        )

        assert benar_dulu.per_class[0].average_precision == pytest.approx(1.0)
        assert salah_dulu.per_class[0].average_precision == pytest.approx(0.5)

    def test_ap_dihitung_tangan_untuk_kasus_campuran(self):
        """2 ground truth, 3 prediksi urut: benar, salah, benar.

        Titik (recall, presisi): (0,5 · 1,0), (0,5 · 0,5), (1,0 · 0,667).
        Setelah presisi dibuat monoton: (0,5 · 1,0), (0,5 · 0,667), (1,0 · 0,667).
        AP = 0,5·1,0 + 0,0·0,667 + 0,5·0,667 = 0,8333.
        """
        gt = [
            GroundTruth((0, 0, 10, 10), "Healthy", "a"),
            GroundTruth((100, 0, 10, 10), "Healthy", "a"),
        ]
        pred = [
            Prediction((0, 0, 10, 10), "Healthy", 0.9, "a"),
            Prediction((500, 500, 10, 10), "Healthy", 0.8, "a"),
            Prediction((100, 0, 10, 10), "Healthy", 0.7, "a"),
        ]

        ap = evaluate(pred, gt).per_class[0].average_precision

        assert ap == pytest.approx(0.5 + 0.5 * (2 / 3), abs=1e-6)


class TestAgregat:
    def test_map_hanya_merata_ratakan_kelas_yang_punya_ground_truth(self):
        """Kelas yang tidak pernah muncul di ground truth tidak menyeret mAP."""
        gt = [GroundTruth((0, 0, 10, 10), "Healthy", "a")]
        pred = [
            Prediction((0, 0, 10, 10), "Healthy", 0.9, "a"),
            Prediction((900, 900, 10, 10), "Stunted", 0.4, "a"),
        ]

        hasil = evaluate(pred, gt)

        assert hasil.map50 == pytest.approx(1.0)
        assert any(m.label == "Stunted" and m.support == 0 for m in hasil.per_class)

    def test_micro_f1_konsisten_dengan_presisi_dan_recall(self):
        gt = [GroundTruth((i * 100, 0, 10, 10), "Healthy", "a") for i in range(4)]
        pred = [
            Prediction((0, 0, 10, 10), "Healthy", 0.9, "a"),
            Prediction((100, 0, 10, 10), "Healthy", 0.8, "a"),
            Prediction((900, 900, 10, 10), "Healthy", 0.7, "a"),
        ]

        hasil = evaluate(pred, gt)

        assert hasil.micro_precision == pytest.approx(2 / 3)
        assert hasil.micro_recall == pytest.approx(0.5)
        assert hasil.micro_f1 == pytest.approx(2 * (2 / 3) * 0.5 / ((2 / 3) + 0.5))

    def test_masukan_kosong_tidak_meledak(self):
        hasil = evaluate([], [])

        assert hasil.map50 == 0.0
        assert hasil.per_class == []
        assert hasil.images == 0

    def test_ambang_iou_dapat_diatur(self):
        gt = [GroundTruth((0, 0, 10, 10), "Healthy", "a")]
        pred = [Prediction((3, 0, 10, 10), "Healthy", 0.9, "a")]  # IoU = 70/130 = 0,538

        assert evaluate(pred, gt, iou_threshold=0.5).per_class[0].true_positive == 1
        assert evaluate(pred, gt, iou_threshold=0.75).per_class[0].true_positive == 0
