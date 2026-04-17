from __future__ import annotations

import itertools
import json
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_collatz_refinement_signature_audit import (
    SIGNATURE_DEPTH,
    STATE_MODULI,
    child_states,
    exact_signature,
    is_resolved,
    signature_stats,
    unresolved_states,
)


def v2(n: int) -> int:
    count = 0
    while n % 2 == 0 and n > 0:
        n //= 2
        count += 1
    return count


@lru_cache(None)
def first_resolved_depth(modulus: int, residue: int, depth: int = SIGNATURE_DEPTH) -> int:
    signature = exact_signature(modulus, residue, depth)
    if signature[0] == "R":
        return 0
    if signature[0] == "U":
        return depth + 1

    def walk(node: tuple, current_depth: int) -> int:
        tag = node[0]
        if tag == "R":
            return current_depth
        if tag == "U":
            return depth + 1
        return min(walk(node[1], current_depth + 1), walk(node[2], current_depth + 1))

    return walk(signature, 0)


def feature_vector(modulus: int, residue: int) -> dict[str, int]:
    sig_stats = signature_stats(exact_signature(modulus, residue, SIGNATURE_DEPTH))
    return {
        "modulus_bits": modulus.bit_length(),
        "residue": residue,
        "residue_bucket_128": residue // 128,
        "distance_to_top": modulus - residue,
        "residue_plus_one_v2": v2(residue + 1),
        "three_r_plus_one_v2": v2(3 * residue + 1),
        "popcount_residue": residue.bit_count(),
        "first_resolved_depth": first_resolved_depth(modulus, residue),
        "resolved_leaves_h": sig_stats["resolved_leaves"],
        "unresolved_leaves_h": sig_stats["unresolved_leaves"],
        "branching_nodes_h": sig_stats["branching_nodes"],
    }


def all_edges() -> list[tuple[tuple[int, int], tuple[int, int]]]:
    edges = []
    allowed_moduli = set(STATE_MODULI)
    for modulus in STATE_MODULI[:-1]:
        for state in unresolved_states(modulus):
            for child in child_states(*state):
                if child[0] in allowed_moduli and not is_resolved(*child):
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
        "residue",
        "residue_bucket_128",
        "distance_to_top",
        "residue_plus_one_v2",
        "three_r_plus_one_v2",
        "popcount_residue",
        "first_resolved_depth",
        "resolved_leaves_h",
        "unresolved_leaves_h",
        "branching_nodes_h",
    ]
    specs: list[tuple[tuple[str, int], ...]] = []
    for length in [1, 2, 3]:
        for combo in itertools.combinations(feature_names, length):
            for signs in itertools.product([-1, 1], repeat=length):
                specs.append(tuple(zip(combo, signs, strict=True)))
    return specs


def format_spec(spec: tuple[tuple[str, int], ...]) -> list[dict[str, str]]:
    return [
        {
            "feature": name,
            "orientation": "larger_is_better" if sign == -1 else "smaller_is_better",
        }
        for name, sign in spec
    ]


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
        "verdict": "refinement_arithmetic_measure_search",
        "signature_depth": SIGNATURE_DEPTH,
        "state_moduli": STATE_MODULI,
        "unresolved_state_count": len(states),
        "edge_count": len(edges),
        "candidate_spec_count": len(candidate_feature_specs()),
        "exact_lex_measures": [format_spec(spec) for spec in exact_hits],
        "best_partial_measure": {
            "spec": format_spec(best_spec or ()),
            "decreasing_edge_count": best_count,
            "coverage_ratio": 0.0 if not edges else best_count / len(edges),
        },
        "interpretation": (
            "This extends the earlier local-count measure search by mixing arithmetic residue "
            "features with horizon-limited structural signature features. If this substantially "
            "improves coverage, the missing theorem likely needs arithmetic state rather than "
            "pure tree shape."
        ),
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
