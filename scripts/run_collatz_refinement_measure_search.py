from __future__ import annotations

import itertools
import json
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_collatz_affine_rewrite_compass import Family, search_descent_certificate


PROFILE_WINDOW = 4
STATE_MODULI = [4096, 8192, 16384]


def is_resolved(modulus: int, residue: int) -> bool:
    return search_descent_certificate(
        Family(modulus, residue),
        max_total_cost=90,
        max_rule_depth=14,
    ) is not None


def child_states(modulus: int, residue: int) -> list[tuple[int, int]]:
    return [(2 * modulus, residue), (2 * modulus, residue + modulus)]


def unresolved_states(modulus: int) -> list[tuple[int, int]]:
    return [(modulus, residue) for residue in range(3, modulus, 2) if not is_resolved(modulus, residue)]


@lru_cache(None)
def unresolved_leaf_count(modulus: int, residue: int, depth: int) -> int:
    if is_resolved(modulus, residue):
        return 0
    if depth == 0:
        return 1
    return sum(
        unresolved_leaf_count(child_modulus, child_residue, depth - 1)
        for child_modulus, child_residue in child_states(modulus, residue)
    )


@lru_cache(None)
def resolved_child_count(modulus: int, residue: int, depth: int) -> int:
    frontier = [(modulus, residue)]
    resolved = 0
    for _ in range(depth):
        next_frontier: list[tuple[int, int]] = []
        for node_modulus, node_residue in frontier:
            for child_modulus, child_residue in child_states(node_modulus, node_residue):
                if is_resolved(child_modulus, child_residue):
                    resolved += 1
                else:
                    next_frontier.append((child_modulus, child_residue))
        frontier = next_frontier
    return resolved


def feature_vector(modulus: int, residue: int) -> dict[str, int]:
    features: dict[str, int] = {
        "modulus_bits": modulus.bit_length(),
        "residue": residue,
    }
    for depth in range(1, PROFILE_WINDOW + 1):
        features[f"resolved_children_d{depth}"] = resolved_child_count(modulus, residue, depth)
        features[f"unresolved_leaves_d{depth}"] = unresolved_leaf_count(modulus, residue, depth)
    return features


def all_edges() -> list[tuple[tuple[int, int], tuple[int, int]]]:
    edges = []
    for modulus in STATE_MODULI[:-1]:
        for state in unresolved_states(modulus):
            for child in child_states(*state):
                if child[0] in STATE_MODULI and not is_resolved(*child):
                    edges.append((state, child))
    return edges


def oriented_value(features: dict[str, int], feature_name: str, sign: int) -> int:
    return sign * features[feature_name]


def lex_decreases(
    source_features: dict[str, int],
    child_features: dict[str, int],
    feature_spec: tuple[tuple[str, int], ...],
) -> bool:
    source_tuple = tuple(oriented_value(source_features, name, sign) for name, sign in feature_spec)
    child_tuple = tuple(oriented_value(child_features, name, sign) for name, sign in feature_spec)
    return child_tuple < source_tuple


def candidate_feature_specs() -> list[tuple[tuple[str, int], ...]]:
    feature_names = [
        *(f"resolved_children_d{depth}" for depth in range(1, PROFILE_WINDOW + 1)),
        *(f"unresolved_leaves_d{depth}" for depth in range(1, PROFILE_WINDOW + 1)),
    ]
    specs: list[tuple[tuple[str, int], ...]] = []
    for length in [1, 2, 3]:
        for combo in itertools.combinations(feature_names, length):
            for signs in itertools.product([-1, 1], repeat=length):
                specs.append(tuple(zip(combo, signs, strict=True)))
    return specs


def main() -> int:
    states = [state for modulus in STATE_MODULI for state in unresolved_states(modulus)]
    features = {state: feature_vector(*state) for state in states}
    edges = all_edges()

    exact_hits = []
    best_spec = None
    best_count = -1
    for spec in candidate_feature_specs():
        decreasing = sum(
            1
            for source, child in edges
            if lex_decreases(features[source], features[child], spec)
        )
        if decreasing == len(edges):
            exact_hits.append(spec)
        if decreasing > best_count:
            best_spec = spec
            best_count = decreasing

    payload = {
        "verdict": "refinement_measure_search",
        "state_moduli": STATE_MODULI,
        "unresolved_state_count": len(states),
        "edge_count": len(edges),
        "candidate_spec_count": len(candidate_feature_specs()),
        "exact_lex_measures": [
            [{"feature": name, "orientation": "larger_is_better" if sign == -1 else "smaller_is_better"} for name, sign in spec]
            for spec in exact_hits
        ],
        "best_partial_measure": {
            "spec": [
                {"feature": name, "orientation": "larger_is_better" if sign == -1 else "smaller_is_better"}
                for name, sign in (best_spec or ())
            ],
            "decreasing_edge_count": best_count,
            "coverage_ratio": 0.0 if not edges else best_count / len(edges),
        },
        "interpretation": (
            "This searches for a simple lexicographic measure built from local resolved-child "
            "counts and recursive unresolved-leaf counts. An exact hit would be a strong signal "
            "for a finite-state closure theorem; failure suggests the final rank needs richer state."
        ),
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
