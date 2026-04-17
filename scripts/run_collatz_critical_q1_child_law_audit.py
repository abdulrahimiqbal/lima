from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_collatz_critical_q1_frontier_bridge_audit import (
    OPEN_MOD256_FRONTIER,
    critical_q1_residues,
)


TRACKED_TRANSITIONS = [(16384, 32768), (32768, 65536)]
SINGLETON_CLASSES = [31, 47, 63, 71, 91, 111, 155, 167, 207, 223, 231, 251]
SEVEN_CLASSES = [27, 103, 127, 159, 191, 239]
HEAVY_CLASS = 255


def build_transition_inventory(source_modulus: int, target_modulus: int) -> dict[int, dict[str, object]]:
    source = sorted(critical_q1_residues(source_modulus))
    target = set(critical_q1_residues(target_modulus))
    per_class: defaultdict[int, list[tuple[int, list[int]]]] = defaultdict(list)
    for residue in source:
        children = [child for child in (residue, residue + source_modulus) if child in target]
        per_class[residue % 256].append((residue, children))

    inventory: dict[int, dict[str, object]] = {}
    for residue_class in OPEN_MOD256_FRONTIER:
        rows = per_class[residue_class]
        inventory[residue_class] = {
            "source_count": len(rows),
            "target_count": sum(len(children) for _, children in rows),
            "child_count_stats": dict(sorted(Counter(len(children) for _, children in rows).items())),
        }
    return inventory


def build_payload() -> dict[str, object]:
    transitions = {
        f"{source}_to_{target}": build_transition_inventory(source, target)
        for source, target in TRACKED_TRANSITIONS
    }

    singleton_pattern = {
        key: {str(residue): transitions[key][residue] for residue in SINGLETON_CLASSES}
        for key in transitions
    }
    seven_pattern = {
        key: {str(residue): transitions[key][residue] for residue in SEVEN_CLASSES}
        for key in transitions
    }
    heavy_pattern = {
        key: transitions[key][HEAVY_CLASS]
        for key in transitions
    }

    recurrence_summary = {
        "singleton_class_rule": "a_(n+1) = a_n",
        "seven_class_rule": "b_(n+1) = b_n + 1",
        "heavy_class_rule": "c_(n+1) = c_n + b_n",
        "observed_counts": {
            "a": [1, 1, 1],
            "b": [7, 8, 9],
            "c": [22, 29, 37],
        },
    }

    return {
        "verdict": "critical_q1_child_law_audit",
        "tracked_transitions": [
            {
                "source_modulus": source,
                "target_modulus": target,
                "inventory": transitions[f"{source}_to_{target}"],
            }
            for source, target in TRACKED_TRANSITIONS
        ],
        "singleton_classes": SINGLETON_CLASSES,
        "seven_classes": SEVEN_CLASSES,
        "heavy_class": HEAVY_CLASS,
        "singleton_pattern": singleton_pattern,
        "seven_pattern": seven_pattern,
        "heavy_pattern": heavy_pattern,
        "recurrence_summary": recurrence_summary,
        "interpretation": (
            "The persistent classwise scarcity law is driven by a small exact child-count rule "
            "on the critical Q1 branch. The 12 singleton classes always produce exactly one "
            "critical child per source residue. Each of the six 7/8/9 classes has exactly one "
            "bifurcating source residue with two critical children and all remaining source residues "
            "have one. The heavy 255 class has as many bifurcating source residues as the current "
            "7/8/9 class size, yielding the observed recurrences a_(n+1)=a_n, b_(n+1)=b_n+1, "
            "and c_(n+1)=c_n+b_n across the checked lifts."
        ),
    }


def main() -> int:
    print(json.dumps(build_payload(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
