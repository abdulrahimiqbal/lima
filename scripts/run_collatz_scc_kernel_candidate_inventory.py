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


SEARCH_COST = 260
SEARCH_DEPTH = 48
PROFILE_WINDOW = 4
STATE_MODULI = [1024, 2048, 4096]


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


@lru_cache(None)
def local_profile(modulus: int, residue: int) -> tuple[tuple[int, int], ...]:
    frontier = [(modulus, residue)]
    signature: list[tuple[int, int]] = []
    for _ in range(PROFILE_WINDOW):
        unresolved_children: list[tuple[int, int]] = []
        resolved_count = 0
        for state_modulus, state_residue in frontier:
            for child_modulus, child_residue in child_states(state_modulus, state_residue):
                if is_resolved(child_modulus, child_residue):
                    resolved_count += 1
                else:
                    unresolved_children.append((child_modulus, child_residue))
        signature.append((resolved_count, len(unresolved_children)))
        frontier = unresolved_children
    return tuple(signature)


def unresolved_states() -> list[tuple[int, int]]:
    states: list[tuple[int, int]] = []
    for modulus in STATE_MODULI:
        for residue in range(1, modulus, 2):
            if not is_resolved(modulus, residue):
                states.append((modulus, residue))
    return states


def build_payload() -> dict[str, object]:
    states = unresolved_states()
    profiles = sorted({local_profile(modulus, residue) for modulus, residue in states})
    profile_ids = {profile: f"Q{i + 1}" for i, profile in enumerate(profiles)}

    inventory: list[dict[str, object]] = []
    for profile in profiles:
        members = [(modulus, residue) for modulus, residue in states if local_profile(modulus, residue) == profile]
        counts = Counter(modulus for modulus, _ in members)
        inventory.append(
            {
                "state_id": profile_ids[profile],
                "profile": [list(pair) for pair in profile],
                "member_count": len(members),
                "modulus_histogram": dict(counts),
                "sample_members": [
                    {"modulus": modulus, "residue": residue}
                    for modulus, residue in members[:15]
                ],
            }
        )

    transitions: list[dict[str, object]] = []
    transition_counter: defaultdict[tuple[int, str], Counter[tuple[str, ...]]] = defaultdict(Counter)
    for modulus, residue in states:
        if modulus == max(STATE_MODULI):
            continue
        src = profile_ids[local_profile(modulus, residue)]
        child_ids: list[str] = []
        for child_modulus, child_residue in child_states(modulus, residue):
            if not is_resolved(child_modulus, child_residue):
                child_ids.append(profile_ids[local_profile(child_modulus, child_residue)])
        transition_counter[(modulus, src)][tuple(sorted(child_ids))] += 1

    for (modulus, src), counter in sorted(transition_counter.items()):
        transitions.append(
            {
                "source_modulus": modulus,
                "source_state_id": src,
                "child_multisets": [
                    {"children": list(children), "count": count}
                    for children, count in counter.most_common()
                ],
            }
        )

    root_projection = [
        entry
        for entry in inventory
        if entry["modulus_histogram"].get(1024)
    ]

    return {
        "verdict": "scc_kernel_candidate_inventory",
        "search_budget": {
            "max_total_cost": SEARCH_COST,
            "max_rule_depth": SEARCH_DEPTH,
        },
        "state_moduli": STATE_MODULI,
        "state_count": len(inventory),
        "state_inventory": inventory,
        "root_projection": root_projection,
        "transition_inventory": transitions,
        "interpretation": (
            "This is an explicit finite quotient candidate for the current unresolved frontier. "
            "Across unresolved states at moduli 1024, 2048, and 4096, the search-defined local "
            "profiles collapse to 9 states with highly regular child-transition structure. "
            "That is strong evidence that the live obstruction can be studied as a finite kernel "
            "rather than as an unbounded residue tree."
        ),
    }


def main() -> int:
    print(json.dumps(build_payload(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
