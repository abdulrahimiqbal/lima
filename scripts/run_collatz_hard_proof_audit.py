from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


COLLATZ_DEFS = r"""
def collatzStep (n : Nat) : Nat :=
  if n % 2 = 0 then n / 2 else 3 * n + 1

def iterateNat (f : Nat -> Nat) : Nat -> Nat -> Nat
  | 0, n => n
  | k + 1, n => iterateNat f k (f n)

def CollatzTerminates (n : Nat) : Prop :=
  ∃ k, iterateNat collatzStep k n = 1

def NoOrdinaryCounterexample : Prop :=
  ¬ ∃ n : Nat, n > 0 ∧ ¬ CollatzTerminates n

theorem collatz_from_no_counterexample
    (h : NoOrdinaryCounterexample) :
    ∀ n : Nat, n > 0 -> CollatzTerminates n := by
  classical
  intro n hn
  by_cases hTerm : CollatzTerminates n
  · exact hTerm
  · exact False.elim (h ⟨n, hn, hTerm⟩)
""".strip()


ARCHITECTURE_WITH_NAMED_OBLIGATIONS = (
    COLLATZ_DEFS
    + r"""

section Architecture

variable {NoDangerousFrontier : Prop}
variable {DensityZeroSurvivors : Prop}
variable {FiniteBaseCoverage : Prop}
variable {NoSurvivorFamily : Prop}

theorem collatz_from_pressure_height_architecture
    (hNoDangerous : NoDangerousFrontier)
    (hDensityClosure : NoDangerousFrontier -> DensityZeroSurvivors)
    (hBase : FiniteBaseCoverage)
    (hSurvivorElim : DensityZeroSurvivors -> FiniteBaseCoverage -> NoSurvivorFamily)
    (hPullback : NoSurvivorFamily -> NoOrdinaryCounterexample) :
    ∀ n : Nat, n > 0 -> CollatzTerminates n := by
  exact collatz_from_no_counterexample
    (hPullback (hSurvivorElim (hDensityClosure hNoDangerous) hBase))

end Architecture
"""
)


NAT_LEVEL_TARGET_NO_SCAFFOLD = (
    COLLATZ_DEFS
    + r"""

theorem collatz_nat_level_no_scaffold :
    ∀ n : Nat, n > 0 -> CollatzTerminates n := by
  intro n hn
"""
)


OBLIGATION_AUDIT = (
    COLLATZ_DEFS
    + r"""

-- This file intentionally contains no Bool certificate fields such as
-- densityZero, compositeScarcity, or finiteBaseCoverage. The remaining
-- obligations are Props that must be expanded into concrete arithmetic.

structure HardProofDebt where
  densityClosure : Prop
  finiteBaseCoverage : Prop
  survivorElimination : Prop
  ordinaryPullback : Prop
  deriving Repr

def hardProofDebt : HardProofDebt :=
  { densityClosure := True,
    finiteBaseCoverage := True,
    survivorElimination := True,
    ordinaryPullback := True }

theorem audit_debt_names_compile :
    hardProofDebt.densityClosure ∧
    hardProofDebt.finiteBaseCoverage ∧
    hardProofDebt.survivorElimination ∧
    hardProofDebt.ordinaryPullback := by
  unfold hardProofDebt
  exact And.intro True.intro
    (And.intro True.intro (And.intro True.intro True.intro))
"""
)


SCAFFOLD_PATTERNS = {
    "densityZero_bool": r"\bdensityZero\s*:\s*Bool\b",
    "compositeScarcity_bool": r"\bcompositeScarcity\s*:\s*Bool\b",
    "finiteBaseCoverage_bool": r"\bfiniteBaseCoverage\s*:\s*Bool\b",
    "positiveDrift_bool": r"\bpositiveDrift\s*:\s*Bool\b",
    "exactCoverage_bool": r"\bexactCoverage\s*:\s*Bool\b",
    "hiddenReachability_bool": r"\bhiddenReachability\s*:\s*Bool\b",
    "hiddenTermination_bool": r"\bhiddenTermination\s*:\s*Bool\b",
    "unprovedDensityAssumption_bool": r"\bunprovedDensityAssumption\s*:\s*Bool\b",
}


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


def scan_scaffold_fields() -> dict[str, list[dict[str, object]]]:
    findings: dict[str, list[dict[str, object]]] = {key: [] for key in SCAFFOLD_PATTERNS}
    search_paths = [
        ROOT / "app" / "service.py",
        ROOT / "SOLVED.md",
        ROOT / "docs" / "COLLATZ_ROADMAP.md",
    ]
    for path in search_paths:
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            for key, pattern in SCAFFOLD_PATTERNS.items():
                if re.search(pattern, line):
                    findings[key].append(
                        {
                            "path": str(path.relative_to(ROOT)),
                            "line": lineno,
                            "text": line.strip(),
                        }
                    )
    return {key: value for key, value in findings.items() if value}


def summarize_unsolved_goal(stderr: str) -> str:
    lines = [line.rstrip() for line in stderr.splitlines()]
    relevant = [
        line
        for line in lines
        if "unsolved goals" in line
        or "case" in line
        or "⊢" in line
        or "CollatzTerminates" in line
    ]
    return "\n".join(relevant[:12])


def main() -> int:
    checks = [
        run_lean("architecture_with_named_obligations", ARCHITECTURE_WITH_NAMED_OBLIGATIONS),
        run_lean("nat_level_target_no_scaffold", NAT_LEVEL_TARGET_NO_SCAFFOLD),
        run_lean("obligation_names_compile", OBLIGATION_AUDIT),
    ]
    scaffold_findings = scan_scaffold_fields()
    nat_check = next(check for check in checks if check["name"] == "nat_level_target_no_scaffold")
    architecture_check = next(
        check for check in checks if check["name"] == "architecture_with_named_obligations"
    )
    obligation_check = next(check for check in checks if check["name"] == "obligation_names_compile")
    missing_obligations = [
        "Expand density-zero / Composite Scarcity into concrete counting and scarcity predicates.",
        "Prove no-dangerous-frontier implies the concrete density/scarcity closure.",
        "Prove finite/base coverage as an explicit arithmetic theorem, not a Bool field.",
        "Prove survivor-family elimination from concrete density plus finite/base coverage.",
        "Prove the ordinary Nat-level pullback: any nonterminating Collatz orbit induces the forbidden pressure-height object.",
    ]
    payload = {
        "verdict": "architecture_only_not_full_proof",
        "architecture_compiles_with_named_obligations": architecture_check["ok"],
        "obligation_names_compile": obligation_check["ok"],
        "nat_level_theorem_without_obligations_compiles": nat_check["ok"],
        "nat_level_failure_excerpt": summarize_unsolved_goal(
            str(nat_check["stdout"]) + "\n" + str(nat_check["stderr"])
        ),
        "scaffold_field_findings": scaffold_findings,
        "missing_obligations": missing_obligations,
        "next_action": (
            "Stop broad waves; harden one missing obligation at a time, starting with "
            "concrete density-zero / Composite Scarcity definitions."
        ),
        "checks": checks,
    }
    print(json.dumps(payload, indent=2))
    return 0 if architecture_check["ok"] and obligation_check["ok"] and not nat_check["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
