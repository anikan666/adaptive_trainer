"""add curriculum_units, unit_vocabulary, learner_unit_progress tables and unit_id to learner_vocabulary

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "curriculum_units",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("unit_order", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_curriculum_units_level"), "curriculum_units", ["level"])

    op.create_table(
        "unit_vocabulary",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("word", sa.Text(), nullable=False),
        sa.Column("roman", sa.Text(), nullable=False),
        sa.Column("english", sa.Text(), nullable=False),
        sa.Column("usage_example", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["unit_id"], ["curriculum_units.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "learner_unit_progress",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("learner_id", sa.Integer(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["unit_id"], ["curriculum_units.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("learner_id", "unit_id", name="uq_learner_unit"),
    )
    op.create_index(
        op.f("ix_learner_unit_progress_learner_id"), "learner_unit_progress", ["learner_id"]
    )
    op.create_index(
        op.f("ix_learner_unit_progress_unit_id"), "learner_unit_progress", ["unit_id"]
    )

    op.add_column(
        "learner_vocabulary",
        sa.Column("unit_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_learner_vocabulary_unit_id",
        "learner_vocabulary",
        "curriculum_units",
        ["unit_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_learner_vocabulary_unit_id", "learner_vocabulary", type_="foreignkey")
    op.drop_column("learner_vocabulary", "unit_id")

    op.drop_index(
        op.f("ix_learner_unit_progress_unit_id"), table_name="learner_unit_progress"
    )
    op.drop_index(
        op.f("ix_learner_unit_progress_learner_id"), table_name="learner_unit_progress"
    )
    op.drop_table("learner_unit_progress")
    op.drop_table("unit_vocabulary")

    op.drop_index(op.f("ix_curriculum_units_level"), table_name="curriculum_units")
    op.drop_table("curriculum_units")
