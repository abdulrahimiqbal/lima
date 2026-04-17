import Std

open Std

inductive FrontierCoverage where
  | descends
  | kernelA
  | kernelB
  | kernelC
  deriving DecidableEq, Repr

def frontierCoverage : Nat → Option FrontierCoverage
  | 39 => some .descends
  | 79 => some .descends
  | 95 => some .descends
  | 123 => some .descends
  | 27 => some .kernelB
  | 31 => some .kernelA
  | 47 => some .kernelA
  | 63 => some .kernelA
  | 71 => some .kernelA
  | 91 => some .kernelA
  | 103 => some .kernelB
  | 111 => some .kernelA
  | 127 => some .kernelB
  | 155 => some .kernelA
  | 159 => some .kernelB
  | 167 => some .kernelA
  | 191 => some .kernelB
  | 207 => some .kernelA
  | 223 => some .kernelA
  | 231 => some .kernelA
  | 239 => some .kernelB
  | 251 => some .kernelA
  | 255 => some .kernelC
  | _ => none

def LiveRecurrentFrontierResidue (n : Nat) : Prop :=
  frontierCoverage n ≠ none

theorem phase_kernel_exact_coverage :
    ∀ n, LiveRecurrentFrontierResidue n →
      frontierCoverage n = some .descends ∨
      frontierCoverage n = some .kernelA ∨
      frontierCoverage n = some .kernelB ∨
      frontierCoverage n = some .kernelC := by
  intro n hn
  cases hcov : frontierCoverage n with
  | none =>
      exact False.elim (hn hcov)
  | some label =>
      cases label <;> simp [hcov]
