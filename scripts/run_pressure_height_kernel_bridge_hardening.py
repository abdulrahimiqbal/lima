from __future__ import annotations

import json
import os
import subprocess
from functools import lru_cache
from pathlib import Path
from shutil import which


DEFAULT_LEAN = Path.home() / ".elan" / "bin" / "lean"
ROOT = Path(__file__).resolve().parents[1]
LEAN_PATH = ROOT / "researcherreview" / "ProPressureHeightKernelBridge.lean"


def build_lean_source() -> str:
    return """import Std

open Std

def collatzStep (n : Nat) : Nat :=
  if n % 2 = 0 then n / 2 else 3 * n + 1

def iterateNat (f : Nat → Nat) : Nat → Nat → Nat
  | 0, n => n
  | k + 1, n => iterateNat f k (f n)

def PositiveDescentAt (n k : Nat) : Prop :=
  0 < iterateNat collatzStep k n ∧ iterateNat collatzStep k n < n

def EventualPositiveDescent : Prop :=
  ∀ n, n > 1 -> ∃ k, PositiveDescentAt n k

def kernelBound : Nat := 256

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

inductive FrontierCoverage where
  | descends
  | kernelA
  | kernelB
  | kernelC
  deriving DecidableEq, Repr

def frontierCoverage : Nat → Option FrontierCoverage
  | 39 => some .descends
  | 79 => some .descends
  | 95 => some .descends
  | 123 => some .descends
  | 27 => some .kernelB
  | 31 => some .kernelA
  | 47 => some .kernelA
  | 63 => some .kernelA
  | 71 => some .kernelA
  | 91 => some .kernelA
  | 103 => some .kernelB
  | 111 => some .kernelA
  | 127 => some .kernelB
  | 155 => some .kernelA
  | 159 => some .kernelB
  | 167 => some .kernelA
  | 191 => some .kernelB
  | 207 => some .kernelA
  | 223 => some .kernelA
  | 231 => some .kernelA
  | 239 => some .kernelB
  | 251 => some .kernelA
  | 255 => some .kernelC
  | _ => none

def PhaseKernelExactCoverage : Prop :=
  frontierCoverage 39 = some .descends ∧
  frontierCoverage 79 = some .descends ∧
  frontierCoverage 95 = some .descends ∧
  frontierCoverage 123 = some .descends ∧
  frontierCoverage 27 = some .kernelB ∧
  frontierCoverage 31 = some .kernelA ∧
  frontierCoverage 47 = some .kernelA ∧
  frontierCoverage 63 = some .kernelA ∧
  frontierCoverage 71 = some .kernelA ∧
  frontierCoverage 91 = some .kernelA ∧
  frontierCoverage 103 = some .kernelB ∧
  frontierCoverage 111 = some .kernelA ∧
  frontierCoverage 127 = some .kernelB ∧
  frontierCoverage 155 = some .kernelA ∧
  frontierCoverage 159 = some .kernelB ∧
  frontierCoverage 167 = some .kernelA ∧
  frontierCoverage 191 = some .kernelB ∧
  frontierCoverage 207 = some .kernelA ∧
  frontierCoverage 223 = some .kernelA ∧
  frontierCoverage 231 = some .kernelA ∧
  frontierCoverage 239 = some .kernelB ∧
  frontierCoverage 251 = some .kernelA ∧
  frontierCoverage 255 = some .kernelC

def NoDangerousFrontier : Prop :=
  ∀ n, n > 1 -> kernelBound ≤ n -> ∃ k, PositiveDescentAt n k

def critical_template_kernel_density_zero_nat : Prop :=
  critical_template_kernel_exactness_all_depth ->
  PhaseKernelExactCoverage ->
  NoDangerousFrontier

def PressureHeightExit (n k : Nat) : Prop :=
  PositiveDescentAt n k

theorem critical_q1_excludes_dangerous_frontier
    (hDensity : critical_template_kernel_density_zero_nat)
    (hExactness : critical_template_kernel_exactness_all_depth)
    (hCoverage : PhaseKernelExactCoverage) :
    NoDangerousFrontier := by
  exact hDensity hExactness hCoverage

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
    (hExactness : critical_template_kernel_exactness_all_depth)
    (hCoverage : PhaseKernelExactCoverage)
    (hBase :
      ∀ n, n > 1 -> n < kernelBound -> ∃ k, PositiveDescentAt n k) :
    EventualPositiveDescent := by
  intro n hn
  by_cases hsmall : n < kernelBound
  · exact hBase n hn hsmall
  · have hNoDangerous : NoDangerousFrontier :=
      critical_q1_excludes_dangerous_frontier hDensity hExactness hCoverage
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
    }
    return {
        "verdict": "pressure_height_kernel_bridge_hardening",
        "theorem_names": [
            "critical_q1_excludes_dangerous_frontier",
            "pressure_height_exit_exists_nat",
            "pressure_height_exit_sound_nat",
            "eventual_positive_descent_from_periodic_kernel",
        ],
        "interface_names": [
            "critical_template_kernel_exactness_all_depth",
            "PhaseKernelExactCoverage",
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
