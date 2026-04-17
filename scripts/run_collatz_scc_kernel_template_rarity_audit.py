from __future__ import annotations

import json
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_collatz_scc_kernel_phase_cycle_audit import (
    STATE_MODULI,
    build_transition_counter,
    phase_states,
    unresolved_states,
)
from scripts.run_collatz_scc_kernel_candidate_inventory import local_profile


def compose_templates(
    transition_counter: dict[tuple[int, str], Counter[tuple[str, ...]]],
    *,
    source_state: str,
    modulus_chain: list[int],
) -> Counter[tuple[str, ...]]:
    frontier = Counter({(source_state,): 1})
    for modulus in modulus_chain:
        next_frontier: Counter[tuple[str, ...]] = Counter()
        for multiset, multiplicity in frontier.items():
            expansions = Counter({(): 1})
            for state in multiset:
                step_counter = transition_counter[(modulus, state)]
                updated: Counter[tuple[str, ...]] = Counter()
                for prefix, prefix_multiplicity in expansions.items():
                    for children, child_multiplicity in step_counter.items():
                        updated[tuple(sorted(prefix + children))] += (
                            prefix_multiplicity * child_multiplicity
                        )
                expansions = updated
            for children, child_multiplicity in expansions.items():
                next_frontier[children] += multiplicity * child_multiplicity
        frontier = next_frontier
    return frontier


def template_ratio(
    template: tuple[str, ...],
    *,
    source_state: str,
    weights: dict[str, float],
) -> float:
    return sum(weights[state] for state in template) / (8.0 * weights[source_state])


def serialize_fraction(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def build_cycle_inventory(
    transition_counter: dict[tuple[int, str], Counter[tuple[str, ...]]],
    *,
    cycle_name: str,
    source_states: list[str],
    modulus_chain: list[int],
    weights: dict[str, float],
) -> dict[str, object]:
    by_source: dict[str, object] = {}
    for source_state in source_states:
        templates = compose_templates(
            transition_counter,
            source_state=source_state,
            modulus_chain=modulus_chain,
        )
        total = sum(templates.values())
        rows: list[dict[str, object]] = []
        critical_probability = Fraction(0, 1)
        worst_noncritical_ratio = 0.0
        for template, count in templates.most_common():
            probability = Fraction(count, total)
            ratio = template_ratio(template, source_state=source_state, weights=weights)
            is_critical = all(state == source_states[0] for state in template) and len(template) == 8
            if is_critical:
                critical_probability = probability
            else:
                worst_noncritical_ratio = max(worst_noncritical_ratio, ratio)
            rows.append(
                {
                    "children": list(template),
                    "count": count,
                    "probability": {
                        "rational": serialize_fraction(probability),
                        "float": float(probability),
                    },
                    "normalized_weight_ratio": ratio,
                    "is_critical_all_q1_template": is_critical,
                }
            )
        by_source[source_state] = {
            "template_count": len(rows),
            "critical_template_probability": {
                "rational": serialize_fraction(critical_probability),
                "float": float(critical_probability),
            },
            "worst_noncritical_ratio": worst_noncritical_ratio,
            "templates": rows,
        }

    return {
        "cycle": cycle_name,
        "modulus_chain": modulus_chain,
        "weights": weights,
        "source_inventory": by_source,
    }


def build_payload() -> dict[str, object]:
    states = unresolved_states()
    profiles = sorted({local_profile(modulus, residue) for modulus, residue in states})
    profile_ids = {profile: f"Q{i + 1}" for i, profile in enumerate(profiles)}
    transition_counter = build_transition_counter(states, profile_ids)

    phase0_states = phase_states(states, profile_ids, modulus=1024)
    phase1_states = phase_states(states, profile_ids, modulus=2048)

    phase0_weights = {
        "Q1": 1.0,
        "Q3": 0.5212957369120241,
        "Q6": 0.17736946450561955,
    }
    phase1_weights = {
        "Q1": 1.0,
        "Q2": 0.6124944466517149,
        "Q5": 0.23672834898204773,
        "Q8": 0.047456995331271554,
    }

    phase0_cycle = build_cycle_inventory(
        transition_counter,
        cycle_name="phase0_mod_1024_to_mod_8192",
        source_states=phase0_states,
        modulus_chain=[1024, 2048, 4096],
        weights=phase0_weights,
    )
    phase1_cycle = build_cycle_inventory(
        transition_counter,
        cycle_name="phase1_mod_2048_to_mod_16384",
        source_states=phase1_states,
        modulus_chain=[2048, 4096, 8192],
        weights=phase1_weights,
    )

    return {
        "verdict": "scc_kernel_template_rarity_audit",
        "state_moduli": STATE_MODULI,
        "phase0_cycle": phase0_cycle,
        "phase1_cycle": phase1_cycle,
        "interpretation": (
            "The exact three-step kernel return templates are finite and highly sparse. "
            "For both observed phase cycles, strict weighted contraction fails only because "
            "the source state Q1 admits a rare all-Q1 eight-child return template. Every "
            "other return template contracts under the phase-cycle positive vectors. So the "
            "remaining obstruction is not uncontrolled combinatorics; it is a small, explicit "
            "critical self-cloning branch that must be beaten by a density or rarity theorem."
        ),
    }


def main() -> int:
    print(json.dumps(build_payload(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
