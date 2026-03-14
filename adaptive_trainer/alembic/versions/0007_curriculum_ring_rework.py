"""Curriculum models rework: rename level to ring, enrich atoms, add current_ring to learner

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- CurriculumUnit: rename level -> ring ---
    op.alter_column("curriculum_units", "level", new_column_name="ring")
    op.drop_index("ix_curriculum_units_level", table_name="curriculum_units")
    op.create_index(op.f("ix_curriculum_units_ring"), "curriculum_units", ["ring"])
    op.create_check_constraint(
        "curriculum_unit_ring_range", "curriculum_units", "ring >= 0 AND ring <= 4"
    )
    # Shift existing level values to 0-based rings (level 1 -> ring 0, etc.)
    op.execute("UPDATE curriculum_units SET ring = ring - 1 WHERE ring > 0")

    # --- UnitVocabulary: add enrichment columns ---
    op.add_column(
        "unit_vocabulary",
        sa.Column("tags", sa.ARRAY(sa.String()), nullable=True, server_default="{}"),
    )
    op.add_column(
        "unit_vocabulary",
        sa.Column("grammar_note", sa.Text(), nullable=True),
    )
    op.add_column(
        "unit_vocabulary",
        sa.Column("usage_context", sa.Text(), nullable=True),
    )
    op.add_column(
        "unit_vocabulary",
        sa.Column("related_atoms", sa.ARRAY(sa.Integer()), nullable=True),
    )

    # --- Learner: add current_ring ---
    op.add_column(
        "learners",
        sa.Column("current_ring", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "learner_ring_range", "learners", "current_ring >= 0 AND current_ring <= 4"
    )


def downgrade() -> None:
    # --- Learner: remove current_ring ---
    op.drop_constraint("learner_ring_range", "learners", type_="check")
    op.drop_column("learners", "current_ring")

    # --- UnitVocabulary: remove enrichment columns ---
    op.drop_column("unit_vocabulary", "related_atoms")
    op.drop_column("unit_vocabulary", "usage_context")
    op.drop_column("unit_vocabulary", "grammar_note")
    op.drop_column("unit_vocabulary", "tags")

    # --- CurriculumUnit: rename ring -> level ---
    # Shift ring values back to 1-based levels
    op.execute("UPDATE curriculum_units SET ring = ring + 1")
    op.drop_constraint("curriculum_unit_ring_range", "curriculum_units", type_="check")
    op.drop_index(op.f("ix_curriculum_units_ring"), table_name="curriculum_units")
    op.alter_column("curriculum_units", "ring", new_column_name="level")
    op.create_index("ix_curriculum_units_level", "curriculum_units", ["level"])
