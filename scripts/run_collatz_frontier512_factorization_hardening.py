from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


PARENT_MODULUS = 512
CHILD_MODULUS = 1024
OPEN_PARENTS = [
    27, 31, 47, 63, 71, 91, 103, 111, 127, 155, 159, 167, 191, 207, 223, 231, 239, 251, 255,
    283, 287, 303, 319, 327, 347, 359, 367, 383, 411, 415, 423, 447, 463, 479, 487, 495, 507, 511,
]
DIRECT_CHILDREN = [287, 347, 367, 423, 507, 575, 583, 735, 815, 923, 975, 999]


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
class Family:
    coeff: int
    const: int


@dataclass(frozen=True, slots=True)
class DirectCertificate:
    residue: int
    steps: int
    leaf: Family
    path: list[tuple[str, Family, Family]]


@dataclass(frozen=True, slots=True)
class FactorizationCase:
    parent_residue: int
    open_children: tuple[int, ...]
    resolved_children: tuple[int, ...]


ONE_CHILD_CASES = {
    63: (63, 575),
    71: (71, 583),
    223: (223, 735),
    287: (799, 287),
    303: (303, 815),
    347: (859, 347),
    367: (879, 367),
    411: (411, 923),
    423: (935, 423),
    463: (463, 975),
    487: (487, 999),
    507: (1019, 507),
}


def theorem_token(modulus: int, residue: int) -> str:
    return f"fam_{modulus}_{residue}"


def affine_expr(family: Family) -> str:
    return f"{family.coeff}*t + {family.const}"


