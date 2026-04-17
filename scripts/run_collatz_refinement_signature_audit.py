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


SIGNATURE_DEPTH = 5
STATE_MODULI = [4096, 8192, 16384]


def child_states(modulus: int, residue: int) -> list[tuple[int, int]]:
    return [(2 * modulus, residue), (2 * modulus, residue + modulus)]


@lru_cache(None)
def certificate_for_state(modulus: int, residue: int) -> dict[str, object] | None:
    return search_descent_certificate(
        Family(modulus, residue),
        max_total_cost=90,
        max_rule_depth=14,
    )


def is_resolved(modulus: int, residue: int) -> bool:
    return certificate_for_state(modulus, residue) is not None


def unresolved_states(modulus: int) -> list[tuple[int, int]]:
    return [(modulus, residue) for residue in range(3, modulus, 2) if not is_resolved(modulus, residue)]


@lru_cache(None)
def exact_signature(modulus: int, residue: int, depth: int) -> tuple:
    if is_resolved(modulus, residue):
        return ("R",)
    if depth == 0:
        return ("U",)
    left_child, right_child = child_states(modulus, residue)
    return (
        "N",
        exact_signature(*left_child, depth - 1),
        exact_signature(*right_child, depth - 1),
    )


def signature_stats(signature: tuple) -> dict[str, int]:
    resolved_leaves = 0
    unresolved_leaves = 0
    branching_nodes = 0
    max_unresolved_depth = 0

    def walk(node: tuple, depth: int) -> None:
        nonlocal resolved_leaves, unresolved_leaves, branching_nodes, max_unresolved_depth
        tag = node[0]
        if tag == "R":
            resolved_leaves += 1
            return
        if tag == "U":
            unresolved_leaves += 1
            if depth > max_unresolved_depth:
                max_unresolved_depth = depth
            return
        branching_nodes += 1
        walk(node[1], depth + 1)
        walk(node[2], depth + 1)

    walk(signature, 0)
    return {
        "resolved_leaves": resolved_leaves,
        "unresolved_leaves": unresolved_leaves,
        "branching_nodes": branching_nodes,
        "max_unresolved_depth": max_unresolved_depth,
    }


def profile_by_signature_depth(signature: tuple) -> list[dict[str, int]]:
    frontier = [signature]
    profile: list[dict[str, int]] = []
    for depth in range(SIGNATURE_DEPTH):
        resolved = 0
        unresolved = 0
        next_frontier: list[tuple] = []
        for node in frontier:
            tag = node[0]
            if tag == "R":
                resolved += 1
            elif tag == "U":
                unresolved += 1
            else:
                left, right = node[1], node[2]
                for child in (left, right):
                    child_tag = child[0]
                    if child_tag == "R":
                        resolved += 1
                    elif child_tag == "U":
                        unresolved += 1
                    else:
                        next_frontier.append(child)
        profile.append(
            {
                "depth": depth + 1,
                "resolved": resolved,
                "unresolved": unresolved,
            }
        )
        frontier = next_frontier
    return profile


