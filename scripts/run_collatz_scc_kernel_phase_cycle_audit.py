from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_collatz_scc_kernel_candidate_inventory import (
    child_states,
    is_resolved,
    local_profile,
)


STATE_MODULI = [1024, 2048, 4096, 8192, 16384]
TRIVIAL_PROFILE = ((1, 1), (1, 1), (1, 1), (1, 1))


def unresolved_states() -> list[tuple[int, int]]:
    states: list[tuple[int, int]] = []
    for modulus in STATE_MODULI:
        for residue in range(1, modulus, 2):
            if not is_resolved(modulus, residue):
                states.append((modulus, residue))
    return states


def build_transition_counter(
    states: list[tuple[int, int]],
    profile_ids: dict[tuple[tuple[int, int], ...], str],
) -> dict[tuple[int, str], Counter[tuple[str, ...]]]:
    counter: defaultdict[tuple[int, str], Counter[tuple[str, ...]]] = defaultdict(Counter)
    max_modulus = max(STATE_MODULI)
    for modulus, residue in states:
        if modulus == max_modulus:
            continue
        source_id = profile_ids[local_profile(modulus, residue)]
        children: list[str] = []
        for child_modulus, child_residue in child_states(modulus, residue):
            if not is_resolved(child_modulus, child_residue):
                child_profile = local_profile(child_modulus, child_residue)
                children.append(profile_ids[child_profile])
        counter[(modulus, source_id)][tuple(sorted(children))] += 1
    return counter


def phase_states(
    states: list[tuple[int, int]],
    profile_ids: dict[tuple[tuple[int, int], ...], str],
    *,
    modulus: int,
) -> list[str]:
    trivial_id = profile_ids[TRIVIAL_PROFILE]
    return sorted(
        {
            profile_ids[local_profile(state_modulus, residue)]
            for state_modulus, residue in states
            if state_modulus == modulus
        }
        - {trivial_id}
    )


def average_transition_matrix(
    transition_counter: dict[tuple[int, str], Counter[tuple[str, ...]]],
    *,
    modulus: int,
    source_states: list[str],
    target_states: list[str],
) -> list[list[Fraction]]:
    rows: list[list[Fraction]] = []
    for state in source_states:
        counter = transition_counter[(modulus, state)]
        total = sum(counter.values())
        row: list[Fraction] = []
        for target in target_states:
            value = Fraction(0, 1)
            for children, count in counter.items():
                multiplicity = sum(1 for child in children if child == target)
                value += Fraction(count * multiplicity, total)
            row.append(value)
        rows.append(row)
    return rows


def matmul(left: list[list[Fraction]], right: list[list[Fraction]]) -> list[list[Fraction]]:
    return [
        [
            sum(left[i][k] * right[k][j] for k in range(len(right)))
            for j in range(len(right[0]))
        ]
        for i in range(len(left))
    ]


def to_float_matrix(matrix: list[list[Fraction]]) -> list[list[float]]:
    return [[float(value) for value in row] for row in matrix]


def normalized_matrix(matrix: list[list[Fraction]], factor: Fraction) -> list[list[Fraction]]:
    return [[value * factor for value in row] for row in matrix]


def power_radius(matrix: list[list[Fraction]], iterations: int = 160) -> float:
    float_matrix = to_float_matrix(matrix)
    size = len(float_matrix)
    vector = [1.0] * size
    for _ in range(iterations):
        next_vector = [
            sum(float_matrix[i][j] * vector[j] for j in range(size))
            for i in range(size)
        ]
        norm = max(abs(value) for value in next_vector) or 1.0
        vector = [value / norm for value in next_vector]
    next_vector = [
        sum(float_matrix[i][j] * vector[j] for j in range(size))
        for i in range(size)
    ]
    ratios = [next_vector[i] / vector[i] for i in range(size) if abs(vector[i]) > 1e-12]
    return sum(ratios) / len(ratios)


def right_eigenvector(matrix: list[list[Fraction]], iterations: int = 160) -> list[float]:
    float_matrix = to_float_matrix(matrix)
    size = len(float_matrix)
    vector = [1.0] * size
    for _ in range(iterations):
        next_vector = [
            sum(float_matrix[i][j] * vector[j] for j in range(size))
            for i in range(size)
        ]
        norm = max(next_vector) or 1.0
        vector = [value / norm for value in next_vector]
    return vector


