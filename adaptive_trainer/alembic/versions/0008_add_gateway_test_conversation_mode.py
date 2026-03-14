"""add gateway_test to conversation_mode enum

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-14

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE conversation_mode ADD VALUE IF NOT EXISTS 'gateway_test'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; this is intentionally a no-op.
    pass
