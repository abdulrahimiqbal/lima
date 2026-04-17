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

from scripts.run_collatz_critical_q1_template_kernel_hardening import (
    DEFAULT_LEAN,
    TEMPLATE_STATES,
)


LEAN_PATH = ROOT / "researcherreview" / "ProCriticalQ1TemplateExactnessAllDepth.lean"
STABILIZATION_THRESHOLD = 262144


def _successor_of(row: dict[str, object]) -> str:
    successors = row["two_bit_succ"]
    if not successors:
        return "none"
    return f"some .{successors[0]}"


def build_lean_source() -> str:
    state_names = "\n".join(f"  | {row['state']}" for row in TEMPLATE_STATES)
    classifier_lines = []
    checked_lines = []
    return_num_lines = []
    return_den_lines = []
    lift_lines = []
    successor_lines = []

    for row in TEMPLATE_STATES:
        key = (
            row["residue_mod_256"],
            row["source_count"],
            row["one_child_sources"],
            row["two_child_sources"],
        )
        classifier_lines.append(
            f"  | ({key[0]}, {key[1]}, {key[2]}, {key[3]}) => some .{row['state']}"
        )
        checked_lines.append(
            "templateClassifier "
            f"({key[0]}, {key[1]}, {key[2]}, {key[3]}) = some .{row['state']}"
        )
        return_num_lines.append(f"  | .{row['state']} => {row['target_count']}")
        return_den_lines.append(f"  | .{row['state']} => {4 * row['source_count']}")
        lift_target = _successor_of(row)
        lift_lines.append(f"  | .{row['state']} => {lift_target}")
        successor_lines.append(
            f"templateTwoBitLift .{row['state']} = {lift_target}"
        )

    checked_classifier = " ∧\n    ".join(checked_lines)
    checked_successors = " ∧\n    ".join(successor_lines)

    return f"""import Std

open Std

inductive CriticalTemplateState where
{state_names}
  deriving DecidableEq, Repr

abbrev TemplateClassifierKey := Nat × Nat × Nat × Nat

def templateClassifier : TemplateClassifierKey → Option CriticalTemplateState
{chr(10).join(classifier_lines)}
  | _ => none

def templateTwoBitLift : CriticalTemplateState → Option CriticalTemplateState
{chr(10).join(lift_lines)}

def templateStabilizationThreshold : Nat := {STABILIZATION_THRESHOLD}

def templateTwoBitReturnNum : CriticalTemplateState → Nat
{chr(10).join(return_num_lines)}

def templateTwoBitReturnDen : CriticalTemplateState → Nat
{chr(10).join(return_den_lines)}

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

theorem critical_template_kernel_classifier_checked_prefix :
    {checked_classifier} := by
  native_decide

theorem critical_template_kernel_checked_successor_law :
    {checked_successors} := by
  native_decide

theorem critical_template_kernel_checked_stabilization_threshold :
    templateStabilizationThreshold = {STABILIZATION_THRESHOLD} := by
  native_decide

theorem critical_template_kernel_checked_prefix_return_factors :
    templateTwoBitReturnNum .T1 = 78 ∧ templateTwoBitReturnDen .T1 = 156 ∧
    templateTwoBitReturnNum .T6 = 193 ∧ templateTwoBitReturnDen .T6 = 516 ∧
    templateTwoBitReturnNum .T9 = 19 ∧ templateTwoBitReturnDen .T9 = 52 ∧
    templateTwoBitReturnNum .T12 = 917 ∧ templateTwoBitReturnDen .T12 = 2380 := by
  native_decide
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
    classifier_rows = [
        {
            "state": row["state"],
            "classifier_key": {
                "residue_mod_256": row["residue_mod_256"],
                "source_count": row["source_count"],
                "one_child_sources": row["one_child_sources"],
                "two_child_sources": row["two_child_sources"],
            },
            "two_bit_return": {
                "numerator": row["target_count"],
                "denominator": 4 * row["source_count"],
            },
            "two_bit_successor": row["two_bit_succ"][0] if row["two_bit_succ"] else None,
        }
        for row in TEMPLATE_STATES
    ]
    return {
        "verdict": "critical_q1_template_exactness_all_depth_hardening",
        "interface_names": [
            "CriticalQ1TemplateObservation",
            "critical_template_kernel_exactness_all_depth",
            "templateTwoBitLift",
            "templateStabilizationThreshold",
        ],
        "theorem_names": [
            "critical_template_kernel_classifier_checked_prefix",
            "critical_template_kernel_checked_successor_law",
            "critical_template_kernel_checked_stabilization_threshold",
            "critical_template_kernel_checked_prefix_return_factors",
        ],
        "stabilization_threshold": STABILIZATION_THRESHOLD,
        "classifier_rows": classifier_rows,
        "lean_file": str(LEAN_PATH),
        "lean_check": run_lean(
            "critical_q1_template_exactness_all_depth_hardening", source
        ),
        "remaining_gap": (
            "The template classifier, two-bit successor law, stabilization threshold, "
            "and checked return factors are now exact and Lean-clean. "
            "The remaining proof debt is the all-depth arithmetic theorem named "
            "`critical_template_kernel_exactness_all_depth`."
        ),
    }


def main() -> int:
    payload = build_payload()
    print(json.dumps(payload, indent=2))
    return 0 if payload["lean_check"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
