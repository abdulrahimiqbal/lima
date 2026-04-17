from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


PARENT_MODULUS = 256
CHILD_MODULUS = 512
OPEN_PARENTS = [27, 31, 47, 63, 71, 91, 103, 111, 127, 155, 159, 167, 191, 207, 223, 231, 239, 251, 255]


LEAN_PREAMBLE = r"""import Std

def collatzStep (n : Nat) : Nat :=
  if n % 2 = 0 then n / 2 else 3 * n + 1

def iterateNat (f : Nat -> Nat) : Nat -> Nat -> Nat
  | 0, n => n
  | k + 1, n => iterateNat f k (f n)

def PositiveDescentAt (n k : Nat) : Prop :=
  0 < iterateNat collatzStep k n ∧ iterateNat collatzStep k n < n

def FamilyDescends (a b : Nat) : Prop :=
  ∀ t, a * t + b > 1 -> ∃ k, PositiveDescentAt (a * t + b) k

theorem parent_descends_of_bit_children
    (a b : Nat)
    (hEven : FamilyDescends (2 * a) b)
    (hOdd : FamilyDescends (2 * a) (a + b)) :
    FamilyDescends a b := by
  intro t ht
  have hcases := Nat.mod_two_eq_zero_or_one t
  cases hcases with
  | inl hmod =>
      let q := t / 2
      have hrepr : t = 2 * q := by
        dsimp [q]
        have hdecomp : t % 2 + 2 * (t / 2) = t := by
          simpa [Nat.add_comm] using (Nat.mod_add_div t 2)
        omega
      have hEq : a * t + b = (2 * a) * q + b := by
        rw [hrepr]
        simp [Nat.mul_left_comm, Nat.mul_comm]
      have hgt : (2 * a) * q + b > 1 := by
        simpa [hEq] using ht
      obtain ⟨k, hk⟩ := hEven q hgt
      refine ⟨k, ?_⟩
      simpa [hEq] using hk
  | inr hmod =>
      let q := t / 2
      have hrepr : t = 2 * q + 1 := by
        dsimp [q]
        have hdecomp : t % 2 + 2 * (t / 2) = t := by
          simpa [Nat.add_comm] using (Nat.mod_add_div t 2)
        omega
      have hEq : a * t + b = (2 * a) * q + (a + b) := by
        rw [hrepr]
        rw [Nat.mul_add, Nat.mul_one]
        simp [Nat.mul_left_comm, Nat.mul_comm, Nat.add_assoc, Nat.add_left_comm, Nat.add_comm]
      have hgt : (2 * a) * q + (a + b) > 1 := by
        simpa [hEq] using ht
      obtain ⟨k, hk⟩ := hOdd q hgt
      refine ⟨k, ?_⟩
      simpa [hEq] using hk
"""


@dataclass(frozen=True, slots=True)
class FactorizationCase:
    parent_residue: int
    open_children: tuple[int, int]


def theorem_token(modulus: int, residue: int) -> str:
    return f"fam_{modulus}_{residue}"


def build_cases() -> list[FactorizationCase]:
    return [
        FactorizationCase(parent_residue=residue, open_children=(residue, residue + PARENT_MODULUS))
        for residue in OPEN_PARENTS
    ]


def render_factorization(case: FactorizationCase) -> str:
    token = theorem_token(PARENT_MODULUS, case.parent_residue)
    left, right = case.open_children
    return "\n".join(
        [
            f"theorem {token}_factorization",
            f"    (h_{left} : FamilyDescends {CHILD_MODULUS} {left})",
            f"    (h_{right} : FamilyDescends {CHILD_MODULUS} {right})",
            f"    : FamilyDescends {PARENT_MODULUS} {case.parent_residue} := by",
            f"  apply parent_descends_of_bit_children {PARENT_MODULUS} {case.parent_residue}",
            f"  · simpa using h_{left}",
            f"  · simpa using h_{right}",
            "",
        ]
    )


def render_bundle(cases: list[FactorizationCase]) -> str:
    conjuncts = " ∧\n    ".join(
        f"((FamilyDescends 512 {case.open_children[0]}) -> (FamilyDescends 512 {case.open_children[1]}) -> FamilyDescends 256 {case.parent_residue})"
        for case in cases
    )
    lines = [
        "theorem frontier256_factorization_bundle :",
        f"    {conjuncts} := by",
        "  repeat' constructor",
    ]
    for case in cases:
        lines.append(f"  · exact {theorem_token(PARENT_MODULUS, case.parent_residue)}_factorization")
    lines.append("")
    return "\n".join(lines)


def build_lean_source() -> str:
    cases = build_cases()
    sections = [LEAN_PREAMBLE, ""]
    for case in cases:
        sections.append(render_factorization(case))
    sections.append(render_bundle(cases))
    return "\n".join(sections) + "\n"


def build_payload() -> dict[str, object]:
    cases = build_cases()
    return {
        "verdict": "frontier256_factorization_hardened",
        "parent_modulus": PARENT_MODULUS,
        "child_modulus": CHILD_MODULUS,
        "factor_cases": [
            {
                "parent_residue": case.parent_residue,
                "open_children": list(case.open_children),
            }
            for case in cases
        ],
        "interpretation": (
            "This is an exact theorem-level statement of the next unresolved refinement layer: "
            "every surviving mod-256 frontier family currently depends on both of its mod-512 "
            "children. No one-bit reduction remains at this layer under the present direct descent facts."
        ),
    }


def run_lean(name: str, source: str) -> dict[str, object]:
    result = subprocess.run(
        ["lean", "--stdin"],
        input=source,
        text=True,
        capture_output=True,
        timeout=60,
    )
    return {
        "name": name,
        "returncode": result.returncode,
        "ok": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def main() -> int:
    source = build_lean_source()
    check = run_lean("frontier256_factorization_hardening", source)
    payload = build_payload()
    payload["lean_check"] = check
    print(json.dumps(payload, indent=2))
    return 0 if check["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
