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

from scripts.run_collatz_critical_q1_phase_machine_exactness_hardening import (
    DEFAULT_LEAN,
    PHASE_STATES,
)


LEAN_PATH = ROOT / "researcherreview" / "ProPhaseKernelExactCoverage.lean"
DESCENDED_ROOTS_128 = [39, 79, 95, 123]

KERNEL_CLASSIFICATION = {}
for residue in DESCENDED_ROOTS_128:
    KERNEL_CLASSIFICATION[residue] = "descends"
for residue in PHASE_STATES["A"]:
    KERNEL_CLASSIFICATION[residue] = "kernelA"
for residue in PHASE_STATES["B"]:
    KERNEL_CLASSIFICATION[residue] = "kernelB"
for residue in PHASE_STATES["C"]:
    KERNEL_CLASSIFICATION[residue] = "kernelC"

ORDERED_FRONTIER = [
    39,
    79,
    95,
    123,
    27,
    31,
    47,
    63,
    71,
    91,
    103,
    111,
    127,
    155,
    159,
    167,
    191,
    207,
    223,
    231,
    239,
    251,
    255,
]


def build_lean_source() -> str:
    coverage_lines = []
    for residue in ORDERED_FRONTIER:
        coverage_lines.append(
            f"frontierCoverage {residue} = some .{KERNEL_CLASSIFICATION[residue]}"
        )
    coverage_body = " ∧\n    ".join(coverage_lines)

    classifier_lines = [
        f"  | {residue} => some .{label}"
        for residue, label in KERNEL_CLASSIFICATION.items()
    ]

    return f"""import Std

open Std

inductive FrontierCoverage where
  | descends
  | kernelA
  | kernelB
  | kernelC
  deriving DecidableEq, Repr

def frontierCoverage : Nat → Option FrontierCoverage
{chr(10).join(classifier_lines)}
  | _ => none

def PhaseKernelExactCoverage : Prop :=
  {coverage_body}

theorem phase_kernel_exact_coverage : PhaseKernelExactCoverage := by
  repeat' constructor
  all_goals rfl
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
        "verdict": "phase_kernel_exact_coverage_hardening",
        "frontier_classification": {
            str(residue): KERNEL_CLASSIFICATION[residue] for residue in ORDERED_FRONTIER
        },
        "theorem_names": [
            "phase_kernel_exact_coverage",
        ],
        "interface_names": [
            "FrontierCoverage",
            "PhaseKernelExactCoverage",
        ],
        "lean_file": str(LEAN_PATH),
        "lean_check": run_lean("phase_kernel_exact_coverage_hardening", source),
        "interpretation": (
            "This packages the live arithmetic frontier as a finite exact classification theorem: "
            "the descended mod-128 roots are marked `descends`, and the 19 open mod-256 classes "
            "are placed into the kernel A/B/C projection."
        ),
    }


def main() -> int:
    payload = build_payload()
    print(json.dumps(payload, indent=2))
    return 0 if payload["lean_check"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