def tarjan_scc(graph: dict[str, set[str]]) -> list[list[str]]:
    index = 0
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []

    sys.setrecursionlimit(max(10000, len(graph) * 4))

    def strongconnect(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlink[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for neighbor in sorted(graph.get(node, ())):
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


def build_signature_inventory() -> tuple[dict[tuple, str], list[dict[str, object]]]:
    signature_members: dict[tuple, list[tuple[int, int]]] = defaultdict(list)
    for modulus in STATE_MODULI:
        for state in unresolved_states(modulus):
            signature_members[exact_signature(*state, SIGNATURE_DEPTH)].append(state)

    signature_ids = {
        signature: f"T{i}"
        for i, signature in enumerate(
            sorted(
                signature_members,
                key=lambda sig: (
                    signature_stats(sig)["unresolved_leaves"],
                    signature_stats(sig)["branching_nodes"],
                    sig,
                ),
            ),
            start=1,
        )
    }

    inventory: list[dict[str, object]] = []
    for signature, members in sorted(signature_members.items(), key=lambda item: signature_ids[item[0]]):
        stats = signature_stats(signature)
        inventory.append(
            {
                "signature_id": signature_ids[signature],
                "member_count": len(members),
                "modulus_histogram": dict(Counter(modulus for modulus, _ in members)),
                "sample_members": [
                    {"modulus": modulus, "residue": residue}
                    for modulus, residue in members[:8]
                ],
                "signature_stats": stats,
                "resolution_profile": profile_by_signature_depth(signature),
            }
        )
    return signature_ids, inventory


def build_transition_graph(signature_ids: dict[tuple, str]) -> tuple[list[dict[str, object]], dict[str, set[str]]]:
    graph: dict[str, set[str]] = defaultdict(set)
    summary: list[dict[str, object]] = []
    for modulus in STATE_MODULI[:-1]:
        source_counter: dict[str, Counter[tuple[str, ...]]] = defaultdict(Counter)
        for state in unresolved_states(modulus):
            source_signature = exact_signature(*state, SIGNATURE_DEPTH)
            source_id = signature_ids[source_signature]
            child_signature_ids = []
            for child in child_states(*state):
                if child[0] in STATE_MODULI and not is_resolved(*child):
                    child_id = signature_ids[exact_signature(*child, SIGNATURE_DEPTH)]
                    child_signature_ids.append(child_id)
                    graph[source_id].add(child_id)
            source_counter[source_id][tuple(sorted(child_signature_ids))] += 1
        summary.append(
            {
                "source_modulus": modulus,
                "transition_summary": [
                    {
                        "source_signature_id": source_id,
                        "child_signature_multisets": [
                            {"children": list(child_ids), "count": count}
                            for child_ids, count in counter.most_common()
                        ],
                    }
                    for source_id, counter in sorted(source_counter.items())
                ],
            }
        )
    for signature_id in signature_ids.values():
        graph.setdefault(signature_id, set())
    return summary, graph


def recurrent_core(
    inventory: list[dict[str, object]],
    graph: dict[str, set[str]],
) -> list[dict[str, object]]:
    inventory_by_id = {entry["signature_id"]: entry for entry in inventory}
    components = tarjan_scc(graph)
    result = []
    for component in components:
        is_recurrent = len(component) > 1 or any(node in graph[node] for node in component)
        if not is_recurrent:
            continue
        result.append(
            {
                "component": component,
                "total_member_count": sum(inventory_by_id[node]["member_count"] for node in component),
                "member_summaries": [
                    {
                        "signature_id": node,
                        "member_count": inventory_by_id[node]["member_count"],
                        "signature_stats": inventory_by_id[node]["signature_stats"],
                    }
                    for node in component
                ],
            }
        )
    return sorted(result, key=lambda item: (-item["total_member_count"], item["component"]))


def main() -> int:
    signature_ids, inventory = build_signature_inventory()
    transition_summary, graph = build_transition_graph(signature_ids)
    recurrent_components = recurrent_core(inventory, graph)
    payload = {
        "verdict": "refinement_signature_audit",
        "signature_depth": SIGNATURE_DEPTH,
        "state_moduli": STATE_MODULI,
        "signature_count": len(inventory),
        "signature_inventory": inventory,
        "transition_inventory": transition_summary,
        "recurrent_signature_core": recurrent_components,
        "interpretation": (
            "This is a stronger search audit than the local child-count compass. It groups "
            "unresolved states by their exact resolved/unresolved dyadic tree out to a fixed "
            "horizon and then studies how those exact signatures transition under one more "
            "refinement step."
        ),
        "next_signal": (
            "If the recurrent signature core stays tiny, the next missing theorem is likely a "
            "closure lemma for one or a few exact refinement archetypes rather than another "
            "broad residue wave."
        ),
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
