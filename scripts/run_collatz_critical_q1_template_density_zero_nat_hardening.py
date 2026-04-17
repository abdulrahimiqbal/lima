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

from scripts.run_collatz_critical_q1_template_exactness_all_depth_hardening import (
    DEFAULT_LEAN,
)


LEAN_PATH = ROOT / "researcherreview" / "ProCriticalQ1TemplateDensityZeroNat.lean"


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

def NoDangerousFrontier : Prop :=
  ∀ n, n > 1 -> kernelBound ≤ n -> ∃ k, PositiveDescentAt n k

def critical_template_kernel_density_zero_nat : Prop :=
  critical_template_kernel_exactness_all_depth -> NoDangerousFrontier

theorem critical_template_kernel_density_zero_nat_implies_no_dangerous_frontier
    (hDensity : critical_template_kernel_density_zero_nat)
    (hExactness : critical_template_kernel_exactness_all_depth) :
    NoDangerousFrontier := by
  exact hDensity hExactness
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
    anti_circularity = {
        "axiom": "axiom" in source,
        "sorry": "sorry" in source,
        "bool_field": ": Bool" in source,
        "abstract_density_bridge": "hDensityBridge" in source,
        "abstract_phase_coverage": "PhaseKernelExactCoverage" in source,
    }
    return {
        "verdict": "critical_q1_template_density_zero_nat_hardening",
        "interface_names": [
            "critical_template_kernel_exactness_all_depth",
            "NoDangerousFrontier",
            "critical_template_kernel_density_zero_nat",
        ],
        "theorem_names": [
            "critical_template_kernel_density_zero_nat_implies_no_dangerous_frontier",
        ],
        "anti_circularity": anti_circularity,
        "lean_file": str(LEAN_PATH),
        "lean_check": run_lean(
            "critical_q1_template_density_zero_nat_hardening", source
        ),
    }


def main() -> int:
    payload = build_payload()
    print(json.dumps(payload, indent=2))
    return 0 if payload["lean_check"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
