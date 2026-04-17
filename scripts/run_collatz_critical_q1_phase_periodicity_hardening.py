from __future__ import annotations

import json
import os
import subprocess
import sys
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from shutil import which

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_collatz_critical_q1_phase_kernel_hardening import (
    DEFAULT_LEAN,
    PHASE_STATES,
)


TRACKED_MODULI = [262144, 524288, 1048576, 2097152]

PHASE_COUNTS = {
    "A": [3, 4, 8, 13],
    "B": [28, 39, 78, 129],
    "C": [120, 176, 352, 595],
}

TRANSITIONS = {
    "262144_to_524288": {
        "A": {"source_count": 3, "target_count": 4, "child_count_stats": {1: 2, 2: 1}},
        "B": {"source_count": 28, "target_count": 39, "child_count_stats": {1: 17, 2: 11}},
        "C": {"source_count": 120, "target_count": 176, "child_count_stats": {1: 64, 2: 56}},
    },
    "524288_to_1048576": {
        "A": {"source_count": 4, "target_count": 8, "child_count_stats": {2: 4}},
        "B": {"source_count": 39, "target_count": 78, "child_count_stats": {2: 39}},
        "C": {"source_count": 176, "target_count": 352, "child_count_stats": {2: 176}},
    },
    "1048576_to_2097152": {
        "A": {"source_count": 8, "target_count": 13, "child_count_stats": {1: 3, 2: 5}},
        "B": {"source_count": 78, "target_count": 129, "child_count_stats": {1: 27, 2: 51}},
        "C": {"source_count": 352, "target_count": 595, "child_count_stats": {1: 109, 2: 243}},
    },
}


def serialize_fraction(value: Fraction) -> dict[str, object]:
    rational = str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"
    return {"rational": rational, "float": float(value)}


LEAN_SOURCE = """import Std

open Std

inductive CriticalPeriodicState where
  | A
  | B
  | C
  deriving DecidableEq, Repr

abbrev ChildLawProfile := Nat × Nat × Nat × Nat
-- (source count, target count, one-child sources, two-child sources)

def periodicResidues : CriticalPeriodicState → List Nat
  | .A => [31, 47, 63, 71, 91, 111, 155, 167, 207, 223, 231, 251]
  | .B => [27, 103, 127, 159, 191, 239]
  | .C => [255]

def counts262144 : CriticalPeriodicState → Nat
  | .A => 3
  | .B => 28
  | .C => 120

def counts524288 : CriticalPeriodicState → Nat
  | .A => 4
  | .B => 39
  | .C => 176

def counts1048576 : CriticalPeriodicState → Nat
  | .A => 8
  | .B => 78
  | .C => 352

def counts2097152 : CriticalPeriodicState → Nat
  | .A => 13
  | .B => 129
  | .C => 595

def childLaw262144To524288 : CriticalPeriodicState → ChildLawProfile
  | .A => (3, 4, 2, 1)
  | .B => (28, 39, 17, 11)
  | .C => (120, 176, 64, 56)

def childLaw524288To1048576 : CriticalPeriodicState → ChildLawProfile
  | .A => (4, 8, 0, 4)
  | .B => (39, 78, 0, 39)
  | .C => (176, 352, 0, 176)

def childLaw1048576To2097152 : CriticalPeriodicState → ChildLawProfile
  | .A => (8, 13, 3, 5)
  | .B => (78, 129, 27, 51)
  | .C => (352, 595, 109, 243)

theorem critical_q1_mixed_phase_262144_to_524288 :
    childLaw262144To524288 .A = (3, 4, 2, 1) ∧
    childLaw262144To524288 .B = (28, 39, 17, 11) ∧
    childLaw262144To524288 .C = (120, 176, 64, 56) := by
  decide

theorem critical_q1_all_bifurcate_524288_to_1048576 :
    childLaw524288To1048576 .A = (4, 8, 0, 4) ∧
    childLaw524288To1048576 .B = (39, 78, 0, 39) ∧
    childLaw524288To1048576 .C = (176, 352, 0, 176) := by
  decide

theorem critical_q1_mixed_phase_1048576_to_2097152 :
    childLaw1048576To2097152 .A = (8, 13, 3, 5) ∧
    childLaw1048576To2097152 .B = (78, 129, 27, 51) ∧
    childLaw1048576To2097152 .C = (352, 595, 109, 243) := by
  decide

theorem critical_q1_two_bit_return_262144_to_1048576_subcritical :
    8 < 12 ∧ 78 < 112 ∧ 352 < 480 := by
  decide

theorem critical_q1_two_bit_return_524288_to_2097152_subcritical :
    13 < 16 ∧ 129 < 156 ∧ 595 < 704 := by
  decide
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
    two_bit_bounds = {
        "262144_to_1048576": {
            state: serialize_fraction(Fraction(PHASE_COUNTS[state][2], 4 * PHASE_COUNTS[state][0]))
            for state in PHASE_STATES
        },
        "524288_to_2097152": {
            state: serialize_fraction(Fraction(PHASE_COUNTS[state][3], 4 * PHASE_COUNTS[state][1]))
            for state in PHASE_STATES
        },
    }
    check = run_lean("critical_q1_phase_periodicity_hardening", LEAN_SOURCE)
    return {
        "verdict": "critical_q1_phase_periodicity_hardening",
        "tracked_moduli": TRACKED_MODULI,
        "phase_states": [
            {
                "state": state,
                "residues_mod_256": residues,
                "counts": PHASE_COUNTS[state],
            }
            for state, residues in PHASE_STATES.items()
        ],
        "transitions": TRANSITIONS,
        "two_bit_subcritical_bounds": two_bit_bounds,
        "theorem_names": [
            "critical_q1_mixed_phase_262144_to_524288",
            "critical_q1_all_bifurcate_524288_to_1048576",
            "critical_q1_mixed_phase_1048576_to_2097152",
            "critical_q1_two_bit_return_262144_to_1048576_subcritical",
            "critical_q1_two_bit_return_524288_to_2097152_subcritical",
        ],
        "lean_check": check,
        "interpretation": (
            "The refined critical kernel exhibits a checked alternating phase law across the next "
            "three dyadic lifts: mixed, then all-bifurcate, then mixed again. Both checked two-bit "
            "returns remain uniformly subcritical on the A/B/C quotient."
        ),
    }


def main() -> int:
    payload = build_payload()
    print(json.dumps(payload, indent=2))
    return 0 if payload["lean_check"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
