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

DEFAULT_LEAN = Path.home() / ".elan" / "bin" / "lean"
LEAN_PATH = ROOT / "researcherreview" / "ProCriticalQ1BaseCoverage.lean"
KERNEL_BOUND = 256
BASE_WITNESSES = [
    0, 0, 1, 6, 1, 3, 1, 11, 1, 3, 1, 8, 1, 3, 1, 11,
    1, 3, 1, 6, 1, 3, 1, 8, 1, 3, 1, 96, 1, 3, 1, 91,
    1, 3, 1, 6, 1, 3, 1, 13, 1, 3, 1, 8, 1, 3, 1, 88,
    1, 3, 1, 6, 1, 3, 1, 8, 1, 3, 1, 11, 1, 3, 1, 88,
    1, 3, 1, 6, 1, 3, 1, 83, 1, 3, 1, 8, 1, 3, 1, 13,
    1, 3, 1, 6, 1, 3, 1, 8, 1, 3, 1, 73, 1, 3, 1, 13,
    1, 3, 1, 6, 1, 3, 1, 68, 1, 3, 1, 8, 1, 3, 1, 50,
    1, 3, 1, 6, 1, 3, 1, 8, 1, 3, 1, 13, 1, 3, 1, 24,
    1, 3, 1, 6, 1, 3, 1, 11, 1, 3, 1, 8, 1, 3, 1, 11,
    1, 3, 1, 6, 1, 3, 1, 8, 1, 3, 1, 65, 1, 3, 1, 34,
    1, 3, 1, 6, 1, 3, 1, 47, 1, 3, 1, 8, 1, 3, 1, 13,
    1, 3, 1, 6, 1, 3, 1, 8, 1, 3, 1, 11, 1, 3, 1, 21,
    1, 3, 1, 6, 1, 3, 1, 13, 1, 3, 1, 8, 1, 3, 1, 21,
    1, 3, 1, 6, 1, 3, 1, 8, 1, 3, 1, 13, 1, 3, 1, 50,
    1, 3, 1, 6, 1, 3, 1, 19, 1, 3, 1, 8, 1, 3, 1, 32,
    1, 3, 1, 6, 1, 3, 1, 8, 1, 3, 1, 44, 1, 3, 1, 21,
]


def build_lean_source() -> str:
    witness_lines = []
    for i in range(0, len(BASE_WITNESSES), 16):
        chunk = ", ".join(str(x) for x in BASE_WITNESSES[i : i + 16])
        suffix = "," if i + 16 < len(BASE_WITNESSES) else ""
        witness_lines.append(f"  {chunk}{suffix}")
    witness_body = "\n".join(witness_lines)
    return f"""import Std

open Std

set_option maxRecDepth 1000000

def collatzStep (n : Nat) : Nat :=
  if n % 2 = 0 then n / 2 else 3 * n + 1

def iterateNat (f : Nat → Nat) : Nat → Nat → Nat
  | 0, n => n
  | k + 1, n => iterateNat f k (f n)

def kernelBound : Nat := {KERNEL_BOUND}

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
        timeout=120,
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
    return {
        "verdict": "critical_q1_base_coverage_hardening",
        "kernel_bound": KERNEL_BOUND,
        "witness_count": len(BASE_WITNESSES),
        "max_witness": max(BASE_WITNESSES),
        "sample_witnesses": {
            "2": BASE_WITNESSES[2],
            "27": BASE_WITNESSES[27],
            "31": BASE_WITNESSES[31],
            "127": BASE_WITNESSES[127],
            "255": BASE_WITNESSES[255],
        },
        "theorem_names": [
            "baseWitness_sound_fin",
            "kernel_bound_has_finite_base_coverage",
        ],
        "lean_file": str(LEAN_PATH),
        "lean_check": run_lean("critical_q1_base_coverage_hardening", build_lean_source()),
    }


def main() -> int:
    payload = build_payload()
    print(json.dumps(payload, indent=2))
    return 0 if payload["lean_check"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
