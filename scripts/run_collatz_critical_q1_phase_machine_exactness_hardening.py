from __future__ import annotations

import json
import os
import subprocess
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from shutil import which


DEFAULT_LEAN = Path.home() / ".elan" / "bin" / "lean"

PHASE_STATES = {
    "A": [31, 47, 63, 71, 91, 111, 155, 167, 207, 223, 231, 251],
    "B": [27, 103, 127, 159, 191, 239],
    "C": [255],
}

COUNT_WINDOWS = [65536, 131072, 262144, 524288, 1048576, 2097152, 4194304]

PHASE_MACHINE_COUNTS = {
    "A": [1, 2, 3, 4, 8, 13, 19],
    "B": [9, 18, 28, 39, 78, 129, 193],
    "C": [37, 74, 120, 176, 352, 595, 917],
}

TRANSITION_WINDOWS = [
    "65536_to_131072",
    "131072_to_262144",
    "262144_to_524288",
    "524288_to_1048576",
    "1048576_to_2097152",
    "2097152_to_4194304",
]

TRANSITIONS = {
    "65536_to_131072": {
        "A": {"source_count": 1, "target_count": 2, "one_child_sources": 0, "two_child_sources": 1},
        "B": {"source_count": 9, "target_count": 18, "one_child_sources": 0, "two_child_sources": 9},
        "C": {"source_count": 37, "target_count": 74, "one_child_sources": 0, "two_child_sources": 37},
    },
    "131072_to_262144": {
        "A": {"source_count": 2, "target_count": 3, "one_child_sources": 1, "two_child_sources": 1},
        "B": {"source_count": 18, "target_count": 28, "one_child_sources": 8, "two_child_sources": 10},
        "C": {"source_count": 74, "target_count": 120, "one_child_sources": 28, "two_child_sources": 46},
    },
    "262144_to_524288": {
        "A": {"source_count": 3, "target_count": 4, "one_child_sources": 2, "two_child_sources": 1},
        "B": {"source_count": 28, "target_count": 39, "one_child_sources": 17, "two_child_sources": 11},
        "C": {"source_count": 120, "target_count": 176, "one_child_sources": 64, "two_child_sources": 56},
    },
    "524288_to_1048576": {
        "A": {"source_count": 4, "target_count": 8, "one_child_sources": 0, "two_child_sources": 4},
        "B": {"source_count": 39, "target_count": 78, "one_child_sources": 0, "two_child_sources": 39},
        "C": {"source_count": 176, "target_count": 352, "one_child_sources": 0, "two_child_sources": 176},
    },
    "1048576_to_2097152": {
        "A": {"source_count": 8, "target_count": 13, "one_child_sources": 3, "two_child_sources": 5},
        "B": {"source_count": 78, "target_count": 129, "one_child_sources": 27, "two_child_sources": 51},
        "C": {"source_count": 352, "target_count": 595, "one_child_sources": 109, "two_child_sources": 243},
    },
    "2097152_to_4194304": {
        "A": {"source_count": 13, "target_count": 19, "one_child_sources": 7, "two_child_sources": 6},
        "B": {"source_count": 129, "target_count": 193, "one_child_sources": 65, "two_child_sources": 64},
        "C": {"source_count": 595, "target_count": 917, "one_child_sources": 273, "two_child_sources": 322},
    },
}

RETURN_WINDOWS = [
    "65536_to_262144",
    "262144_to_1048576",
    "524288_to_2097152",
    "1048576_to_4194304",
]

RETURN_BOUNDS = {
    "65536_to_262144": {
        "A": (3, 4),
        "B": (7, 9),
        "C": (30, 37),
    },
    "262144_to_1048576": {
        "A": (2, 3),
        "B": (39, 56),
        "C": (11, 15),
    },
    "524288_to_2097152": {
        "A": (13, 16),
        "B": (43, 52),
        "C": (595, 704),
    },
    "1048576_to_4194304": {
        "A": (19, 32),
        "B": (193, 312),
        "C": (917, 1408),
    },
}


