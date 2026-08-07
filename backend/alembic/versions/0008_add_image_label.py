"""Label per citra, menggantikan peran blok kebun.

Konsep aplikasi bergeser: tidak lagi memetakan sebaran secara geografis,
melainkan memindai citra yang diberi nama sendiri oleh pengunggah.

Kolom `block`, `area_ha`, dan koordinat SENGAJA tidak dihapus. Data yang sudah
terkumpul tetap utuh, dan menghidupkan kembali fitur peta di kemudian hari tidak
memerlukan pemulihan data — hanya menampilkannya lagi.

Revision ID: 0008
Revises: 0007
"""

from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("images", sa.Column("label", sa.String(200)))
    op.create_index("ix_images_label", "images", ["label"])

    # Citra yang sudah ada diberi label dari data yang tersedia, supaya tidak ada
    # baris tanpa nama setelah tampilan berganti ke label.
    op.execute(
        """
        UPDATE images
        SET label = CASE
            WHEN block IS NOT NULL AND block <> '' THEN block || ' · ' || filename
            ELSE filename
        END
        WHERE label IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_images_label", table_name="images")
    op.drop_column("images", "label")
