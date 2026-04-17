from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_collatz_affine_rewrite_compass import Family, search_descent_certificate


OPEN_MOD256 = [
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

OPEN_MOD512 = [
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
    283,
    287,
    303,
    319,
    327,
    347,
    359,
    367,
    383,
    411,
    415,
    423,
    447,
    463,
    479,
    487,
    495,
    507,
    511,
]


def resolved_signature(
    roots: list[int],
    *,
    root_modulus: int,
    child_modulus_base: int,
    audit_moduli: list[int],
    max_total_cost: int = 140,
    max_rule_depth: int = 24,
) -> dict[str, object]:
    grouped: dict[tuple[int, ...], list[int]] = defaultdict(list)
    level_counts: dict[int, list[dict[str, int]]] = {}
    for residue in roots:
        counts: list[int] = []
        levels: list[dict[str, int]] = []
        for modulus in audit_moduli:
            scale = modulus // child_modulus_base
            resolved = 0
            for offset in range(scale):
                child_residue = residue + child_modulus_base * offset
                cert = search_descent_certificate(
                    Family(modulus, child_residue),
                    max_total_cost=max_total_cost,
                    max_rule_depth=max_rule_depth,
                )
                if cert is not None:
                    resolved += 1
            counts.append(resolved)
            levels.append(
                {
                    "modulus": modulus,
                    "resolved_child_count": resolved,
                    "unresolved_child_count": scale - resolved,
                    "total_child_count": scale,
                }
            )
        signature = tuple(counts)
        grouped[signature].append(residue)
        level_counts[residue] = levels

    clusters = []
    for index, (signature, residues) in enumerate(sorted(grouped.items()), start=1):
        representative = residues[0]
        clusters.append(
            {
                "cluster_id": f"S{index}",
                "residues": residues,
                "resolved_signature": list(signature),
                "unresolved_signature": [
                    level["unresolved_child_count"] for level in level_counts[representative]
                ],
                "levels": level_counts[representative],
            }
        )

    return {
        "root_modulus": root_modulus,
        "child_modulus_base": child_modulus_base,
        "audit_moduli": audit_moduli,
        "cluster_count": len(clusters),
        "clusters": clusters,
    }


def build_payload() -> dict[str, object]:
    open_mod256_lift_signatures = resolved_signature(
        OPEN_MOD256,
        root_modulus=256,
        child_modulus_base=512,
        audit_moduli=[1024, 2048, 4096, 8192],
    )
    open_mod512_lift_signatures = resolved_signature(
        OPEN_MOD512,
        root_modulus=512,
        child_modulus_base=1024,
        audit_moduli=[2048, 4096, 8192, 16384],
    )
    return {
        "verdict": "kernel_refinement_audit",
        "open_mod256_lift_signatures": open_mod256_lift_signatures,
        "open_mod512_lift_signatures": open_mod512_lift_signatures,
        "interpretation": (
            "The unresolved binary refinement kernel continues to compress under one deeper "
            "lift-signature audit: the open mod-256 residue set falls into three classes when "
            "sampled on larger 512-spaced lifts, and the open mod-512 residue set falls into "
            "four classes when sampled on larger 1024-spaced lifts. This is search-only "
            "evidence about coarse finite-state structure, not an exact theorem about child closure."
        ),
    }


def main() -> int:
    print(json.dumps(build_payload(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
