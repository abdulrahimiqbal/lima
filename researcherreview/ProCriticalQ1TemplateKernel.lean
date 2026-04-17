import Std

open Std

/-!
This file freezes the current checked critical shadow into a deterministic
phase-aware template kernel. The state order is canonical: lexicographic by
`(phase, residue_mod_256, one_child_sources, two_child_sources, target_count)`.
The currently checked two-bit successor data is exact on the verified window
through source moduli `262144`, `524288`, `1048576`, and `2097152`.
-/

inductive CriticalPhase where
  | mixed
  | bifurcate
  deriving DecidableEq, Repr

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

def templatePhase : CriticalTemplateState → CriticalPhase
  | .T1 => .bifurcate
  | .T2 => .bifurcate
  | .T3 => .bifurcate
  | .T4 => .mixed
  | .T5 => .mixed
  | .T6 => .mixed
  | .T7 => .mixed
  | .T8 => .mixed
  | .T9 => .mixed
  | .T10 => .mixed
  | .T11 => .mixed
  | .T12 => .mixed

def templateResidueClass : CriticalTemplateState → Nat
  | .T1 => 27
  | .T2 => 31
  | .T3 => 255
  | .T4 => 27
  | .T5 => 27
  | .T6 => 27
  | .T7 => 31
  | .T8 => 31
  | .T9 => 31
  | .T10 => 255
  | .T11 => 255
  | .T12 => 255

def templateSourceCount : CriticalTemplateState → Nat
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

def templateTargetCount : CriticalTemplateState → Nat
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

def templateOneChildSources : CriticalTemplateState → Nat
  | .T1 => 0
  | .T2 => 0
  | .T3 => 0
  | .T4 => 17
  | .T5 => 27
  | .T6 => 65
  | .T7 => 2
  | .T8 => 3
  | .T9 => 7
  | .T10 => 64
  | .T11 => 109
  | .T12 => 273

def templateTwoChildSources : CriticalTemplateState → Nat
  | .T1 => 39
  | .T2 => 4
  | .T3 => 176
  | .T4 => 11
  | .T5 => 51
  | .T6 => 64
  | .T7 => 1
  | .T8 => 5
  | .T9 => 6
  | .T10 => 56
  | .T11 => 243
  | .T12 => 322

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

def templateWeight (s : CriticalTemplateState) : Rat :=
  (templateWeightNum s : Rat) / templateWeightDen s

def templateTwoBitSucc : CriticalTemplateState → List CriticalTemplateState
  | .T1 => [.T6]
  | .T2 => [.T9]
  | .T3 => [.T12]
  | .T4 => [.T5]
  | .T5 => [.T6]
  | .T6 => []
  | .T7 => [.T8]
  | .T8 => [.T9]
  | .T9 => []
  | .T10 => [.T11]
  | .T11 => [.T12]
  | .T12 => []

