from __future__ import annotations

import json
import subprocess


REFINEMENT_PARTITION_AUDIT = r"""
import Std

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

theorem parent_descends_of_refined_children
    (a b m : Nat)
    (hChildren : ∀ r, r < 2 ^ m -> FamilyDescends (a * 2 ^ m) (a * r + b)) :
    FamilyDescends a b := by
  induction m generalizing a b with
  | zero =>
      intro t ht
      have hFam := hChildren 0 (by omega)
      have ht0 : a * 2 ^ 0 * t + (a * 0 + b) > 1 := by
        simpa using ht
      obtain ⟨k, hk⟩ := hFam t ht0
      refine ⟨k, ?_⟩
      simpa using hk
  | succ m ih =>
      apply parent_descends_of_bit_children a b
      · have hEvenChildren :
            ∀ r, r < 2 ^ m -> FamilyDescends ((2 * a) * 2 ^ m) ((2 * a) * r + b) := by
          intro r hr
          have hlt : 2 * r < 2 ^ Nat.succ m := by
            omega
          have hFam := hChildren (2 * r) hlt
          simpa [Nat.pow_succ, Nat.mul_assoc, Nat.mul_left_comm, Nat.mul_comm] using hFam
        exact ih (2 * a) b hEvenChildren
      · have hOddChildren :
            ∀ r, r < 2 ^ m -> FamilyDescends ((2 * a) * 2 ^ m) ((2 * a) * r + (a + b)) := by
          intro r hr
          have hlt : 2 * r + 1 < 2 ^ Nat.succ m := by
            omega
          have hFam := hChildren (2 * r + 1) hlt
          simpa [Nat.pow_succ, Nat.mul_add, Nat.mul_assoc, Nat.mul_left_comm, Nat.mul_comm,
            Nat.add_assoc, Nat.add_left_comm, Nat.add_comm] using hFam
        exact ih (2 * a) (a + b) hOddChildren

theorem thirtyone_mod_256_of_all_mod_4096_children
    (hChildren : ∀ r, r < 16 -> FamilyDescends 4096 (256 * r + 31)) :
    FamilyDescends 256 31 := by
  simpa using parent_descends_of_refined_children 256 31 4 hChildren

theorem twentyseven_mod_256_of_all_mod_4096_children
    (hChildren : ∀ r, r < 16 -> FamilyDescends 4096 (256 * r + 27)) :
    FamilyDescends 256 27 := by
  simpa using parent_descends_of_refined_children 256 27 4 hChildren
"""


def run_lean(name: str, source: str) -> dict[str, object]:
    result = subprocess.run(
        ["lean", "--stdin"],
        input=source,
        text=True,
        capture_output=True,
        timeout=40,
    )
    return {
        "name": name,
        "returncode": result.returncode,
        "ok": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def main() -> int:
    check = run_lean("refinement_partition_audit", REFINEMENT_PARTITION_AUDIT)
    payload = {
        "verdict": "refinement_partition_hardened",
        "partition_audit_compiles": check["ok"],
        "proved_now": [
            "If both one-bit children of an affine family descend, then the parent family descends.",
            "If all 2^m dyadic children of an affine family descend, then the parent family descends.",
            "In particular, closing all 16 mod-4096 children of 256*t+31 would close 256*t+31.",
            "In particular, closing all 16 mod-4096 children of 256*t+27 would close 256*t+27.",
        ],
        "new_proof_object": (
            "The remaining problem can now be phrased as a child-closure theorem on a dyadic "
            "refinement tree, rather than only as a list of isolated residue lemmas."
        ),
        "next_action": (
            "Combine this partition theorem with the unresolved-state transition compass to "
            "identify a finite family of child-closure obligations or a decreasing measure on them."
        ),
        "checks": [check],
    }
    print(json.dumps(payload, indent=2))
    return 0 if check["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
