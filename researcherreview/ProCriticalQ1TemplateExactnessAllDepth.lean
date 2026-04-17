import Std

open Std

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

def templateTwoBitReturnNum : CriticalTemplateState → Nat
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

def templateTwoBitReturnDen : CriticalTemplateState → Nat
  | .T1 => 156
  | .T2 => 16
  | .T3 => 704
  | .T4 => 112
  | .T5 => 312
  | .T6 => 516
  | .T7 => 12
  | .T8 => 32
  | .T9 => 52
  | .T10 => 480
  | .T11 => 1408
  | .T12 => 2380

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

theorem critical_template_kernel_classifier_checked_prefix :
    templateClassifier (27, 39, 0, 39) = some .T1 ∧
    templateClassifier (31, 4, 0, 4) = some .T2 ∧
    templateClassifier (255, 176, 0, 176) = some .T3 ∧
    templateClassifier (27, 28, 17, 11) = some .T4 ∧
    templateClassifier (27, 78, 27, 51) = some .T5 ∧
    templateClassifier (27, 129, 65, 64) = some .T6 ∧
    templateClassifier (31, 3, 2, 1) = some .T7 ∧
    templateClassifier (31, 8, 3, 5) = some .T8 ∧
    templateClassifier (31, 13, 7, 6) = some .T9 ∧
    templateClassifier (255, 120, 64, 56) = some .T10 ∧
    templateClassifier (255, 352, 109, 243) = some .T11 ∧
    templateClassifier (255, 595, 273, 322) = some .T12 := by
  native_decide

theorem critical_template_kernel_checked_prefix_return_factors :
    templateTwoBitReturnNum .T1 = 78 ∧ templateTwoBitReturnDen .T1 = 156 ∧
    templateTwoBitReturnNum .T6 = 193 ∧ templateTwoBitReturnDen .T6 = 516 ∧
    templateTwoBitReturnNum .T9 = 19 ∧ templateTwoBitReturnDen .T9 = 52 ∧
    templateTwoBitReturnNum .T12 = 917 ∧ templateTwoBitReturnDen .T12 = 2380 := by
  native_decide
