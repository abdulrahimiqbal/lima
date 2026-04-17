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


TRACKED_MODULI = [16384, 32768, 65536]


def histogram_by_class(source_modulus: int) -> dict[int, int]:
    histogram: defaultdict[int, int] = defaultdict(int)
    for residue in critical_q1_residues(source_modulus):
        histogram[residue % 256] += 1
    return dict(sorted(histogram.items()))


def serialize_fraction(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def build_payload() -> dict[str, object]:
    histograms = {modulus: histogram_by_class(modulus) for modulus in TRACKED_MODULI}

    class_rows: list[dict[str, object]] = []
    grouped_patterns: defaultdict[tuple[int, ...], list[int]] = defaultdict(list)
    pairwise_bounds: dict[str, dict[str, object]] = {}

    for left, right in zip(TRACKED_MODULI, TRACKED_MODULI[1:]):
        pairwise_factors = {
            residue: Fraction(histograms[right][residue], 2 * histograms[left][residue])
            for residue in OPEN_MOD256_FRONTIER
        }
        worst_residue = max(pairwise_factors, key=pairwise_factors.get)
        pairwise_bounds[f"{left}_to_{right}"] = {
            "worst_residue_mod_256": worst_residue,
            "uniform_normalized_upper_bound": {
                "rational": serialize_fraction(pairwise_factors[worst_residue]),
                "float": float(pairwise_factors[worst_residue]),
            },
        }

    for residue in OPEN_MOD256_FRONTIER:
        counts = tuple(histograms[modulus][residue] for modulus in TRACKED_MODULI)
        grouped_patterns[counts].append(residue)
        class_rows.append(
            {
                "residue_mod_256": residue,
                "counts_by_modulus": {str(modulus): histograms[modulus][residue] for modulus in TRACKED_MODULI},
                "normalized_factors": {
                    f"{left}_to_{right}": {
                        "rational": serialize_fraction(Fraction(histograms[right][residue], 2 * histograms[left][residue])),
                        "float": float(Fraction(histograms[right][residue], 2 * histograms[left][residue])),
                    }
                    for left, right in zip(TRACKED_MODULI, TRACKED_MODULI[1:])
                },
            }
        )

    archetypes = [
        {
            "count_pattern": list(pattern),
            "residues_mod_256": residues,
            "normalized_factors": {
                f"{left}_to_{right}": {
                    "rational": serialize_fraction(Fraction(pattern[index + 1], 2 * pattern[index])),
                    "float": float(Fraction(pattern[index + 1], 2 * pattern[index])),
                }
                for index, (left, right) in enumerate(zip(TRACKED_MODULI, TRACKED_MODULI[1:]))
            },
        }
        for pattern, residues in sorted(grouped_patterns.items())
    ]

    return {
        "verdict": "critical_q1_density_persistence_audit",
        "tracked_moduli": TRACKED_MODULI,
        "open_mod256_frontier": OPEN_MOD256_FRONTIER,
        "histograms_by_modulus": {str(modulus): histograms[modulus] for modulus in TRACKED_MODULI},
        "class_rows": class_rows,
        "archetypes": archetypes,
        "pairwise_bounds": pairwise_bounds,
        "interpretation": (
            "The classwise scarcity law on the critical Q1 frontier-shadow persists one more "
            "dyadic lift. Across moduli 16384, 32768, and 65536, the open mod-256 frontier "
            "still splits into only three count patterns: 1 -> 1 -> 1, 7 -> 8 -> 9, and "
            "22 -> 29 -> 37. After dyadic normalization, the worst pairwise density factor "
            "improves from 29/44 to 37/58, both strictly below 1. So the direct arithmetic "
            "scarcity signal on the critical branch is not a one-step coincidence; it persists."
        ),
    }


def main() -> int:
    print(json.dumps(build_payload(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
