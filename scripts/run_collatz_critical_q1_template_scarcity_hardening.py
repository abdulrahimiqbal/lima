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

from scripts.run_collatz_critical_q1_template_kernel_hardening import (
    DEFAULT_LEAN,
    LEAN_PATH as TEMPLATE_KERNEL_LEAN_PATH,
    TEMPLATE_STATES,
)


LEAN_PATH = ROOT / "researcherreview" / "ProCriticalQ1TemplateScarcity.lean"
EPSILON = Fraction(1, 2)


def serialize_fraction(value: Fraction) -> dict[str, object]:
    rational = str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"
    return {"rational": rational, "float": float(value)}


def build_lean_source() -> str:
    state_names = "\n".join(f"  | {row['state']}" for row in TEMPLATE_STATES)
    source_clause = "\n".join(f"  | .{row['state']} => {row['source_count']}" for row in TEMPLATE_STATES)
    target_clause = "\n".join(f"  | .{row['state']} => {row['target_count']}" for row in TEMPLATE_STATES)
    den_clause = "\n".join(f"  | .{row['state']} => 1" for row in TEMPLATE_STATES)
    return f"""import Std

open Std

/-!
This file packages the exact two-bit contraction data on the checked template
kernel. The proved theorem is an integer cross-multiplication form of the
dyadically normalized contraction inequality with uniform epsilon `1/2`.
The remaining analytic step is explicit: turn this concrete contraction law
into a density-zero theorem for the true stabilized critical shadow.
-/

inductive CriticalTemplateState where
{state_names}
  deriving DecidableEq, Repr

def templateWeightNum : CriticalTemplateState → Nat
{source_clause}

def templateWeightDen : CriticalTemplateState → Nat
{den_clause}

def weightedTwoBitMassNum : CriticalTemplateState → Nat
{target_clause}

def weightedTwoBitMassDen : CriticalTemplateState → Nat
  | .T1 => 4
  | .T2 => 4
  | .T3 => 4
  | .T4 => 4
  | .T5 => 4
  | .T6 => 4
  | .T7 => 4
  | .T8 => 4
  | .T9 => 4
  | .T10 => 4
  | .T11 => 4
  | .T12 => 4

def templateEpsilonNum : Nat := 1
def templateEpsilonDen : Nat := 2

theorem critical_template_kernel_weight_positive :
    ∀ s, 0 < templateWeightNum s ∧ 0 < templateWeightDen s := by
  intro s
  cases s <;> decide

theorem critical_template_kernel_two_bit_contraction :
    ∀ s,
      weightedTwoBitMassNum s * templateEpsilonDen * templateWeightDen s ≤
        weightedTwoBitMassDen s * (templateEpsilonDen - templateEpsilonNum) * templateWeightNum s := by
  intro s
  cases s <;> decide

theorem critical_template_kernel_density_zero
    {{DensityZeroCriticalShadow : Prop}}
    (hDensityBridge :
      (∀ s, weightedTwoBitMassNum s * templateEpsilonDen * templateWeightDen s ≤
        weightedTwoBitMassDen s * (templateEpsilonDen - templateEpsilonNum) * templateWeightNum s) ->
      DensityZeroCriticalShadow) :
    DensityZeroCriticalShadow := by
  apply hDensityBridge
  exact critical_template_kernel_two_bit_contraction
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
    ratios = {
        row["state"]: serialize_fraction(Fraction(row["target_count"], 4 * row["source_count"]))
        for row in TEMPLATE_STATES
    }
    return {
        "verdict": "critical_q1_template_scarcity_hardening",
        "template_kernel_lean_file": str(TEMPLATE_KERNEL_LEAN_PATH),
        "lean_file": str(LEAN_PATH),
        "epsilon": serialize_fraction(EPSILON),
        "per_state_two_bit_ratio": ratios,
        "worst_ratio": serialize_fraction(max(Fraction(row["target_count"], 4 * row["source_count"]) for row in TEMPLATE_STATES)),
        "theorem_names": [
            "critical_template_kernel_weight_positive",
            "critical_template_kernel_two_bit_contraction",
            "critical_template_kernel_density_zero",
        ],
        "lean_check": run_lean("critical_q1_template_scarcity_hardening", build_lean_source()),
    }


def main() -> int:
    payload = build_payload()
    print(json.dumps(payload, indent=2))
    return 0 if payload["lean_check"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
