"""FastAPI application entrypoint.

Intentionally minimal for this step: app boot + health check only. `/query` and ingestion
endpoints land in later steps (see docs/ARCHITECTURE.md section 10).
"""

from fastapi import FastAPI

app = FastAPI(title="Internal Knowledge Assistant")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
