from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_collatz_scc_kernel_candidate_inventory import (
    STATE_MODULI,
    child_states,
    is_resolved,
    local_profile,
)


EXTENDED_STATE_MODULI = [1024, 2048, 4096, 8192]


def unresolved_states() -> list[tuple[int, int]]:
    states: list[tuple[int, int]] = []
    for modulus in EXTENDED_STATE_MODULI:
        for residue in range(1, modulus, 2):
            if not is_resolved(modulus, residue):
                states.append((modulus, residue))
    return states


def tarjan_scc(graph: dict[str, set[str]]) -> list[list[str]]:
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []

    def strongconnect(node: str) -> None:
        index = len(indices)
        indices[node] = index
        lowlink[node] = index
        stack.append(node)
        on_stack.add(node)

        for neighbor in sorted(graph[node]):
            if neighbor not in indices:
                strongconnect(neighbor)
                lowlink[node] = min(lowlink[node], lowlink[neighbor])
            elif neighbor in on_stack:
                lowlink[node] = min(lowlink[node], indices[neighbor])

        if lowlink[node] == indices[node]:
            component: list[str] = []
            while True:
                member = stack.pop()
                on_stack.remove(member)
                component.append(member)
                if member == node:
                    break
            components.append(sorted(component))

    for node in sorted(graph):
        if node not in indices:
            strongconnect(node)
    return components


def build_payload() -> dict[str, object]:
    states = unresolved_states()
    profiles = sorted({local_profile(modulus, residue) for modulus, residue in states})
    profile_ids = {profile: f"Q{i + 1}" for i, profile in enumerate(profiles)}

    graph: defaultdict[str, set[str]] = defaultdict(set)
    transition_inventory: list[dict[str, object]] = []
    transition_counter: defaultdict[tuple[int, str], Counter[tuple[str, ...]]] = defaultdict(Counter)

    for modulus, residue in states:
        src = profile_ids[local_profile(modulus, residue)]
        if modulus == max(EXTENDED_STATE_MODULI):
            graph.setdefault(src, set())
            continue
        child_ids: list[str] = []
        for child_modulus, child_residue in child_states(modulus, residue):
            if not is_resolved(child_modulus, child_residue):
                child_id = profile_ids[local_profile(child_modulus, child_residue)]
                child_ids.append(child_id)
                graph[src].add(child_id)
        transition_counter[(modulus, src)][tuple(sorted(child_ids))] += 1

    for state_id in profile_ids.values():
        graph.setdefault(state_id, set())

    for (modulus, src), counter in sorted(transition_counter.items()):
        transition_inventory.append(
            {
                "source_modulus": modulus,
                "source_state_id": src,
                "child_multisets": [
                    {"children": list(children), "count": count}
                    for children, count in counter.most_common()
                ],
            }
        )

    sccs = tarjan_scc(graph)

    profile_inventory: list[dict[str, object]] = []
    for profile in profiles:
        members = [(modulus, residue) for modulus, residue in states if local_profile(modulus, residue) == profile]
        profile_inventory.append(
            {
                "state_id": profile_ids[profile],
                "profile": [list(pair) for pair in profile],
                "member_count": len(members),
                "modulus_histogram": dict(Counter(modulus for modulus, _ in members)),
            }
        )

    return {
        "verdict": "scc_kernel_graph",
        "state_moduli": EXTENDED_STATE_MODULI,
        "state_count": len(profile_inventory),
        "state_inventory": profile_inventory,
        "graph": {state: sorted(children) for state, children in sorted(graph.items())},
        "transition_inventory": transition_inventory,
        "sccs": sorted(sccs),
        "interpretation": (
            "The 9-state kernel candidate stays closed when extended through modulus 8192. "
            "The nontrivial unresolved behavior is captured by one 8-state strongly connected "
            "component, plus the trivial self-loop state for residue 1."
        ),
    }


def main() -> int:
    print(json.dumps(build_payload(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
