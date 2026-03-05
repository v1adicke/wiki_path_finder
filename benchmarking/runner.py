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


async def run_benchmark(cases: List[BenchmarkCase], time_limit: int, concurrency: int) -> List[BenchmarkResult]:
    semaphore = asyncio.Semaphore(max(1, concurrency))
    results: List[BenchmarkResult] = []

    async with WikiApiClient() as client:
        finder = WikiPathFinder(client=client, time_limit=time_limit)

        async def _run_case(case: BenchmarkCase) -> None:
            async with semaphore:
                try:
                    result = await finder.find_path(case.start, case.end)
                    success = bool(result.success)
                    path_len = len(result.path or [])
                    status = _resolve_status(success, result.elapsed_time, time_limit, result.error)
                    results.append(
                        BenchmarkResult(
                            case=case,
                            elapsed_sec=result.elapsed_time,
                            success=success,
                            path_len=path_len,
                            status=status,
                            error=result.error,
                        )
                    )
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

    results.sort(key=lambda item: item.case.case_id)
    return results