theorem critical_template_kernel_partition_checked_window :
    templatePhase .T1 = .bifurcate ∧
    templateResidueClass .T1 = 27 ∧
    templateSourceCount .T1 = 39 ∧
    templateTargetCount .T1 = 78 ∧
    templateOneChildSources .T1 = 0 ∧
    templateTwoChildSources .T1 = 39 ∧
    templatePhase .T2 = .bifurcate ∧
    templateResidueClass .T2 = 31 ∧
    templateSourceCount .T2 = 4 ∧
    templateTargetCount .T2 = 8 ∧
    templateOneChildSources .T2 = 0 ∧
    templateTwoChildSources .T2 = 4 ∧
    templatePhase .T3 = .bifurcate ∧
    templateResidueClass .T3 = 255 ∧
    templateSourceCount .T3 = 176 ∧
    templateTargetCount .T3 = 352 ∧
    templateOneChildSources .T3 = 0 ∧
    templateTwoChildSources .T3 = 176 ∧
    templatePhase .T4 = .mixed ∧
    templateResidueClass .T4 = 27 ∧
    templateSourceCount .T4 = 28 ∧
    templateTargetCount .T4 = 39 ∧
    templateOneChildSources .T4 = 17 ∧
    templateTwoChildSources .T4 = 11 ∧
    templatePhase .T5 = .mixed ∧
    templateResidueClass .T5 = 27 ∧
    templateSourceCount .T5 = 78 ∧
    templateTargetCount .T5 = 129 ∧
    templateOneChildSources .T5 = 27 ∧
    templateTwoChildSources .T5 = 51 ∧
    templatePhase .T6 = .mixed ∧
    templateResidueClass .T6 = 27 ∧
    templateSourceCount .T6 = 129 ∧
    templateTargetCount .T6 = 193 ∧
    templateOneChildSources .T6 = 65 ∧
    templateTwoChildSources .T6 = 64 ∧
    templatePhase .T7 = .mixed ∧
    templateResidueClass .T7 = 31 ∧
    templateSourceCount .T7 = 3 ∧
    templateTargetCount .T7 = 4 ∧
    templateOneChildSources .T7 = 2 ∧
    templateTwoChildSources .T7 = 1 ∧
    templatePhase .T8 = .mixed ∧
    templateResidueClass .T8 = 31 ∧
    templateSourceCount .T8 = 8 ∧
    templateTargetCount .T8 = 13 ∧
    templateOneChildSources .T8 = 3 ∧
    templateTwoChildSources .T8 = 5 ∧
    templatePhase .T9 = .mixed ∧
    templateResidueClass .T9 = 31 ∧
    templateSourceCount .T9 = 13 ∧
    templateTargetCount .T9 = 19 ∧
    templateOneChildSources .T9 = 7 ∧
    templateTwoChildSources .T9 = 6 ∧
    templatePhase .T10 = .mixed ∧
    templateResidueClass .T10 = 255 ∧
    templateSourceCount .T10 = 120 ∧
    templateTargetCount .T10 = 176 ∧
    templateOneChildSources .T10 = 64 ∧
    templateTwoChildSources .T10 = 56 ∧
    templatePhase .T11 = .mixed ∧
    templateResidueClass .T11 = 255 ∧
    templateSourceCount .T11 = 352 ∧
    templateTargetCount .T11 = 595 ∧
    templateOneChildSources .T11 = 109 ∧
    templateTwoChildSources .T11 = 243 ∧
    templatePhase .T12 = .mixed ∧
    templateResidueClass .T12 = 255 ∧
    templateSourceCount .T12 = 595 ∧
    templateTargetCount .T12 = 917 ∧
    templateOneChildSources .T12 = 273 ∧
    templateTwoChildSources .T12 = 322 := by
  simp [
    templatePhase,
    templateResidueClass,
    templateSourceCount,
    templateTargetCount,
    templateOneChildSources,
    templateTwoChildSources,
  ]

theorem critical_template_kernel_transition_checked_window :
    templateTwoBitSucc .T1 = [.T6] ∧
    templateTwoBitSucc .T2 = [.T9] ∧
    templateTwoBitSucc .T3 = [.T12] ∧
    templateTwoBitSucc .T4 = [.T5] ∧
    templateTwoBitSucc .T5 = [.T6] ∧
    templateTwoBitSucc .T6 = [] ∧
    templateTwoBitSucc .T7 = [.T8] ∧
    templateTwoBitSucc .T8 = [.T9] ∧
    templateTwoBitSucc .T9 = [] ∧
    templateTwoBitSucc .T10 = [.T11] ∧
    templateTwoBitSucc .T11 = [.T12] ∧
    templateTwoBitSucc .T12 = [] := by
  simp [templateTwoBitSucc]

theorem critical_template_kernel_weight_data_checked_window :
    templateWeightNum .T1 = 39 ∧
    templateWeightDen .T1 = 1 ∧
    templateWeightNum .T2 = 4 ∧
    templateWeightDen .T2 = 1 ∧
    templateWeightNum .T3 = 176 ∧
    templateWeightDen .T3 = 1 ∧
    templateWeightNum .T4 = 28 ∧
    templateWeightDen .T4 = 1 ∧
    templateWeightNum .T5 = 78 ∧
    templateWeightDen .T5 = 1 ∧
    templateWeightNum .T6 = 129 ∧
    templateWeightDen .T6 = 1 ∧
    templateWeightNum .T7 = 3 ∧
    templateWeightDen .T7 = 1 ∧
    templateWeightNum .T8 = 8 ∧
    templateWeightDen .T8 = 1 ∧
    templateWeightNum .T9 = 13 ∧
    templateWeightDen .T9 = 1 ∧
    templateWeightNum .T10 = 120 ∧
    templateWeightDen .T10 = 1 ∧
    templateWeightNum .T11 = 352 ∧
    templateWeightDen .T11 = 1 ∧
    templateWeightNum .T12 = 595 ∧
    templateWeightDen .T12 = 1 := by
  simp [templateWeightNum, templateWeightDen]
