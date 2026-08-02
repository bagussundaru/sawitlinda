"""Add plantation block and covered area to images

Blok kebun dan luas area tidak dapat disimpulkan dari citra maupun metadatanya,
jadi keduanya diisi operator saat mengunggah. Nullable agar citra lama tetap sah.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("images", sa.Column("block", sa.String(length=64), nullable=True))
    op.add_column("images", sa.Column("area_ha", sa.Float(), nullable=True))
    op.create_index("ix_images_block", "images", ["block"])


def downgrade() -> None:
    op.drop_index("ix_images_block", table_name="images")
    op.drop_column("images", "area_ha")
    op.drop_column("images", "block")
