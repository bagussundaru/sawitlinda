"""Build CSV and PDF reports from a detection result.

These take the API schema (not ORM objects) as input, so a report is always built
from exactly the payload the frontend showed the user.
"""

import csv
import io
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app import schemas

CSV_HEADERS = [
    "no",
    "nama_berkas",
    "waktu_pemotretan",
    "penyakit",
    "keparahan",
    "kepercayaan",
    "bbox_x",
    "bbox_y",
    "bbox_lebar",
    "bbox_tinggi",
    "lintang",
    "bujur",
]

SEVERITY_COLORS = {
    "sehat": colors.HexColor("#2e7d32"),
    "ringan": colors.HexColor("#f9a825"),
    "sedang": colors.HexColor("#ef6c00"),
    "berat": colors.HexColor("#c62828"),
}


def _format_time(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if value else "-"


def to_csv(result: schemas.DetectionResult) -> bytes:
    """One row per detected tree. UTF-8 BOM so Excel opens it correctly."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_HEADERS)

    captured = _format_time(result.captured_at)
    for index, detection in enumerate(result.detections, start=1):
        x, y, w, h = detection.bbox
        writer.writerow(
            [
                index,
                result.filename,
                captured,
                detection.disease,
                detection.severity,
                f"{detection.confidence:.2f}",
                x,
                y,
                w,
                h,
                detection.gps.lat if detection.gps else "",
                detection.gps.lng if detection.gps else "",
            ]
        )

    return buffer.getvalue().encode("utf-8-sig")


def _summary_table(result: schemas.DetectionResult) -> Table:
    summary = result.summary
    table = Table(
        [
            ["Total pohon", "Sehat", "Terinfeksi", "Keparahan berat"],
            [summary.total, summary.healthy, summary.infected, summary.severe],
        ],
        colWidths=[42 * mm] * 4,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eceff1")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 1), (-1, 1), 16),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#b0bec5")),
                ("TOPPADDING", (0, 1), (-1, 1), 8),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
                ("TEXTCOLOR", (2, 1), (2, 1), SEVERITY_COLORS["sedang"]),
                ("TEXTCOLOR", (3, 1), (3, 1), SEVERITY_COLORS["berat"]),
                ("TEXTCOLOR", (1, 1), (1, 1), SEVERITY_COLORS["sehat"]),
            ]
        )
    )
    return table


def _detection_table(result: schemas.DetectionResult) -> Table:
    rows = [["No", "Penyakit", "Keparahan", "Kepercayaan", "Koordinat"]]
    severity_rows: list[tuple[int, str]] = []

    for index, detection in enumerate(result.detections, start=1):
        coordinate = (
            f"{detection.gps.lat:.5f}, {detection.gps.lng:.5f}" if detection.gps else "-"
        )
        rows.append(
            [
                str(index),
                detection.disease,
                detection.severity,
                f"{detection.confidence:.0%}",
                coordinate,
            ]
        )
        severity_rows.append((index, detection.severity))

    table = Table(
        rows,
        colWidths=[12 * mm, 62 * mm, 24 * mm, 26 * mm, 44 * mm],
        repeatRows=1,
    )
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eceff1")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cfd8dc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for row_index, severity in severity_rows:
        style.append(("TEXTCOLOR", (2, row_index), (2, row_index), SEVERITY_COLORS[severity]))
    table.setStyle(TableStyle(style))
    return table


def to_pdf(result: schemas.DetectionResult) -> bytes:
    """A one-file report: header, summary figures, then every detection."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=f"Laporan Deteksi — {result.filename}",
        author="SawitScan AI",
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    styles = getSampleStyleSheet()

    location = (
        f"{result.gps.lat:.5f}, {result.gps.lng:.5f}" if result.gps else "tidak tersedia"
    )
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    story = [
        Paragraph("Laporan Deteksi Penyakit Kelapa Sawit", styles["Title"]),
        Spacer(1, 4 * mm),
        Paragraph(f"<b>Berkas:</b> {result.filename}", styles["Normal"]),
        Paragraph(
            f"<b>Waktu pemotretan:</b> {_format_time(result.captured_at)}", styles["Normal"]
        ),
        Paragraph(f"<b>Lokasi citra:</b> {location}", styles["Normal"]),
        Paragraph(f"<b>Laporan dibuat:</b> {generated}", styles["Normal"]),
        Spacer(1, 6 * mm),
        _summary_table(result),
        Spacer(1, 8 * mm),
        Paragraph("Rincian temuan", styles["Heading2"]),
        Spacer(1, 2 * mm),
    ]

    if result.detections:
        story.append(_detection_table(result))
    else:
        story.append(Paragraph("Tidak ada pohon terdeteksi pada citra ini.", styles["Normal"]))

    story += [
        Spacer(1, 8 * mm),
        Paragraph(
            "<i>Hasil deteksi bersifat bantuan dan perlu diverifikasi di lapangan.</i>",
            styles["Normal"],
        ),
    ]

    doc.build(story)
    return buffer.getvalue()
