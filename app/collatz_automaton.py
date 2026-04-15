from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
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

    modulus, seen, adjacency, progress_exit_count, bad_reset_count = _build_bad_pressure_graph(
        window=window,
        modulus_bits=modulus_bits,
    )

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


def analyze_height_lifted_pressure_automaton(
    *,
    window: int,
    modulus_bits: int,
    max_cycle_states: int = 16,
    max_components: int = 8,
    exact_scc_limit: int = 4000,
    relation_mode: RelationMode = "residue_relation",
) -> dict:
    if relation_mode != "residue_relation":
        raise ValueError(f"Unsupported relation_mode={relation_mode!r}")
    if window < 1:
        raise ValueError("window must be at least 1")
    if modulus_bits < 1:
        raise ValueError("modulus_bits must be at least 1")

    modulus, seen, adjacency, progress_exit_count, bad_reset_count = _build_bad_pressure_graph(
        window=window,
        modulus_bits=modulus_bits,
    )
    recurrent_components = _recurrent_components(adjacency, seen)
    component_reports = []
    dangerous_count = 0
    unchecked_count = 0
    expanding_count = 0
    contracting_or_neutral_count = 0

    for component in recurrent_components[:max_components]:
        component_set = set(component)
        cycle = _find_cycle_in_component(adjacency, component_set)
        min_log_height_drift = None
        if len(component) <= exact_scc_limit:
            min_log_height_drift = _min_cycle_mean_log_height(component, adjacency)
        witness_drift = _height_drift_payload(cycle)
        if min_log_height_drift is None:
            classification = "unchecked_large_recurrent_component"
            unchecked_count += 1
        elif min_log_height_drift > 1.0e-12:
            classification = "height_expanding_escape"
            expanding_count += 1
        else:
            classification = "dangerous_nonexpanding_bad_component"
            dangerous_count += 1
            contracting_or_neutral_count += 1
        component_reports.append(
            {
                "size": len(component),
                "edge_count": sum(
                    1
                    for state in component
                    for next_state in adjacency.get(state, [])
                    if next_state in component_set
                ),
                "classification": classification,
                "min_cycle_mean_log2_height_drift": min_log_height_drift,
                "witness_cycle": _cycle_payload(cycle, modulus, max_cycle_states) if cycle else None,
                "witness_height_drift": witness_drift,
                "ghost_family": _ghost_family(cycle, modulus),
            }
        )

    omitted_component_count = max(0, len(recurrent_components) - max_components)
    if omitted_component_count:
        unchecked_count += omitted_component_count

    if not recurrent_components:
        decision = "acyclic_bad_subgraph"
    elif dangerous_count:
        decision = "dangerous_nonexpanding_bad_cycle_found"
    elif unchecked_count:
        decision = "needs_larger_exact_scc_check"
    else:
        decision = "all_checked_bad_cycles_height_expanding"

    return {
        "window": window,
        "modulus_bits": modulus_bits,
        "modulus": modulus,
        "relation_mode": relation_mode,
        "height_rule": "cycle drift is log2(3) * odd_edges - even_edges",
        "state_count": len(seen),
        "edge_count": sum(len(edges) for edges in adjacency.values()),
        "progress_exit_count": progress_exit_count,
        "bad_reset_count": bad_reset_count,
        "recurrent_component_count": len(recurrent_components),
        "reported_component_count": len(component_reports),
        "omitted_component_count": omitted_component_count,
        "height_expanding_component_count": expanding_count,
        "dangerous_component_count": dangerous_count,
        "unchecked_component_count": unchecked_count,
        "contracting_or_neutral_component_count": contracting_or_neutral_count,
        "all_checked_bad_cycles_height_expanding": (
            bool(recurrent_components) and dangerous_count == 0 and unchecked_count == 0
        ),
        "decision": decision,
        "components": component_reports,
        "interpretation": _height_interpretation(decision),
    }


def _build_bad_pressure_graph(
    *,
    window: int,
    modulus_bits: int,
) -> tuple[int, set[PressureState], dict[PressureState, list[PressureState]], int, int]:
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
    return modulus, seen, adjacency, progress_exit_count, bad_reset_count


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


