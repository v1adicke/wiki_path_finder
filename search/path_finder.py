from __future__ import annotations

import asyncio
import time
from typing import Dict, List, Optional, Set

from search.api_client import WikiApiClient
from search.result import WikiPathResult


class WikiPathFinder:
    """
    Двунаправленный поиск с использованием API.
    """

    def __init__(self, client: WikiApiClient, time_limit: int = 30) -> None:
        """
        Args:
            client: WikiApiClient для взаимодействия с API.
            time_limit: Максимальное время поиска (сек).
        """
        self._client = client
        self._time_limit = time_limit


    @staticmethod
    def _reconstruct_path(
        prev_fwd: Dict[str, Optional[str]],
        prev_bwd: Dict[str, Optional[str]],
        meet_node: str,
    ) -> List[str]:
        """
        Построение пути через узел встречи прямого и обратного поиска.
        """
        path_front: List[str] = []
        node: Optional[str] = meet_node
        while node is not None:
            path_front.append(node)
            node = prev_fwd[node]
        path_front.reverse()

        path_back: List[str] = []
        node = prev_bwd[meet_node]
        while node is not None:
            path_back.append(node)
            node = prev_bwd[node]

        return path_front + path_back


    async def find_path(self, start: str, end: str) -> WikiPathResult:
        """
        Находит путь между статьями Википедии через двунаправленный поиск.
        """
        t0 = time.monotonic()

        start = (start or "").strip()
        end = (end or "").strip()
        if not start or not end:
            return WikiPathResult(
                error="Названия страниц не могут быть пустыми",
                elapsed_time=time.monotonic() - t0,
            )

        if start == end:
            elapsed = time.monotonic() - t0
            return WikiPathResult(path=[start], elapsed_time=elapsed, steps_count=1)

        fwd_front: Set[str] = {start}
        bwd_front: Set[str] = {end}

        prev_fwd: Dict[str, Optional[str]] = {start: None}
        prev_bwd: Dict[str, Optional[str]] = {end: None}

        dist_fwd: Dict[str, int] = {start: 0}
        dist_bwd: Dict[str, int] = {end: 0}

        best_len = float("inf")
        meet: Optional[str] = None

        while fwd_front and bwd_front and (time.monotonic() - t0) < self._time_limit:
            min_f = min(dist_fwd[n] for n in fwd_front)
            min_b = min(dist_bwd[n] for n in bwd_front)
            if min_f + min_b >= best_len:
                break

            expand_fwd = len(fwd_front) <= len(bwd_front)
            if expand_fwd:
                tasks = [self._client.fetch_links(node) for node in fwd_front]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                next_front: Set[str] = set()
                for node, neighs in zip(fwd_front, results):
                    if isinstance(neighs, Exception):
                        continue
                    d = dist_fwd[node]
                    for nbr in neighs:
                        if nbr not in dist_fwd:
                            dist_fwd[nbr] = d + 1
                            prev_fwd[nbr] = node
                            if nbr in dist_bwd:
                                total = dist_fwd[nbr] + dist_bwd[nbr]
                                if total < best_len:
                                    best_len = total
                                    meet = nbr
                            next_front.add(nbr)
                fwd_front = next_front
            else:
                tasks = [self._client.fetch_backlinks(node) for node in bwd_front]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                next_front: Set[str] = set()
                for node, neighs in zip(bwd_front, results):
                    if isinstance(neighs, Exception):
                        continue
                    d = dist_bwd[node]
                    for nbr in neighs:
                        if nbr not in dist_bwd:
                            dist_bwd[nbr] = d + 1
                            prev_bwd[nbr] = node
                            if nbr in dist_fwd:
                                total = dist_fwd[nbr] + dist_bwd[nbr]
                                if total < best_len:
                                    best_len = total
                                    meet = nbr
                            next_front.add(nbr)
                bwd_front = next_front

        elapsed = time.monotonic() - t0
        if best_len < float("inf") and meet:
            path = self._reconstruct_path(prev_fwd, prev_bwd, meet)
            return WikiPathResult(path=path, elapsed_time=elapsed, steps_count=len(path))

        return WikiPathResult(elapsed_time=elapsed)