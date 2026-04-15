"""create payment_reconcile_bmt table

Revision ID: 7db52d20e98a
Revises: edc27a866c5f
Create Date: 2026-04-15 10:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "7db52d20e98a"
down_revision: Union[str, Sequence[str], None] = "edc27a866c5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_reconcile_bmt",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payment_fingerprint", sa.Text(), nullable=False),
        sa.Column("id_pelanggan", sa.String(length=50), nullable=False),
        sa.Column("ket", sa.Text(), nullable=True),
        sa.Column("dracc", sa.String(length=50), nullable=True),
        sa.Column("nominalrp", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("tgltrn", sa.String(length=20), nullable=True),
        sa.Column("trnuser", sa.String(length=100), nullable=True),
        sa.Column("batch", sa.Integer(), nullable=True),
        sa.Column("notrn", sa.Integer(), nullable=True),
        sa.Column("inptgl", sa.String(length=30), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "processed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=True,
        ),
        sa.Column("processed_error", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "uq_payment_reconcile_bmt_fingerprint",
        "payment_reconcile_bmt",
        ["payment_fingerprint"],
        unique=True,
    )
    op.create_index(
        "idx_payment_reconcile_bmt_processed_at",
        "payment_reconcile_bmt",
        ["processed_at"],
        unique=False,
    )
    op.create_index(
        "idx_payment_reconcile_bmt_id_pelanggan",
        "payment_reconcile_bmt",
        ["id_pelanggan"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_payment_reconcile_bmt_id_pelanggan",
        table_name="payment_reconcile_bmt",
    )
    op.drop_index(
        "idx_payment_reconcile_bmt_processed_at",
        table_name="payment_reconcile_bmt",
    )
    op.drop_index(
        "uq_payment_reconcile_bmt_fingerprint",
        table_name="payment_reconcile_bmt",
    )
    op.drop_table("payment_reconcile_bmt")
