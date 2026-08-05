"""Add app_settings table

Menyimpan pengaturan yang diubah saat aplikasi berjalan, mis. kunci API Nebius
yang diisi lewat layar Pengaturan. Nilai seperti itu tidak boleh masuk
repositori maupun berkas .env yang di-commit.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
