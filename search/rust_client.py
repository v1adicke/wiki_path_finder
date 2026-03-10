from __future__ import annotations

from dataclasses import fields
from typing import Any

import aiohttp

from search.result import WikiPathResult


class RustSearchClientError(RuntimeError):
    """Raised when the Rust search service request fails."""


class RustSearchClient:
    """HTTP client for the external Rust search service."""

    def __init__(self, base_url: str, timeout_seconds: float = 35.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    async def find_path(self, start_article: str, end_article: str, time_limit: int) -> WikiPathResult:
        payload = {
            "start_article": start_article,
            "end_article": end_article,
            "time_limit": time_limit,
        }

        try:
            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                async with session.post(f"{self._base_url}/search", json=payload) as response:
                    if response.status != 200:
                        body = await response.text()
                        raise RustSearchClientError(
                            f"Rust service returned HTTP {response.status}: {body[:300]}"
                        )
                    data = await response.json()
        except (aiohttp.ClientError, aiohttp.ContentTypeError, TimeoutError) as exc:
            raise RustSearchClientError(f"Rust service request failed: {exc}") from exc

        return self._decode_result(data)

    @staticmethod
    def _decode_result(data: Any) -> WikiPathResult:
        if not isinstance(data, dict):
            raise RustSearchClientError("Rust service returned non-object JSON")

        allowed = {f.name for f in fields(WikiPathResult)}
        normalized = {key: value for key, value in data.items() if key in allowed}

        if "steps_count" not in normalized:
            path = normalized.get("path")
            normalized["steps_count"] = len(path) if isinstance(path, list) else 0

        try:
            return WikiPathResult(**normalized)
        except TypeError as exc:
            raise RustSearchClientError(f"Invalid Rust service payload: {exc}") from exc
