from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_collatz_affine_rewrite_compass import Family, search_descent_certificate


ROOT_RESIDUES = [27, 31, 39, 47, 63, 71, 79, 91, 95, 103, 111, 123, 127]
MODULI = [128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536]


@lru_cache(None)
def unresolved(modulus: int, residue: int) -> bool:
    return search_descent_certificate(
        Family(modulus, residue),
        max_total_cost=90,
        max_rule_depth=14,
    ) is None


def unresolved_count_in_cylinder(root_residue: int, modulus: int) -> int:
    count = 0
    for residue in range(root_residue, modulus, 128):
        if residue % 2 == 1 and unresolved(modulus, residue):
            count += 1
    return count


def child_unresolved_count(modulus: int, residue: int) -> int:
    children = [(2 * modulus, residue), (2 * modulus, residue + modulus)]
    return sum(1 for child_modulus, child_residue in children if unresolved(child_modulus, child_residue))


def cylinder_sequence(root_residue: int) -> tuple[int, ...]:
    return tuple(unresolved_count_in_cylinder(root_residue, modulus) for modulus in MODULI)


def split_histogram(root_residue: int, modulus: int) -> dict[int, int]:
    histogram: Counter[int] = Counter()
    for residue in range(root_residue, modulus, 128):
        if residue % 2 == 1 and unresolved(modulus, residue):
            histogram[child_unresolved_count(modulus, residue)] += 1
    return dict(histogram)


def main() -> int:
    sequences = {root: cylinder_sequence(root) for root in ROOT_RESIDUES}
    by_archetype: dict[tuple[int, ...], list[int]] = defaultdict(list)
    for root, sequence in sequences.items():
        by_archetype[sequence].append(root)

    payload = {
        "verdict": "cylinder_persistence_audit",
        "root_residues_mod_128": ROOT_RESIDUES,
        "moduli": MODULI,
        "cylinder_sequences": {
            str(root): list(sequence) for root, sequence in sequences.items()
        },
        "archetypes": [
            {
                "roots": members,
                "unresolved_count_sequence": list(sequence),
                "split_histograms": {
                    str(modulus): split_histogram(members[0], modulus)
                    for modulus in MODULI[:-1]
                },
            }
            for sequence, members in sorted(by_archetype.items(), key=lambda item: item[1])
        ],
        "interpretation": (
            "This audit checks whether the 13 unresolved mod-128 residue cylinders persist "
            "under deeper dyadic refinement and whether they collapse into a small number of "
            "shared growth archetypes."
        ),
        "next_signal": (
            "If all cylinders persist but only a few exact archetypes remain, the next proof "
            "target is an infinite-branch exclusion or drift theorem for those archetypes "
            "rather than one theorem per residue."
        ),
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
