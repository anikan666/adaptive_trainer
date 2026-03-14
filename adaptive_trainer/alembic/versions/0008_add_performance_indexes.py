"""Add performance indexes on LearnerVocabulary.due_date, Conversation.updated_at, SessionRecord.created_at

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
    op.create_index(
        op.f("ix_learner_vocabulary_due_date"),
        "learner_vocabulary",
        ["due_date"],
    )
    op.create_index(
        op.f("ix_conversations_updated_at"),
        "conversations",
        ["updated_at"],
    )
    op.create_index(
        op.f("ix_session_records_created_at"),
        "session_records",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_session_records_created_at"), table_name="session_records")
    op.drop_index(op.f("ix_conversations_updated_at"), table_name="conversations")
    op.drop_index(op.f("ix_learner_vocabulary_due_date"), table_name="learner_vocabulary")
