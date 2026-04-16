from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_collatz_affine_rewrite_compass import Family, RULES, search_descent_certificate


BASE_PARENT_MODULUS = 256
PARENT_FRONTIER = [27, 31, 47, 63, 71, 91, 103, 111, 127]
REFINEMENT_MODULI = [1024, 4096, 8192, 16384]


def classify_root(modulus: int, residue: int) -> dict[str, object]:
    certificate = search_descent_certificate(
        Family(modulus, residue),
        max_total_cost=90,
        max_rule_depth=14,
    )
    return {
        "residue": residue,
        "resolved": certificate is not None,
        "certificate": certificate,
    }


def child_residues(parent_residue: int, modulus: int) -> list[int]:
    scale = modulus // BASE_PARENT_MODULUS
    return [parent_residue + BASE_PARENT_MODULUS * offset for offset in range(scale)]


def parent_profile(parent_residue: int) -> dict[str, object]:
    levels = []
    for modulus in REFINEMENT_MODULI:
        children = [classify_root(modulus, residue) for residue in child_residues(parent_residue, modulus)]
        resolved = [child["residue"] for child in children if child["resolved"]]
        unresolved = [child["residue"] for child in children if not child["resolved"]]
        levels.append(
            {
                "modulus": modulus,
                "resolved_child_count": len(resolved),
                "total_child_count": len(children),
                "resolved_children": resolved,
                "unresolved_children": unresolved,
            }
        )
    return {
        "parent_root_mod_256": parent_residue,
        "levels": levels,
    }


def global_resolution_profile(modulus: int) -> dict[str, object]:
    odd_residues = list(range(3, modulus, 2))
    resolved_count = 0
    unresolved: list[int] = []
    for residue in odd_residues:
        if classify_root(modulus, residue)["resolved"]:
            resolved_count += 1
        else:
            unresolved.append(residue)
    return {
        "modulus": modulus,
        "resolved_count": resolved_count,
        "total_odd_roots": len(odd_residues),
        "resolution_ratio": resolved_count / len(odd_residues),
        "first_unresolved_roots": unresolved[:64],
    }


def cluster_profiles(parent_profiles: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[int, ...], list[int]] = defaultdict(list)
    for profile in parent_profiles:
        signature = tuple(level["resolved_child_count"] for level in profile["levels"])
        grouped[signature].append(int(profile["parent_root_mod_256"]))
    clusters = []
    for signature, parents in sorted(grouped.items()):
        clusters.append(
            {
                "parents": parents,
                "resolved_child_signature": list(signature),
            }
        )
    return clusters


def main() -> int:
    parent_profiles = [parent_profile(parent) for parent in PARENT_FRONTIER]
    global_profiles = [global_resolution_profile(modulus) for modulus in [4096, 8192, 16384]]
    payload = {
        "verdict": "affine_refinement_compass",
        "base_parent_modulus": BASE_PARENT_MODULUS,
        "parent_frontier": PARENT_FRONTIER,
        "rule_inventory": [
            {
                "name": rule.name,
                "cost": rule.cost,
                "modulus": rule.modulus,
                "residue": rule.residue,
                "coeff_numerator": rule.coeff_numerator,
                "coeff_denominator": rule.coeff_denominator,
                "leaf_const": rule.leaf_const,
            }
            for rule in RULES
        ],
        "parent_profiles": parent_profiles,
        "profile_clusters": cluster_profiles(parent_profiles),
        "global_resolution_profiles": global_profiles,
        "interpretation": (
            "The new 1024 and 4096 descent rules harden refined children of the unresolved "
            "mod-256 parents, not the parents themselves. This exposes the real missing "
            "object as a dyadic refinement tree with rewrite closure, rather than a single "
            "rewrite path on each parent family."
        ),
        "next_signal": (
            "A universal proof along this route would need a well-founded theorem saying that "
            "repeated dyadic refinement plus affine rewrite eventually closes every child branch."
        ),
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
