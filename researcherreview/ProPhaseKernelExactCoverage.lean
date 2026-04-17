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
  | 31 => some .kernelA
  | 47 => some .kernelA
  | 63 => some .kernelA
  | 71 => some .kernelA
  | 91 => some .kernelA
  | 111 => some .kernelA
  | 155 => some .kernelA
  | 167 => some .kernelA
  | 207 => some .kernelA
  | 223 => some .kernelA
  | 231 => some .kernelA
  | 251 => some .kernelA
  | 27 => some .kernelB
  | 103 => some .kernelB
  | 127 => some .kernelB
  | 159 => some .kernelB
  | 191 => some .kernelB
  | 239 => some .kernelB
  | 255 => some .kernelC
  | _ => none

def PhaseKernelExactCoverage : Prop :=
  frontierCoverage 39 = some .descends ∧
    frontierCoverage 79 = some .descends ∧
    frontierCoverage 95 = some .descends ∧
    frontierCoverage 123 = some .descends ∧
    frontierCoverage 27 = some .kernelB ∧
    frontierCoverage 31 = some .kernelA ∧
    frontierCoverage 47 = some .kernelA ∧
    frontierCoverage 63 = some .kernelA ∧
    frontierCoverage 71 = some .kernelA ∧
    frontierCoverage 91 = some .kernelA ∧
    frontierCoverage 103 = some .kernelB ∧
    frontierCoverage 111 = some .kernelA ∧
    frontierCoverage 127 = some .kernelB ∧
    frontierCoverage 155 = some .kernelA ∧
    frontierCoverage 159 = some .kernelB ∧
    frontierCoverage 167 = some .kernelA ∧
    frontierCoverage 191 = some .kernelB ∧
    frontierCoverage 207 = some .kernelA ∧
    frontierCoverage 223 = some .kernelA ∧
    frontierCoverage 231 = some .kernelA ∧
    frontierCoverage 239 = some .kernelB ∧
    frontierCoverage 251 = some .kernelA ∧
    frontierCoverage 255 = some .kernelC

theorem phase_kernel_exact_coverage : PhaseKernelExactCoverage := by
  repeat' constructor
  all_goals rfl
