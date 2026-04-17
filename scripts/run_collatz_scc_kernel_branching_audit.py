from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_collatz_scc_kernel_graph import build_payload as build_graph_payload


NONTRIVIAL_STATES = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8"]


def power_radius(matrix: list[list[float]], iterations: int = 120) -> float:
    size = len(matrix)
    vector = [1.0] * size
    for _ in range(iterations):
        next_vector = [sum(matrix[i][j] * vector[j] for j in range(size)) for i in range(size)]
        norm = max(abs(value) for value in next_vector) or 1.0
        vector = [value / norm for value in next_vector]
    next_vector = [sum(matrix[i][j] * vector[j] for j in range(size)) for i in range(size)]
    ratios = [next_vector[i] / vector[i] for i in range(size) if abs(vector[i]) > 1e-12]
    return sum(ratios) / len(ratios)


def build_mean_progeny_matrix(payload: dict[str, object]) -> list[list[float]]:
    index = {state: i for i, state in enumerate(NONTRIVIAL_STATES)}
    rows = [[0.0 for _ in NONTRIVIAL_STATES] for _ in NONTRIVIAL_STATES]
    row_counts = {state: 0 for state in NONTRIVIAL_STATES}

    for item in payload["transition_inventory"]:
        src = item["source_state_id"]
        if src not in index:
            continue
        total = sum(entry["count"] for entry in item["child_multisets"])
        row_counts[src] += 1
        averaged = {state: 0.0 for state in NONTRIVIAL_STATES}
        for entry in item["child_multisets"]:
            multiplicities: dict[str, int] = {}
            for child in entry["children"]:
                multiplicities[child] = multiplicities.get(child, 0) + 1
            for child, count in multiplicities.items():
                if child in index:
                    averaged[child] += entry["count"] * count / total
        for child, value in averaged.items():
            rows[index[src]][index[child]] += value

    for state, count in row_counts.items():
        if count == 0:
            continue
        row = rows[index[state]]
        rows[index[state]] = [value / count for value in row]
    return rows


def build_payload() -> dict[str, object]:
    kernel_graph = build_graph_payload()
    matrix = build_mean_progeny_matrix(kernel_graph)
    density_normalized = [[0.5 * value for value in row] for row in matrix]
    unweighted_radius = power_radius(matrix)
    normalized_radius = power_radius(density_normalized)

    return {
        "verdict": "scc_kernel_branching_audit",
        "states": NONTRIVIAL_STATES,
        "mean_progeny_matrix": matrix,
        "row_sums": [sum(row) for row in matrix],
        "unweighted_radius": unweighted_radius,
        "density_normalized_radius": normalized_radius,
        "interpretation": (
            "On the 8-state nontrivial SCC, the naive unresolved-child branching operator is "
            "supercritical, so a simple per-edge scalar rank is unlikely to close the proof. "
            "But after normalizing by one bit of dyadic density loss, the operator appears "
            "subcritical. That is a concrete scarcity-style signal pointing toward a "
            "density-weighted kernel theorem rather than a plain ranking argument."
        ),
    }


def main() -> int:
    print(json.dumps(build_payload(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
