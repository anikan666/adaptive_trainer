"""End-to-end workflow tests against real Postgres.

Covers the full happy path: onboard → lesson → exercise answers → review → gateway.
Only the Claude API and WhatsApp sender are mocked; all database operations hit
a real PostgreSQL instance with real schema (created via SQLAlchemy metadata).
"""

import json
import os
import subprocess
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# Test database URL — uses local Postgres with a dedicated test database.
_TEST_DB_NAME = "ql_e2e_test"
_PG_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432"
_TEST_DB_URL = f"{_PG_URL}/{_TEST_DB_NAME}"

# Set env vars BEFORE importing app modules so Settings picks them up.
os.environ["ANTHROPIC_API_KEY"] = "test-key"
os.environ["WHATSAPP_VERIFY_TOKEN"] = "test-verify"
os.environ["WHATSAPP_ACCESS_TOKEN"] = "test-access"
os.environ["WHATSAPP_APP_SECRET"] = "test-secret"
os.environ["WHATSAPP_PHONE_NUMBER_ID"] = "test-phone-id"
os.environ["DATABASE_URL"] = _TEST_DB_URL

from app.db.base import Base  # noqa: E402
from app.db import session as db_session_mod  # noqa: E402
from app.models import (  # noqa: E402
    Conversation,
    ConversationMode,
    CurriculumUnit,
    Learner,
    LearnerUnitProgress,
    LearnerVocabulary,
    UnitVocabulary,
    VocabularyItem,
)
from app.models.session import SessionRecord  # noqa: E402, F401 — register model

_PHONE = "919999000001"

# ---------------------------------------------------------------------------
# Captured WhatsApp messages — module-level so all tests share one list
# ---------------------------------------------------------------------------

_sent_messages: list[tuple[str, str]] = []


async def _fake_send(phone: str, body: str) -> None:
    _sent_messages.append((phone, body))


# ---------------------------------------------------------------------------
# Database setup/teardown via psql subprocess (event-loop-safe)
# ---------------------------------------------------------------------------

_PSQL_ENV = {**os.environ, "PGPASSWORD": "postgres"}


def setup_module():
    """Create test database using psql (synchronous, no event loop issues)."""
    subprocess.run(
        ["psql", "-U", "postgres", "-h", "localhost", "-c",
         f'DROP DATABASE IF EXISTS "{_TEST_DB_NAME}"'],
        env=_PSQL_ENV, capture_output=True,
    )
    subprocess.run(
        ["psql", "-U", "postgres", "-h", "localhost", "-c",
         f'CREATE DATABASE "{_TEST_DB_NAME}"'],
        env=_PSQL_ENV, capture_output=True, check=True,
    )
    # Create schema via synchronous sqlalchemy
    from sqlalchemy import create_engine
    sync_url = f"postgresql://postgres:postgres@localhost:5432/{_TEST_DB_NAME}"
    engine = create_engine(sync_url)
    Base.metadata.create_all(engine)
    engine.dispose()


