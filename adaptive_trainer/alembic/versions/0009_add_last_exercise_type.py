"""Add last_exercise_type to learner_vocabulary for production weighting

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "learner_vocabulary",
        sa.Column("last_exercise_type", sa.String(30), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("learner_vocabulary", "last_exercise_type")