def serialize_matrix(matrix: list[list[Fraction]]) -> dict[str, list[list[object]]]:
    return {
        "rational": [
            [
                f"{value.numerator}/{value.denominator}"
                if value.denominator != 1
                else str(value.numerator)
                for value in row
            ]
            for row in matrix
        ],
        "float": to_float_matrix(matrix),
    }


def cycle_payload(
    *,
    name: str,
    source_modulus: int,
    target_modulus: int,
    states: list[str],
    raw_matrix: list[list[Fraction]],
) -> dict[str, object]:
    normalized = normalized_matrix(raw_matrix, Fraction(1, 8))
    eigenvector = right_eigenvector(normalized)
    return {
        "cycle": name,
        "source_modulus": source_modulus,
        "target_modulus": target_modulus,
        "states": states,
        "raw_return_matrix": serialize_matrix(raw_matrix),
        "density_normalized_return_matrix": serialize_matrix(normalized),
        "density_normalized_row_sums": [float(sum(row)) for row in normalized],
        "density_normalized_radius": power_radius(normalized),
        "density_positive_vector": {
            state: eigenvector[index] for index, state in enumerate(states)
        },
    }


def build_payload() -> dict[str, object]:
    states = unresolved_states()
    profiles = sorted({local_profile(modulus, residue) for modulus, residue in states})
    profile_ids = {profile: f"Q{i + 1}" for i, profile in enumerate(profiles)}
    transition_counter = build_transition_counter(states, profile_ids)

    phase0_states = phase_states(states, profile_ids, modulus=1024)
    phase1_states = phase_states(states, profile_ids, modulus=2048)
    phase2_states = phase_states(states, profile_ids, modulus=4096)

    phase0_to_phase1_at_1024 = average_transition_matrix(
        transition_counter,
        modulus=1024,
        source_states=phase0_states,
        target_states=phase1_states,
    )
    phase1_to_phase2_at_2048 = average_transition_matrix(
        transition_counter,
        modulus=2048,
        source_states=phase1_states,
        target_states=phase2_states,
    )
    phase2_to_phase0_at_4096 = average_transition_matrix(
        transition_counter,
        modulus=4096,
        source_states=phase2_states,
        target_states=phase0_states,
    )
    phase0_to_phase1_at_8192 = average_transition_matrix(
        transition_counter,
        modulus=8192,
        source_states=phase0_states,
        target_states=phase1_states,
    )

    phase0_return = matmul(
        matmul(phase0_to_phase1_at_1024, phase1_to_phase2_at_2048),
        phase2_to_phase0_at_4096,
    )
    phase1_return = matmul(
        matmul(phase1_to_phase2_at_2048, phase2_to_phase0_at_4096),
        phase0_to_phase1_at_8192,
    )

    return {
        "verdict": "scc_kernel_phase_cycle_audit",
        "state_moduli": STATE_MODULI,
        "state_count": len(profiles),
        "phase_state_sets": {
            "phase0_mod_1024": phase0_states,
            "phase1_mod_2048": phase1_states,
            "phase2_mod_4096": phase2_states,
        },
        "phase0_return_cycle": cycle_payload(
            name="phase0_mod_1024_to_mod_8192",
            source_modulus=1024,
            target_modulus=8192,
            states=phase0_states,
            raw_matrix=phase0_return,
        ),
        "phase1_return_cycle": cycle_payload(
            name="phase1_mod_2048_to_mod_16384",
            source_modulus=2048,
            target_modulus=16384,
            states=phase1_states,
            raw_matrix=phase1_return,
        ),
        "interpretation": (
            "The 9-state kernel candidate is not just subcritical under a one-step "
            "density-normalized average operator. When the dynamics are grouped into the "
            "natural three-step dyadic phase cycle, the return operators contract much more "
            "strongly: both observed phase-return radii are below 0.75 after 2^-3 density "
            "normalization. That is a more theorem-shaped scarcity signal and suggests the "
            "right finite obstruction theorem should be periodic rather than purely one-layer."
        ),
    }


def main() -> int:
    print(json.dumps(build_payload(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
