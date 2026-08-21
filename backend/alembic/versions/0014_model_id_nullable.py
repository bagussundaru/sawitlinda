"""model_id boleh kosong sampai checkpoint dipilih

Bobot belum ada saat eksperimen didaftarkan, sementara hipotesis harus sudah
beku sebelum training dimulai. Keduanya hanya dapat dipenuhi bersamaan bila
identitas checkpoint diisi belakangan — tepat saat status maju ke
`ready_for_final_test`.

Revision ID: 0014
Revises: 0013
"""

from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "experiments", "model_id", existing_type=sa.String(64), nullable=True
    )


def downgrade() -> None:
    # Catatan yang checkpoint-nya belum dipilih tidak punya nilai yang sah untuk
    # kolom ini; diberi penanda agar downgrade tidak gagal di tengah jalan.
    op.execute("UPDATE experiments SET model_id = 'pending' WHERE model_id IS NULL")
    op.alter_column(
        "experiments", "model_id", existing_type=sa.String(64), nullable=False
    )
