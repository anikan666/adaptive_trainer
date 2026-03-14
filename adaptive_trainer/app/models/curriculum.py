from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class CurriculumUnit(Base):
    __tablename__ = "curriculum_units"
    __table_args__ = (
        CheckConstraint("ring >= 0 AND ring <= 4", name="curriculum_unit_ring_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ring: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    unit_order: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class UnitVocabulary(Base):
    __tablename__ = "unit_vocabulary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("curriculum_units.id", ondelete="CASCADE"), nullable=False
    )
    word: Mapped[str] = mapped_column(Text, nullable=False)
    roman: Mapped[str] = mapped_column(Text, nullable=False)
    english: Mapped[str] = mapped_column(Text, nullable=False)
    usage_example: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True, server_default="{}")
    grammar_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    usage_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_atoms: Mapped[list[int] | None] = mapped_column(ARRAY(Integer), nullable=True)


class LearnerUnitProgress(Base):
    __tablename__ = "learner_unit_progress"
    __table_args__ = (
        UniqueConstraint("learner_id", "unit_id", name="uq_learner_unit"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    learner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("learners.id", ondelete="CASCADE"), nullable=False, index=True
    )
    unit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("curriculum_units.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
