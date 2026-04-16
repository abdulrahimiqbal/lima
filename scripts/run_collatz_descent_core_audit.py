from __future__ import annotations

import json
import subprocess


COLLATZ_DESCENT_CORE = r"""
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
""".strip()


EXIT_BRIDGE_COMPRESSION = (
    COLLATZ_DESCENT_CORE
    + r"""

axiom NoDangerousFrontier : Prop
axiom PressureHeightExit : Nat -> Nat -> Prop

theorem eventual_positive_descent_from_pressure_height_exit_bridge
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

theorem collatz_from_pressure_height_exit_bridge
    (hNoDanger : NoDangerousFrontier)
    (hExitExists :
      NoDangerousFrontier ->
      ∀ n, n > 1 -> ∃ k, PressureHeightExit n k)
    (hExitSound :
      ∀ n k, n > 1 -> PressureHeightExit n k ->
        0 < iterateNat collatzStep k n ∧ iterateNat collatzStep k n < n) :
    ∀ n, n > 0 -> CollatzTerminates n := by
  exact collatz_from_eventual_positive_descent
    (eventual_positive_descent_from_pressure_height_exit_bridge
      hNoDanger hExitExists hExitSound)
"""
)


RAW_PRESSURE_HEIGHT_BRIDGE_ATTEMPT = (
    COLLATZ_DESCENT_CORE
    + r"""

axiom NoDangerousFrontier : Prop

theorem no_dangerous_frontier_implies_eventual_positive_descent_raw
    (hNoDanger : NoDangerousFrontier) :
    EventualPositiveDescent := by
  intro n hn
"""
)


def run_lean(name: str, source: str) -> dict[str, object]:
    result = subprocess.run(
        ["lean", "--stdin"],
        input=source,
        text=True,
        capture_output=True,
        timeout=30,
    )
    return {
        "name": name,
        "returncode": result.returncode,
        "ok": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def excerpt_failure(check: dict[str, object]) -> str:
    text = f"{check.get('stdout', '')}\n{check.get('stderr', '')}"
    lines = []
    for line in str(text).splitlines():
        if (
            "unsolved goals" in line
            or "⊢" in line
            or "EventualPositiveDescent" in line
            or "iterateNat collatzStep" in line
        ):
            lines.append(line.rstrip())
    return "\n".join(lines[:16])


def main() -> int:
    checks = [
        run_lean("descent_core_strong_induction", COLLATZ_DESCENT_CORE),
        run_lean("exit_bridge_compression", EXIT_BRIDGE_COMPRESSION),
        run_lean("raw_no_dangerous_to_descent_attempt", RAW_PRESSURE_HEIGHT_BRIDGE_ATTEMPT),
    ]
    core = checks[0]
    bridge = checks[1]
    raw = checks[2]
    payload = {
        "verdict": "descent_core_extracted",
        "descent_core_compiles": core["ok"],
        "exit_bridge_compression_compiles": bridge["ok"],
        "raw_no_dangerous_to_descent_compiles": raw["ok"],
        "raw_bridge_failure_excerpt": excerpt_failure(raw),
        "proved_now": [
            "Eventual positive descent below n implies Collatz termination by strong induction.",
            "The pressure-height route would imply Collatz if it supplies exit existence and exit soundness.",
        ],
        "single_compressed_target": (
            "For every n > 1, no-dangerous-frontier must produce a positive iterate below n."
        ),
        "remaining_pressure_height_bridges": [
            "Every ordinary n > 1 induces the relevant pressure-height frontier/object.",
            "No dangerous frontier forces a pressure-height exit for that object.",
            "Every such exit is sound as an actual Nat-level descent below n.",
        ],
        "next_action": (
            "Try to prove the exit-existence and exit-soundness bridge with concrete definitions; "
            "do not run more architecture probes until this bridge is expanded."
        ),
        "checks": checks,
    }
    print(json.dumps(payload, indent=2))
    return 0 if core["ok"] and bridge["ok"] and not raw["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
