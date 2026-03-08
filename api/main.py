from __future__ import annotations

from dataclasses import asdict
import os
from pathlib import Path
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from search.api_client import WikiApiClient
from search.path_finder import WikiPathFinder


FORBIDDEN_TITLE_CHARS = set("#<>[]{}|")
MAX_TITLE_LENGTH = 255


def _parse_cors_origins() -> list[str]:
    """Берет CORS origins из env и аккуратно разбирает список"""
    raw = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    return origins or ["http://localhost:5173"]


def _validate_title(title: str, field_name: str) -> str:
    value = (title or "").strip().replace("_", " ")
    value = " ".join(value.split())

    if not value:
        raise HTTPException(status_code=400, detail=f"{field_name} must not be empty")
    if len(value) > MAX_TITLE_LENGTH:
        raise HTTPException(status_code=400, detail=f"{field_name} is too long")
    if any(ch in FORBIDDEN_TITLE_CHARS for ch in value):
        raise HTTPException(status_code=400, detail=f"{field_name} contains forbidden characters")
    if any(ord(ch) < 32 for ch in value):
        raise HTTPException(status_code=400, detail=f"{field_name} contains control characters")

    return value


class SearchRequest(BaseModel):
    start_article: str = Field(min_length=1)
    end_article: str = Field(min_length=1)


class SearchResponse(BaseModel):
    path: list[str] | None
    elapsed_time: float
    error: str | None
    steps_count: int


app = FastAPI(title="Wiki Path Finder API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(),
    allow_credentials=False,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/search", response_model=SearchResponse)
async def search_path(payload: SearchRequest) -> SearchResponse:
    start_article = _validate_title(payload.start_article, "start_article")
    end_article = _validate_title(payload.end_article, "end_article")

    async with WikiApiClient() as client:
        finder = WikiPathFinder(client=client, time_limit=30)
        result = await finder.find_path(start_article, end_article)

    return SearchResponse(**asdict(result))


@app.get("/api/metrics")
async def get_metrics() -> dict:
    metrics_path = Path("reports/metrics.json")
    if not metrics_path.exists():
        raise HTTPException(status_code=404, detail="reports/metrics.json not found")

    try:
        return json.loads(metrics_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Invalid metrics JSON") from exc
