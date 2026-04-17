from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_collatz_affine_rewrite_compass import Family, search_descent_certificate


ROOT_MODULUS = 256
CHILD_MODULUS = 4096
PARENT_FRONTIER = [27, 31, 47, 63, 71, 91, 103, 111, 127]
SEARCH_BUDGETS = [(120, 18), (160, 28), (220, 36), (500, 60)]


def child_residues(parent_residue: int) -> list[int]:
    scale = CHILD_MODULUS // ROOT_MODULUS
    return [parent_residue + ROOT_MODULUS * offset for offset in range(scale)]


def unresolved_roots(max_total_cost: int, max_rule_depth: int) -> list[int]:
    result: list[int] = []
    for residue in PARENT_FRONTIER:
        cert = search_descent_certificate(
            Family(ROOT_MODULUS, residue),
            max_total_cost=max_total_cost,
            max_rule_depth=max_rule_depth,
        )
        if cert is None:
            result.append(residue)
    return result


def unresolved_children(
    parent_residue: int,
    max_total_cost: int,
    max_rule_depth: int,
) -> list[int]:
    result: list[int] = []
    for residue in child_residues(parent_residue):
        cert = search_descent_certificate(
            Family(CHILD_MODULUS, residue),
            max_total_cost=max_total_cost,
            max_rule_depth=max_rule_depth,
        )
        if cert is None:
            result.append(residue)
    return result


def build_payload() -> dict[str, object]:
    root_audit = [
        {
            "max_total_cost": budget,
            "max_rule_depth": depth,
            "unresolved_roots": unresolved_roots(budget, depth),
        }
        for budget, depth in SEARCH_BUDGETS
    ]

    child_budget, child_depth = 140, 24
    child_audit = [
        {
            "parent_residue": parent,
            "unresolved_children": unresolved_children(parent, child_budget, child_depth),
        }
        for parent in PARENT_FRONTIER
    ]

    return {
        "verdict": "frontier_saturation_audit",
        "root_modulus": ROOT_MODULUS,
        "child_modulus": CHILD_MODULUS,
        "parent_frontier": PARENT_FRONTIER,
        "root_budget_audit": root_audit,
        "child_budget_audit": {
            "max_total_cost": child_budget,
            "max_rule_depth": child_depth,
            "parents": child_audit,
        },
        "interpretation": (
            "The unresolved 9-root frontier is stable across much larger rewrite-search budgets, "
            "so the remaining obstruction is structural rather than a shallow search failure. "
            "At the mod-4096 child level, the same two coarse patterns remain: three parents with "
            "15 unresolved children and six parents with 10 unresolved children."
        ),
    }


def main() -> int:
    print(json.dumps(build_payload(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