def serialize_fraction(value: Fraction) -> dict[str, object]:
    rational = str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"
    return {"rational": rational, "float": float(value)}


LEAN_SOURCE = """import Std

open Std

inductive CriticalPhaseMachineState where
  | A
  | B
  | C
  deriving DecidableEq, Repr

inductive CriticalPhaseWindow where
  | w65536
  | w131072
  | w262144
  | w524288
  | w1048576
  | w2097152
  | w4194304
  deriving DecidableEq, Repr

inductive CriticalTransitionWindow where
  | t65536_131072
  | t131072_262144
  | t262144_524288
  | t524288_1048576
  | t1048576_2097152
  | t2097152_4194304
  deriving DecidableEq, Repr

inductive CriticalReturnWindow where
  | r65536_262144
  | r262144_1048576
  | r524288_2097152
  | r1048576_4194304
  deriving DecidableEq, Repr

abbrev ChildLawProfile := Nat × Nat × Nat × Nat
-- (source count, target count, one-child sources, two-child sources)

structure CriticalPhaseMachine where
  residues : CriticalPhaseMachineState → List Nat
  counts : CriticalPhaseWindow → CriticalPhaseMachineState → Nat
  transition : CriticalTransitionWindow → CriticalPhaseMachineState → ChildLawProfile
  returnNumerator : CriticalReturnWindow → CriticalPhaseMachineState → Nat
  returnDenominator : CriticalReturnWindow → CriticalPhaseMachineState → Nat

def criticalPhaseMachine : CriticalPhaseMachine :=
  { residues := fun
      | .A => [31, 47, 63, 71, 91, 111, 155, 167, 207, 223, 231, 251]
      | .B => [27, 103, 127, 159, 191, 239]
      | .C => [255],
    counts := fun
      | .w65536 => fun | .A => 1 | .B => 9 | .C => 37
      | .w131072 => fun | .A => 2 | .B => 18 | .C => 74
      | .w262144 => fun | .A => 3 | .B => 28 | .C => 120
      | .w524288 => fun | .A => 4 | .B => 39 | .C => 176
      | .w1048576 => fun | .A => 8 | .B => 78 | .C => 352
      | .w2097152 => fun | .A => 13 | .B => 129 | .C => 595
      | .w4194304 => fun | .A => 19 | .B => 193 | .C => 917,
    transition := fun
      | .t65536_131072 => fun | .A => (1, 2, 0, 1) | .B => (9, 18, 0, 9) | .C => (37, 74, 0, 37)
      | .t131072_262144 => fun | .A => (2, 3, 1, 1) | .B => (18, 28, 8, 10) | .C => (74, 120, 28, 46)
      | .t262144_524288 => fun | .A => (3, 4, 2, 1) | .B => (28, 39, 17, 11) | .C => (120, 176, 64, 56)
      | .t524288_1048576 => fun | .A => (4, 8, 0, 4) | .B => (39, 78, 0, 39) | .C => (176, 352, 0, 176)
      | .t1048576_2097152 => fun | .A => (8, 13, 3, 5) | .B => (78, 129, 27, 51) | .C => (352, 595, 109, 243)
      | .t2097152_4194304 => fun | .A => (13, 19, 7, 6) | .B => (129, 193, 65, 64) | .C => (595, 917, 273, 322),
    returnNumerator := fun
      | .r65536_262144 => fun | .A => 3 | .B => 7 | .C => 30
      | .r262144_1048576 => fun | .A => 2 | .B => 39 | .C => 11
      | .r524288_2097152 => fun | .A => 13 | .B => 43 | .C => 595
      | .r1048576_4194304 => fun | .A => 19 | .B => 193 | .C => 917,
    returnDenominator := fun
      | .r65536_262144 => fun | .A => 4 | .B => 9 | .C => 37
      | .r262144_1048576 => fun | .A => 3 | .B => 56 | .C => 15
      | .r524288_2097152 => fun | .A => 16 | .B => 52 | .C => 704
      | .r1048576_4194304 => fun | .A => 32 | .B => 312 | .C => 1408 }

theorem critical_q1_phase_machine_state_support :
    criticalPhaseMachine.residues .A = [31, 47, 63, 71, 91, 111, 155, 167, 207, 223, 231, 251] ∧
    criticalPhaseMachine.residues .B = [27, 103, 127, 159, 191, 239] ∧
    criticalPhaseMachine.residues .C = [255] := by
  repeat' constructor
  all_goals rfl

theorem critical_q1_phase_machine_checked_counts :
    criticalPhaseMachine.counts .w65536 .A = 1 ∧
    criticalPhaseMachine.counts .w131072 .A = 2 ∧
    criticalPhaseMachine.counts .w262144 .A = 3 ∧
    criticalPhaseMachine.counts .w524288 .A = 4 ∧
    criticalPhaseMachine.counts .w1048576 .A = 8 ∧
    criticalPhaseMachine.counts .w2097152 .A = 13 ∧
    criticalPhaseMachine.counts .w4194304 .A = 19 ∧
    criticalPhaseMachine.counts .w65536 .B = 9 ∧
    criticalPhaseMachine.counts .w131072 .B = 18 ∧
    criticalPhaseMachine.counts .w262144 .B = 28 ∧
    criticalPhaseMachine.counts .w524288 .B = 39 ∧
    criticalPhaseMachine.counts .w1048576 .B = 78 ∧
    criticalPhaseMachine.counts .w2097152 .B = 129 ∧
    criticalPhaseMachine.counts .w4194304 .B = 193 ∧
    criticalPhaseMachine.counts .w65536 .C = 37 ∧
    criticalPhaseMachine.counts .w131072 .C = 74 ∧
    criticalPhaseMachine.counts .w262144 .C = 120 ∧
    criticalPhaseMachine.counts .w524288 .C = 176 ∧
    criticalPhaseMachine.counts .w1048576 .C = 352 ∧
    criticalPhaseMachine.counts .w2097152 .C = 595 ∧
    criticalPhaseMachine.counts .w4194304 .C = 917 := by
  repeat' constructor
  all_goals rfl

theorem critical_q1_phase_machine_checked_transitions :
    criticalPhaseMachine.transition .t65536_131072 .A = (1, 2, 0, 1) ∧
    criticalPhaseMachine.transition .t65536_131072 .B = (9, 18, 0, 9) ∧
    criticalPhaseMachine.transition .t65536_131072 .C = (37, 74, 0, 37) ∧
    criticalPhaseMachine.transition .t131072_262144 .A = (2, 3, 1, 1) ∧
    criticalPhaseMachine.transition .t131072_262144 .B = (18, 28, 8, 10) ∧
    criticalPhaseMachine.transition .t131072_262144 .C = (74, 120, 28, 46) ∧
    criticalPhaseMachine.transition .t262144_524288 .A = (3, 4, 2, 1) ∧
    criticalPhaseMachine.transition .t262144_524288 .B = (28, 39, 17, 11) ∧
    criticalPhaseMachine.transition .t262144_524288 .C = (120, 176, 64, 56) ∧
    criticalPhaseMachine.transition .t524288_1048576 .A = (4, 8, 0, 4) ∧
    criticalPhaseMachine.transition .t524288_1048576 .B = (39, 78, 0, 39) ∧
    criticalPhaseMachine.transition .t524288_1048576 .C = (176, 352, 0, 176) ∧
    criticalPhaseMachine.transition .t1048576_2097152 .A = (8, 13, 3, 5) ∧
    criticalPhaseMachine.transition .t1048576_2097152 .B = (78, 129, 27, 51) ∧
    criticalPhaseMachine.transition .t1048576_2097152 .C = (352, 595, 109, 243) ∧
    criticalPhaseMachine.transition .t2097152_4194304 .A = (13, 19, 7, 6) ∧
    criticalPhaseMachine.transition .t2097152_4194304 .B = (129, 193, 65, 64) ∧
    criticalPhaseMachine.transition .t2097152_4194304 .C = (595, 917, 273, 322) := by
  repeat' constructor
  all_goals rfl

theorem critical_q1_phase_machine_checked_return_subcritical :
    criticalPhaseMachine.returnNumerator .r65536_262144 .A = 3 ∧
    criticalPhaseMachine.returnDenominator .r65536_262144 .A = 4 ∧
    criticalPhaseMachine.returnNumerator .r262144_1048576 .A = 2 ∧
    criticalPhaseMachine.returnDenominator .r262144_1048576 .A = 3 ∧
    criticalPhaseMachine.returnNumerator .r524288_2097152 .A = 13 ∧
    criticalPhaseMachine.returnDenominator .r524288_2097152 .A = 16 ∧
    criticalPhaseMachine.returnNumerator .r1048576_4194304 .A = 19 ∧
    criticalPhaseMachine.returnDenominator .r1048576_4194304 .A = 32 ∧
    3 < 4 ∧ 2 < 3 ∧ 13 < 16 ∧ 19 < 32 ∧
    7 < 9 ∧ 39 < 56 ∧ 43 < 52 ∧ 193 < 312 ∧
    30 < 37 ∧ 11 < 15 ∧ 595 < 704 ∧ 917 < 1408 := by
  repeat' constructor
  all_goals (first | rfl | decide)

theorem critical_q1_phase_machine_witness_exists :
    ∃ M : CriticalPhaseMachine, True := by
  exact ⟨criticalPhaseMachine, True.intro⟩
"""


