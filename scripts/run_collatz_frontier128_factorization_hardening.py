from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_collatz_frontier_split_hardening import (
    Family,
    DirectCertificate,
    LEAN_PREAMBLE,
    ROOT_MODULUS,
    affine_expr,
    theorem_token,
    direct_deterministic_descent,
)


PARENT_MODULUS = 128
DIRECT_CHILDREN = [39, 79, 95, 123, 175, 199, 219]


@dataclass(frozen=True, slots=True)
class FactorizationCase:
    parent_residue: int
    open_children: tuple[int, ...]
    resolved_children: tuple[int, ...]


FACTOR_CASES = [
    FactorizationCase(parent_residue=27, open_children=(27, 155), resolved_children=()),
    FactorizationCase(parent_residue=31, open_children=(31, 159), resolved_children=()),
    FactorizationCase(parent_residue=39, open_children=(167,), resolved_children=(39,)),
    FactorizationCase(parent_residue=47, open_children=(47,), resolved_children=(175,)),
    FactorizationCase(parent_residue=63, open_children=(63, 191), resolved_children=()),
    FactorizationCase(parent_residue=71, open_children=(71,), resolved_children=(199,)),
    FactorizationCase(parent_residue=79, open_children=(207,), resolved_children=(79,)),
    FactorizationCase(parent_residue=91, open_children=(91,), resolved_children=(219,)),
    FactorizationCase(parent_residue=95, open_children=(223,), resolved_children=(95,)),
    FactorizationCase(parent_residue=103, open_children=(103, 231), resolved_children=()),
    FactorizationCase(parent_residue=111, open_children=(111, 239), resolved_children=()),
    FactorizationCase(parent_residue=123, open_children=(251,), resolved_children=(123,)),
    FactorizationCase(parent_residue=127, open_children=(127, 255), resolved_children=()),
]


BIT_CHILD_PREAMBLE = r"""
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


def render_direct_certificate(certificate: DirectCertificate) -> str:
    token = theorem_token(ROOT_MODULUS, certificate.residue)
    lines: list[str] = []
    for step_index, (step_kind, current, nxt) in enumerate(certificate.path, start=1):
        theorem_name = f"{token}_step_{step_index}_eq"
        lines.extend(
            [
                f"-- Ordinary Collatz evolution for {affine_expr(Family(ROOT_MODULUS, certificate.residue))}.",
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
            f"    iterateNat collatzStep {certificate.steps} ({affine_expr(Family(ROOT_MODULUS, certificate.residue))}) = {affine_expr(certificate.leaf)} := by",
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
            f"    ∃ k, PositiveDescentAt ({affine_expr(Family(ROOT_MODULUS, certificate.residue))}) k := by",
            f"  refine ⟨{certificate.steps}, ?_, ?_⟩",
            f"  · rw [{token}_iterate_eq]",
            "    omega",
            f"  · rw [{token}_iterate_eq]",
            "    omega",
            "",
            f"theorem {token}_descends : FamilyDescends {ROOT_MODULUS} {certificate.residue} := by",
            "  intro t ht",
            f"  simpa using {token}_descent t",
            "",
        ]
    )
    return "\n".join(lines)


def render_factorization(case: FactorizationCase) -> str:
    token = theorem_token(PARENT_MODULUS, case.parent_residue)
    lines = [
        f"theorem {token}_factorization",
    ]
    for open_child in case.open_children:
        lines.append(
            f"    (h_{open_child} : FamilyDescends {ROOT_MODULUS} {open_child})"
        )
    lines.extend(
        [
            f"    : FamilyDescends {PARENT_MODULUS} {case.parent_residue} := by",
            f"  apply parent_descends_of_bit_children {PARENT_MODULUS} {case.parent_residue}",
        ]
    )

    even_child = case.parent_residue
    odd_child = case.parent_residue + PARENT_MODULUS
    for child in [even_child, odd_child]:
        if child in case.open_children:
            proof_term = f"h_{child}"
        else:
            proof_term = f"{theorem_token(ROOT_MODULUS, child)}_descends"
        lines.append(f"  · simpa using {proof_term}")
    lines.append("")
    return "\n".join(lines)


def render_summary_theorem() -> str:
    conjuncts = " ∧\n    ".join(
        f"((FamilyDescends 256 {case.open_children[0]}) -> FamilyDescends 128 {case.parent_residue})"
        if len(case.open_children) == 1
        else f"((FamilyDescends 256 {case.open_children[0]}) -> (FamilyDescends 256 {case.open_children[1]}) -> FamilyDescends 128 {case.parent_residue})"
        for case in FACTOR_CASES
    )

    lines = [
        "theorem frontier128_factorization_bundle :",
        f"    {conjuncts} := by",
    ]
    theorem_names = [f"{theorem_token(PARENT_MODULUS, case.parent_residue)}_factorization" for case in FACTOR_CASES]
    lines.append("  repeat' constructor")
    for theorem_name in theorem_names:
        lines.append(f"  · exact {theorem_name}")
    lines.append("")
    return "\n".join(lines)


def build_certificates() -> list[DirectCertificate]:
    return [
        direct_deterministic_descent(Family(ROOT_MODULUS, residue))
        for residue in DIRECT_CHILDREN
    ]


def build_lean_source() -> str:
    certificates = build_certificates()
    sections = [LEAN_PREAMBLE, "", BIT_CHILD_PREAMBLE, ""]
    for certificate in certificates:
        sections.append(render_direct_certificate(certificate))
    for case in FACTOR_CASES:
        sections.append(render_factorization(case))
    sections.append(render_summary_theorem())
    return "\n".join(sections) + "\n"


def build_payload() -> dict[str, object]:
    return {
        "verdict": "frontier128_factorization_hardened",
        "parent_modulus": PARENT_MODULUS,
        "root_modulus": ROOT_MODULUS,
        "direct_children": DIRECT_CHILDREN,
        "factor_cases": [
            {
                "parent_residue": case.parent_residue,
                "open_children": list(case.open_children),
                "resolved_children": list(case.resolved_children),
            }
            for case in FACTOR_CASES
        ],
        "interpretation": (
            "This is the exact theorem-level factorization currently supported by local proof "
            "artifacts: each of the 13 mod-128 frontier families either depends on one open "
            "mod-256 child because the sibling child already descends, or depends on both "
            "mod-256 children when neither sibling is yet proved."
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
    check = run_lean("frontier128_factorization_hardening", source)
    payload = build_payload()
    payload["lean_check"] = check
    print(json.dumps(payload, indent=2))
    return 0 if check["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
