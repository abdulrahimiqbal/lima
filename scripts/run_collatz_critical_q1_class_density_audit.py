from __future__ import annotations

import json
import sys
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_collatz_critical_q1_frontier_bridge_audit import (
    OPEN_MOD256_FRONTIER,
    critical_q1_residues,
)


SOURCE_MODULUS = 16384
TARGET_MODULUS = 32768


def class_histogram(source_modulus: int) -> dict[int, int]:
    histogram: defaultdict[int, int] = defaultdict(int)
    for residue in critical_q1_residues(source_modulus):
        histogram[residue % 256] += 1
    return dict(sorted(histogram.items()))


def serialize_fraction(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def build_payload() -> dict[str, object]:
    source_histogram = class_histogram(SOURCE_MODULUS)
    target_histogram = class_histogram(TARGET_MODULUS)

    grouped: defaultdict[tuple[int, int], list[int]] = defaultdict(list)
    class_rows: list[dict[str, object]] = []
    normalized_factors: dict[int, Fraction] = {}

    for residue in OPEN_MOD256_FRONTIER:
        source_count = source_histogram[residue]
        target_count = target_histogram[residue]
        factor = Fraction(target_count, 2 * source_count)
        normalized_factors[residue] = factor
        grouped[(source_count, target_count)].append(residue)
        class_rows.append(
            {
                "residue_mod_256": residue,
                "source_count": source_count,
                "target_count": target_count,
                "normalized_density_factor": {
                    "rational": serialize_fraction(factor),
                    "float": float(factor),
                },
            }
        )

    archetypes = [
        {
            "source_count": source_count,
            "target_count": target_count,
            "normalized_density_factor": {
                "rational": serialize_fraction(Fraction(target_count, 2 * source_count)),
                "float": float(Fraction(target_count, 2 * source_count)),
            },
            "residues_mod_256": residues,
        }
        for (source_count, target_count), residues in sorted(grouped.items())
    ]

    worst_residue = max(normalized_factors, key=normalized_factors.get)
    worst_factor = normalized_factors[worst_residue]

    return {
        "verdict": "critical_q1_class_density_audit",
        "source_modulus": SOURCE_MODULUS,
        "target_modulus": TARGET_MODULUS,
        "open_mod256_frontier": OPEN_MOD256_FRONTIER,
        "class_rows": class_rows,
        "archetypes": archetypes,
        "uniform_normalized_upper_bound": {
            "rational": serialize_fraction(worst_factor),
            "float": float(worst_factor),
        },
        "worst_residue_mod_256": worst_residue,
        "interpretation": (
            "Once the critical Q1 self-cloning branch stabilizes onto the full open mod-256 "
            "frontier, one more dyadic lift step already shows a finite scarcity law. The "
            "per-class critical-lift counts fall into only three archetypes: 1 -> 1, 7 -> 8, "
            "and 22 -> 29. After the natural 1/2 dyadic normalization, those become density "
            "factors 1/2, 4/7, and 29/44, all strictly below 1. So the frontier-shadow of the "
            "critical branch is already classwise subcritical in a direct arithmetic sense."
        ),
    }


def main() -> int:
    print(json.dumps(build_payload(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
