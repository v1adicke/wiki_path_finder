from __future__ import annotations

import asyncio
from typing import List

from benchmarking.models import BenchmarkCase, BenchmarkResult
from search.api_client import WikiApiClient
from search.path_finder import WikiPathFinder


def _resolve_status(success: bool, elapsed_sec: float, time_limit: int, error: str | None) -> str:
    if error:
        return "error"
    if success:
        return "success"
    if elapsed_sec >= float(time_limit) * 0.98:
        return "timeout"
    return "not_found"


def _normalize_title(title: str) -> str:
    value = (title or "").strip().replace("_", " ")
    return " ".join(value.split())


async def _run_case_with_finder(
    case: BenchmarkCase,
    *,
    finder: WikiPathFinder,
    time_limit: int,
) -> BenchmarkResult:
    result = await finder.find_path(_normalize_title(case.start), _normalize_title(case.end))
    success = bool(result.success)
    path_len = len(result.path or [])
    status = _resolve_status(success, result.elapsed_time, time_limit, result.error)
    return BenchmarkResult(
        case=case,
        elapsed_sec=result.elapsed_time,
        success=success,
        path_len=path_len,
        status=status,
        error=result.error,
    )


async def run_benchmark(cases: List[BenchmarkCase], time_limit: int, concurrency: int) -> List[BenchmarkResult]:
    semaphore = asyncio.Semaphore(max(1, concurrency))
    results: List[BenchmarkResult] = []

    async with WikiApiClient() as client:
        finder = WikiPathFinder(client=client, time_limit=time_limit)

        async def _run_case(case: BenchmarkCase) -> None:
            async with semaphore:
                try:
                    results.append(await _run_case_with_finder(case, finder=finder, time_limit=time_limit))
                except Exception as exc:
                    results.append(
                        BenchmarkResult(
                            case=case,
                            elapsed_sec=float(time_limit),
                            success=False,
                            path_len=0,
                            status="error",
                            error=str(exc),
                        )
                    )

        await asyncio.gather(*[_run_case(case) for case in cases])

    # In high-concurrency runs, transient API throttling can produce false negatives.
    # Re-check non-error failures one-by-one with a fresh client to mirror normal single search mode.
    if concurrency > 1:
        retry_indexes = [
            idx
            for idx, item in enumerate(results)
            if not item.success and item.status in {"not_found", "timeout"}
        ]

        for idx in retry_indexes:
            case = results[idx].case
            try:
                async with WikiApiClient() as retry_client:
                    retry_finder = WikiPathFinder(client=retry_client, time_limit=time_limit)
                    retry_result = await _run_case_with_finder(case, finder=retry_finder, time_limit=time_limit)
                if retry_result.success:
                    results[idx] = retry_result
            except Exception:
                # Keep the original benchmark result if retry failed unexpectedly.
                pass

    results.sort(key=lambda item: item.case.case_id)
    return results
