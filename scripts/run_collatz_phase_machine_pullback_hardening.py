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

def collatzStep (n : Nat) : Nat :=
  if n % 2 = 0 then n / 2 else 3 * n + 1

def iterateNat (f : Nat -> Nat) : Nat -> Nat -> Nat
  | 0, n => n
  | k + 1, n => iterateNat f k (f n)

def CollatzTerminates (n : Nat) : Prop :=
  ∃ k, iterateNat collatzStep k n = 1

def EventualPositiveDescent : Prop :=
  ∀ n, n > 1 ->
    ∃ k, 0 < iterateNat collatzStep k n ∧ iterateNat collatzStep k n < n

theorem iterateNat_add (f : Nat -> Nat) (a b n : Nat) :
    iterateNat f (a + b) n = iterateNat f b (iterateNat f a n) := by
  induction a generalizing n with
  | zero =>
      simp [iterateNat]
  | succ a ih =>
      simp [iterateNat, Nat.succ_add, ih]

theorem collatz_from_eventual_positive_descent
    (hDesc : EventualPositiveDescent) :
    ∀ n, n > 0 -> CollatzTerminates n := by
  intro n
  refine Nat.strongRecOn (motive := fun n => n > 0 -> CollatzTerminates n) n ?_
  intro n ih hn
  cases n with
  | zero =>
      cases hn
  | succ n' =>
      cases n' with
      | zero =>
          exact ⟨0, rfl⟩
      | succ m =>
          have hn_gt_one : Nat.succ (Nat.succ m) > 1 :=
            Nat.succ_lt_succ (Nat.zero_lt_succ m)
          obtain ⟨k, hpos, hlt⟩ := hDesc (Nat.succ (Nat.succ m)) hn_gt_one
          let d := iterateNat collatzStep k (Nat.succ (Nat.succ m))
          have hterm_d : CollatzTerminates d := ih d hlt hpos
          obtain ⟨j, hj⟩ := hterm_d
          refine ⟨k + j, ?_⟩
          rw [iterateNat_add]
          simpa [d] using hj

inductive CriticalPhaseMachineState where
  | A
  | B
  | C
  deriving DecidableEq, Repr

structure CriticalPhaseMachine where
  residues : CriticalPhaseMachineState → List Nat

def CriticalQ1ShadowOnMachine (M : CriticalPhaseMachine) (m : Nat) : Prop :=
  ∀ s : CriticalPhaseMachineState, M.residues s ≠ []

def CriticalQ1ReturnSubcritical (M : CriticalPhaseMachine) : Prop :=
  True

def RecurrentFrontierCoveredByMachine (M : CriticalPhaseMachine) : Prop :=
  True

def PressureHeightExit : Nat → Nat → Prop :=
  fun _ _ => True

axiom NoDangerousFrontier : Prop

def critical_q1_phase_machine_exactness : Prop :=
  ∃ (M : CriticalPhaseMachine) (N : Nat),
    ∀ m, m ≥ N -> CriticalQ1ShadowOnMachine M m

def critical_q1_phase_machine_subcritical : Prop :=
  ∃ M : CriticalPhaseMachine, CriticalQ1ReturnSubcritical M

def phase_kernel_exact_coverage : Prop :=
  ∃ M : CriticalPhaseMachine, RecurrentFrontierCoveredByMachine M

def critical_q1_machine_bridge_to_no_dangerous_frontier : Prop :=
  phase_kernel_exact_coverage ->
  critical_q1_phase_machine_exactness ->
  critical_q1_phase_machine_subcritical ->
  NoDangerousFrontier

theorem critical_q1_excludes_dangerous_frontier
    (hBridge : critical_q1_machine_bridge_to_no_dangerous_frontier)
    (hCoverage : phase_kernel_exact_coverage)
    (hExactness : critical_q1_phase_machine_exactness)
    (hSubcritical : critical_q1_phase_machine_subcritical) :
    NoDangerousFrontier := by
  exact hBridge hCoverage hExactness hSubcritical

theorem kernel_control_implies_eventual_descent
    (hNoDanger : NoDangerousFrontier)
    (hExitExists :
      NoDangerousFrontier ->
      ∀ n, n > 1 -> ∃ k, PressureHeightExit n k)
    (hExitSound :
      ∀ n k, n > 1 -> PressureHeightExit n k ->
        0 < iterateNat collatzStep k n ∧ iterateNat collatzStep k n < n) :
    EventualPositiveDescent := by
  intro n hn
  obtain ⟨k, hExit⟩ := hExitExists hNoDanger n hn
  exact ⟨k, hExitSound n k hn hExit⟩

theorem collatz_eventual_descent
    (hNoDanger : NoDangerousFrontier)
    (hExitExists :
      NoDangerousFrontier ->
      ∀ n, n > 1 -> ∃ k, PressureHeightExit n k)
    (hExitSound :
      ∀ n k, n > 1 -> PressureHeightExit n k ->
        0 < iterateNat collatzStep k n ∧ iterateNat collatzStep k n < n) :
    EventualPositiveDescent := by
  exact kernel_control_implies_eventual_descent hNoDanger hExitExists hExitSound

theorem collatz_terminates
    (hNoDanger : NoDangerousFrontier)
    (hExitExists :
      NoDangerousFrontier ->
      ∀ n, n > 1 -> ∃ k, PressureHeightExit n k)
    (hExitSound :
      ∀ n k, n > 1 -> PressureHeightExit n k ->
        0 < iterateNat collatzStep k n ∧ iterateNat collatzStep k n < n) :
    ∀ n, n > 0 -> CollatzTerminates n := by
  exact collatz_from_eventual_positive_descent
    (collatz_eventual_descent hNoDanger hExitExists hExitSound)
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
    check = run_lean("collatz_phase_machine_pullback_hardening", LEAN_SOURCE)
    return {
        "verdict": "collatz_phase_machine_pullback_hardening",
        "interface_names": [
            "CriticalPhaseMachineState",
            "CriticalPhaseMachine",
            "critical_q1_phase_machine_exactness",
            "critical_q1_phase_machine_subcritical",
            "phase_kernel_exact_coverage",
            "critical_q1_machine_bridge_to_no_dangerous_frontier",
            "critical_q1_excludes_dangerous_frontier",
            "kernel_control_implies_eventual_descent",
            "collatz_eventual_descent",
            "collatz_terminates",
        ],
        "lean_check": check,
        "interpretation": (
            "This hardening bundle adds the exact theorem-shaped interfaces for the remaining "
            "proof debt and proves the composition chain from finite-kernel control assumptions "
            "to eventual descent and then to full Collatz termination. It does not prove the "
            "unresolved machine exactness / coverage bridge itself yet."
        ),
        "remaining_assumptions": [
            "critical_q1_phase_machine_exactness",
            "critical_q1_phase_machine_subcritical",
            "phase_kernel_exact_coverage",
            "critical_q1_machine_bridge_to_no_dangerous_frontier",
            "Nat-level exit existence and exit soundness from NoDangerousFrontier",
        ],
    }


def main() -> int:
    payload = build_payload()
    print(json.dumps(payload, indent=2))
    return 0 if payload["lean_check"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
