from __future__ import annotations

import asyncio
import json
from typing import Dict, Set, Optional

import aiohttp


class WikiApiClient:
    """
    Асинхронный клиент для Wikipedia API.
    """

    def __init__(
        self,
        base_url: str = "https://ru.wikipedia.org/w/api.php",
        user_agent: str = "WikiPathFinder/1.0",
        total_timeout: int = 30,
        connector_limit: int = 50,
        retries: int = 3,
    ) -> None:
        """
        Инициализация клиента API.

        Args:
            base_url: Базовый URL API.
            user_agent: HTTP User-Agent.
            total_timeout: Максимальное время для запроса.
            connector_limit: Максимальное количество соединений.
            retries: Количество попыток при ошибках/таймаутах.
        """
        self._base_url = base_url
        self._user_agent = user_agent
        self._timeout = aiohttp.ClientTimeout(total=total_timeout)
        self._connector = aiohttp.TCPConnector(limit=connector_limit)
        self._retries = retries
        self._session: Optional[aiohttp.ClientSession] = None


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
        """
        GET запрос с ретраями и экспоненциальной паузой.
        """
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
        """
        Извлечение всех ссылок со страницы.
        """
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


    async def fetch_backlinks(self, title: str) -> Set[str]:
        """
        Извлечение всех ссылок на страницу.
        """
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