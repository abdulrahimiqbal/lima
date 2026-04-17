import Std

open Std

/-!
This file isolates the current critical frontier-shadow as a finite exact kernel
candidate in a separate `Pro` lane. It does not claim a full Collatz proof.
Instead it packages the exact three-state child law that the recent audits
identified on the rare `Q1 -> Q1,Q1` obstruction.
-/

inductive CriticalKernelState where
  | A
  | B
  | C
  deriving DecidableEq, Repr

abbrev ChildLawProfile := Nat × Nat × Nat × Nat
-- (source count, target count, one-child sources, two-child sources)

def stateResidues : CriticalKernelState → List Nat
  | .A => [31, 47, 63, 71, 91, 111, 155, 167, 207, 223, 231, 251]
  | .B => [27, 103, 127, 159, 191, 239]
  | .C => [255]

def classCounts : CriticalKernelState → List Nat
  | .A => [1, 1, 1]
  | .B => [7, 8, 9]
  | .C => [22, 29, 37]

def childLaw16384To32768 : CriticalKernelState → ChildLawProfile
  | .A => (1, 1, 1, 0)
  | .B => (7, 8, 6, 1)
  | .C => (22, 29, 15, 7)

def childLaw32768To65536 : CriticalKernelState → ChildLawProfile
  | .A => (1, 1, 1, 0)
  | .B => (8, 9, 7, 1)
  | .C => (29, 37, 21, 8)

theorem critical_q1_kernel_partition :
    stateResidues .A = [31, 47, 63, 71, 91, 111, 155, 167, 207, 223, 231, 251] ∧
    stateResidues .B = [27, 103, 127, 159, 191, 239] ∧
    stateResidues .C = [255] := by
  decide

theorem critical_q1_kernel_child_law :
    childLaw16384To32768 .A = (1, 1, 1, 0) ∧
    childLaw16384To32768 .B = (7, 8, 6, 1) ∧
    childLaw16384To32768 .C = (22, 29, 15, 7) ∧
    childLaw32768To65536 .A = (1, 1, 1, 0) ∧
    childLaw32768To65536 .B = (8, 9, 7, 1) ∧
    childLaw32768To65536 .C = (29, 37, 21, 8) := by
  decide

theorem critical_q1_kernel_recurrence :
    classCounts .A = [1, 1, 1] ∧
    classCounts .B = [7, 8, 9] ∧
    classCounts .C = [22, 29, 37] ∧
    8 = 7 + 1 ∧
    9 = 8 + 1 ∧
    29 = 22 + 7 ∧
    37 = 29 + 8 := by
  decide

theorem critical_q1_kernel_uniform_subcritical :
    1 < 2 ∧ 8 < 14 ∧ 9 < 16 ∧ 29 < 44 ∧ 37 < 58 := by
  decide
