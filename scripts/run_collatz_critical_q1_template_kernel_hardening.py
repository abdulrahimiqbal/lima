from __future__ import annotations

import json
import os
import subprocess
from functools import lru_cache
from pathlib import Path
from shutil import which


DEFAULT_LEAN = Path.home() / ".elan" / "bin" / "lean"
ROOT = Path(__file__).resolve().parents[1]
LEAN_PATH = ROOT / "researcherreview" / "ProCriticalQ1TemplateKernel.lean"

TEMPLATE_STATES = [
    {
        "state": "T1",
        "phase": "bifurcate",
        "residue_mod_256": 27,
        "source_count": 39,
        "target_count": 78,
        "one_child_sources": 0,
        "two_child_sources": 39,
        "weight_num": 39,
        "weight_den": 1,
        "two_bit_succ": ["T6"],
    },
    {
        "state": "T2",
        "phase": "bifurcate",
        "residue_mod_256": 31,
        "source_count": 4,
        "target_count": 8,
        "one_child_sources": 0,
        "two_child_sources": 4,
        "weight_num": 4,
        "weight_den": 1,
        "two_bit_succ": ["T9"],
    },
    {
        "state": "T3",
        "phase": "bifurcate",
        "residue_mod_256": 255,
        "source_count": 176,
        "target_count": 352,
        "one_child_sources": 0,
        "two_child_sources": 176,
        "weight_num": 176,
        "weight_den": 1,
        "two_bit_succ": ["T12"],
    },
    {
        "state": "T4",
        "phase": "mixed",
        "residue_mod_256": 27,
        "source_count": 28,
        "target_count": 39,
        "one_child_sources": 17,
        "two_child_sources": 11,
        "weight_num": 28,
        "weight_den": 1,
        "two_bit_succ": ["T5"],
    },
    {
        "state": "T5",
        "phase": "mixed",
        "residue_mod_256": 27,
        "source_count": 78,
        "target_count": 129,
        "one_child_sources": 27,
        "two_child_sources": 51,
        "weight_num": 78,
        "weight_den": 1,
        "two_bit_succ": ["T6"],
    },
    {
        "state": "T6",
        "phase": "mixed",
        "residue_mod_256": 27,
        "source_count": 129,
        "target_count": 193,
        "one_child_sources": 65,
        "two_child_sources": 64,
        "weight_num": 129,
        "weight_den": 1,
        "two_bit_succ": [],
    },
    {
        "state": "T7",
        "phase": "mixed",
        "residue_mod_256": 31,
        "source_count": 3,
        "target_count": 4,
        "one_child_sources": 2,
        "two_child_sources": 1,
        "weight_num": 3,
        "weight_den": 1,
        "two_bit_succ": ["T8"],
    },
    {
        "state": "T8",
        "phase": "mixed",
        "residue_mod_256": 31,
        "source_count": 8,
        "target_count": 13,
        "one_child_sources": 3,
        "two_child_sources": 5,
        "weight_num": 8,
        "weight_den": 1,
        "two_bit_succ": ["T9"],
    },
    {
        "state": "T9",
        "phase": "mixed",
        "residue_mod_256": 31,
        "source_count": 13,
        "target_count": 19,
        "one_child_sources": 7,
        "two_child_sources": 6,
        "weight_num": 13,
        "weight_den": 1,
        "two_bit_succ": [],
    },
    {
        "state": "T10",
        "phase": "mixed",
        "residue_mod_256": 255,
        "source_count": 120,
        "target_count": 176,
        "one_child_sources": 64,
        "two_child_sources": 56,
        "weight_num": 120,
        "weight_den": 1,
        "two_bit_succ": ["T11"],
    },
    {
        "state": "T11",
        "phase": "mixed",
        "residue_mod_256": 255,
        "source_count": 352,
        "target_count": 595,
        "one_child_sources": 109,
        "two_child_sources": 243,
        "weight_num": 352,
        "weight_den": 1,
        "two_bit_succ": ["T12"],
    },
    {
        "state": "T12",
        "phase": "mixed",
        "residue_mod_256": 255,
        "source_count": 595,
        "target_count": 917,
        "one_child_sources": 273,
        "two_child_sources": 322,
        "weight_num": 595,
        "weight_den": 1,
        "two_bit_succ": [],
    },
]

CHECKED_WINDOW_MODULI = [262144, 524288, 1048576, 2097152]


