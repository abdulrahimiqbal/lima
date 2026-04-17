import Std

open Std

/-!
This file packages the exact two-bit contraction data on the checked template
kernel. The proved theorem is an integer cross-multiplication form of the
dyadically normalized contraction inequality with uniform epsilon `1/2`.
The remaining analytic step is explicit: turn this concrete contraction law
into a density-zero theorem for the true stabilized critical shadow.
-/

inductive CriticalTemplateState where
  | T1
  | T2
  | T3
  | T4
  | T5
  | T6
  | T7
  | T8
  | T9
  | T10
  | T11
  | T12
  deriving DecidableEq, Repr

def templateWeightNum : CriticalTemplateState → Nat
  | .T1 => 39
  | .T2 => 4
  | .T3 => 176
  | .T4 => 28
  | .T5 => 78
  | .T6 => 129
  | .T7 => 3
  | .T8 => 8
  | .T9 => 13
  | .T10 => 120
  | .T11 => 352
  | .T12 => 595

def templateWeightDen : CriticalTemplateState → Nat
  | .T1 => 1
  | .T2 => 1
  | .T3 => 1
  | .T4 => 1
  | .T5 => 1
  | .T6 => 1
  | .T7 => 1
  | .T8 => 1
  | .T9 => 1
  | .T10 => 1
  | .T11 => 1
  | .T12 => 1

def weightedTwoBitMassNum : CriticalTemplateState → Nat
  | .T1 => 78
  | .T2 => 8
  | .T3 => 352
  | .T4 => 39
  | .T5 => 129
  | .T6 => 193
  | .T7 => 4
  | .T8 => 13
  | .T9 => 19
  | .T10 => 176
  | .T11 => 595
  | .T12 => 917

def weightedTwoBitMassDen : CriticalTemplateState → Nat
  | .T1 => 4
  | .T2 => 4
  | .T3 => 4
  | .T4 => 4
  | .T5 => 4
  | .T6 => 4
  | .T7 => 4
  | .T8 => 4
  | .T9 => 4
  | .T10 => 4
  | .T11 => 4
  | .T12 => 4

def templateEpsilonNum : Nat := 1
def templateEpsilonDen : Nat := 2

theorem critical_template_kernel_weight_positive :
    ∀ s, 0 < templateWeightNum s ∧ 0 < templateWeightDen s := by
  intro s
  cases s <;> decide

theorem critical_template_kernel_two_bit_contraction :
    ∀ s,
      weightedTwoBitMassNum s * templateEpsilonDen * templateWeightDen s ≤
        weightedTwoBitMassDen s * (templateEpsilonDen - templateEpsilonNum) * templateWeightNum s := by
  intro s
  cases s <;> decide

theorem critical_template_kernel_density_zero
    {DensityZeroCriticalShadow : Prop}
    (hDensityBridge :
      (∀ s, weightedTwoBitMassNum s * templateEpsilonDen * templateWeightDen s ≤
        weightedTwoBitMassDen s * (templateEpsilonDen - templateEpsilonNum) * templateWeightNum s) ->
      DensityZeroCriticalShadow) :
    DensityZeroCriticalShadow := by
  apply hDensityBridge
  exact critical_template_kernel_two_bit_contraction
