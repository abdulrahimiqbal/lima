from __future__ import annotations

import json
import sys
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_collatz_affine_rewrite_compass import Family, search_descent_certificate


FRONTIER_128 = [27, 31, 39, 47, 63, 71, 79, 91, 95, 103, 111, 123, 127]
ROOT_MODULUS = 256
PARENT_FRONTIER_256 = [27, 31, 47, 63, 71, 91, 103, 111, 127]
REFINEMENT_MODULI = [1024, 4096, 8192, 16384]
K1_SIGNATURE = (0, 1, 6, 12)
K2_SIGNATURE = (1, 6, 17, 34)
FRONTIER_128_TO_OPEN_CHILD_256 = {
    39: 167,
    47: 47,
    71: 71,
    79: 207,
    91: 91,
    95: 223,
    123: 251,
}


@lru_cache(None)
def certificate_for_state(modulus: int, residue: int) -> dict[str, object] | None:
    return search_descent_certificate(
        Family(modulus, residue),
        max_total_cost=90,
        max_rule_depth=14,
    )


def child_residues(parent_residue: int, modulus: int) -> list[int]:
    scale = modulus // ROOT_MODULUS
    return [parent_residue + ROOT_MODULUS * offset for offset in range(scale)]


def frontier_split() -> dict[str, object]:
    rewrite_descended: list[int] = []
    parent_frontier: list[int] = []
    certificates: dict[str, object] = {}
    for residue in FRONTIER_128:
        certificate = certificate_for_state(ROOT_MODULUS, residue)
        if certificate is None:
            parent_frontier.append(residue)
        else:
            rewrite_descended.append(residue)
            certificates[str(residue)] = certificate
    return {
        "frontier_128": FRONTIER_128,
        "rewrite_descended": rewrite_descended,
        "parent_frontier_256": parent_frontier,
        "certificates": certificates,
    }


def parent_signature(parent_residue: int) -> tuple[tuple[int, ...], list[dict[str, int]]]:
    resolved_counts: list[int] = []
    levels: list[dict[str, int]] = []
    for modulus in REFINEMENT_MODULI:
        resolved = 0
        total = modulus // ROOT_MODULUS
        for residue in child_residues(parent_residue, modulus):
            if certificate_for_state(modulus, residue) is not None:
                resolved += 1
        resolved_counts.append(resolved)
        levels.append(
            {
                "modulus": modulus,
                "resolved_child_count": resolved,
                "unresolved_child_count": total - resolved,
                "total_child_count": total,
            }
        )
    return tuple(resolved_counts), levels


def kernel_candidates() -> dict[str, object]:
    grouped: dict[tuple[int, ...], list[int]] = defaultdict(list)
    level_inventory: dict[int, list[dict[str, int]]] = {}
    for parent in PARENT_FRONTIER_256:
        signature, levels = parent_signature(parent)
        grouped[signature].append(parent)
        level_inventory[parent] = levels

    clusters: list[dict[str, object]] = []
    for index, (signature, parents) in enumerate(sorted(grouped.items()), start=1):
        representative_levels = level_inventory[parents[0]]
        clusters.append(
            {
                "cluster_id": f"K{index}",
                "parents": parents,
                "resolved_child_signature": list(signature),
                "unresolved_child_signature": [
                    level["unresolved_child_count"] for level in representative_levels
                ],
                "levels": representative_levels,
            }
        )

    return {
        "parent_frontier_256": PARENT_FRONTIER_256,
        "cluster_count": len(clusters),
        "clusters": clusters,
    }


def frontier128_kernel_projection() -> dict[str, object]:
    parent_signatures: dict[int, tuple[int, ...]] = {}
    for parent in PARENT_FRONTIER_256:
        signature, _ = parent_signature(parent)
        parent_signatures[parent] = signature

    reduction_targets = []
    for residue_128, open_child_256 in FRONTIER_128_TO_OPEN_CHILD_256.items():
        signature, levels = parent_signature(open_child_256)
        reduction_targets.append(
            {
                "frontier_residue_128": residue_128,
                "open_child_256": open_child_256,
                "resolved_child_signature": list(signature),
                "unresolved_child_signature": [
                    level["unresolved_child_count"] for level in levels
                ],
                "lands_in_k2_signature": signature == K2_SIGNATURE,
            }
        )

    k1_roots = [parent for parent, signature in parent_signatures.items() if signature == K1_SIGNATURE]
    k2_roots = [parent for parent, signature in parent_signatures.items() if signature == K2_SIGNATURE]

    return {
        "k1_roots_256": k1_roots,
        "k2_roots_256": k2_roots,
        "frontier128_reduction_targets": reduction_targets,
        "all_reduction_targets_land_in_k2": all(
            item["lands_in_k2_signature"] for item in reduction_targets
        ),
        "interpretation": (
            "Combining the theorem-backed mod-128 child reductions with the refinement-signature "
            "audit shows that every non-K1 frontier root now projects into the same K2 kernel "
            "signature. That compresses the live odd frontier to two coarse kernel classes."
        ),
    }


def build_payload() -> dict[str, object]:
    split = frontier_split()
    kernel = kernel_candidates()
    projection = frontier128_kernel_projection()
    return {
        "verdict": "pro_kernel_audit",
        "architecture": "hybrid_scaffold_hardening",
        "frontier_split": split,
        "kernel_candidates": kernel,
        "frontier128_kernel_projection": projection,
        "minimal_winning_set": [
            "frontier128_split_or_descend",
            "frontier256_factors_through_sccKernel",
            "sccKernel_exact_coverage",
            "sccKernel_positive_drift",
            "explicit_kernel_control_implies_no_dangerous_frontier",
            "no_dangerous_frontier_implies_density_zero_closure",
            "kernel_bound_has_finite_base_coverage",
            "density_zero_closure_pullback_gives_eventual_descent",
        ],
        "first_aristotle_runs": [
            "frontier256_factors_through_sccKernel",
            "sccKernel_exact_coverage",
            "sccKernel_positive_drift",
            "explicit_kernel_control_implies_no_dangerous_frontier",
            "frontier128_split_or_descend",
        ],
        "interpretation": (
            "This audit does not prove the SCC kernel route. It packages the current repo "
            "evidence for the strongest parallel endgame: a 13-to-9 frontier split plus "
            "two coarse parent refinement archetypes that make a finite obstruction quotient "
            "plausible."
        ),
    }


def main() -> int:
    print(json.dumps(build_payload(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
