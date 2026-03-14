"""Add streak tracking columns to learners table

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "learners",
        sa.Column("last_session_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "learners",
        sa.Column("current_streak", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("learners", "current_streak")
    op.drop_column("learners", "last_session_date")
