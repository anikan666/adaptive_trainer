"""Add unique constraint on learner_vocabulary(learner_id, vocabulary_item_id)

Revision ID: 0011
Revises: 0010
Create Date: 2026-03-14

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Deduplicate any existing rows before adding constraint.
    # Keep the row with the highest id (most recent) for each pair.
    op.execute("""
        DELETE FROM learner_vocabulary a
        USING learner_vocabulary b
        WHERE a.learner_id = b.learner_id
          AND a.vocabulary_item_id = b.vocabulary_item_id
          AND a.id < b.id
    """)
    op.create_unique_constraint(
        "uq_learner_vocab_item",
        "learner_vocabulary",
        ["learner_id", "vocabulary_item_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_learner_vocab_item", "learner_vocabulary", type_="unique")