def next_family(family: Family) -> tuple[str, Family]:
    if family.const % 2 == 0:
        if family.coeff % 2 != 0:
            raise ValueError(f"even step reached odd coefficient in {family}")
        return "even", Family(family.coeff // 2, family.const // 2)
    return "odd", Family(3 * family.coeff, 3 * family.const + 1)


def direct_deterministic_descent(root: Family, max_steps: int = 100) -> DirectCertificate:
    start = root
    current = root
    path: list[tuple[str, Family, Family]] = []
    for step_index in range(max_steps):
        step_kind, nxt = next_family(current)
        path.append((step_kind, current, nxt))
        current = nxt
        if current.coeff < start.coeff and current.const < start.const:
            return DirectCertificate(
                residue=root.const,
                steps=step_index + 1,
                leaf=current,
                path=path,
            )
    raise ValueError(f"no descent certificate found for {root}")


def build_certificates() -> list[DirectCertificate]:
    return [
        direct_deterministic_descent(Family(CHILD_MODULUS, residue))
        for residue in DIRECT_CHILDREN
    ]


def build_cases() -> list[FactorizationCase]:
    cases: list[FactorizationCase] = []
    for residue in OPEN_PARENTS:
        if residue in ONE_CHILD_CASES:
            open_child, resolved_child = ONE_CHILD_CASES[residue]
            cases.append(
                FactorizationCase(
                    parent_residue=residue,
                    open_children=(open_child,),
                    resolved_children=(resolved_child,),
                )
            )
        else:
            cases.append(
                FactorizationCase(
                    parent_residue=residue,
                    open_children=(residue, residue + PARENT_MODULUS),
                    resolved_children=(),
                )
            )
    return cases


def render_direct_certificate(certificate: DirectCertificate) -> str:
    token = theorem_token(CHILD_MODULUS, certificate.residue)
    lines: list[str] = []
    for step_index, (step_kind, current, nxt) in enumerate(certificate.path, start=1):
        theorem_name = f"{token}_step_{step_index}_eq"
        lines.extend(
            [
                f"-- Ordinary Collatz evolution for {affine_expr(Family(CHILD_MODULUS, certificate.residue))}.",
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
            f"theorem {token}_iterate_eq (t : Nat) :",
            f"    iterateNat collatzStep {certificate.steps} ({affine_expr(Family(CHILD_MODULUS, certificate.residue))}) = {affine_expr(certificate.leaf)} := by",
            "  simp [iterateNat,",
        ]
    )
    for step_index in range(1, certificate.steps + 1):
        suffix = "," if step_index < certificate.steps else "]"
        lines.append(f"    {token}_step_{step_index}_eq{suffix}")
    lines.extend(
        [
            "",
            f"theorem {token}_descent (t : Nat) :",
            f"    ∃ k, PositiveDescentAt ({affine_expr(Family(CHILD_MODULUS, certificate.residue))}) k := by",
            f"  refine ⟨{certificate.steps}, ?_, ?_⟩",
            f"  · rw [{token}_iterate_eq]",
            "    omega",
            f"  · rw [{token}_iterate_eq]",
            "    omega",
            "",
            f"theorem {token}_descends : FamilyDescends {CHILD_MODULUS} {certificate.residue} := by",
            "  intro t ht",
            f"  simpa using {token}_descent t",
            "",
        ]
    )
    return "\n".join(lines)


def render_factorization(case: FactorizationCase) -> str:
    token = theorem_token(PARENT_MODULUS, case.parent_residue)
    lines = [f"theorem {token}_factorization"]
    for open_child in case.open_children:
        lines.append(f"    (h_{open_child} : FamilyDescends {CHILD_MODULUS} {open_child})")
    lines.append(f"    : FamilyDescends {PARENT_MODULUS} {case.parent_residue} := by")
    lines.append(f"  apply parent_descends_of_bit_children {PARENT_MODULUS} {case.parent_residue}")

    even_child = case.parent_residue
    odd_child = case.parent_residue + PARENT_MODULUS
    for child in (even_child, odd_child):
        if child in case.open_children:
            proof_term = f"h_{child}"
        else:
            proof_term = f"{theorem_token(CHILD_MODULUS, child)}_descends"
        lines.append(f"  · simpa using {proof_term}")
    lines.append("")
    return "\n".join(lines)


def render_bundle(cases: list[FactorizationCase]) -> str:
    conjuncts = " ∧\n    ".join(
        (
            f"((FamilyDescends 1024 {case.open_children[0]}) -> FamilyDescends 512 {case.parent_residue})"
            if len(case.open_children) == 1
            else f"((FamilyDescends 1024 {case.open_children[0]}) -> (FamilyDescends 1024 {case.open_children[1]}) -> FamilyDescends 512 {case.parent_residue})"
        )
        for case in cases
    )
    lines = [
        "theorem frontier512_factorization_bundle :",
        f"    {conjuncts} := by",
        "  repeat' constructor",
    ]
    for case in cases:
        lines.append(f"  · exact {theorem_token(PARENT_MODULUS, case.parent_residue)}_factorization")
    lines.append("")
    return "\n".join(lines)


def build_lean_source() -> str:
    certificates = build_certificates()
    cases = build_cases()
    sections = [LEAN_PREAMBLE, ""]
    for certificate in certificates:
        sections.append(render_direct_certificate(certificate))
    for case in cases:
        sections.append(render_factorization(case))
    sections.append(render_bundle(cases))
    return "\n".join(sections) + "\n"


def build_payload() -> dict[str, object]:
    certificates = build_certificates()
    cases = build_cases()
    return {
        "verdict": "frontier512_factorization_hardened",
        "parent_modulus": PARENT_MODULUS,
        "child_modulus": CHILD_MODULUS,
        "direct_children": DIRECT_CHILDREN,
        "certificate_summaries": [
            {
                "residue": certificate.residue,
                "steps": certificate.steps,
                "leaf_coeff": certificate.leaf.coeff,
                "leaf_const": certificate.leaf.const,
            }
            for certificate in certificates
        ],
        "factor_cases": [
            {
                "parent_residue": case.parent_residue,
                "open_children": list(case.open_children),
                "resolved_children": list(case.resolved_children),
            }
            for case in cases
        ],
        "interpretation": (
            "This is the exact theorem-level factorization currently supported at the 512-to-1024 "
            "layer: 12 open mod-512 parents reduce to a single mod-1024 child because the sibling "
            "child already has a verified direct descent theorem, while the rest still depend on both children."
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
    check = run_lean("frontier512_factorization_hardening", source)
    payload = build_payload()
    payload["lean_check"] = check
    print(json.dumps(payload, indent=2))
    return 0 if check["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
