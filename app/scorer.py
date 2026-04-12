from __future__ import annotations

from .schemas import ExecutionResult


def score_result(result: ExecutionResult) -> float:
    if result.status == "proved":
        return 1.0
    if result.status == "refuted":
        return 0.5
    if result.status == "blocked":
        return -0.2
    return -0.05