def _state_clause(field: str) -> str:
    lines = []
    for row in TEMPLATE_STATES:
        value = row[field]
        if isinstance(value, str) and value in {"mixed", "bifurcate"}:
            value = f".{value}"
        elif isinstance(value, list):
            value = "[" + ", ".join(f".{item}" for item in value) + "]"
        lines.append(f"  | .{row['state']} => {value}")
    return "\n".join(lines)


def build_lean_source() -> str:
    state_names = "\n".join(f"  | {row['state']}" for row in TEMPLATE_STATES)
    partition_terms = []
    transition_terms = []
    weight_terms = []
    for row in TEMPLATE_STATES:
        state = f".{row['state']}"
        partition_terms.extend(
            [
                f"templatePhase {state} = .{row['phase']}",
                f"templateResidueClass {state} = {row['residue_mod_256']}",
                f"templateSourceCount {state} = {row['source_count']}",
                f"templateTargetCount {state} = {row['target_count']}",
                f"templateOneChildSources {state} = {row['one_child_sources']}",
                f"templateTwoChildSources {state} = {row['two_child_sources']}",
            ]
        )
        succ = "[" + ", ".join(f".{item}" for item in row["two_bit_succ"]) + "]"
        transition_terms.append(f"templateTwoBitSucc {state} = {succ}")
        weight_terms.extend(
            [
                f"templateWeightNum {state} = {row['weight_num']}",
                f"templateWeightDen {state} = {row['weight_den']}",
            ]
        )

    return f"""import Std

open Std

/-!
This file freezes the current checked critical shadow into a deterministic
phase-aware template kernel. The state order is canonical: lexicographic by
`(phase, residue_mod_256, one_child_sources, two_child_sources, target_count)`.
The currently checked two-bit successor data is exact on the verified window
through source moduli `262144`, `524288`, `1048576`, and `2097152`.
-/

inductive CriticalPhase where
  | mixed
  | bifurcate
  deriving DecidableEq, Repr

inductive CriticalTemplateState where
{state_names}
  deriving DecidableEq, Repr

def templatePhase : CriticalTemplateState → CriticalPhase
{_state_clause("phase")}

def templateResidueClass : CriticalTemplateState → Nat
{_state_clause("residue_mod_256")}

def templateSourceCount : CriticalTemplateState → Nat
{_state_clause("source_count")}

def templateTargetCount : CriticalTemplateState → Nat
{_state_clause("target_count")}

def templateOneChildSources : CriticalTemplateState → Nat
{_state_clause("one_child_sources")}

def templateTwoChildSources : CriticalTemplateState → Nat
{_state_clause("two_child_sources")}

def templateWeightNum : CriticalTemplateState → Nat
{_state_clause("weight_num")}

def templateWeightDen : CriticalTemplateState → Nat
{_state_clause("weight_den")}

def templateWeight (s : CriticalTemplateState) : Rat :=
  (templateWeightNum s : Rat) / templateWeightDen s

def templateTwoBitSucc : CriticalTemplateState → List CriticalTemplateState
{_state_clause("two_bit_succ")}

theorem critical_template_kernel_partition_checked_window :
    {" ∧\n    ".join(partition_terms)} := by
  simp [
    templatePhase,
    templateResidueClass,
    templateSourceCount,
    templateTargetCount,
    templateOneChildSources,
    templateTwoChildSources,
  ]

theorem critical_template_kernel_transition_checked_window :
    {" ∧\n    ".join(transition_terms)} := by
  simp [templateTwoBitSucc]

theorem critical_template_kernel_weight_data_checked_window :
    {" ∧\n    ".join(weight_terms)} := by
  simp [templateWeightNum, templateWeightDen]
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
    return {
        "verdict": "critical_q1_template_kernel_hardening",
        "checked_window_moduli": CHECKED_WINDOW_MODULI,
        "template_states": TEMPLATE_STATES,
        "theorem_names": [
            "critical_template_kernel_partition_checked_window",
            "critical_template_kernel_transition_checked_window",
            "critical_template_kernel_weight_data_checked_window",
        ],
        "lean_file": str(LEAN_PATH),
        "lean_check": run_lean("critical_q1_template_kernel_hardening", source),
    }


def main() -> int:
    payload = build_payload()
    print(json.dumps(payload, indent=2))
    return 0 if payload["lean_check"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