def teardown_module():
    """Drop test database."""
    subprocess.run(
        ["psql", "-U", "postgres", "-h", "localhost", "-c",
         f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
         f"WHERE datname = '{_TEST_DB_NAME}' AND pid <> pg_backend_pid()"],
        env=_PSQL_ENV, capture_output=True,
    )
    subprocess.run(
        ["psql", "-U", "postgres", "-h", "localhost", "-c",
         f'DROP DATABASE IF EXISTS "{_TEST_DB_NAME}"'],
        env=_PSQL_ENV, capture_output=True,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Modules that import send_message with `from ... import send_message`.
_SEND_MSG_TARGETS = [
    "app.services.whatsapp_sender.send_message",
    "app.services.onboarding.send_message",
    "app.services.lesson_session.send_message",
    "app.services.review_session.send_message",
    "app.services.gateway_session.send_message",
    "app.routers.whatsapp.send_message",
]

# Modules that import AsyncSessionLocal with `from app.db.session import AsyncSessionLocal`.
_SESSION_TARGETS = [
    "app.routers.whatsapp.AsyncSessionLocal",
    "app.services.curriculum.AsyncSessionLocal",
    "app.services.gateway_session.AsyncSessionLocal",
    "app.services.lesson_session.AsyncSessionLocal",
    "app.services.level_tracker.AsyncSessionLocal",
    "app.services.onboarding.AsyncSessionLocal",
    "app.services.progress.AsyncSessionLocal",
    "app.services.review_session.AsyncSessionLocal",
    "app.services.topics.AsyncSessionLocal",
    "app.data.curriculum_seed.AsyncSessionLocal",
    "app.db.AsyncSessionLocal",
]


@pytest_asyncio.fixture(autouse=True)
async def _patch_db_session():
    """Redirect every AsyncSessionLocal() in the app to the test database.

    Uses NullPool to avoid event-loop-crossing connection reuse.
    A fresh engine is created per test so each binds to the correct event loop.
    Tables are truncated after each test.
    """
    engine = create_async_engine(_TEST_DB_URL, poolclass=NullPool)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False,
    )

    original_factory = db_session_mod.AsyncSessionLocal
    original_engine = db_session_mod.engine
    db_session_mod.AsyncSessionLocal = factory
    db_session_mod.engine = engine

    # Patch AsyncSessionLocal at every import site (same pattern as send_message).
    session_patches = [patch(t, factory) for t in _SESSION_TARGETS]
    for p in session_patches:
        p.start()

    yield factory

    for p in session_patches:
        p.stop()

    # Truncate all tables for isolation.
    async with engine.begin() as conn:
        await conn.execute(text(
            "DO $$ DECLARE r RECORD; BEGIN "
            "FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP "
            "EXECUTE 'TRUNCATE TABLE ' || quote_ident(r.tablename) || ' CASCADE'; "
            "END LOOP; END $$"
        ))

    db_session_mod.AsyncSessionLocal = original_factory
    db_session_mod.engine = original_engine
    await engine.dispose()


@pytest.fixture(autouse=True)
def _mock_whatsapp():
    """Capture all outbound WhatsApp messages via module-level list."""
    _sent_messages.clear()
    patches = [patch(t, side_effect=_fake_send) for t in _SEND_MSG_TARGETS]
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()


@pytest.fixture(autouse=True)
def _clear_rate_limiter():
    from app.services import rate_limiter
    rate_limiter._call_log.clear()
    yield
    rate_limiter._call_log.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_exercises(count: int = 4) -> list[dict]:
    """Return deterministic exercises for lesson tests."""
    exercises = []
    types = ["mcq", "fill_in_blank", "translation", "translation"]
    words = [
        ("namaskara", "hello"),
        ("hegiddira", "how are you"),
        ("dhanyavada", "thank you"),
        ("hogi banni", "goodbye"),
    ]
    for i in range(count):
        kannada, english = words[i % len(words)]
        ex_type = types[i % len(types)]
        ex: dict = {
            "type": ex_type,
            "question": f"What is '{english}' in Kannada?" if ex_type == "mcq" else english,
            "answer": kannada,
            "distractors": ["wrong1", "wrong2", "wrong3"] if ex_type in ("mcq", "fill_in_blank") else [],
            "explanation": f"'{kannada}' means '{english}' in Kannada.",
        }
        exercises.append(ex)
    return exercises


def _texts() -> list[str]:
    """Extract just the text bodies from sent messages."""
    return [t for _, t in _sent_messages]


# ---------------------------------------------------------------------------
# Seed data helpers
# ---------------------------------------------------------------------------


