"""Task 4 - FastAPI analytical API.

Run: uvicorn src.api.main:app --reload
Docs: http://localhost:8000/docs
"""
from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(
    title="Medical Telegram Warehouse API",
    description="Analytical API over the dbt star schema.",
    version="0.1.0",
)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


# TODO Task 4 endpoints:
#   GET /api/reports/top-products?limit=10
#   GET /api/channels/{channel_name}/activity
#   GET /api/search/messages?query=paracetamol&limit=20
#   GET /api/reports/visual-content
