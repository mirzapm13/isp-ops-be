"""create payment_receipt_logs table

Revision ID: a9f182c3d4e5
Revises: 7db52d20e98a
Create Date: 2026-09-02 00:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a9f182c3d4e5"
down_revision: Union[str, Sequence[str], None] = "7db52d20e98a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_receipt_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("id_pelanggan", sa.String(length=50), nullable=False),
        sa.Column("nama_pelanggan", sa.String(length=255), nullable=True),
        sa.Column("phone_number", sa.String(length=50), nullable=False),
        sa.Column("billing_period", sa.String(length=20), nullable=False),
        sa.Column("receipt_url", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'PENDING'"),
            nullable=False,
        ),
        sa.Column("qiscus_response", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id_pelanggan",
            "billing_period",
            name="uq_payment_receipt_log_pelanggan_period",
        ),
    )
    op.create_index(
        "idx_payment_receipt_logs_id_pelanggan",
        "payment_receipt_logs",
        ["id_pelanggan"],
        unique=False,
    )
    op.create_index(
        "idx_payment_receipt_logs_billing_period",
        "payment_receipt_logs",
        ["billing_period"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_payment_receipt_logs_billing_period",
        table_name="payment_receipt_logs",
    )
    op.drop_index(
        "idx_payment_receipt_logs_id_pelanggan",
        table_name="payment_receipt_logs",
    )
    op.drop_table("payment_receipt_logs")
