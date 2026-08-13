"""Desa asal citra, untuk pengelompokan pada peta.

Revision ID: 0009
Revises: 0008
"""

from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("images", sa.Column("village", sa.String(64)))
    op.create_index("ix_images_village", "images", ["village"])


def downgrade() -> None:
    op.drop_index("ix_images_village", table_name="images")
    op.drop_column("images", "village")
