"""add unique constraint to vocabulary_items.word

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-13

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Deduplicate any existing rows before adding the constraint.
    # Keep the row with the lowest id for each word.
    op.execute("""
        DELETE FROM vocabulary_items
        WHERE id NOT IN (
            SELECT MIN(id) FROM vocabulary_items GROUP BY word
        )
    """)
    op.create_unique_constraint("uq_vocabulary_items_word", "vocabulary_items", ["word"])


def downgrade() -> None:
    op.drop_constraint("uq_vocabulary_items_word", "vocabulary_items", type_="unique")
