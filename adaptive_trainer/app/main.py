import asyncio
import logging
logging.basicConfig(level=logging.INFO)

from contextlib import asynccontextmanager

import anthropic
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.data.curriculum_seed import seed_vocabulary
from app.routers import admin, webhook
from app.services.timeout_warning import run_timeout_warning_loop
from app.services.whatsapp_sender import close_client as close_whatsapp_client

logger = logging.getLogger(__name__)

_SEED_MAX_RETRIES = 3


@asynccontextmanager
async def lifespan(app: FastAPI):
    for attempt in range(1, _SEED_MAX_RETRIES + 1):
        try:
            count = await seed_vocabulary()
            if count:
                logger.info("Seeded %d curriculum vocabulary items", count)
            break
        except Exception:
            logger.exception(
                "Failed to seed curriculum vocabulary (attempt %d/%d)",
                attempt, _SEED_MAX_RETRIES,
            )
            if attempt == _SEED_MAX_RETRIES:
                raise RuntimeError(
                    "Curriculum seed failed after %d attempts — refusing to start "
                    "with empty curriculum." % _SEED_MAX_RETRIES
                )
            await asyncio.sleep(2 ** attempt)

    warning_task = asyncio.create_task(run_timeout_warning_loop())
    yield
    warning_task.cancel()
    try:
        await warning_task
    except asyncio.CancelledError:
        pass
    await close_whatsapp_client()


app = FastAPI(title="Adaptive Trainer", description="Adaptive Kannada language learning via WhatsApp", lifespan=lifespan)

app.include_router(webhook.router)
app.include_router(admin.router)


# ---------------------------------------------------------------------------
# Global exception handlers
#
# The WhatsApp Business API requires HTTP 200 on all POST /webhook calls.
# These handlers ensure that any uncaught exception still returns 200 so
# WhatsApp does not trigger retry storms.  Errors are logged for observability.
# ---------------------------------------------------------------------------


@app.exception_handler(SQLAlchemyError)
async def handle_db_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.error("db_error path=%s err=%s", request.url.path, exc, exc_info=True)
    return JSONResponse(status_code=200, content={"status": "ok"})


@app.exception_handler(anthropic.RateLimitError)
async def handle_anthropic_rate_limit(request: Request, exc: anthropic.RateLimitError) -> JSONResponse:
    logger.error("anthropic_rate_limit path=%s err=%s", request.url.path, exc)
    return JSONResponse(status_code=200, content={"status": "ok"})


@app.exception_handler(anthropic.APIStatusError)
async def handle_anthropic_api_error(request: Request, exc: anthropic.APIStatusError) -> JSONResponse:
    logger.error(
        "anthropic_api_error path=%s status=%d err=%s",
        request.url.path,
        exc.status_code,
        exc,
    )
    return JSONResponse(status_code=200, content={"status": "ok"})


@app.exception_handler(Exception)
async def handle_generic_error(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_error path=%s err=%s", request.url.path, exc, exc_info=True)
    return JSONResponse(status_code=200, content={"status": "ok"})


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
