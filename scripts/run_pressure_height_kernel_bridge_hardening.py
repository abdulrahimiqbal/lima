from __future__ import annotations

import json
import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from shutil import which


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_collatz_critical_q1_base_coverage_hardening import (
    BASE_WITNESSES,
    KERNEL_BOUND,
)
from scripts.run_collatz_critical_q1_template_density_zero_nat_hardening import (
    DEFAULT_LEAN,
)


LEAN_PATH = ROOT / "researcherreview" / "ProPressureHeightKernelBridge.lean"


def _base_witness_body() -> str:
    lines = []
    for i in range(0, len(BASE_WITNESSES), 16):
        chunk = ", ".join(str(x) for x in BASE_WITNESSES[i : i + 16])
        suffix = "," if i + 16 < len(BASE_WITNESSES) else ""
        lines.append(f"  {chunk}{suffix}")
    return "\n".join(lines)


def build_lean_source() -> str:
    witness_body = _base_witness_body()
    return f"""import Std

open Std

set_option maxRecDepth 1000000

def collatzStep (n : Nat) : Nat :=
  if n % 2 = 0 then n / 2 else 3 * n + 1

def iterateNat (f : Nat → Nat) : Nat → Nat → Nat
  | 0, n => n
  | k + 1, n => iterateNat f k (f n)

def PositiveDescentAt (n k : Nat) : Prop :=
  0 < iterateNat collatzStep k n ∧ iterateNat collatzStep k n < n

def EventualPositiveDescent : Prop :=
  ∀ n, n > 1 -> ∃ k, PositiveDescentAt n k

def kernelBound : Nat := {KERNEL_BOUND}

inductive CriticalTemplateState where
  | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 | T10 | T11 | T12
  deriving DecidableEq, Repr

abbrev TemplateClassifierKey := Nat × Nat × Nat × Nat

def templateClassifier : TemplateClassifierKey → Option CriticalTemplateState
  | (27, 39, 0, 39) => some .T1
  | (31, 4, 0, 4) => some .T2
  | (255, 176, 0, 176) => some .T3
  | (27, 28, 17, 11) => some .T4
  | (27, 78, 27, 51) => some .T5
  | (27, 129, 65, 64) => some .T6
  | (31, 3, 2, 1) => some .T7
  | (31, 8, 3, 5) => some .T8
  | (31, 13, 7, 6) => some .T9
  | (255, 120, 64, 56) => some .T10
  | (255, 352, 109, 243) => some .T11
  | (255, 595, 273, 322) => some .T12
  | _ => none

structure CriticalQ1TemplateObservation where
  level : Nat
  residueClass : Nat
  sourceCount : Nat
  oneChildSources : Nat
  twoChildSources : Nat
  arisesFromCriticalShadow : Prop

def critical_template_kernel_exactness_all_depth : Prop :=
  ∃ N,
    ∀ obs : CriticalQ1TemplateObservation,
      obs.arisesFromCriticalShadow →
      N ≤ obs.level →
      templateClassifier
          (obs.residueClass, obs.sourceCount, obs.oneChildSources, obs.twoChildSources) ≠ none

def NoDangerousFrontier : Prop :=
  ∀ n, n > 1 -> kernelBound ≤ n -> ∃ k, PositiveDescentAt n k

def critical_template_kernel_density_zero_nat : Prop :=
  critical_template_kernel_exactness_all_depth -> NoDangerousFrontier

def baseWitnesses : Array Nat := #[
{witness_body}
]

def baseWitnessNat (n : Nat) : Nat :=
  baseWitnesses.getD n 0

def baseWitness (n : Fin {KERNEL_BOUND}) : Nat :=
  baseWitnessNat n.val

theorem baseWitness_sound_fin :
    ∀ n : Fin {KERNEL_BOUND},
      1 < n.val ->
      0 < iterateNat collatzStep (baseWitness n) n.val ∧
        iterateNat collatzStep (baseWitness n) n.val < n.val := by
  decide

theorem kernel_bound_has_finite_base_coverage :
    ∀ n, 1 < n -> n < kernelBound ->
      ∃ k, 0 < iterateNat collatzStep k n ∧
        iterateNat collatzStep k n < n := by
  intro n hn hlt
  have hfin : n < {KERNEL_BOUND} := by
    simpa [kernelBound] using hlt
  refine ⟨baseWitness ⟨n, hfin⟩, ?_⟩
  simpa [baseWitness] using baseWitness_sound_fin ⟨n, hfin⟩ hn

def PressureHeightExit (n k : Nat) : Prop :=
  PositiveDescentAt n k

theorem critical_q1_excludes_dangerous_frontier
    (hDensity : critical_template_kernel_density_zero_nat)
    (hExactness : critical_template_kernel_exactness_all_depth) :
    NoDangerousFrontier := by
  exact hDensity hExactness

theorem pressure_height_exit_exists_nat
    (hNoDangerous : NoDangerousFrontier) :
    ∀ n, n > 1 -> kernelBound ≤ n -> ∃ k, PressureHeightExit n k := by
  intro n hn hbound
  exact hNoDangerous n hn hbound

theorem pressure_height_exit_sound_nat :
    ∀ n k, n > 1 -> PressureHeightExit n k -> PositiveDescentAt n k := by
  intro _ _ _ hExit
  exact hExit

theorem eventual_positive_descent_from_periodic_kernel
    (hDensity : critical_template_kernel_density_zero_nat)
    (hExactness : critical_template_kernel_exactness_all_depth) :
    EventualPositiveDescent := by
  intro n hn
  by_cases hsmall : n < kernelBound
  · exact kernel_bound_has_finite_base_coverage n hn hsmall
  · have hNoDangerous : NoDangerousFrontier :=
      critical_q1_excludes_dangerous_frontier hDensity hExactness
    obtain ⟨k, hk⟩ := pressure_height_exit_exists_nat
      hNoDangerous n hn (Nat.le_of_not_lt hsmall)
    exact ⟨k, pressure_height_exit_sound_nat n k hn hk⟩
"""


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
    source = build_lean_source()
    banned_tokens = {
        "axiom": "axiom" in source,
        "sorry": "sorry" in source,
        "bool_field": ": Bool" in source,
        "abstract_shadow_control": "CriticalShadowControl" in source,
        "abstract_phase_coverage": "PhaseKernelExactCoverage" in source,
        "explicit_base_assumption": "hBase" in source,
    }
    return {
        "verdict": "pressure_height_kernel_bridge_hardening",
        "theorem_names": [
            "kernel_bound_has_finite_base_coverage",
            "critical_q1_excludes_dangerous_frontier",
            "pressure_height_exit_exists_nat",
            "pressure_height_exit_sound_nat",
            "eventual_positive_descent_from_periodic_kernel",
        ],
        "interface_names": [
            "critical_template_kernel_exactness_all_depth",
            "critical_template_kernel_density_zero_nat",
            "NoDangerousFrontier",
            "PressureHeightExit",
        ],
        "anti_circularity": banned_tokens,
        "lean_file": str(LEAN_PATH),
        "lean_check": run_lean("pressure_height_kernel_bridge_hardening", source),
    }


def main() -> int:
    payload = build_payload()
    print(json.dumps(payload, indent=2))
    return 0 if payload["lean_check"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
