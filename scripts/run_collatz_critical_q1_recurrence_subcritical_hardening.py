from __future__ import annotations

import json
import os
import subprocess
from functools import lru_cache
from pathlib import Path
from shutil import which


DEFAULT_LEAN = Path.home() / ".elan" / "bin" / "lean"


LEAN_SOURCE = r"""import Std

open Std

def aSeq : Nat -> Nat
  | 0 => 1
  | n + 1 => aSeq n

def bSeq : Nat -> Nat
  | 0 => 7
  | n + 1 => bSeq n + 1

def cSeq : Nat -> Nat
  | 0 => 22
  | n + 1 => cSeq n + bSeq n

theorem aSeq_fixed : ∀ n, aSeq n = 1
  | 0 => by simp [aSeq]
  | n + 1 => by simpa [aSeq] using aSeq_fixed n

theorem bSeq_recurrence :
    bSeq 0 = 7 ∧ ∀ n, bSeq (n + 1) = bSeq n + 1 := by
  constructor
  · simp [bSeq]
  · intro n
    simp [bSeq]

theorem cSeq_recurrence :
    cSeq 0 = 22 ∧ ∀ n, cSeq (n + 1) = cSeq n + bSeq n := by
  constructor
  · simp [cSeq]
  · intro n
    simp [cSeq]

theorem b_ge_seven : ∀ n, 7 ≤ bSeq n
  | 0 => by simp [bSeq]
  | n + 1 => by
      have ih := b_ge_seven n
      simpa [bSeq] using Nat.le_succ_of_le ih

theorem c_ge_twenty_two : ∀ n, 22 ≤ cSeq n
  | 0 => by simp [cSeq]
  | n + 1 => by
      have ih := c_ge_twenty_two n
      have hmono : cSeq n ≤ cSeq n + bSeq n := Nat.le_add_right (cSeq n) (bSeq n)
      simpa [cSeq] using le_trans ih hmono

theorem b_gt_one (n : Nat) : 1 < bSeq n := by
  exact lt_of_lt_of_le (by decide) (b_ge_seven n)

theorem c_gt_one (n : Nat) : 1 < cSeq n := by
  exact lt_of_lt_of_le (by decide) (c_ge_twenty_two n)

theorem b_lt_c : ∀ n, bSeq n < cSeq n
  | 0 => by decide
  | n + 1 => by
      have hc : 1 < cSeq n := c_gt_one n
      have h := Nat.add_lt_add_left hc (bSeq n)
      simpa [bSeq, cSeq, Nat.add_comm, Nat.add_left_comm, Nat.add_assoc] using h

theorem b_subcritical : ∀ n, bSeq (n + 1) < 2 * bSeq n
  | n => by
      have hb : 1 < bSeq n := b_gt_one n
      have h := Nat.add_lt_add_left hb (bSeq n)
      simpa [bSeq, Nat.two_mul, Nat.add_comm, Nat.add_left_comm, Nat.add_assoc] using h

theorem c_subcritical : ∀ n, cSeq (n + 1) < 2 * cSeq n
  | n => by
      have hb : bSeq n < cSeq n := b_lt_c n
      have h := Nat.add_lt_add_left hb (cSeq n)
      simpa [cSeq, Nat.two_mul, Nat.add_comm, Nat.add_left_comm, Nat.add_assoc] using h

theorem critical_q1_abstract_kernel_uniform_subcritical :
    (∀ n, bSeq (n + 1) < 2 * bSeq n) ∧
    (∀ n, cSeq (n + 1) < 2 * cSeq n) := by
  exact ⟨b_subcritical, c_subcritical⟩
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
    check = run_lean("critical_q1_recurrence_subcritical_hardening", LEAN_SOURCE)
    return {
        "verdict": "critical_q1_recurrence_subcritical_hardening",
        "theorem_names": [
            "aSeq_fixed",
            "bSeq_recurrence",
            "cSeq_recurrence",
            "b_lt_c",
            "b_subcritical",
            "c_subcritical",
            "critical_q1_abstract_kernel_uniform_subcritical",
        ],
        "lean_check": check,
        "interpretation": (
            "This is the all-depth algebraic side of the critical Q1 kernel. "
            "If the actual arithmetic shadow is shown to follow the A/B/C recurrence, "
            "then the strict subcriticality inequalities are already Lean-clean."
        ),
    }


def main() -> int:
    payload = build_payload()
    print(json.dumps(payload, indent=2))
    return 0 if payload["lean_check"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
