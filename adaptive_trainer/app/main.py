from fastapi import FastAPI

from app.routers import webhook

app = FastAPI(title="Adaptive Trainer", description="Adaptive Kannada language learning via WhatsApp")

app.include_router(webhook.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
