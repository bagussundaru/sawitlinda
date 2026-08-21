"""Siklus status eksperimen.

Revision ID: 0013
Revises: 0012
"""

from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "experiments",
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
    )
    op.create_index("ix_experiments_status", "experiments", ["status"])
    # Catatan lama yang sudah punya hasil berarti sudah selesai diuji.
    op.execute("UPDATE experiments SET status = 'final_tested' WHERE metrics IS NOT NULL")


def downgrade() -> None:
    op.drop_index("ix_experiments_status", table_name="experiments")
    op.drop_column("experiments", "status")
