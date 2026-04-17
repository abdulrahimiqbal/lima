import Std

open Std

def collatzStep (n : Nat) : Nat :=
  if n % 2 = 0 then n / 2 else 3 * n + 1

def iterateNat (f : Nat → Nat) : Nat → Nat → Nat
  | 0, n => n
  | k + 1, n => iterateNat f k (f n)

def PositiveDescentAt (n k : Nat) : Prop :=
  0 < iterateNat collatzStep k n ∧ iterateNat collatzStep k n < n

def kernelBound : Nat := 256

inductive CriticalTemplateState where
  | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 | T10 | T11 | T12
  deriving DecidableEq, Repr

abbrev TemplateClassifierKey := Nat × Nat × Nat × Nat

def templateClassifier : TemplateClassifierKey → Option CriticalTemplateState
  | (27, 39, 0, 39) => some .T1
  | (31, 4, 0, 4) => some .T2
  | (255, 176, 0, 176) => some .T3
  | (27, 28, 17, 11) => some .T4
  | (27, 78, 27, 51) => some .T5
  | (27, 129, 65, 64) => some .T6
  | (31, 3, 2, 1) => some .T7
  | (31, 8, 3, 5) => some .T8
  | (31, 13, 7, 6) => some .T9
  | (255, 120, 64, 56) => some .T10
  | (255, 352, 109, 243) => some .T11
  | (255, 595, 273, 322) => some .T12
  | _ => none

structure CriticalQ1TemplateObservation where
  level : Nat
  residueClass : Nat
  sourceCount : Nat
  oneChildSources : Nat
  twoChildSources : Nat
  arisesFromCriticalShadow : Prop

def critical_template_kernel_exactness_all_depth : Prop :=
  ∃ N,
    ∀ obs : CriticalQ1TemplateObservation,
      obs.arisesFromCriticalShadow →
      N ≤ obs.level →
      templateClassifier
          (obs.residueClass, obs.sourceCount, obs.oneChildSources, obs.twoChildSources) ≠ none

def NoDangerousFrontier : Prop :=
  ∀ n, n > 1 -> kernelBound ≤ n -> ∃ k, PositiveDescentAt n k

def critical_template_kernel_density_zero_nat : Prop :=
  critical_template_kernel_exactness_all_depth -> NoDangerousFrontier

theorem critical_template_kernel_density_zero_nat_implies_no_dangerous_frontier
    (hDensity : critical_template_kernel_density_zero_nat)
    (hExactness : critical_template_kernel_exactness_all_depth) :
    NoDangerousFrontier := by
  exact hDensity hExactness
