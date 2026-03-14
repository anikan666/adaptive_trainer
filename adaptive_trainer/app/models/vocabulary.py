from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base



class VocabularyItem(Base):
    __tablename__ = "vocabulary_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    word: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    translations: Mapped[dict] = mapped_column(JSONB, nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, server_default="{}")


class LearnerVocabulary(Base):
    __tablename__ = "learner_vocabulary"
    __table_args__ = (
        UniqueConstraint("learner_id", "vocabulary_item_id", name="uq_learner_vocab_item"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    learner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("learners.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vocabulary_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("vocabulary_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    unit_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("curriculum_units.id", ondelete="SET NULL"), nullable=True
    )
    ease_factor: Mapped[float] = mapped_column(Float, nullable=False, default=2.5)
    interval: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    repetitions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_exercise_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
