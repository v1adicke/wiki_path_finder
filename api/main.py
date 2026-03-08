from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import asdict
import os
from pathlib import Path
import json
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from search.api_client import WikiApiClient
from search.path_finder import WikiPathFinder


FORBIDDEN_TITLE_CHARS = set("#<>[]{}|")
MAX_TITLE_LENGTH = 255

PRODUCTION: bool = os.getenv("PRODUCTION", "False").lower() in ("true", "1", "yes")

_RATE_LIMIT_CALLS: int = int(os.getenv("RATE_LIMIT_CALLS", "30"))
_RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))


class _RateLimiter:
    """Sliding-window rate limiter по IP-адресу клиента"""

    def __init__(self, max_calls: int, window_seconds: int) -> None:
        self._max_calls = max_calls
        self._window = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_allowed(self, key: str) -> bool:
        async with self._lock:
            now = time.monotonic()
            cutoff = now - self._window
            bucket = self._buckets[key]
            self._buckets[key] = [t for t in bucket if t > cutoff]
            if len(self._buckets[key]) >= self._max_calls:
                return False
            self._buckets[key].append(now)
            return True


_rate_limiter = _RateLimiter(max_calls=_RATE_LIMIT_CALLS, window_seconds=_RATE_LIMIT_WINDOW)


def _extract_client_ip(request: Request) -> str:
    """Определяет IP клиента с учетом reverse-proxy заголовков"""
    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    if forwarded_for:
        first_hop = forwarded_for.split(",")[0].strip()
        if first_hop:
            return first_hop

    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip

    return request.client.host if request.client else "unknown"


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


app = FastAPI(
    title="Wiki Path Finder API",
    docs_url=None if PRODUCTION else "/docs",
    redoc_url=None if PRODUCTION else "/redoc",
    openapi_url=None if PRODUCTION else "/openapi.json",
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


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
async def search_path(payload: SearchRequest, request: Request) -> SearchResponse:
    client_ip = _extract_client_ip(request)
    if not await _rate_limiter.is_allowed(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait before searching again.")

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
