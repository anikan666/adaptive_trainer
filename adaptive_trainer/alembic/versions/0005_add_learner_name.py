"""add name column to learners table

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("learners", sa.Column("name", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("learners", "name")
