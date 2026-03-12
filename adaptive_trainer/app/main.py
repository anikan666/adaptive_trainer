from fastapi import FastAPI

app = FastAPI(title="Adaptive Trainer", description="Adaptive Kannada language learning via WhatsApp")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
