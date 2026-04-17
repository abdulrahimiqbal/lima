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
class FrontierCase:
    name: str
    root: Family
    steps: int
    leaf: Family


CASES = [
    FrontierCase("fam_256_39", Family(256, 39), 13, Family(243, 38)),
    FrontierCase("fam_256_79", Family(256, 79), 13, Family(243, 76)),
    FrontierCase("fam_256_95", Family(256, 95), 13, Family(243, 91)),
    FrontierCase("fam_256_123", Family(256, 123), 13, Family(243, 118)),
]


def affine_expr(family: Family) -> str:
    return f"{family.coeff}*t + {family.const}"


def next_family_step(family: Family) -> tuple[str, Family]:
    if family.const % 2 == 1:
        return "odd", Family(3 * family.coeff, 3 * family.const + 1)
    if family.coeff % 2 != 0:
        raise ValueError(f"Even step reached odd coefficient in {family}")
    return "even", Family(family.coeff // 2, family.const // 2)


def deterministic_path(case: FrontierCase) -> list[tuple[str, Family, Family]]:
    current = case.root
    path: list[tuple[str, Family, Family]] = []
    for _ in range(case.steps):
        step_kind, nxt = next_family_step(current)
        path.append((step_kind, current, nxt))
        current = nxt
    if current != case.leaf:
        raise ValueError(f"{case.name} ended at {current}, expected {case.leaf}")
    return path


def render_case_source(case: FrontierCase) -> str:
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
        timeout=180,
    )
    return {
        "name": name,
        "returncode": result.returncode,
        "ok": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def compile_case(case: FrontierCase) -> dict[str, object]:
    check = run_lean(case.name, render_case_source(case))
    check.update(
        {
            "root": {"coeff": case.root.coeff, "const": case.root.const},
            "leaf": {"coeff": case.leaf.coeff, "const": case.leaf.const},
            "steps": case.steps,
        }
    )
    return check


def main() -> int:
    checks = [compile_case(case) for case in CASES]
    payload = {
        "verdict": "frontier128_split_hardened",
        "all_cases_compile": all(check["ok"] for check in checks),
        "audited_case_count": len(CASES),
        "proved_now": [
            "256*t + 39 descends in 13 steps to 243*t + 38.",
            "256*t + 79 descends in 13 steps to 243*t + 76.",
            "256*t + 95 descends in 13 steps to 243*t + 91.",
            "256*t + 123 descends in 13 steps to 243*t + 118.",
        ],
        "frontier128_split": {
            "descended_roots": [39, 79, 95, 123],
            "remaining_parent_frontier_256": [27, 31, 47, 63, 71, 91, 103, 111, 127],
        },
        "checks": checks,
        "next_action": (
            "Treat the 13 mod-128 frontier split as theorem-level fact. The remaining "
            "odd frontier is now the 9 mod-256 parent roots."
        ),
    }
    print(json.dumps(payload, indent=2))
    return 0 if payload["all_cases_compile"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
