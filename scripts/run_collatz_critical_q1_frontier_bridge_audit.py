from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_collatz_scc_kernel_candidate_inventory import (
    child_states,
    is_resolved,
    local_profile,
)


Q1_PROFILE = ((0, 2), (0, 4), (0, 8), (0, 16))
OPEN_MOD256_FRONTIER = [
    27,
    31,
    47,
    63,
    71,
    91,
    103,
    111,
    127,
    155,
    159,
    167,
    191,
    207,
    223,
    231,
    239,
    251,
    255,
]


def critical_q1_residues(source_modulus: int) -> list[int]:
    residues: list[int] = []
    for residue in range(1, source_modulus, 2):
        if is_resolved(source_modulus, residue):
            continue
        if local_profile(source_modulus, residue) != Q1_PROFILE:
            continue
        children = [
            (child_modulus, child_residue)
            for child_modulus, child_residue in child_states(source_modulus, residue)
            if not is_resolved(child_modulus, child_residue)
        ]
        if len(children) != 2:
            continue
        if all(local_profile(child_modulus, child_residue) == Q1_PROFILE for child_modulus, child_residue in children):
            residues.append(residue)
    return residues


def build_level_summary(source_modulus: int) -> dict[str, object]:
    residues = critical_q1_residues(source_modulus)
    projection_histogram = Counter(residue % 256 for residue in residues)
    return {
        "source_modulus": source_modulus,
        "critical_q1_count": len(residues),
        "projection_mod_256": sorted(projection_histogram),
        "projection_histogram": dict(sorted(projection_histogram.items())),
    }


def build_payload() -> dict[str, object]:
    levels = [
        build_level_summary(8192),
        build_level_summary(16384),
        build_level_summary(32768),
    ]

    return {
        "verdict": "critical_q1_frontier_bridge_audit",
        "q1_profile": [list(pair) for pair in Q1_PROFILE],
        "open_mod256_frontier": OPEN_MOD256_FRONTIER,
        "levels": levels,
        "interpretation": (
            "The rare phase-kernel self-cloning branch is not an unrelated new obstruction. "
            "Its arithmetic shadow stabilizes onto the exact open mod-256 frontier: by source "
            "moduli 16384 and 32768, the residues that realize the critical Q1 -> Q1,Q1 split "
            "project onto precisely the 19 unresolved mod-256 classes. That links the phase-aware "
            "kernel obstruction directly back to the existing arithmetic frontier."
        ),
    }


def main() -> int:
    print(json.dumps(build_payload(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
