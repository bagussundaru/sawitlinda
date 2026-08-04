"""Add AI image-level assessment columns

Penilaian tingkat citra dari model vision (Nebius). Seluruh kolom nullable karena
fitur ini opsional — tanpa NEBIUS_API_KEY aplikasi tetap berjalan penuh.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = [
    ("ai_summary", sa.Text()),
    ("ai_recommendation", sa.Text()),
    ("ai_dominant_condition", sa.String(length=128)),
    ("ai_confidence", sa.Float()),
    ("ai_affected_share", sa.Float()),
    ("ai_notes", sa.Text()),
    ("ai_model", sa.String(length=128)),
    ("ai_created_at", sa.DateTime(timezone=True)),
]


def upgrade() -> None:
    for name, type_ in COLUMNS:
        op.add_column("images", sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    for name, _ in reversed(COLUMNS):
        op.drop_column("images", name)