def _strongly_connected_components(
    adjacency: dict[PressureState, list[PressureState]],
    states: set[PressureState],
) -> list[list[PressureState]]:
    sys.setrecursionlimit(max(sys.getrecursionlimit(), len(states) + 1000))
    index = 0
    indices: dict[PressureState, int] = {}
    lowlinks: dict[PressureState, int] = {}
    stack: list[PressureState] = []
    on_stack: set[PressureState] = set()
    components: list[list[PressureState]] = []

    def visit(state: PressureState) -> None:
        nonlocal index
        indices[state] = index
        lowlinks[state] = index
        index += 1
        stack.append(state)
        on_stack.add(state)
        for next_state in adjacency.get(state, []):
            if next_state not in indices:
                visit(next_state)
                lowlinks[state] = min(lowlinks[state], lowlinks[next_state])
            elif next_state in on_stack:
                lowlinks[state] = min(lowlinks[state], indices[next_state])
        if lowlinks[state] == indices[state]:
            component = []
            while True:
                next_state = stack.pop()
                on_stack.remove(next_state)
                component.append(next_state)
                if next_state == state:
                    break
            components.append(component)

    for state in states:
        if state not in indices:
            visit(state)
    return components


def _recurrent_components(
    adjacency: dict[PressureState, list[PressureState]],
    states: set[PressureState],
) -> list[list[PressureState]]:
    recurrent = []
    for component in _strongly_connected_components(adjacency, states):
        component_set = set(component)
        has_cycle = len(component) > 1 or any(
            state in adjacency.get(state, []) for state in component
        )
        if has_cycle:
            recurrent.append(component)
    return sorted(recurrent, key=len, reverse=True)


def _find_cycle_in_component(
    adjacency: dict[PressureState, list[PressureState]],
    component: set[PressureState],
) -> list[PressureState]:
    color: dict[PressureState, int] = {}
    path: list[PressureState] = []
    position: dict[PressureState, int] = {}

    def visit(state: PressureState) -> list[PressureState] | None:
        color[state] = 1
        position[state] = len(path)
        path.append(state)
        for next_state in adjacency.get(state, []):
            if next_state not in component:
                continue
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

    for state in component:
        if color.get(state, 0) == 0:
            found = visit(state)
            if found:
                return found
    return []


def _min_cycle_mean_log_height(
    component: list[PressureState],
    adjacency: dict[PressureState, list[PressureState]],
) -> float:
    nodes = list(component)
    node_index = {state: index for index, state in enumerate(nodes)}
    edges = [
        (
            node_index[state],
            node_index[next_state],
            math.log2(3) if state.residue % 2 else -1.0,
        )
        for state in nodes
        for next_state in adjacency.get(state, [])
        if next_state in node_index
    ]
    n = len(nodes)
    if n == 0 or not edges:
        return 0.0
    infinity = 1.0e100
    dp = [[infinity] * n for _ in range(n + 1)]
    dp[0] = [0.0] * n
    for step in range(1, n + 1):
        previous = dp[step - 1]
        current = dp[step]
        for source, target, weight in edges:
            candidate = previous[source] + weight
            if candidate < current[target]:
                current[target] = candidate

    best = infinity
    for vertex in range(n):
        if dp[n][vertex] >= infinity / 2:
            continue
        worst_prefix_gap = -infinity
        for step in range(n):
            if dp[step][vertex] < infinity / 2:
                average = (dp[n][vertex] - dp[step][vertex]) / (n - step)
                worst_prefix_gap = max(worst_prefix_gap, average)
        best = min(best, worst_prefix_gap)
    return best


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


def _height_drift_payload(cycle: list[PressureState]) -> dict:
    bits = [state.residue % 2 for state in cycle]
    odd_count = sum(bits)
    even_count = len(bits) - odd_count
    if not cycle:
        comparison = "no_cycle"
        log2_multiplier = 0.0
    else:
        log2_multiplier = odd_count * math.log2(3) - even_count
        if log2_multiplier > 1.0e-12:
            comparison = "height_expanding"
        elif log2_multiplier < -1.0e-12:
            comparison = "height_contracting"
        else:
            comparison = "height_neutral"
    return {
        "cycle_odd_count": odd_count,
        "cycle_even_count": even_count,
        "linear_multiplier": f"3^{odd_count}/2^{even_count}",
        "log2_linear_multiplier": log2_multiplier,
        "comparison": comparison,
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


def _height_interpretation(decision: str) -> str:
    if decision == "acyclic_bad_subgraph":
        return (
            "No recurrent bad component exists; the pressure automaton already has "
            "a finite acyclic certificate at this horizon."
        )
    if decision == "all_checked_bad_cycles_height_expanding":
        return (
            "Every checked recurrent bad component has positive Archimedean height "
            "drift, so these cycles are residue ghosts rather than bounded positive "
            "integer cycles. The next proof gate is to connect height escape to the "
            "minimal-survivor/density argument."
        )
    if decision == "dangerous_nonexpanding_bad_cycle_found":
        return (
            "A recurrent bad component has nonpositive height drift. This is a real "
            "pressure-route obstruction unless a more refined invariant separates it."
        )
    return (
        "At least one recurrent bad component was too large for the configured exact "
        "cycle-mean check; increase the bound before treating this horizon as signal."
    )
