from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    start: str
    end: str
    difficulty: str


@dataclass
class BenchmarkResult:
    case: BenchmarkCase
    elapsed_sec: float
    success: bool
    path_len: int
    status: str
    error: Optional[str] = None


@dataclass(frozen=True)
class BenchmarkConfig:
    total_cases: int = 240
    time_limit: int = 40
    concurrency: int = 8
