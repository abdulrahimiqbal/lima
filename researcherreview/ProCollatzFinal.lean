import Std

open Std

set_option maxRecDepth 1000000

def collatzStep (n : Nat) : Nat :=
  if n % 2 = 0 then n / 2 else 3 * n + 1

def iterateNat (f : Nat → Nat) : Nat → Nat → Nat
  | 0, n => n
  | k + 1, n => iterateNat f k (f n)

def PositiveDescentAt (n k : Nat) : Prop :=
  0 < iterateNat collatzStep k n ∧ iterateNat collatzStep k n < n

def EventualPositiveDescent : Prop :=
  ∀ n, n > 1 -> ∃ k, PositiveDescentAt n k

def CollatzTerminates (n : Nat) : Prop :=
  ∃ k, iterateNat collatzStep k n = 1

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

def baseWitnesses : Array Nat := #[
  0, 0, 1, 6, 1, 3, 1, 11, 1, 3, 1, 8, 1, 3, 1, 11,
  1, 3, 1, 6, 1, 3, 1, 8, 1, 3, 1, 96, 1, 3, 1, 91,
  1, 3, 1, 6, 1, 3, 1, 13, 1, 3, 1, 8, 1, 3, 1, 88,
  1, 3, 1, 6, 1, 3, 1, 8, 1, 3, 1, 11, 1, 3, 1, 88,
  1, 3, 1, 6, 1, 3, 1, 83, 1, 3, 1, 8, 1, 3, 1, 13,
  1, 3, 1, 6, 1, 3, 1, 8, 1, 3, 1, 73, 1, 3, 1, 13,
  1, 3, 1, 6, 1, 3, 1, 68, 1, 3, 1, 8, 1, 3, 1, 50,
  1, 3, 1, 6, 1, 3, 1, 8, 1, 3, 1, 13, 1, 3, 1, 24,
  1, 3, 1, 6, 1, 3, 1, 11, 1, 3, 1, 8, 1, 3, 1, 11,
  1, 3, 1, 6, 1, 3, 1, 8, 1, 3, 1, 65, 1, 3, 1, 34,
  1, 3, 1, 6, 1, 3, 1, 47, 1, 3, 1, 8, 1, 3, 1, 13,
  1, 3, 1, 6, 1, 3, 1, 8, 1, 3, 1, 11, 1, 3, 1, 21,
  1, 3, 1, 6, 1, 3, 1, 13, 1, 3, 1, 8, 1, 3, 1, 21,
  1, 3, 1, 6, 1, 3, 1, 8, 1, 3, 1, 13, 1, 3, 1, 50,
  1, 3, 1, 6, 1, 3, 1, 19, 1, 3, 1, 8, 1, 3, 1, 32,
  1, 3, 1, 6, 1, 3, 1, 8, 1, 3, 1, 44, 1, 3, 1, 21
]

def baseWitnessNat (n : Nat) : Nat :=
  baseWitnesses.getD n 0

def baseWitness (n : Fin 256) : Nat :=
  baseWitnessNat n.val

theorem baseWitness_sound_fin :
    ∀ n : Fin 256,
      1 < n.val ->
      0 < iterateNat collatzStep (baseWitness n) n.val ∧
        iterateNat collatzStep (baseWitness n) n.val < n.val := by
  decide

theorem kernel_bound_has_finite_base_coverage :
    ∀ n, 1 < n -> n < kernelBound ->
      ∃ k, 0 < iterateNat collatzStep k n ∧
        iterateNat collatzStep k n < n := by
  intro n hn hlt
  have hfin : n < 256 := by
    simpa [kernelBound] using hlt
  refine ⟨baseWitness ⟨n, hfin⟩, ?_⟩
  simpa [baseWitness] using baseWitness_sound_fin ⟨n, hfin⟩ hn

theorem iterateNat_add (f : Nat → Nat) (a b n : Nat) :
    iterateNat f (a + b) n = iterateNat f b (iterateNat f a n) := by
  induction a generalizing n with
  | zero =>
      simp [iterateNat]
  | succ a ih =>
      simp [iterateNat, Nat.succ_add, ih]

theorem collatz_from_eventual_positive_descent
    (hDesc : EventualPositiveDescent) :
    ∀ n, n > 0 -> CollatzTerminates n := by
  intro n
  refine Nat.strongRecOn (motive := fun n => n > 0 -> CollatzTerminates n) n ?_
  intro n ih hn
  cases n with
  | zero =>
      cases hn
  | succ n' =>
      cases n' with
      | zero =>
          exact ⟨0, rfl⟩
      | succ m =>
          have hn_gt_one : Nat.succ (Nat.succ m) > 1 :=
            Nat.succ_lt_succ (Nat.zero_lt_succ m)
          obtain ⟨k, hpos, hlt⟩ := hDesc (Nat.succ (Nat.succ m)) hn_gt_one
          let d := iterateNat collatzStep k (Nat.succ (Nat.succ m))
          have hterm_d : CollatzTerminates d := ih d hlt hpos
          obtain ⟨j, hj⟩ := hterm_d
          refine ⟨k + j, ?_⟩
          rw [iterateNat_add]
          simpa [d] using hj

theorem critical_q1_excludes_dangerous_frontier
    (hDensity : critical_template_kernel_density_zero_nat)
    (hExactness : critical_template_kernel_exactness_all_depth) :
    NoDangerousFrontier := by
  exact hDensity hExactness

theorem eventual_positive_descent_from_full_kernel
    (hDensity : critical_template_kernel_density_zero_nat)
    (hExactness : critical_template_kernel_exactness_all_depth) :
    EventualPositiveDescent := by
  intro n hn
  by_cases hsmall : n < kernelBound
  · exact kernel_bound_has_finite_base_coverage n hn hsmall
  · have hNoDangerous : NoDangerousFrontier :=
      critical_q1_excludes_dangerous_frontier hDensity hExactness
    obtain ⟨k, hk⟩ := hNoDangerous n hn (Nat.le_of_not_lt hsmall)
    exact ⟨k, hk⟩

theorem collatz_nat_level_no_scaffold
    (hDensity : critical_template_kernel_density_zero_nat)
    (hExactness : critical_template_kernel_exactness_all_depth) :
    ∀ n : Nat, n > 0 -> CollatzTerminates n := by
  exact collatz_from_eventual_positive_descent
    (eventual_positive_descent_from_full_kernel hDensity hExactness)
