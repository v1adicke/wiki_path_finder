from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from benchmarking.case_generator import generate_cases
from benchmarking.metrics import summarize_results
from benchmarking.models import BenchmarkConfig
from benchmarking.runner import run_benchmark


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Wiki Path Finder benchmark service")
    parser.add_argument("--total-cases", type=int, default=240, help="Количество сценариев")
    parser.add_argument("--time-limit", type=int, default=40, help="Тайм-лимит на один поиск (сек)")
    parser.add_argument("--concurrency", type=int, default=8, help="Параллелизм выполнения")
    parser.add_argument("--seed", type=int, default=42, help="Seed генератора сценариев")
    parser.add_argument("--out-json", type=str, default="reports/metrics.json", help="Путь JSON с метриками")
    return parser.parse_args()


async def run_service(config: BenchmarkConfig, seed: int, out_json: str) -> None:
    cases = generate_cases(total_cases=config.total_cases, seed=seed)
    results = await run_benchmark(cases=cases, time_limit=config.time_limit, concurrency=config.concurrency)

    summary = summarize_results(results)

    out_json_path = Path(out_json)
    out_json_path.parent.mkdir(parents=True, exist_ok=True)
    with out_json_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def main() -> None:
    args = _parse_args()
    config = BenchmarkConfig(
        total_cases=max(3, args.total_cases),
        time_limit=max(5, args.time_limit),
        concurrency=max(1, args.concurrency),
    )

    asyncio.run(
        run_service(
            config=config,
            seed=args.seed,
            out_json=args.out_json,
        )
    )


if __name__ == "__main__":
    main()
