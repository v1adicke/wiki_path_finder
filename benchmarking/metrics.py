from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime
from typing import Dict, List

from benchmarking.models import BenchmarkResult


def _safe_mean(values: List[float]) -> float:
    return statistics.mean(values) if values else 0.0


def _safe_median(values: List[float]) -> float:
    return statistics.median(values) if values else 0.0


def _safe_percentile(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int((len(ordered) - 1) * q)
    idx = max(0, min(idx, len(ordered) - 1))
    return ordered[idx]


def summarize_results(results: List[BenchmarkResult]) -> Dict:
    elapsed = [r.elapsed_sec for r in results]
    successful = [r for r in results if r.success]
    status_counter = Counter(r.status for r in results)

    by_difficulty = defaultdict(list)
    for item in results:
        by_difficulty[item.case.difficulty].append(item)

    difficulty_stats = {}
    difficulty_order = ["easy", "medium", "hard", "very_hard"]
    present = set(by_difficulty.keys())
    ordered_difficulties = [d for d in difficulty_order if d in present]
    ordered_difficulties.extend(sorted(present - set(difficulty_order)))

    for difficulty in ordered_difficulties:
        group = by_difficulty.get(difficulty, [])
        total = len(group)
        successes = sum(1 for item in group if item.success)
        avg_time = _safe_mean([item.elapsed_sec for item in group])
        difficulty_stats[difficulty] = {
            "total": total,
            "success_rate": (successes / total * 100.0) if total else 0.0,
            "avg_time": avg_time,
        }

    top_slowest = sorted(results, key=lambda item: item.elapsed_sec, reverse=True)[:10]

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_cases": len(results),
        "success_count": len(successful),
        "success_rate": (len(successful) / len(results) * 100.0) if results else 0.0,
        "avg_time": _safe_mean(elapsed),
        "median_time": _safe_median(elapsed),
        "p90_time": _safe_percentile(elapsed, 0.90),
        "p95_time": _safe_percentile(elapsed, 0.95),
        "max_time": max(elapsed) if elapsed else 0.0,
        "avg_path_len_success": _safe_mean([float(r.path_len) for r in successful]),
        "status_counts": dict(status_counter),
        "difficulty_stats": difficulty_stats,
        "top_slowest": [
            {
                "case_id": item.case.case_id,
                "start": item.case.start,
                "end": item.case.end,
                "difficulty": item.case.difficulty,
                "elapsed_sec": item.elapsed_sec,
                "status": item.status,
            }
            for item in top_slowest
        ],
        "results": [
            {
                **asdict(r.case),
                "elapsed_sec": r.elapsed_sec,
                "success": r.success,
                "path_len": r.path_len,
                "status": r.status,
                "error": r.error,
            }
            for r in results
        ],
    }
    return summary
