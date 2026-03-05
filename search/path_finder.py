from __future__ import annotations

import asyncio
import re
import time
from typing import Dict, Iterable, List, Optional, Set, Tuple

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
    def _tokenize_title(title: str) -> Set[str]:
        # Выделяем только смысловые токены для грубой эвристики близости статей.
        return {
            token
            for token in re.findall(r"[\w\-]+", (title or "").lower())
            if len(token) > 2
        }

    @staticmethod
    def _rank_neighbors(
        neighbors: Iterable[str],
        target_tokens: Set[str],
        target_title: str,
        max_neighbors: Optional[int],
    ) -> List[str]:
        ranked = list(neighbors)
        if not ranked or max_neighbors is None or len(ranked) <= max_neighbors:
            return ranked

        target_lc = target_title.lower()

        def score(title: str) -> Tuple[int, int, int]:
            title_lc = title.lower()
            tokens = WikiPathFinder._tokenize_title(title)
            overlap = len(tokens & target_tokens) if target_tokens else 0
            contains_target = 1 if target_lc and target_lc in title_lc else 0
            # Более короткие названия чаще являются общими сущностями, а не списками.
            return (contains_target, overlap, -len(title_lc))

        ranked.sort(key=score, reverse=True)
        return ranked[:max_neighbors]

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

    async def _search_bidirectional(
        self,
        start: str,
        end: str,
        *,
        time_budget: float,
        max_neighbors_per_node: Optional[int],
    ) -> Tuple[Optional[List[str]], float]:
        t0 = time.monotonic()

        fwd_front: Set[str] = {start}
        bwd_front: Set[str] = {end}

        prev_fwd: Dict[str, Optional[str]] = {start: None}
        prev_bwd: Dict[str, Optional[str]] = {end: None}

        dist_fwd: Dict[str, int] = {start: 0}
        dist_bwd: Dict[str, int] = {end: 0}

        best_len = float("inf")
        meet: Optional[str] = None

        end_tokens = self._tokenize_title(end)
        start_tokens = self._tokenize_title(start)

        while fwd_front and bwd_front and (time.monotonic() - t0) < time_budget:
            # Раннее завершение, если уже встретились фронты на границе уровней.
            border_intersection = fwd_front & bwd_front
            if border_intersection:
                border_node = next(iter(border_intersection))
                path = self._reconstruct_path(prev_fwd, prev_bwd, border_node)
                return path, time.monotonic() - t0

            min_f = min(dist_fwd[n] for n in fwd_front)
            min_b = min(dist_bwd[n] for n in bwd_front)
            if min_f + min_b >= best_len:
                break

            expand_fwd = len(fwd_front) <= len(bwd_front)
            if expand_fwd:
                current_front = list(fwd_front)
                tasks = [self._client.fetch_links(node) for node in current_front]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                next_front: Set[str] = set()
                for node, neighs in zip(current_front, results):
                    if isinstance(neighs, Exception):
                        continue
                    ranked_neighbors = self._rank_neighbors(
                        neighs,
                        target_tokens=end_tokens,
                        target_title=end,
                        max_neighbors=max_neighbors_per_node,
                    )
                    d = dist_fwd[node]
                    for nbr in ranked_neighbors:
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
                current_front = list(bwd_front)
                tasks = [self._client.fetch_backlinks(node) for node in current_front]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                next_front: Set[str] = set()
                for node, neighs in zip(current_front, results):
                    if isinstance(neighs, Exception):
                        continue
                    ranked_neighbors = self._rank_neighbors(
                        neighs,
                        target_tokens=start_tokens,
                        target_title=start,
                        max_neighbors=max_neighbors_per_node,
                    )
                    d = dist_bwd[node]
                    for nbr in ranked_neighbors:
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

        if best_len < float("inf") and meet:
            return self._reconstruct_path(prev_fwd, prev_bwd, meet), time.monotonic() - t0

        return None, time.monotonic() - t0

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

        # Сначала быстрый проход с ограничением ветвления, затем точный fallback.
        fast_budget = min(10.0, self._time_limit * 0.6)
        fast_path, _ = await self._search_bidirectional(
            start,
            end,
            time_budget=fast_budget,
            max_neighbors_per_node=120,
        )
        if fast_path:
            elapsed = time.monotonic() - t0
            return WikiPathResult(path=fast_path, elapsed_time=elapsed, steps_count=len(fast_path))

        spent = time.monotonic() - t0
        remaining = self._time_limit - spent
        if remaining <= 0:
            return WikiPathResult(elapsed_time=spent)

        exact_path, _ = await self._search_bidirectional(
            start,
            end,
            time_budget=remaining,
            max_neighbors_per_node=None,
        )

        elapsed = time.monotonic() - t0
        if exact_path:
            return WikiPathResult(path=exact_path, elapsed_time=elapsed, steps_count=len(exact_path))

        return WikiPathResult(elapsed_time=elapsed)
