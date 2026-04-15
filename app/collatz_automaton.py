from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import sys
from typing import Literal


RelationMode = Literal["residue_relation"]


@dataclass(frozen=True, slots=True)
class PressureState:
    residue: int
    phase: int
    odd_count: int
    even_count: int


def positive_pressure(even_count: int, odd_count: int) -> bool:
    """Conservative integer surrogate for 2^even > 3^odd."""

    return 8 * odd_count < 5 * even_count


def signed_residue(residue: int, modulus: int) -> int:
    half = modulus // 2
    return residue if residue < half else residue - modulus


def collatz_residue_successors(residue: int, modulus_bits: int) -> list[int]:
    """Sound one-step residue relation modulo 2^modulus_bits.

    Odd Collatz steps are deterministic modulo 2^w. Even steps are not:
    if n = r mod 2^w and r is even, then n / 2 can be either
    r / 2 or r / 2 + 2^(w-1) modulo 2^w depending on the hidden high bit.
    This over-approximates positive integer trajectories but is sound for
    dynamic admissibility discovery.
    """

    modulus = 1 << modulus_bits
    if residue % 2 == 1:
        return [((3 * residue) + 1) % modulus]
    low = residue // 2
    high = low + (modulus // 2)
    return [low] if low == high else [low, high]


def analyze_dynamic_pressure_automaton(
    *,
    window: int,
    modulus_bits: int,
    max_cycle_states: int = 16,
    relation_mode: RelationMode = "residue_relation",
) -> dict:
    if relation_mode != "residue_relation":
        raise ValueError(f"Unsupported relation_mode={relation_mode!r}")
    if window < 1:
        raise ValueError("window must be at least 1")
    if modulus_bits < 1:
        raise ValueError("modulus_bits must be at least 1")

    modulus = 1 << modulus_bits
    initial_states = [PressureState(residue, 0, 0, 0) for residue in range(modulus)]
    adjacency: dict[PressureState, list[PressureState]] = defaultdict(list)
    seen = set(initial_states)
    stack = list(initial_states)
    progress_exit_count = 0
    bad_reset_count = 0

    while stack:
        state = stack.pop()
        bit = state.residue % 2
        for next_residue in collatz_residue_successors(state.residue, modulus_bits):
            next_odd = state.odd_count + bit
            next_even = state.even_count + (1 - bit)
            next_phase = state.phase + 1
            if next_phase == window:
                if positive_pressure(next_even, next_odd):
                    progress_exit_count += 1
                    continue
                bad_reset_count += 1
                next_state = PressureState(next_residue, 0, 0, 0)
            else:
                next_state = PressureState(next_residue, next_phase, next_odd, next_even)
            adjacency[state].append(next_state)
            if next_state not in seen:
                seen.add(next_state)
                stack.append(next_state)

    cycle = _find_cycle(adjacency, seen)
    if cycle:
        certificate = {
            "kind": "bad_cycle_obstruction",
            "cycle_length": len(cycle),
            "cycle": _cycle_payload(cycle, modulus, max_cycle_states),
        }
    else:
        certificate = {
            "kind": "acyclic_bad_subgraph",
            "max_rank": _max_acyclic_rank(adjacency, seen),
            "rank_meaning": "maximum bad-graph steps before every path exits through a positive-pressure window",
        }

    return {
        "window": window,
        "modulus_bits": modulus_bits,
        "modulus": modulus,
        "relation_mode": relation_mode,
        "overapproximation": "sound residue relation; even division keeps both hidden high-bit successors",
        "pressure_rule": "positive iff 8 * odd_count < 5 * even_count",
        "state_count": len(seen),
        "edge_count": sum(len(edges) for edges in adjacency.values()),
        "progress_exit_count": progress_exit_count,
        "bad_reset_count": bad_reset_count,
        "cycle_found": bool(cycle),
        "ghost_family": _ghost_family(cycle, modulus),
        "certificate": certificate,
        "interpretation": _interpretation(cycle),
    }


def _find_cycle(
    adjacency: dict[PressureState, list[PressureState]],
    states: set[PressureState],
) -> list[PressureState]:
    sys.setrecursionlimit(max(sys.getrecursionlimit(), len(states) + 1000))
    color: dict[PressureState, int] = {}
    path: list[PressureState] = []
    position: dict[PressureState, int] = {}

    def visit(state: PressureState) -> list[PressureState] | None:
        color[state] = 1
        position[state] = len(path)
        path.append(state)
        for next_state in adjacency.get(state, []):
            next_color = color.get(next_state, 0)
            if next_color == 1:
                return path[position[next_state] :].copy()
            if next_color == 0:
                found = visit(next_state)
                if found:
                    return found
        path.pop()
        position.pop(state, None)
        color[state] = 2
        return None

    for state in states:
        if color.get(state, 0) == 0:
            found = visit(state)
            if found:
                return found
    return []


def _max_acyclic_rank(
    adjacency: dict[PressureState, list[PressureState]],
    states: set[PressureState],
) -> int:
    memo: dict[PressureState, int] = {}

    def rank(state: PressureState) -> int:
        if state in memo:
            return memo[state]
        children = adjacency.get(state, [])
        memo[state] = 0 if not children else 1 + max(rank(child) for child in children)
        return memo[state]

    return max((rank(state) for state in states), default=0)


def _cycle_payload(
    cycle: list[PressureState],
    modulus: int,
    max_cycle_states: int,
) -> dict:
    shown = cycle[:max_cycle_states]
    bits = [state.residue % 2 for state in cycle]
    odd_count = sum(bits)
    even_count = len(bits) - odd_count
    return {
        "states": [
            {
                "residue": state.residue,
                "signed_residue": signed_residue(state.residue, modulus),
                "phase": state.phase,
                "odd_count": state.odd_count,
                "even_count": state.even_count,
            }
            for state in shown
        ],
        "truncated": len(cycle) > max_cycle_states,
        "edge_bits": bits[:max_cycle_states],
        "cycle_odd_count": odd_count,
        "cycle_even_count": even_count,
        "cycle_positive_pressure": positive_pressure(even_count, odd_count),
    }


def _ghost_family(cycle: list[PressureState], modulus: int) -> str | None:
    signed = {signed_residue(state.residue, modulus) for state in cycle}
    if {-2, -1}.issubset(signed):
        return "2-adic negative ghost cycle -2 <-> -1"
    return None


def _interpretation(cycle: list[PressureState]) -> str:
    if not cycle:
        return (
            "No bad cycle exists in the sound finite residue over-approximation; "
            "the report carries an acyclic rank certificate."
        )
    return (
        "A bad cycle exists in the sound residue over-approximation. Treat this as "
        "an obstruction to pure 2-adic pressure until an Archimedean/positive-integer "
        "side condition removes the ghost."
    )
