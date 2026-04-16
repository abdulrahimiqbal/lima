from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_collatz_affine_rewrite_compass import Family, search_descent_certificate


PROFILE_WINDOW = 4
PROFILE_MODULI = [4096, 8192, 16384]


def is_resolved(modulus: int, residue: int) -> bool:
    return search_descent_certificate(
        Family(modulus, residue),
        max_total_cost=90,
        max_rule_depth=14,
    ) is not None


def child_states(modulus: int, residue: int) -> list[tuple[int, int]]:
    return [(2 * modulus, residue), (2 * modulus, residue + modulus)]


def local_profile(modulus: int, residue: int, levels: int = PROFILE_WINDOW) -> tuple[tuple[int, int], ...]:
    frontier = [(modulus, residue)]
    signature: list[tuple[int, int]] = []
    for _ in range(levels):
        unresolved_children: list[tuple[int, int]] = []
        resolved_count = 0
        for node_modulus, node_residue in frontier:
            for child_modulus, child_residue in child_states(node_modulus, node_residue):
                if is_resolved(child_modulus, child_residue):
                    resolved_count += 1
                else:
                    unresolved_children.append((child_modulus, child_residue))
        signature.append((resolved_count, len(unresolved_children)))
        frontier = unresolved_children
    return tuple(signature)


def unresolved_states(modulus: int) -> list[tuple[int, int]]:
    return [(modulus, residue) for residue in range(3, modulus, 2) if not is_resolved(modulus, residue)]


def cluster_inventory() -> tuple[dict[tuple[tuple[int, int], ...], str], list[dict[str, object]]]:
    clusters: dict[tuple[tuple[int, int], ...], list[tuple[int, int]]] = defaultdict(list)
    for modulus in PROFILE_MODULI:
        for state in unresolved_states(modulus):
            clusters[local_profile(*state)].append(state)
    profile_ids = {profile: f"S{i}" for i, profile in enumerate(sorted(clusters), start=1)}
    inventory = []
    for profile in sorted(clusters):
        members = clusters[profile]
        inventory.append(
            {
                "profile_id": profile_ids[profile],
                "local_profile": [list(pair) for pair in profile],
                "member_count": len(members),
                "modulus_histogram": dict(Counter(modulus for modulus, _ in members)),
                "sample_members": [
                    {"modulus": modulus, "residue": residue} for modulus, residue in members[:8]
                ],
            }
        )
    return profile_ids, inventory


def transition_inventory(
    profile_ids: dict[tuple[tuple[int, int], ...], str]
) -> list[dict[str, object]]:
    inventories = []
    for modulus in [4096, 8192]:
        transitions: dict[str, Counter[tuple[str, ...]]] = defaultdict(Counter)
        for state in unresolved_states(modulus):
            source_id = profile_ids[local_profile(*state)]
            child_profile_ids = []
            for child in child_states(*state):
                if not is_resolved(*child):
                    child_profile_ids.append(profile_ids[local_profile(*child)])
            transitions[source_id][tuple(sorted(child_profile_ids))] += 1
        inventories.append(
            {
                "source_modulus": modulus,
                "transition_summary": [
                    {
                        "source_profile_id": source_id,
                        "child_profile_multisets": [
                            {"children": list(child_ids), "count": count}
                            for child_ids, count in counter.most_common()
                        ],
                    }
                    for source_id, counter in sorted(transitions.items())
                ],
            }
        )
    return inventories


def main() -> int:
    profile_ids, profiles = cluster_inventory()
    payload = {
        "verdict": "refinement_transition_compass",
        "profile_window": PROFILE_WINDOW,
        "profile_moduli": PROFILE_MODULI,
        "profile_inventory": profiles,
        "transition_inventory": transition_inventory(profile_ids),
        "interpretation": (
            "This is a search compass, not a proof. It clusters unresolved dyadic refinement "
            "states by their next four levels of resolved/unresolved child counts and records "
            "how those profile classes transition under one-bit refinement."
        ),
        "next_signal": (
            "If these profile classes stay small and structured as the modulus grows, the next "
            "proof target is to replace this compass with a genuine finite-state closure or "
            "well-foundedness theorem in Lean."
        ),
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
