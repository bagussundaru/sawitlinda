"""Rename detections.disease to detections.condition

Kelas yang dihasilkan model adalah kondisi tanaman (sehat, daun menguning, pohon
mati, pertumbuhan kerdil), bukan diagnosis penyakit. Nama kolom disesuaikan agar
istilah di database, API, dan UI konsisten.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-02
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("detections", "disease", new_column_name="condition")


def downgrade() -> None:
    op.alter_column("detections", "condition", new_column_name="disease")
