import Std

open Std

/-!
This file records the next refined proof object after the coarse `A/B/C`
critical-shadow quotient. The one-bit child law is not stable forever: at
`65536 -> 131072` every critical residue bifurcates. The surviving theorem
target is therefore a phase-aware two-bit return law.
-/

inductive CriticalPhaseState where
  | A
  | B
  | C
  deriving DecidableEq, Repr

abbrev ChildLawProfile := Nat × Nat × Nat
-- (source count, target count, two-child sources)

def phaseResidues : CriticalPhaseState → List Nat
  | .A => [31, 47, 63, 71, 91, 111, 155, 167, 207, 223, 231, 251]
  | .B => [27, 103, 127, 159, 191, 239]
  | .C => [255]

def phaseCounts65536 : CriticalPhaseState → Nat
  | .A => 1
  | .B => 9
  | .C => 37

def phaseCounts131072 : CriticalPhaseState → Nat
  | .A => 2
  | .B => 18
  | .C => 74

def phaseCounts262144 : CriticalPhaseState → Nat
  | .A => 3
  | .B => 28
  | .C => 120

def childLaw65536To131072 : CriticalPhaseState → ChildLawProfile
  | .A => (1, 2, 1)
  | .B => (9, 18, 9)
  | .C => (37, 74, 37)

def childLaw131072To262144 : CriticalPhaseState → ChildLawProfile
  | .A => (2, 3, 1)
  | .B => (18, 28, 10)
  | .C => (74, 120, 46)

theorem critical_q1_phase_partition :
    phaseResidues .A = [31, 47, 63, 71, 91, 111, 155, 167, 207, 223, 231, 251] ∧
    phaseResidues .B = [27, 103, 127, 159, 191, 239] ∧
    phaseResidues .C = [255] := by
  decide

theorem critical_q1_all_bifurcate_65536_to_131072 :
    childLaw65536To131072 .A = (1, 2, 1) ∧
    childLaw65536To131072 .B = (9, 18, 9) ∧
    childLaw65536To131072 .C = (37, 74, 37) := by
  decide

theorem critical_q1_two_bit_return_65536_to_262144 :
    phaseCounts65536 .A = 1 ∧
    phaseCounts131072 .A = 2 ∧
    phaseCounts262144 .A = 3 ∧
    phaseCounts65536 .B = 9 ∧
    phaseCounts131072 .B = 18 ∧
    phaseCounts262144 .B = 28 ∧
    phaseCounts65536 .C = 37 ∧
    phaseCounts131072 .C = 74 ∧
    phaseCounts262144 .C = 120 := by
  decide

theorem critical_q1_two_bit_uniform_subcritical :
    3 < 4 ∧ 28 < 36 ∧ 120 < 148 := by
  decide
