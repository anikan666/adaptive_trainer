import logging
logging.basicConfig(level=logging.INFO)

import anthropic
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.routers import webhook

logger = logging.getLogger(__name__)

app = FastAPI(title="Adaptive Trainer", description="Adaptive Kannada language learning via WhatsApp")

app.include_router(webhook.router)


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
