from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


LEAN_PREAMBLE = """import Std

def collatzStep (n : Nat) : Nat :=
  if n % 2 = 0 then n / 2 else 3 * n + 1

def iterateNat (f : Nat -> Nat) : Nat -> Nat -> Nat
  | 0, n => n
  | k + 1, n => iterateNat f k (f n)

def PositiveDescentAt (n k : Nat) : Prop :=
  0 < iterateNat collatzStep k n ∧ iterateNat collatzStep k n < n
"""


@dataclass(frozen=True, slots=True)
class Family:
    coeff: int
    const: int


@dataclass(frozen=True, slots=True)
class ExtensionCase:
    name: str
    root: Family
    steps: int
    leaf: Family

    @property
    def rule_modulus(self) -> int:
        return self.root.coeff

    @property
    def rule_residue(self) -> int:
        return self.root.const


CASES = [
    ExtensionCase("fam_1024_287", Family(1024, 287), 16, Family(729, 205)),
    ExtensionCase("fam_1024_815", Family(1024, 815), 16, Family(729, 581)),
    ExtensionCase("fam_1024_575", Family(1024, 575), 16, Family(729, 410)),
    ExtensionCase("fam_1024_583", Family(1024, 583), 16, Family(729, 416)),
    ExtensionCase("fam_1024_347", Family(1024, 347), 16, Family(729, 248)),
    ExtensionCase("fam_1024_367", Family(1024, 367), 16, Family(729, 262)),
    ExtensionCase("fam_4096_2587", Family(4096, 2587), 19, Family(2187, 1382)),
    ExtensionCase("fam_4096_615", Family(4096, 615), 19, Family(2187, 329)),
    ExtensionCase("fam_4096_383", Family(4096, 383), 19, Family(2187, 205)),
]


def affine_expr(family: Family) -> str:
    return f"{family.coeff}*t + {family.const}"


def next_family(family: Family) -> tuple[str, Family]:
    if family.const % 2 == 0:
        if family.coeff % 2 != 0:
            raise ValueError(f"even step reached odd coefficient in {family}")
        return "even", Family(family.coeff // 2, family.const // 2)
    return "odd", Family(3 * family.coeff, 3 * family.const + 1)


def deterministic_path(case: ExtensionCase) -> list[tuple[str, Family, Family]]:
    current = case.root
    path: list[tuple[str, Family, Family]] = []
    for _ in range(case.steps):
        step_kind, nxt = next_family(current)
        path.append((step_kind, current, nxt))
        current = nxt
    if current != case.leaf:
        raise ValueError(f"{case.name} ended at {current}, expected {case.leaf}")
    return path


def render_case_source(case: ExtensionCase) -> str:
    path = deterministic_path(case)
    lines = [LEAN_PREAMBLE, ""]
    for step_index, (step_kind, current, nxt) in enumerate(path, start=1):
        theorem_name = f"{case.name}_step_{step_index}_eq"
        lines.extend(
            [
                f"theorem {theorem_name} (t : Nat) :",
                f"    collatzStep ({affine_expr(current)}) = {affine_expr(nxt)} := by",
                "  unfold collatzStep",
            ]
        )
        if step_kind == "odd":
            lines.extend(
                [
                    f"  have hodd : ({affine_expr(current)}) % 2 ≠ 0 := by omega",
                    "  simp [hodd]",
                    "  omega",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    f"  have heven : ({affine_expr(current)}) % 2 = 0 := by omega",
                    "  simp [heven]",
                    "  omega",
                    "",
                ]
            )

    lines.extend(
        [
            f"theorem {case.name}_iterate_eq (t : Nat) :",
            f"    iterateNat collatzStep {case.steps} ({affine_expr(case.root)}) = {affine_expr(case.leaf)} := by",
            "  simp [iterateNat,",
        ]
    )
    for step_index in range(1, case.steps + 1):
        suffix = "," if step_index < case.steps else "]"
        lines.append(f"    {case.name}_step_{step_index}_eq{suffix}")
    lines.extend(
        [
            "",
            f"theorem {case.name}_descent (t : Nat) :",
            f"    ∃ k, PositiveDescentAt ({affine_expr(case.root)}) k := by",
            f"  refine ⟨{case.steps}, ?_, ?_⟩",
            f"  · rw [{case.name}_iterate_eq]",
            "    omega",
            f"  · rw [{case.name}_iterate_eq]",
            "    omega",
        ]
    )
    return "\n".join(lines) + "\n"


def run_lean(name: str, source: str) -> dict[str, object]:
    result = subprocess.run(
        ["lean", "--stdin"],
        input=source,
        text=True,
        capture_output=True,
        timeout=45,
    )
    return {
        "name": name,
        "returncode": result.returncode,
        "ok": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def compile_case(case: ExtensionCase) -> dict[str, object]:
    check = run_lean(case.name, render_case_source(case))
    check.update(
        {
            "root": {"coeff": case.root.coeff, "const": case.root.const},
            "leaf": {"coeff": case.leaf.coeff, "const": case.leaf.const},
            "steps": case.steps,
            "rule": {
                "name": case.name,
                "modulus": case.rule_modulus,
                "residue": case.rule_residue,
                "coeff_numerator": case.leaf.coeff,
                "coeff_denominator": case.root.coeff,
                "leaf_const": case.leaf.const,
                "cost": case.steps,
            },
        }
    )
    return check


def main() -> int:
    checks = [compile_case(case) for case in CASES]
    payload = {
        "verdict": "collatz_descent_extension_hardened",
        "all_cases_compile": all(check["ok"] for check in checks),
        "audited_case_count": len(CASES),
        "researcher_draft_path": "researcherreview/Collatz Conjecture Extension.lean",
        "proved_now": [
            "1024*t + 287 descends in 16 steps to 729*t + 205.",
            "1024*t + 815 descends in 16 steps to 729*t + 581.",
            "1024*t + 575 descends in 16 steps to 729*t + 410.",
            "1024*t + 583 descends in 16 steps to 729*t + 416.",
            "1024*t + 347 descends in 16 steps to 729*t + 248.",
            "1024*t + 367 descends in 16 steps to 729*t + 262.",
            "4096*t + 2587 descends in 19 steps to 2187*t + 1382.",
            "4096*t + 615 descends in 19 steps to 2187*t + 329.",
            "4096*t + 383 descends in 19 steps to 2187*t + 205.",
        ],
        "generic_rule_inventory": [check["rule"] for check in checks],
        "next_action": (
            "These rules harden refined residue children, not full parent roots. "
            "Use them inside the affine rewrite compass, then analyze the dyadic "
            "refinement tree needed to close all children of each unresolved parent family."
        ),
        "checks": checks,
    }
    print(json.dumps(payload, indent=2))
    return 0 if payload["all_cases_compile"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
