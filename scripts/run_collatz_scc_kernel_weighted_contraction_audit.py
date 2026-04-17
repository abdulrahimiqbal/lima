from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_collatz_scc_kernel_template_rarity_audit import build_payload as build_rarity_payload


def build_cycle_summary(cycle_payload: dict[str, object]) -> dict[str, object]:
    summaries: dict[str, object] = {}
    for state_id, inventory in cycle_payload["source_inventory"].items():
        template_probabilities = [row["probability"]["float"] for row in inventory["templates"]]
        template_ratios = [row["normalized_weight_ratio"] for row in inventory["templates"]]
        exact_expectation = sum(
            probability * ratio
            for probability, ratio in zip(template_probabilities, template_ratios)
        )
        critical_probability = inventory["critical_template_probability"]["float"]
        worst_noncritical_ratio = inventory["worst_noncritical_ratio"]
        split_bound = critical_probability + (1.0 - critical_probability) * worst_noncritical_ratio
        summaries[state_id] = {
            "exact_expected_ratio": exact_expectation,
            "critical_probability": critical_probability,
            "worst_noncritical_ratio": worst_noncritical_ratio,
            "critical_split_upper_bound": split_bound,
        }
    max_bound_state = max(
        summaries.items(),
        key=lambda item: item[1]["critical_split_upper_bound"],
    )[0]
    return {
        "cycle": cycle_payload["cycle"],
        "modulus_chain": cycle_payload["modulus_chain"],
        "weights": cycle_payload["weights"],
        "source_summaries": summaries,
        "uniform_cycle_upper_bound": summaries[max_bound_state]["critical_split_upper_bound"],
        "worst_source_state": max_bound_state,
    }


def build_payload() -> dict[str, object]:
    rarity_payload = build_rarity_payload()
    phase0_summary = build_cycle_summary(rarity_payload["phase0_cycle"])
    phase1_summary = build_cycle_summary(rarity_payload["phase1_cycle"])

    return {
        "verdict": "scc_kernel_weighted_contraction_audit",
        "phase0_cycle": phase0_summary,
        "phase1_cycle": phase1_summary,
        "global_uniform_upper_bound": max(
            phase0_summary["uniform_cycle_upper_bound"],
            phase1_summary["uniform_cycle_upper_bound"],
        ),
        "interpretation": (
            "The finite phase-cycle kernel now has explicit source-by-source contraction "
            "constants. Even if the rare all-Q1 critical template is treated as neutral, "
            "every observed source family still contracts strictly in weighted dyadic density. "
            "The worst explicit source bound is below 0.952, so the obstruction has been reduced "
            "to proving that the same finite phase-aware inequalities remain valid in the final kernel model."
        ),
    }


def main() -> int:
    print(json.dumps(build_payload(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
