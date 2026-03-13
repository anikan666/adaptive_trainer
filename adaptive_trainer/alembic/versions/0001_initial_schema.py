"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "learners",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("phone_number", sa.String(20), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("level >= 1 AND level <= 5", name="learner_level_range"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone_number"),
    )
    op.create_index(op.f("ix_learners_phone_number"), "learners", ["phone_number"])

    op.create_table(
        "vocabulary_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("word", sa.Text(), nullable=False),
        sa.Column("translations", postgresql.JSONB(), nullable=False),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "learner_vocabulary",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("learner_id", sa.Integer(), nullable=False),
        sa.Column("vocabulary_item_id", sa.Integer(), nullable=False),
        sa.Column("ease_factor", sa.Float(), nullable=False, server_default="2.5"),
        sa.Column("interval", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("repetitions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["vocabulary_item_id"], ["vocabulary_items.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_learner_vocabulary_learner_id"), "learner_vocabulary", ["learner_id"]
    )
    op.create_index(
        op.f("ix_learner_vocabulary_vocabulary_item_id"),
        "learner_vocabulary",
        ["vocabulary_item_id"],
    )


    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("phone_number", sa.String(20), nullable=False),
        sa.Column(
            "mode",
            sa.Enum("lesson", "quick_lookup", "onboarding", name="conversation_mode", create_type=True),
            nullable=False,
        ),
        sa.Column("lesson_context", postgresql.JSONB(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_conversations_phone_number"), "conversations", ["phone_number"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_conversations_phone_number"), table_name="conversations")
    op.drop_table("conversations")
    op.execute("DROP TYPE conversation_mode")

    op.drop_index(
        op.f("ix_learner_vocabulary_vocabulary_item_id"), table_name="learner_vocabulary"
    )
    op.drop_index(
        op.f("ix_learner_vocabulary_learner_id"), table_name="learner_vocabulary"
    )
    op.drop_table("learner_vocabulary")
    op.drop_table("vocabulary_items")

    op.drop_index(op.f("ix_learners_phone_number"), table_name="learners")
    op.drop_table("learners")
