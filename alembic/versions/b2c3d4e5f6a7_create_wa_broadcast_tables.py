"""create wa_broadcast_runs and wa_broadcast_logs tables

Revision ID: b2c3d4e5f6a7
Revises: a9f182c3d4e5
Create Date: 2026-10-26 12:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a9f182c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wa_broadcast_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("template_name", sa.String(length=100), nullable=False),
        sa.Column("namespace", sa.String(length=150), nullable=False),
        sa.Column(
            "language_code",
            sa.String(length=20),
            server_default=sa.text("'id'"),
            nullable=False,
        ),
        sa.Column(
            "dry_run",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "delay_seconds",
            sa.Float(),
            server_default=sa.text("1.0"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default=sa.text("'RUNNING'"),
            nullable=False,
        ),
        sa.Column(
            "stop_requested",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "total",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "processed",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "success",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "failed",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_wa_broadcast_runs_status",
        "wa_broadcast_runs",
        ["status"],
        unique=False,
    )

    op.create_table(
        "wa_broadcast_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("excel_row", sa.Integer(), nullable=False),
        sa.Column("id_pelanggan", sa.String(length=100), nullable=True),
        sa.Column("nama_pelanggan", sa.String(length=255), nullable=True),
        sa.Column("phone_number", sa.String(length=50), nullable=False),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default=sa.text("'PENDING'"),
            nullable=False,
        ),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("message_id", sa.String(length=150), nullable=True),
        sa.Column("wa_id", sa.String(length=100), nullable=True),
        sa.Column("qiscus_payload", sa.Text(), nullable=True),
        sa.Column("qiscus_response", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["wa_broadcast_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_wa_broadcast_logs_run_id",
        "wa_broadcast_logs",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        "idx_wa_broadcast_logs_id_pelanggan",
        "wa_broadcast_logs",
        ["id_pelanggan"],
        unique=False,
    )
    op.create_index(
        "idx_wa_broadcast_logs_phone_number",
        "wa_broadcast_logs",
        ["phone_number"],
        unique=False,
    )
    op.create_index(
        "idx_wa_broadcast_logs_status",
        "wa_broadcast_logs",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_wa_broadcast_logs_status", table_name="wa_broadcast_logs")
    op.drop_index("idx_wa_broadcast_logs_phone_number", table_name="wa_broadcast_logs")
    op.drop_index("idx_wa_broadcast_logs_id_pelanggan", table_name="wa_broadcast_logs")
    op.drop_index("idx_wa_broadcast_logs_run_id", table_name="wa_broadcast_logs")
    op.drop_table("wa_broadcast_logs")

    op.drop_index("idx_wa_broadcast_runs_status", table_name="wa_broadcast_runs")
    op.drop_table("wa_broadcast_runs")
