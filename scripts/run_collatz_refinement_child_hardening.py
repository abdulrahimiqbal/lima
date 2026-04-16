from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_collatz_refinement_parent_wave import (
    CHILD_MODULUS,
    PARENT_FRONTIER,
    DirectCertificate,
    direct_children,
    render_direct_certificate,
)


LEAN_PREAMBLE = """import Std

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


def unique_direct_certificates() -> list[DirectCertificate]:
    seen: dict[int, DirectCertificate] = {}
    for parent in PARENT_FRONTIER:
        for certificate in direct_children(parent):
            seen.setdefault(certificate.residue, certificate)
    return [seen[residue] for residue in sorted(seen)]


def render_source(certificates: list[DirectCertificate]) -> str:
    parts = [LEAN_PREAMBLE, ""]
    for certificate in certificates:
        parts.append(render_direct_certificate(certificate))
    return "\n".join(parts) + "\n"


def run_lean(source: str) -> dict[str, object]:
    result = subprocess.run(
        ["lean", "--stdin"],
        input=source,
        text=True,
        capture_output=True,
        timeout=180,
    )
    return {
        "returncode": result.returncode,
        "ok": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def main() -> int:
    certificates = unique_direct_certificates()
    source = render_source(certificates)
    check = run_lean(source)
    payload = {
        "verdict": "collatz_refinement_child_hardened",
        "child_modulus": CHILD_MODULUS,
        "audited_case_count": len(certificates),
        "all_cases_compile": check["ok"],
        "proved_now": [
            {
                "residue": certificate.residue,
                "steps": certificate.steps,
                "leaf_coeff": certificate.leaf.coeff,
                "leaf_const": certificate.leaf.const,
            }
            for certificate in certificates
        ],
        "interpretation": (
            "These are standalone theorem-level direct descent facts for the mod-4096 child "
            "families exposed by the refinement-parent wave. They are the local exits we "
            "already know how to prove without Aristotle."
        ),
        "next_action": (
            "Use these direct child facts to shrink future parent-closure probes and update "
            "the Collatz theorem inventory before attacking the remaining unresolved children."
        ),
        "checks": [check],
    }
    print(json.dumps(payload, indent=2))
    return 0 if check["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
