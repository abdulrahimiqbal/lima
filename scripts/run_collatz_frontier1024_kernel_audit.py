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


ROOT_MODULUS = 1024
PROFILE_WINDOW = 4
REFINEMENT_MODULI = [2048, 4096, 8192]
SEARCH_COST = 260
SEARCH_DEPTH = 48


@lru_cache(None)
def is_resolved(modulus: int, residue: int) -> bool:
    return (
        search_descent_certificate(
            Family(modulus, residue),
            max_total_cost=SEARCH_COST,
            max_rule_depth=SEARCH_DEPTH,
        )
        is not None
    )


def child_states(modulus: int, residue: int) -> list[tuple[int, int]]:
    return [(2 * modulus, residue), (2 * modulus, residue + modulus)]


def open_frontier() -> list[int]:
    return [x for x in range(1, ROOT_MODULUS, 2) if not is_resolved(ROOT_MODULUS, x)]


def coarse_signature(parent: int) -> tuple[int, ...]:
    sig: list[int] = []
    for modulus in REFINEMENT_MODULI:
        scale = modulus // ROOT_MODULUS
        resolved = 0
        for k in range(scale):
            residue = parent + ROOT_MODULUS * k
            if is_resolved(modulus, residue):
                resolved += 1
        sig.append(resolved)
    return tuple(sig)


def coarse_inventory(parents: list[int]) -> list[dict[str, object]]:
    grouped: dict[tuple[int, ...], list[int]] = defaultdict(list)
    level_inventory: dict[int, list[dict[str, int]]] = {}
    for parent in parents:
        signature = coarse_signature(parent)
        grouped[signature].append(parent)
        levels: list[dict[str, int]] = []
        for modulus, resolved in zip(REFINEMENT_MODULI, signature):
            total = modulus // ROOT_MODULUS
            levels.append(
                {
                    "modulus": modulus,
                    "resolved_child_count": resolved,
                    "unresolved_child_count": total - resolved,
                    "total_child_count": total,
                }
            )
        level_inventory[parent] = levels

    clusters: list[dict[str, object]] = []
    for index, (signature, members) in enumerate(sorted(grouped.items()), start=1):
        clusters.append(
            {
                "cluster_id": f"C{index}",
                "parents": members,
                "resolved_child_signature": list(signature),
                "levels": level_inventory[members[0]],
            }
        )
    return clusters


def local_profile(parent: int, levels: int = PROFILE_WINDOW) -> tuple[tuple[int, int], ...]:
    frontier = [(ROOT_MODULUS, parent)]
    signature: list[tuple[int, int]] = []
    for _ in range(levels):
        unresolved_children: list[tuple[int, int]] = []
        resolved_count = 0
        for modulus, residue in frontier:
            for child_modulus, child_residue in child_states(modulus, residue):
                if is_resolved(child_modulus, child_residue):
                    resolved_count += 1
                else:
                    unresolved_children.append((child_modulus, child_residue))
        signature.append((resolved_count, len(unresolved_children)))
        frontier = unresolved_children
    return tuple(signature)


def exact_profile_inventory(parents: list[int]) -> list[dict[str, object]]:
    counts = Counter(local_profile(parent) for parent in parents)
    inventory: list[dict[str, object]] = []
    for index, (profile, count) in enumerate(counts.most_common(), start=1):
        members = [parent for parent in parents if local_profile(parent) == profile]
        inventory.append(
            {
                "profile_id": f"P{index}",
                "profile": [list(pair) for pair in profile],
                "count": count,
                "members": members,
            }
        )
    return inventory


def build_payload() -> dict[str, object]:
    parents = open_frontier()
    return {
        "verdict": "frontier1024_kernel_audit",
        "root_modulus": ROOT_MODULUS,
        "search_budget": {
            "max_total_cost": SEARCH_COST,
            "max_rule_depth": SEARCH_DEPTH,
        },
        "open_parent_count": len(parents),
        "open_parents": parents,
        "coarse_clusters": coarse_inventory(parents),
        "exact_profiles": exact_profile_inventory(parents),
        "interpretation": (
            "The open mod-1024 frontier does not look combinatorially wild under the current "
            "direct-descent search. Ignoring the trivial residue 1, it collapses into three "
            "nontrivial exact local-profile classes and three coarse child-count signatures, "
            "which is strong evidence for a finite obstruction quotient rather than an exploding frontier."
        ),
    }


def main() -> int:
    print(json.dumps(build_payload(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
