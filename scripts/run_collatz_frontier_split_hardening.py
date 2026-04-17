from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


ROOT_MODULUS = 256
FRONTIER_DESCENDED_ROOTS = [39, 79, 95, 123]


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


def affine_expr(family: Family) -> str:
    return f"{family.coeff}*t + {family.const}"


def theorem_token(modulus: int, residue: int) -> str:
    return f"fam_{modulus}_{residue}"


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


def render_frontier_theorem(certificates: list[DirectCertificate]) -> str:
    tokens = [theorem_token(ROOT_MODULUS, certificate.residue) for certificate in certificates]
    residues = [certificate.residue for certificate in certificates]
    return "\n".join(
        [
            "theorem frontier128_composed_descended_cases :",
            "    FamilyDescends 256 39 ∧ FamilyDescends 256 79 ∧",
            "    FamilyDescends 256 95 ∧ FamilyDescends 256 123 := by",
            f"  exact ⟨{tokens[0]}_descends, {tokens[1]}_descends, {tokens[2]}_descends, {tokens[3]}_descends⟩",
            "",
            "theorem frontier128_split_or_descend_family",
            "    (r : Nat)",
            "    (hr : r = 39 ∨ r = 79 ∨ r = 95 ∨ r = 123) :",
            "    FamilyDescends 256 r := by",
            "  rcases hr with h39 | hrest",
            "  · simpa [h39] using fam_256_39_descends",
            "  · rcases hrest with h79 | hrest",
            "    · simpa [h79] using fam_256_79_descends",
            "    · rcases hrest with h95 | h123",
            "      · simpa [h95] using fam_256_95_descends",
            "      · simpa [h123] using fam_256_123_descends",
            "",
            f"-- Descended roots packaged here: {residues}.",
        ]
    )


def build_certificates() -> list[DirectCertificate]:
    return [
        direct_deterministic_descent(Family(ROOT_MODULUS, residue))
        for residue in FRONTIER_DESCENDED_ROOTS
    ]


def build_lean_source() -> str:
    certificates = build_certificates()
    sections = [LEAN_PREAMBLE, ""]
    for certificate in certificates:
        sections.append(render_direct_certificate(certificate))
    sections.append(render_frontier_theorem(certificates))
    return "\n".join(sections) + "\n"


def build_payload() -> dict[str, object]:
    certificates = build_certificates()
    return {
        "verdict": "frontier_split_hardened",
        "root_modulus": ROOT_MODULUS,
        "descended_roots": FRONTIER_DESCENDED_ROOTS,
        "certificate_summaries": [
            {
                "residue": certificate.residue,
                "steps": certificate.steps,
                "leaf_coeff": certificate.leaf.coeff,
                "leaf_const": certificate.leaf.const,
                "path_kinds": [kind for kind, _, _ in certificate.path],
            }
            for certificate in certificates
        ],
        "theorems": [
            *(f"{theorem_token(ROOT_MODULUS, residue)}_descends" for residue in FRONTIER_DESCENDED_ROOTS),
            "frontier128_composed_descended_cases",
            "frontier128_split_or_descend_family",
        ],
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
    check = run_lean("frontier_split_hardening", source)
    payload = build_payload()
    payload["lean_check"] = check
    payload["interpretation"] = (
        "This is not a proof of Collatz. It hardens one real missing bridge by turning the "
        "rewrite-compass facts for 39, 79, 95, and 123 into Lean-checked affine-family descent "
        "theorems, which is the first theorem-level step in shrinking the live frontier from 13 "
        "roots to the 9-parent mod-256 frontier."
    )
    print(json.dumps(payload, indent=2))
    return 0 if check["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
