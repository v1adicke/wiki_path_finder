from __future__ import annotations

import asyncio
import json
from collections import OrderedDict
from typing import Dict, Optional, Set

import aiohttp


class WikiApiClient:
    """Клиент к Wikipedia API с кешем и защитой от лишних повторов"""

    def __init__(
        self,
        base_url: str = "https://ru.wikipedia.org/w/api.php",
        user_agent: str = "WikiPathFinder/1.0 (vdenyshev@inbox.ru)",
        total_timeout: int = 30,
        connector_limit: int = 50,
        retries: int = 3,
        cache_size: int = 2000,
    ) -> None:
        """Настраивает клиент, таймауты, ретраи и размер кеша"""
        self._base_url = base_url
        self._user_agent = user_agent
        self._timeout = aiohttp.ClientTimeout(total=total_timeout)
        self._connector = aiohttp.TCPConnector(limit=connector_limit)
        self._retries = retries
        self._cache_size = max(100, cache_size)
        self._session: Optional[aiohttp.ClientSession] = None

        self._links_cache: "OrderedDict[str, Set[str]]" = OrderedDict()
        self._backlinks_cache: "OrderedDict[str, Set[str]]" = OrderedDict()
        self._exists_cache: "OrderedDict[str, bool]" = OrderedDict()

        self._links_inflight: Dict[str, asyncio.Task] = {}
        self._backlinks_inflight: Dict[str, asyncio.Task] = {}
        self._exists_inflight: Dict[str, asyncio.Task] = {}

    def _cache_get(self, cache: "OrderedDict[str, object]", key: str):
        if key in cache:
            cache.move_to_end(key)
            return cache[key]
        return None

    def _cache_set(self, cache: "OrderedDict[str, object]", key: str, value: object) -> None:
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > self._cache_size:
            cache.popitem(last=False)

    async def _run_cached(
        self,
        key: str,
        *,
        cache: "OrderedDict[str, object]",
        inflight: Dict[str, asyncio.Task],
        fetch_coro,
    ):
        cached = self._cache_get(cache, key)
        if cached is not None:
            return cached

        task = inflight.get(key)
        if task is not None:
            return await task

        task = asyncio.create_task(fetch_coro())
        inflight[key] = task
        try:
            value = await task
            self._cache_set(cache, key, value)
            return value
        finally:
            inflight.pop(key, None)

    async def __aenter__(self) -> "WikiApiClient":
        self._session = aiohttp.ClientSession(
            timeout=self._timeout,
            headers={"User-Agent": self._user_agent},
            connector=self._connector,
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise RuntimeError("Client session is not initialized.")
        return self._session

    async def _fetch_json_with_retries(self, params: Dict[str, str]) -> Dict:
        """Делает GET и при сбоях повторяет с экспоненциальной паузой"""
        backoff = 1.0
        for attempt in range(self._retries):
            try:
                async with self.session.get(self._base_url, params=params) as resp:
                    if resp.status == 429:
                        retry_after = resp.headers.get("Retry-After")
                        wait = (
                            float(retry_after)
                            if retry_after and retry_after.isdigit()
                            else backoff
                        )
                        await asyncio.sleep(wait)
                        backoff *= 2
                        continue

                    if resp.status != 200:
                        if attempt == self._retries - 1:
                            raise RuntimeError(f"HTTP {resp.status}")
                        await asyncio.sleep(backoff)
                        backoff *= 2
                        continue

                    text = await resp.text()
                    try:
                        return await resp.json(content_type=None)
                    except aiohttp.ContentTypeError:
                        try:
                            return json.loads(text)
                        except ValueError:
                            return {}
            except asyncio.TimeoutError:
                if attempt == self._retries - 1:
                    raise RuntimeError("Превышено время ожидания")
                await asyncio.sleep(backoff)
                backoff *= 2

        raise RuntimeError("Превышен лимит попыток")

    async def fetch_links(self, title: str) -> Set[str]:
        """Возвращает все исходящие ссылки со статьи"""
        title = (title or "").strip()
        if not title:
            return set()

        async def _do_fetch() -> Set[str]:
            params: Dict[str, str] = {
                "action": "query",
                "format": "json",
                "prop": "links",
                "titles": title,
                "pllimit": "max",
                "plnamespace": "0",
            }
            links: Set[str] = set()
            cont: Dict[str, str] = {}
            while True:
                data = await self._fetch_json_with_retries({**params, **cont})
                pages = data.get("query", {}).get("pages", {})
                for page in pages.values():
                    for link in page.get("links", []) or []:
                        title_val = link.get("title")
                        if title_val:
                            links.add(title_val)

                if "continue" in data:
                    cont = data["continue"]
                else:
                    break

            return links

        result = await self._run_cached(
            title,
            cache=self._links_cache,
            inflight=self._links_inflight,
            fetch_coro=_do_fetch,
        )
        return set(result)

    async def fetch_backlinks(self, title: str) -> Set[str]:
        """Возвращает все статьи, которые ссылаются на эту страницу"""
        title = (title or "").strip()
        if not title:
            return set()

        async def _do_fetch() -> Set[str]:
            params: Dict[str, str] = {
                "action": "query",
                "format": "json",
                "list": "backlinks",
                "bltitle": title,
                "bllimit": "max",
                "blnamespace": "0",
            }
            backlinks: Set[str] = set()
            cont: Dict[str, str] = {}
            while True:
                data = await self._fetch_json_with_retries({**params, **cont})
                for item in data.get("query", {}).get("backlinks", []) or []:
                    title_val = item.get("title")
                    if title_val:
                        backlinks.add(title_val)

                if "continue" in data:
                    cont = data["continue"]
                else:
                    break

            return backlinks

        result = await self._run_cached(
            title,
            cache=self._backlinks_cache,
            inflight=self._backlinks_inflight,
            fetch_coro=_do_fetch,
        )
        return set(result)

    async def page_exists(self, title: str) -> bool:
        title = (title or "").strip()
        if not title:
            return False

        async def _do_fetch() -> bool:
            params: Dict[str, str] = {
                "action": "query",
                "format": "json",
                "titles": title,
                "prop": "info",
                "redirects": "1",
            }
            data = await self._fetch_json_with_retries(params)
            pages = data.get("query", {}).get("pages", {})
            if not pages:
                return False
            for page in pages.values():
                if "missing" in page:
                    return False
            return True

        result = await self._run_cached(
            title,
            cache=self._exists_cache,
            inflight=self._exists_inflight,
            fetch_coro=_do_fetch,
        )
        return bool(result)
