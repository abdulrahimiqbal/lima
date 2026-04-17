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
    ROOT_MODULUS,
    LEAN_PREAMBLE,
    affine_expr,
    theorem_token,
    direct_deterministic_descent,
)


PARENT_MODULUS = 128
DESCENDED_CHILDREN = [39, 79, 95, 123, 175, 199, 219]


@dataclass(frozen=True, slots=True)
class ChildReduction:
    parent_residue: int
    open_child: int
    resolved_child: int


CHILD_REDUCTIONS = [
    ChildReduction(parent_residue=39, open_child=167, resolved_child=39),
    ChildReduction(parent_residue=47, open_child=47, resolved_child=175),
    ChildReduction(parent_residue=71, open_child=71, resolved_child=199),
    ChildReduction(parent_residue=79, open_child=207, resolved_child=79),
    ChildReduction(parent_residue=91, open_child=91, resolved_child=219),
    ChildReduction(parent_residue=95, open_child=223, resolved_child=95),
    ChildReduction(parent_residue=123, open_child=251, resolved_child=123),
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


def render_child_reduction(reduction: ChildReduction) -> str:
    parent_token = theorem_token(PARENT_MODULUS, reduction.parent_residue)
    open_token = theorem_token(ROOT_MODULUS, reduction.open_child)
    resolved_token = theorem_token(ROOT_MODULUS, reduction.resolved_child)
    return "\n".join(
        [
            f"theorem {parent_token}_descends_of_{reduction.open_child}",
            f"    (hOpen : FamilyDescends {ROOT_MODULUS} {reduction.open_child}) :",
            f"    FamilyDescends {PARENT_MODULUS} {reduction.parent_residue} := by",
            f"  apply parent_descends_of_bit_children {PARENT_MODULUS} {reduction.parent_residue}",
            f"  · simpa using {('hOpen' if reduction.open_child == reduction.parent_residue else resolved_token + '_descends')}",
            f"  · simpa using {('hOpen' if reduction.open_child == reduction.parent_residue + PARENT_MODULUS else resolved_token + '_descends')}",
            "",
        ]
    )


def build_certificates() -> list[DirectCertificate]:
    return [
        direct_deterministic_descent(Family(ROOT_MODULUS, residue))
        for residue in DESCENDED_CHILDREN
    ]


def build_lean_source() -> str:
    certificates = build_certificates()
    sections = [LEAN_PREAMBLE, "", BIT_CHILD_PREAMBLE, ""]
    for certificate in certificates:
        sections.append(render_direct_certificate(certificate))
    for reduction in CHILD_REDUCTIONS:
        sections.append(render_child_reduction(reduction))
    return "\n".join(sections) + "\n"


def build_payload() -> dict[str, object]:
    certificates = build_certificates()
    return {
        "verdict": "frontier_child_reduction_hardened",
        "root_modulus": ROOT_MODULUS,
        "parent_modulus": PARENT_MODULUS,
        "descended_children": DESCENDED_CHILDREN,
        "certificate_summaries": [
            {
                "residue": certificate.residue,
                "steps": certificate.steps,
                "leaf_coeff": certificate.leaf.coeff,
                "leaf_const": certificate.leaf.const,
            }
            for certificate in certificates
        ],
        "child_reductions": [
            {
                "parent_residue": reduction.parent_residue,
                "open_child": reduction.open_child,
                "resolved_child": reduction.resolved_child,
            }
            for reduction in CHILD_REDUCTIONS
        ],
        "interpretation": (
            "This still does not prove Collatz. It proves several mod-128 frontier families reduce "
            "to a single mod-256 child family because the sibling child already has a verified "
            "direct descent theorem."
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
    check = run_lean("frontier_child_reduction_hardening", source)
    payload = build_payload()
    payload["lean_check"] = check
    print(json.dumps(payload, indent=2))
    return 0 if check["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