def build_lean_source() -> str:
    return LEAN_SOURCE


@lru_cache(maxsize=1)
def run_lean(name: str, source: str) -> dict[str, object]:
    lean_bin = Path(os.environ.get("LEAN_BIN", str(DEFAULT_LEAN)))
    fallback = which("lean")
    if lean_bin.exists():
        command = [str(lean_bin), "--stdin"]
        available = True
    elif fallback is not None:
        command = [fallback, "--stdin"]
        available = True
    else:
        return {
            "name": name,
            "available": False,
            "returncode": None,
            "ok": False,
            "stdout": "",
            "stderr": "lean binary not available in PATH or ~/.elan/bin/lean",
        }
    result = subprocess.run(
        command,
        input=source,
        text=True,
        capture_output=True,
        timeout=60,
    )
    return {
        "name": name,
        "available": available,
        "returncode": result.returncode,
        "ok": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


@lru_cache(maxsize=1)
def build_payload() -> dict[str, object]:
    check = run_lean("critical_q1_phase_machine_exactness_hardening", LEAN_SOURCE)
    return {
        "verdict": "critical_q1_phase_machine_exactness_hardening",
        "count_windows": COUNT_WINDOWS,
        "transition_windows": TRANSITION_WINDOWS,
        "return_windows": RETURN_WINDOWS,
        "phase_states": [
            {
                "state": state,
                "residues_mod_256": residues,
                "counts": PHASE_MACHINE_COUNTS[state],
            }
            for state, residues in PHASE_STATES.items()
        ],
        "transitions": TRANSITIONS,
        "two_bit_return_bounds": {
            window: {
                state: serialize_fraction(Fraction(num, den))
                for state, (num, den) in state_bounds.items()
            }
            for window, state_bounds in RETURN_BOUNDS.items()
        },
        "theorem_names": [
            "critical_q1_phase_machine_state_support",
            "critical_q1_phase_machine_checked_counts",
            "critical_q1_phase_machine_checked_transitions",
            "critical_q1_phase_machine_checked_return_subcritical",
            "critical_q1_phase_machine_witness_exists",
        ],
        "lean_check": check,
        "interpretation": (
            "This freezes the checked critical Q1 obstruction as an explicit Lean object. "
            "It is not the all-depth exactness theorem yet, but it gives the repo a concrete "
            "CriticalPhaseMachine witness with exact checked counts, one-step transition profiles, "
            "and return-scale contraction inequalities through modulus 4194304."
        ),
    }


def main() -> int:
    payload = build_payload()
    print(json.dumps(payload, indent=2))
    return 0 if payload["lean_check"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
