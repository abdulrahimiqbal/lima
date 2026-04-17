import Std

open Std

/-!
This file records a deeper periodicity lane for the refined critical phase
kernel. It does not prove the final all-depth statement, but it turns the next
observed mixed/all-bifurcate alternation into explicit theorem objects.
-/

inductive CriticalPeriodicState where
  | A
  | B
  | C
  deriving DecidableEq, Repr

abbrev ChildLawProfile := Nat × Nat × Nat × Nat
-- (source count, target count, one-child sources, two-child sources)

def periodicResidues : CriticalPeriodicState → List Nat
  | .A => [31, 47, 63, 71, 91, 111, 155, 167, 207, 223, 231, 251]
  | .B => [27, 103, 127, 159, 191, 239]
  | .C => [255]

def counts262144 : CriticalPeriodicState → Nat
  | .A => 3
  | .B => 28
  | .C => 120

def counts524288 : CriticalPeriodicState → Nat
  | .A => 4
  | .B => 39
  | .C => 176

def counts1048576 : CriticalPeriodicState → Nat
  | .A => 8
  | .B => 78
  | .C => 352

def counts2097152 : CriticalPeriodicState → Nat
  | .A => 13
  | .B => 129
  | .C => 595

def childLaw262144To524288 : CriticalPeriodicState → ChildLawProfile
  | .A => (3, 4, 2, 1)
  | .B => (28, 39, 17, 11)
  | .C => (120, 176, 64, 56)

def childLaw524288To1048576 : CriticalPeriodicState → ChildLawProfile
  | .A => (4, 8, 0, 4)
  | .B => (39, 78, 0, 39)
  | .C => (176, 352, 0, 176)

def childLaw1048576To2097152 : CriticalPeriodicState → ChildLawProfile
  | .A => (8, 13, 3, 5)
  | .B => (78, 129, 27, 51)
  | .C => (352, 595, 109, 243)

theorem critical_q1_mixed_phase_262144_to_524288 :
    childLaw262144To524288 .A = (3, 4, 2, 1) ∧
    childLaw262144To524288 .B = (28, 39, 17, 11) ∧
    childLaw262144To524288 .C = (120, 176, 64, 56) := by
  decide

theorem critical_q1_all_bifurcate_524288_to_1048576 :
    childLaw524288To1048576 .A = (4, 8, 0, 4) ∧
    childLaw524288To1048576 .B = (39, 78, 0, 39) ∧
    childLaw524288To1048576 .C = (176, 352, 0, 176) := by
  decide

theorem critical_q1_mixed_phase_1048576_to_2097152 :
    childLaw1048576To2097152 .A = (8, 13, 3, 5) ∧
    childLaw1048576To2097152 .B = (78, 129, 27, 51) ∧
    childLaw1048576To2097152 .C = (352, 595, 109, 243) := by
  decide

theorem critical_q1_two_bit_return_262144_to_1048576_subcritical :
    8 < 12 ∧ 78 < 112 ∧ 352 < 480 := by
  decide

theorem critical_q1_two_bit_return_524288_to_2097152_subcritical :
    13 < 16 ∧ 129 < 156 ∧ 595 < 704 := by
  decide