async def _seed_curriculum(factory):
    """Create a minimal curriculum: one ring-0 unit with 2 vocabulary words."""
    async with factory() as db:
        unit = CurriculumUnit(ring=0, unit_order=1, name="Greetings", slug="greetings-r0")
        db.add(unit)
        await db.flush()

        words = [
            UnitVocabulary(
                unit_id=unit.id, word="namaskara_kn", roman="namaskara",
                english="hello", usage_example="namaskara, hegiddira?",
            ),
            UnitVocabulary(
                unit_id=unit.id, word="dhanyavada_kn", roman="dhanyavada",
                english="thank you", usage_example="dhanyavada, tumba thanks",
            ),
        ]
        db.add_all(words)
        await db.commit()
        return unit.id


async def _get_learner(factory) -> Learner | None:
    async with factory() as db:
        result = await db.execute(select(Learner).where(Learner.phone_number == _PHONE))
        return result.scalar_one_or_none()


async def _get_convo(factory) -> Conversation | None:
    async with factory() as db:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.phone_number == _PHONE)
            .order_by(Conversation.updated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def _get_learner_vocab(factory, learner_id: int) -> list[LearnerVocabulary]:
    async with factory() as db:
        result = await db.execute(
            select(LearnerVocabulary).where(LearnerVocabulary.learner_id == learner_id)
        )
        return list(result.scalars().all())


async def _onboard(phone: str = _PHONE):
    """Run the full onboarding flow for a test user."""
    from app.services.onboarding import handle_onboarding
    await handle_onboarding(phone, "hi")
    await handle_onboarding(phone, "Tester")
    await handle_onboarding(phone, "0")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOnboarding:
    """Onboard a new user through the 3-step flow."""

    async def test_step1_welcome(self, _patch_db_session):
        """First message from new user creates onboarding convo and sends welcome."""
        from app.services.onboarding import handle_onboarding, needs_onboarding

        assert await needs_onboarding(_PHONE) is True

        await handle_onboarding(_PHONE, "hi")

        assert any("Welcome" in t for t in _texts())

        convo = await _get_convo(_patch_db_session)
        assert convo is not None
        assert convo.mode == ConversationMode.onboarding
        assert convo.lesson_context["step"] == "ask_name"

    async def test_step2_name(self, _patch_db_session):
        """User provides name → conversation advances to ask_level."""
        from app.services.onboarding import handle_onboarding

        await handle_onboarding(_PHONE, "hi")
        await handle_onboarding(_PHONE, "Anika")

        assert any("Anika" in t for t in _texts())

        convo = await _get_convo(_patch_db_session)
        assert convo.lesson_context["step"] == "ask_level"
        assert convo.lesson_context["name"] == "Anika"

    async def test_step3_level_creates_learner(self, _patch_db_session):
        """User provides level → Learner record created, main menu shown."""
        from app.services.onboarding import handle_onboarding, needs_onboarding

        await handle_onboarding(_PHONE, "hi")
        await handle_onboarding(_PHONE, "Anika")
        await handle_onboarding(_PHONE, "0")

        assert any("all set" in t.lower() for t in _texts())

        learner = await _get_learner(_patch_db_session)
        assert learner is not None
        assert learner.name == "Anika"
        assert learner.current_ring == 0
        assert learner.level == 1

        assert await needs_onboarding(_PHONE) is False


@pytest.mark.asyncio
class TestLessonFlow:
    """Start a lesson, answer exercises, verify vocabulary is recorded."""

    async def test_lesson_start_and_exercise_answers(self, _patch_db_session):
        """Full lesson: start → answer all 4 exercises → finish."""
        await _onboard()

        exercises = _mock_exercises()
        lesson_text = "Lesson: Greetings\n1. namaskara — hello"

        with (
            patch(
                "app.services.lesson.ask_sonnet",
                new_callable=AsyncMock,
                return_value=lesson_text,
            ),
            patch(
                "app.services.exercise.ask_sonnet",
                new_callable=AsyncMock,
                return_value=json.dumps(exercises),
            ),
            patch(
                "app.services.evaluator.ask_sonnet",
                new_callable=AsyncMock,
                return_value=json.dumps({
                    "correct": True,
                    "score": 1.0,
                    "feedback": "Perfect!",
                    "corrected_kannada": None,
                }),
            ),
        ):
            from app.services.lesson_session import handle_exercise_answer, start_lesson

            await start_lesson(_PHONE, "greetings")

            convo = await _get_convo(_patch_db_session)
            assert convo.mode == ConversationMode.lesson
            assert convo.lesson_context is not None
            assert len(convo.lesson_context["exercises"]) == 4

            for i in range(4):
                await handle_exercise_answer(_PHONE, "namaskara")

            convo = await _get_convo(_patch_db_session)
            assert convo.mode == ConversationMode.quick_lookup
            assert convo.lesson_context is None

        learner = await _get_learner(_patch_db_session)
        vocab = await _get_learner_vocab(_patch_db_session, learner.id)
        assert len(vocab) > 0

        assert any("Session complete" in t for t in _texts())

    async def test_curriculum_lesson_with_unit(self, _patch_db_session):
        """Curriculum-driven lesson: uses unit vocabulary and tracks progress."""
        await _onboard()
        unit_id = await _seed_curriculum(_patch_db_session)

        exercises = _mock_exercises(count=4)
        lesson_text = "Lesson: Greetings\n1. namaskara — hello"

        with (
            patch(
                "app.services.lesson.ask_sonnet",
                new_callable=AsyncMock,
                return_value=lesson_text,
            ),
            patch(
                "app.services.exercise.ask_sonnet",
                new_callable=AsyncMock,
                return_value=json.dumps(exercises),
            ),
            patch(
                "app.services.evaluator.ask_sonnet",
                new_callable=AsyncMock,
                return_value=json.dumps({
                    "correct": True,
                    "score": 1.0,
                    "feedback": "Perfect!",
                    "corrected_kannada": None,
                }),
            ),
        ):
            from app.services.lesson_session import handle_exercise_answer, start_lesson

            await start_lesson(_PHONE, "lesson")

            convo = await _get_convo(_patch_db_session)
            assert convo.lesson_context.get("unit_id") == unit_id

            for i in range(4):
                await handle_exercise_answer(_PHONE, "namaskara")

        learner = await _get_learner(_patch_db_session)
        async with _patch_db_session() as db:
            result = await db.execute(
                select(LearnerUnitProgress)
                .where(LearnerUnitProgress.learner_id == learner.id)
                .where(LearnerUnitProgress.unit_id == unit_id)
            )
            progress = result.scalar_one_or_none()
        assert progress is not None


@pytest.mark.asyncio
class TestReviewFlow:
    """Review due vocabulary items and verify SRS updates."""

    async def _setup_learner_with_vocab(self, factory):
        """Create a learner with vocabulary items due today."""
        await _onboard()
        learner = await _get_learner(factory)

        async with factory() as db:
            for english, kannada in [("hello", "namaskara"), ("thank you", "dhanyavada")]:
                vi = VocabularyItem(
                    word=english,
                    translations={"roman": kannada, "explanation": f"{kannada} = {english}"},
                    tags=[],
                )
                db.add(vi)
                await db.flush()

                lv = LearnerVocabulary(
                    learner_id=learner.id,
                    vocabulary_item_id=vi.id,
                    due_date=date.today(),
                    ease_factor=2.5,
                    interval=1,
                    repetitions=0,
                )
                db.add(lv)
            await db.commit()

        return learner

    async def test_review_full_session(self, _patch_db_session):
        """Start review → answer all items → verify SRS updates."""
        learner = await self._setup_learner_with_vocab(_patch_db_session)

        with patch(
            "app.services.evaluator.ask_sonnet",
            new_callable=AsyncMock,
            return_value=json.dumps({
                "correct": True,
                "score": 1.0,
                "feedback": "Perfect!",
                "corrected_kannada": None,
            }),
        ):
            from app.services.review_session import handle_review_answer, start_review

            await start_review(_PHONE)

            convo = await _get_convo(_patch_db_session)
            assert convo.mode == ConversationMode.review
            items = convo.lesson_context["items"]
            assert len(items) == 2

            for _ in range(len(items)):
                await handle_review_answer(_PHONE, "namaskara")

            convo = await _get_convo(_patch_db_session)
            assert convo.mode == ConversationMode.quick_lookup

        vocab = await _get_learner_vocab(_patch_db_session, learner.id)
        for lv in vocab:
            assert lv.repetitions >= 1
            assert lv.due_date > date.today()

        assert any("Review complete" in t for t in _texts())

    async def test_review_no_due_items(self, _patch_db_session):
        """Review with no due items sends appropriate message."""
        await _onboard()

        from app.services.review_session import start_review
        await start_review(_PHONE)

        assert any("No vocabulary" in t or "No words due" in t for t in _texts())


@pytest.mark.asyncio
class TestGatewayFlow:
    """Gateway roleplay test: multi-turn conversation → evaluation → ring advancement."""

    async def test_gateway_pass_advances_ring(self, _patch_db_session):
        """Complete gateway test with passing score → ring advances."""
        await _onboard()

        evaluation_json = json.dumps({
            "passed": True,
            "score": 0.85,
            "feedback": "Great job!",
            "strengths": ["Good greetings", "Correct food vocabulary"],
            "areas_to_improve": ["Practice numbers"],
        })

        with patch(
            "app.services.gateway_session.ask_sonnet",
            new_callable=AsyncMock,
            side_effect=[
                "Sari, ondu dosa, ondu kaafi. Bere yenu beku?",
                "Dosa 50 rupayi, kaafi 20 rupayi. Total 70 rupayi.",
                "Dhanyavada! Banni, matte banni!",
                evaluation_json,
            ],
        ):
            from app.services.gateway_session import handle_gateway_turn, start_gateway

            await start_gateway(_PHONE, ring=0)

            convo = await _get_convo(_patch_db_session)
            assert convo.mode == ConversationMode.gateway_test
            ctx = convo.lesson_context
            assert ctx["ring"] == 0
            assert ctx["expected_turns"] == 4

            for _ in range(4):
                await handle_gateway_turn(_PHONE, "namaskara, ondu dosa kodi")

            convo = await _get_convo(_patch_db_session)
            assert convo.mode == ConversationMode.quick_lookup

        learner = await _get_learner(_patch_db_session)
        assert learner.current_ring == 1

        assert any("PASSED" in t for t in _texts())
        assert any("Ring 1" in t for t in _texts())

    async def test_gateway_fail_stays_on_ring(self, _patch_db_session):
        """Fail gateway test → ring stays the same."""
        await _onboard()

        evaluation_json = json.dumps({
            "passed": False,
            "score": 0.3,
            "feedback": "Keep practicing!",
            "strengths": ["Good effort"],
            "areas_to_improve": ["Vocabulary", "Grammar"],
        })

        with patch(
            "app.services.gateway_session.ask_sonnet",
            new_callable=AsyncMock,
            side_effect=[
                "Sari, yenu beku?",
                "Ondu nimishaaa...",
                "Hmm, swalpa kashta aaythu.",
                evaluation_json,
            ],
        ):
            from app.services.gateway_session import handle_gateway_turn, start_gateway

            await start_gateway(_PHONE, ring=0)

            for _ in range(4):
                await handle_gateway_turn(_PHONE, "uh... hello")

            convo = await _get_convo(_patch_db_session)
            assert convo.mode == ConversationMode.quick_lookup

        learner = await _get_learner(_patch_db_session)
        assert learner.current_ring == 0

        assert any("NOT YET" in t for t in _texts())


@pytest.mark.asyncio
class TestFullHappyPath:
    """End-to-end: onboard → lesson → review → gateway — in one continuous flow."""

    async def test_onboard_lesson_review_gateway(self, _patch_db_session):
        """Simulate a learner's complete journey through the app."""
        # ---- 1. ONBOARD ----
        from app.services.onboarding import handle_onboarding, needs_onboarding

        assert await needs_onboarding(_PHONE) is True
        await handle_onboarding(_PHONE, "hi")
        await handle_onboarding(_PHONE, "Priya")
        await handle_onboarding(_PHONE, "0")
        assert await needs_onboarding(_PHONE) is False

        learner = await _get_learner(_patch_db_session)
        assert learner.current_ring == 0

        # ---- 2. LESSON ----
        exercises = _mock_exercises()
        lesson_text = "Lesson: Everyday Greetings\n1. namaskara — hello\n2. hegiddira — how are you"

        with (
            patch(
                "app.services.lesson.ask_sonnet",
                new_callable=AsyncMock,
                return_value=lesson_text,
            ),
            patch(
                "app.services.exercise.ask_sonnet",
                new_callable=AsyncMock,
                return_value=json.dumps(exercises),
            ),
            patch(
                "app.services.evaluator.ask_sonnet",
                new_callable=AsyncMock,
                return_value=json.dumps({
                    "correct": True,
                    "score": 0.8,
                    "feedback": "Good!",
                    "corrected_kannada": None,
                }),
            ),
        ):
            from app.services.lesson_session import handle_exercise_answer, start_lesson

            await start_lesson(_PHONE, "greetings")
            for _ in range(4):
                await handle_exercise_answer(_PHONE, "namaskara")

        convo = await _get_convo(_patch_db_session)
        assert convo.mode == ConversationMode.quick_lookup

        learner = await _get_learner(_patch_db_session)
        vocab_after_lesson = await _get_learner_vocab(_patch_db_session, learner.id)
        assert len(vocab_after_lesson) > 0

        # ---- 3. REVIEW ----
        async with _patch_db_session() as db:
            result = await db.execute(
                select(LearnerVocabulary).where(LearnerVocabulary.learner_id == learner.id)
            )
            for lv in result.scalars().all():
                lv.due_date = date.today()
            await db.commit()

        with patch(
            "app.services.evaluator.ask_sonnet",
            new_callable=AsyncMock,
            return_value=json.dumps({
                "correct": True,
                "score": 1.0,
                "feedback": "Excellent!",
                "corrected_kannada": None,
            }),
        ):
            from app.services.review_session import handle_review_answer, start_review

            await start_review(_PHONE)

            convo = await _get_convo(_patch_db_session)
            assert convo.mode == ConversationMode.review
            review_count = len(convo.lesson_context["items"])

            for _ in range(review_count):
                await handle_review_answer(_PHONE, "namaskara")

        convo = await _get_convo(_patch_db_session)
        assert convo.mode == ConversationMode.quick_lookup

        vocab_after_review = await _get_learner_vocab(_patch_db_session, learner.id)
        for lv in vocab_after_review:
            assert lv.repetitions >= 1

        # ---- 4. GATEWAY ----
        evaluation_json = json.dumps({
            "passed": True,
            "score": 0.9,
            "feedback": "Excellent work!",
            "strengths": ["Natural greetings", "Good vocabulary"],
            "areas_to_improve": [],
        })

        with patch(
            "app.services.gateway_session.ask_sonnet",
            new_callable=AsyncMock,
            side_effect=[
                "Namaskara! Yenu beku?",
                "Sari, ondu dosa. Bere?",
                "70 rupayi aagutte.",
                evaluation_json,
            ],
        ):
            from app.services.gateway_session import handle_gateway_turn, start_gateway

            await start_gateway(_PHONE, ring=0)

            for _ in range(4):
                await handle_gateway_turn(_PHONE, "namaskara, ondu dosa kodi dayavittu")

        learner = await _get_learner(_patch_db_session)
        assert learner.current_ring == 1

        texts = _texts()
        assert any("PASSED" in t for t in texts)
        assert any("Ring 1" in t for t in texts)
        assert any("Session complete" in t for t in texts)
        assert any("Review complete" in t for t in texts)
