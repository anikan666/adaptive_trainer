"""add review to conversation_mode enum

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-13

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE conversation_mode ADD VALUE IF NOT EXISTS 'review'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; this is intentionally a no-op.
    pass
