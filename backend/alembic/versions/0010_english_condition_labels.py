"""Label kondisi pada deteksi lama ikut berbahasa Inggris.

Antarmuka diubah ke Bahasa Inggris atas permintaan klien. Kolom
`detections.condition` menyimpan LABEL yang ditampilkan, bukan kunci kelasnya,
sehingga baris lama tetap berbahasa Indonesia sementara baris baru berbahasa
Inggris — dan agregat per kondisi akan terbelah menjadi dua kelompok untuk
kondisi yang sama.

CATATAN RANCANGAN: menyimpan label tampilan di database adalah akar masalahnya.
Menyimpan `key` ("healthy", "yellow", …) dan menerjemahkan saat ditampilkan akan
membuat perubahan bahasa tidak pernah menyentuh data sama sekali. Perubahan itu
menyentuh mapper, evaluasi, ekspor, dan lapisan AI sekaligus, jadi dicatat di
sini sebagai pekerjaan tersendiri.

Revision ID: 0010
Revises: 0009
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

#: Label lama -> label baru. Harus sama persis dengan app/inference/conditions.py.
PETA = {
    "Sehat": "Healthy",
    "Menguning": "Yellowing",
    "Mati/stres": "Dead / stressed",
    "Kerdil": "Stunted",
}


def upgrade() -> None:
    for lama, baru in PETA.items():
        op.execute(
            f"UPDATE detections SET condition = '{baru}' WHERE condition = '{lama}'"
        )
    # Penilaian AI tingkat citra menyimpan label yang sama.
    for lama, baru in PETA.items():
        op.execute(
            "UPDATE images SET ai_dominant_condition = "
            f"'{baru}' WHERE ai_dominant_condition = '{lama}'"
        )


def downgrade() -> None:
    for lama, baru in PETA.items():
        op.execute(
            f"UPDATE detections SET condition = '{lama}' WHERE condition = '{baru}'"
        )
    for lama, baru in PETA.items():
        op.execute(
            "UPDATE images SET ai_dominant_condition = "
            f"'{lama}' WHERE ai_dominant_condition = '{baru}'"
        )
