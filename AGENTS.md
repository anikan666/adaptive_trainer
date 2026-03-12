# adaptive_trainer — AGENTS.md

Adaptive Kannada language learning app delivered via WhatsApp.
Backend: Python/FastAPI · Claude API · WhatsApp Business API · PostgreSQL.

---

## Project Overview

Two core user flows:

1. **Quick Lookup** — user sends a message asking for a phrase/sentence in
   colloquial Kannada; Claude responds immediately with the translation plus
   a brief usage note.

2. **Structured Lessons** — app generates lessons, exercises, and feedback
   adapted to the learner's proficiency level using spaced repetition and
   assessment logic. Claude drives content generation; PostgreSQL stores
   learner state.

---

## Repo Layout (target)

```
adaptive_trainer/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Settings (env vars, secrets)
│   ├── db/
│   │   ├── models.py        # SQLAlchemy ORM models
│   │   └── session.py       # Async DB session factory
│   ├── api/
│   │   └── webhook.py       # WhatsApp Business API webhook
│   ├── services/
│   │   ├── claude_client.py # Anthropic SDK wrapper + prompt templates
│   │   ├── quick_lookup.py  # Quick lookup flow
│   │   ├── lesson.py        # Lesson + exercise generation
│   │   ├── evaluator.py     # Answer evaluation + feedback
│   │   └── srs.py           # Spaced repetition scheduler (SM-2)
│   ├── routers/
│   │   └── whatsapp.py      # Route WhatsApp messages to correct handler
│   └── schemas/
│       └── learner.py       # Pydantic schemas
├── alembic/                 # DB migrations
├── tests/
├── requirements.txt
├── .env.example
└── Dockerfile
```

---

## Architecture Decisions

- **Claude model**: `claude-sonnet-4-6` for lesson gen and evaluation;
  `claude-haiku-4-5-20251001` for low-latency quick lookups.
- **Conversation state**: stored in PostgreSQL (`conversations` table) keyed
  by WhatsApp phone number. Each active session has a `mode` field
  (`quick_lookup` | `lesson` | `exercise`).
- **Spaced repetition**: SM-2 algorithm on `vocabulary_items` table; due
  items surfaced at lesson start.
- **Async**: use `asyncpg` + SQLAlchemy async; `httpx.AsyncClient` for
  Anthropic SDK calls.
- **WhatsApp**: Meta WhatsApp Business API (not Twilio). Verify token via
  `GET /webhook`; receive messages via `POST /webhook`.

---

## Working in this Repo

- All Python in `app/`. Tests in `tests/` with `pytest-asyncio`.
- Use `alembic revision --autogenerate` for schema changes, never hand-edit
  migration files.
- Prompt templates live as module-level constants in `claude_client.py` or
  service files — not inline strings scattered through handlers.
- Never commit secrets; use `.env` (gitignored) + `python-dotenv`.
- `ruff` for linting, `black` for formatting. CI enforces both.

---

## Environment Variables

```
ANTHROPIC_API_KEY=
WHATSAPP_VERIFY_TOKEN=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
DATABASE_URL=postgresql+asyncpg://...
```

---

## Key Constraints

- WhatsApp message window: 24-hour customer-initiated window. The app only
  sends messages in response to user messages (no proactive push for now).
- Kannada output: Claude must produce Kannada script (ಕನ್ನಡ), not
  transliteration, unless the user explicitly requests romanization.
- Colloquial vs formal: quick lookup always targets colloquial/spoken Kannada;
  lessons may include formal variants with clear labeling.
