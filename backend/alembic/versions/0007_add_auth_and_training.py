"""Autentikasi (users, sessions) dan riwayat training.

Revision ID: 0007
Revises: 0006
"""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("username", sa.String(64), primary_key=True),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("full_name", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column(
            "username",
            sa.String(64),
            sa.ForeignKey("users.username", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_username", "sessions", ["username"])
    # Sesi kedaluwarsa dibersihkan tiap kali sesi baru dibuat; tanpa indeks,
    # pembersihan itu memindai seluruh tabel.
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])

    op.create_table(
        "training_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.String(64), nullable=False, unique=True),
        sa.Column("run_name", sa.String(128), nullable=False),
        sa.Column("base_model", sa.String(64), nullable=False),
        sa.Column("epochs", sa.Integer(), nullable=False),
        sa.Column("dataset_filename", sa.String(255)),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("started_by", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("final_map50", sa.Float()),
        sa.Column("final_map50_95", sa.Float()),
        sa.Column("last_epoch", sa.Integer()),
        sa.Column("error", sa.Text()),
        sa.Column("weights_path", sa.String(512)),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_training_runs_job_id", "training_runs", ["job_id"], unique=True)
    op.create_index("ix_training_runs_status", "training_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_training_runs_status", table_name="training_runs")
    op.drop_index("ix_training_runs_job_id", table_name="training_runs")
    op.drop_table("training_runs")
    op.drop_index("ix_sessions_expires_at", table_name="sessions")
    op.drop_index("ix_sessions_username", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")
