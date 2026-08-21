"""Catatan eksperimen yang tidak dapat diubah.

Revision ID: 0012
Revises: 0011
"""

from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "experiments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("experiment_id", sa.String(64), nullable=False, unique=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("model_id", sa.String(64), nullable=False),
        sa.Column("model_name", sa.String(128)),
        sa.Column("dataset_name", sa.String(128), nullable=False),
        sa.Column("dataset_test_hash", sa.String(64), nullable=False),
        sa.Column("dataset_val_hash", sa.String(64)),
        sa.Column("hypothesis", sa.Text()),
        sa.Column("training_config", sa.JSON(), nullable=False),
        sa.Column("git_commit", sa.String(64)),
        sa.Column("metrics", sa.JSON()),
        sa.Column("results_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_experiments_experiment_id", "experiments", ["experiment_id"], unique=True)
    op.create_index("ix_experiments_kind", "experiments", ["kind"])
    # Penjagaan test-set memeriksa pasangan ini pada setiap pencatatan.
    op.create_index("ix_experiments_model_test", "experiments", ["model_id", "dataset_test_hash"])


def downgrade() -> None:
    op.drop_index("ix_experiments_model_test", table_name="experiments")
    op.drop_index("ix_experiments_kind", table_name="experiments")
    op.drop_index("ix_experiments_experiment_id", table_name="experiments")
    op.drop_table("experiments")
