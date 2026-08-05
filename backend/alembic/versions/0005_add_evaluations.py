"""Add evaluations table

Menyimpan hasil evaluasi terhadap anotasi ground truth: mAP@50, presisi/recall
per kelas, dan confusion matrix. Ikut mencatat keadaan sistem saat evaluasi
dijalankan (mock atau model sungguhan) supaya angkanya tidak pernah tertukar.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evaluations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("iou_threshold", sa.Float(), nullable=False),
        sa.Column("inference_mode", sa.String(length=16), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("images", sa.Integer(), nullable=False),
        sa.Column("ground_truths", sa.Integer(), nullable=False),
        sa.Column("predictions", sa.Integer(), nullable=False),
        sa.Column("map50", sa.Float(), nullable=False),
        sa.Column("micro_precision", sa.Float(), nullable=False),
        sa.Column("micro_recall", sa.Float(), nullable=False),
        sa.Column("micro_f1", sa.Float(), nullable=False),
        sa.Column("per_class", sa.JSON(), nullable=False),
        sa.Column("confusion", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("evaluations")
