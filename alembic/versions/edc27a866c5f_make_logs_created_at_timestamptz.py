"""make logs created_at timestamptz

Revision ID: edc27a866c5f
Revises: 8c89070c4905
Create Date: 2026-04-10 10:23:26.515769

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'edc27a866c5f'
down_revision: Union[str, Sequence[str], None] = '8c89070c4905'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "logs",
        "created_at",
        existing_type=sa.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
        postgresql_using="created_at AT TIME ZONE 'UTC'",  # use UTC if old data is UTC
    )
    pass


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "logs",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.TIMESTAMP(),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    pass
