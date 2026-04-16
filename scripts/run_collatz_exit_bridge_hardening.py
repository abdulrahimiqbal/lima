from __future__ import annotations

import json
import subprocess


CONCRETE_EXIT_CASES = r"""
import Std

def collatzStep (n : Nat) : Nat :=
  if n % 2 = 0 then n / 2 else 3 * n + 1

def iterateNat (f : Nat -> Nat) : Nat -> Nat -> Nat
  | 0, n => n
  | k + 1, n => iterateNat f k (f n)

def PositiveDescentAt (n k : Nat) : Prop :=
  0 < iterateNat collatzStep k n ∧ iterateNat collatzStep k n < n

def EventualPositiveDescent : Prop :=
  ∀ n, n > 1 -> ∃ k, PositiveDescentAt n k

theorem iterateNat_add (f : Nat -> Nat) (a b n : Nat) :
    iterateNat f (a + b) n = iterateNat f b (iterateNat f a n) := by
  induction a generalizing n with
  | zero =>
      simp [iterateNat]
  | succ a ih =>
      simp [iterateNat, Nat.succ_add, ih]

theorem even_step_eq (q : Nat) :
    iterateNat collatzStep 1 (2*q) = q := by
  unfold iterateNat collatzStep
  simp [iterateNat, Nat.mul_mod_right, Nat.mul_div_right]

theorem even_param_descent (q : Nat) (hq : q > 0) :
    ∃ k, PositiveDescentAt (2*q) k := by
  refine ⟨1, ?_, ?_⟩
  · rw [even_step_eq]
    exact hq
  · rw [even_step_eq]
    omega

theorem odd_one_mod_four_step1_eq (a : Nat) :
    collatzStep (4*a + 1) = 4*(3*a+1) := by
  unfold collatzStep
  have hodd : (4*a+1) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem step_4_mul_eq (a : Nat) :
    collatzStep (4*(3*a+1)) = 2*(3*a+1) := by
  unfold collatzStep
  have heven : (4*(3*a+1)) % 2 = 0 := by omega
  simp [heven]
  omega

theorem step_2_mul_eq (a : Nat) :
    collatzStep (2*(3*a+1)) = 3*a+1 := by
  unfold collatzStep
  have heven : (2*(3*a+1)) % 2 = 0 := by omega
  simp [heven, Nat.mul_div_right]

theorem odd_one_mod_four_step3_eq (a : Nat) :
    iterateNat collatzStep 3 (4*a + 1) = 3*a + 1 := by
  simp [iterateNat, odd_one_mod_four_step1_eq, step_4_mul_eq, step_2_mul_eq]

theorem odd_one_mod_four_descent (a : Nat) (ha : a > 0) :
    ∃ k, PositiveDescentAt (4*a+1) k := by
  refine ⟨3, ?_, ?_⟩
  · rw [odd_one_mod_four_step3_eq]
    omega
  · rw [odd_one_mod_four_step3_eq]
    omega

theorem eight_b_plus_three_step1_eq (b : Nat) :
    collatzStep (8*b+3) = 2*(12*b+5) := by
  unfold collatzStep
  have hodd : (8*b+3) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem step_2_mul_any_eq (x : Nat) :
    collatzStep (2*x) = x := by
  unfold collatzStep
  have heven : (2*x) % 2 = 0 := by omega
  simp [heven, Nat.mul_div_right]

theorem step_4_mul_any_eq (x : Nat) :
    collatzStep (4*x) = 2*x := by
  unfold collatzStep
  have heven : (4*x) % 2 = 0 := by omega
  simp [heven]
  omega

theorem step_8_mul_any_eq (x : Nat) :
    collatzStep (8*x) = 4*x := by
  have h : 8*x = 2*(4*x) := by omega
  rw [h, step_2_mul_any_eq]

theorem step_16_mul_any_eq (x : Nat) :
    collatzStep (16*x) = 8*x := by
  have h : 16*x = 2*(8*x) := by omega
  rw [h, step_2_mul_any_eq]

theorem iterate_two_on_four_mul_eq (x : Nat) :
    iterateNat collatzStep 2 (4*x) = x := by
  simp [iterateNat, step_4_mul_any_eq, step_2_mul_any_eq]

theorem iterate_three_on_eight_mul_eq (x : Nat) :
    iterateNat collatzStep 3 (8*x) = x := by
  simp [iterateNat, step_8_mul_any_eq, step_4_mul_any_eq, step_2_mul_any_eq]

theorem iterate_four_on_sixteen_mul_eq (x : Nat) :
    iterateNat collatzStep 4 (16*x) = x := by
  simp [iterateNat, step_16_mul_any_eq, step_8_mul_any_eq, step_4_mul_any_eq, step_2_mul_any_eq]

theorem eight_b_plus_three_step2_eq (b : Nat) :
    iterateNat collatzStep 2 (8*b+3) = 12*b+5 := by
  simp [iterateNat, eight_b_plus_three_step1_eq, step_2_mul_any_eq]

theorem twelve_b_plus_five_as_one_mod_four (b : Nat) :
    12*b+5 = 4*(3*b+1)+1 := by
  omega

theorem eight_b_plus_three_step5_eq (b : Nat) :
    iterateNat collatzStep 5 (8*b+3) = 9*b+4 := by
  calc
    iterateNat collatzStep 5 (8*b+3)
        = iterateNat collatzStep 3 (iterateNat collatzStep 2 (8*b+3)) := by
            simpa using (iterateNat_add collatzStep 2 3 (8*b+3)).symm
    _ = iterateNat collatzStep 3 (12*b+5) := by
            rw [eight_b_plus_three_step2_eq]
    _ = iterateNat collatzStep 3 (4*(3*b+1)+1) := by
            rw [twelve_b_plus_five_as_one_mod_four]
    _ = 3*(3*b+1)+1 := by
            rw [odd_one_mod_four_step3_eq]
    _ = 9*b+4 := by
            omega

theorem sixteen_c_plus_three_step6_eq (c : Nat) :
    iterateNat collatzStep 6 (16*c+3) = 9*c+2 := by
  have hn : 16*c+3 = 8*(2*c)+3 := by omega
  have hdouble : 9*(2*c)+4 = 2*(9*c+2) := by omega
  calc
    iterateNat collatzStep 6 (16*c+3)
        = iterateNat collatzStep 6 (8*(2*c)+3) := by
            rw [hn]
    _ = iterateNat collatzStep 1 (iterateNat collatzStep 5 (8*(2*c)+3)) := by
            simpa using (iterateNat_add collatzStep 5 1 (8*(2*c)+3))
    _ = iterateNat collatzStep 1 (9*(2*c)+4) := by
            rw [eight_b_plus_three_step5_eq]
    _ = iterateNat collatzStep 1 (2*(9*c+2)) := by
            rw [hdouble]
    _ = 9*c+2 := by
            simp [iterateNat, step_2_mul_any_eq]

theorem sixteen_c_plus_three_descent (c : Nat) :
    ∃ k, PositiveDescentAt (16*c+3) k := by
  refine ⟨6, ?_, ?_⟩
  · rw [sixteen_c_plus_three_step6_eq]
    omega
  · rw [sixteen_c_plus_three_step6_eq]
    omega

theorem sixteen_c_plus_seven_step1_eq (c : Nat) :
    collatzStep (16*c+7) = 2*(24*c+11) := by
  unfold collatzStep
  have hodd : (16*c+7) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem twenty_four_c_plus_eleven_step_eq (c : Nat) :
    collatzStep (24*c+11) = 2*(36*c+17) := by
  unfold collatzStep
  have hodd : (24*c+11) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem thirty_six_c_plus_seventeen_step_eq (c : Nat) :
    collatzStep (36*c+17) = 4*(27*c+13) := by
  unfold collatzStep
  have hodd : (36*c+17) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem sixteen_c_plus_seven_step7_eq (c : Nat) :
    iterateNat collatzStep 7 (16*c+7) = 27*c+13 := by
  simp [
    iterateNat,
    sixteen_c_plus_seven_step1_eq,
    twenty_four_c_plus_eleven_step_eq,
    thirty_six_c_plus_seventeen_step_eq,
    step_2_mul_any_eq,
    step_4_mul_any_eq
  ]

theorem thirty_two_d_plus_twenty_three_step8_eq (d : Nat) :
    iterateNat collatzStep 8 (32*d+23) = 27*d+20 := by
  have hn : 32*d+23 = 16*(2*d+1)+7 := by omega
  have hlast : 27*(2*d+1)+13 = 2*(27*d+20) := by omega
  calc
    iterateNat collatzStep 8 (32*d+23)
        = iterateNat collatzStep 8 (16*(2*d+1)+7) := by
            rw [hn]
    _ = iterateNat collatzStep 1 (iterateNat collatzStep 7 (16*(2*d+1)+7)) := by
            simpa using (iterateNat_add collatzStep 7 1 (16*(2*d+1)+7))
    _ = iterateNat collatzStep 1 (27*(2*d+1)+13) := by
            rw [sixteen_c_plus_seven_step7_eq]
    _ = iterateNat collatzStep 1 (2*(27*d+20)) := by
            rw [hlast]
    _ = 27*d+20 := by
            simp [iterateNat, step_2_mul_any_eq]

theorem thirty_two_d_plus_twenty_three_descent (d : Nat) :
    ∃ k, PositiveDescentAt (32*d+23) k := by
  refine ⟨8, ?_, ?_⟩
  · rw [thirty_two_d_plus_twenty_three_step8_eq]
    omega
  · rw [thirty_two_d_plus_twenty_three_step8_eq]
    omega

theorem sixteen_c_plus_eleven_step1_eq (c : Nat) :
    collatzStep (16*c+11) = 2*(24*c+17) := by
  unfold collatzStep
  have hodd : (16*c+11) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem twenty_four_c_plus_seventeen_step_eq (c : Nat) :
    collatzStep (24*c+17) = 4*(18*c+13) := by
  unfold collatzStep
  have hodd : (24*c+17) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem sixteen_c_plus_eleven_step5_eq (c : Nat) :
    iterateNat collatzStep 5 (16*c+11) = 18*c+13 := by
  simp [
    iterateNat,
    sixteen_c_plus_eleven_step1_eq,
    twenty_four_c_plus_seventeen_step_eq,
    step_2_mul_any_eq,
    step_4_mul_any_eq
  ]

theorem thirty_six_d_plus_thirteen_step_eq (d : Nat) :
    collatzStep (36*d+13) = 4*(27*d+10) := by
  unfold collatzStep
  have hodd : (36*d+13) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem thirty_two_d_plus_eleven_step8_eq (d : Nat) :
    iterateNat collatzStep 8 (32*d+11) = 27*d+10 := by
  have hn : 32*d+11 = 16*(2*d)+11 := by omega
  have hmid : 18*(2*d)+13 = 36*d+13 := by omega
  calc
    iterateNat collatzStep 8 (32*d+11)
        = iterateNat collatzStep 8 (16*(2*d)+11) := by
            rw [hn]
    _ = iterateNat collatzStep 3 (iterateNat collatzStep 5 (16*(2*d)+11)) := by
            simpa using (iterateNat_add collatzStep 5 3 (16*(2*d)+11))
    _ = iterateNat collatzStep 3 (18*(2*d)+13) := by
            rw [sixteen_c_plus_eleven_step5_eq]
    _ = iterateNat collatzStep 3 (36*d+13) := by
            rw [hmid]
    _ = 27*d+10 := by
            simp [iterateNat, thirty_six_d_plus_thirteen_step_eq, step_4_mul_any_eq, step_2_mul_any_eq]

theorem thirty_two_d_plus_eleven_descent (d : Nat) :
    ∃ k, PositiveDescentAt (32*d+11) k := by
  refine ⟨8, ?_, ?_⟩
  · rw [thirty_two_d_plus_eleven_step8_eq]
    omega
  · rw [thirty_two_d_plus_eleven_step8_eq]
    omega

theorem one_twenty_eight_e_plus_seven_step1_eq (e : Nat) :
    collatzStep (128*e+7) = 2*(192*e+11) := by
  unfold collatzStep
  have hodd : (128*e+7) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem one_ninety_two_e_plus_eleven_step_eq (e : Nat) :
    collatzStep (192*e+11) = 2*(288*e+17) := by
  unfold collatzStep
  have hodd : (192*e+11) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem one_twenty_eight_e_plus_seven_step4_eq (e : Nat) :
    iterateNat collatzStep 4 (128*e+7) = 288*e+17 := by
  simp [
    iterateNat,
    one_twenty_eight_e_plus_seven_step1_eq,
    one_ninety_two_e_plus_eleven_step_eq,
    step_2_mul_any_eq
  ]

theorem two_eighty_eight_e_plus_seventeen_step_eq (e : Nat) :
    collatzStep (288*e+17) = 4*(216*e+13) := by
  unfold collatzStep
  have hodd : (288*e+17) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem two_eighty_eight_e_plus_seventeen_step3_eq (e : Nat) :
    iterateNat collatzStep 3 (288*e+17) = 216*e+13 := by
  calc
    iterateNat collatzStep 3 (288*e+17)
        = iterateNat collatzStep 2 (collatzStep (288*e+17)) := by
            simp [iterateNat]
    _ = iterateNat collatzStep 2 (4*(216*e+13)) := by
            rw [two_eighty_eight_e_plus_seventeen_step_eq]
    _ = 216*e+13 := by
            rw [iterate_two_on_four_mul_eq]

theorem two_sixteen_e_plus_thirteen_step_eq (e : Nat) :
    collatzStep (216*e+13) = 8*(81*e+5) := by
  unfold collatzStep
  have hodd : (216*e+13) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem two_sixteen_e_plus_thirteen_step4_eq (e : Nat) :
    iterateNat collatzStep 4 (216*e+13) = 81*e+5 := by
  calc
    iterateNat collatzStep 4 (216*e+13)
        = iterateNat collatzStep 3 (collatzStep (216*e+13)) := by
            simp [iterateNat]
    _ = iterateNat collatzStep 3 (8*(81*e+5)) := by
            rw [two_sixteen_e_plus_thirteen_step_eq]
    _ = 81*e+5 := by
            rw [iterate_three_on_eight_mul_eq]

theorem one_twenty_eight_e_plus_seven_step11_eq (e : Nat) :
    iterateNat collatzStep 11 (128*e+7) = 81*e+5 := by
  calc
    iterateNat collatzStep 11 (128*e+7)
        = iterateNat collatzStep 7 (iterateNat collatzStep 4 (128*e+7)) := by
            simpa using (iterateNat_add collatzStep 4 7 (128*e+7))
    _ = iterateNat collatzStep 7 (288*e+17) := by
            rw [one_twenty_eight_e_plus_seven_step4_eq]
    _ = iterateNat collatzStep 4 (216*e+13) := by
            calc
              iterateNat collatzStep 7 (288*e+17)
                  = iterateNat collatzStep 4 (iterateNat collatzStep 3 (288*e+17)) := by
                      simpa using (iterateNat_add collatzStep 3 4 (288*e+17))
              _ = iterateNat collatzStep 4 (216*e+13) := by
                      rw [two_eighty_eight_e_plus_seventeen_step3_eq]
    _ = 81*e+5 := by
            rw [two_sixteen_e_plus_thirteen_step4_eq]

theorem one_twenty_eight_e_plus_seven_descent (e : Nat) :
    ∃ k, PositiveDescentAt (128*e+7) k := by
  refine ⟨11, ?_, ?_⟩
  · rw [one_twenty_eight_e_plus_seven_step11_eq]
    omega
  · rw [one_twenty_eight_e_plus_seven_step11_eq]
    omega

theorem one_twenty_eight_e_plus_fifteen_step1_eq (e : Nat) :
    collatzStep (128*e+15) = 2*(192*e+23) := by
  unfold collatzStep
  have hodd : (128*e+15) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem one_ninety_two_e_plus_twenty_three_step_eq (e : Nat) :
    collatzStep (192*e+23) = 2*(288*e+35) := by
  unfold collatzStep
  have hodd : (192*e+23) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem two_eighty_eight_e_plus_thirty_five_step_eq (e : Nat) :
    collatzStep (288*e+35) = 2*(432*e+53) := by
  unfold collatzStep
  have hodd : (288*e+35) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem four_thirty_two_e_plus_fifty_three_step_eq (e : Nat) :
    collatzStep (432*e+53) = 16*(81*e+10) := by
  unfold collatzStep
  have hodd : (432*e+53) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem four_thirty_two_e_plus_fifty_three_step5_eq (e : Nat) :
    iterateNat collatzStep 5 (432*e+53) = 81*e+10 := by
  calc
    iterateNat collatzStep 5 (432*e+53)
        = iterateNat collatzStep 4 (collatzStep (432*e+53)) := by
            simp [iterateNat]
    _ = iterateNat collatzStep 4 (16*(81*e+10)) := by
            rw [four_thirty_two_e_plus_fifty_three_step_eq]
    _ = 81*e+10 := by
            rw [iterate_four_on_sixteen_mul_eq]

theorem one_twenty_eight_e_plus_fifteen_step6_eq (e : Nat) :
    iterateNat collatzStep 6 (128*e+15) = 432*e+53 := by
  simp [
    iterateNat,
    one_twenty_eight_e_plus_fifteen_step1_eq,
    one_ninety_two_e_plus_twenty_three_step_eq,
    two_eighty_eight_e_plus_thirty_five_step_eq,
    step_2_mul_any_eq
  ]

theorem one_twenty_eight_e_plus_fifteen_step11_eq (e : Nat) :
    iterateNat collatzStep 11 (128*e+15) = 81*e+10 := by
  calc
    iterateNat collatzStep 11 (128*e+15)
        = iterateNat collatzStep 5 (iterateNat collatzStep 6 (128*e+15)) := by
            simpa using (iterateNat_add collatzStep 6 5 (128*e+15))
    _ = iterateNat collatzStep 5 (432*e+53) := by
            rw [one_twenty_eight_e_plus_fifteen_step6_eq]
    _ = 81*e+10 := by
            rw [four_thirty_two_e_plus_fifty_three_step5_eq]

theorem one_twenty_eight_e_plus_fifteen_descent (e : Nat) :
    ∃ k, PositiveDescentAt (128*e+15) k := by
  refine ⟨11, ?_, ?_⟩
  · rw [one_twenty_eight_e_plus_fifteen_step11_eq]
    omega
  · rw [one_twenty_eight_e_plus_fifteen_step11_eq]
    omega

theorem one_twenty_eight_e_plus_fifty_nine_step1_eq (e : Nat) :
    collatzStep (128*e+59) = 2*(192*e+89) := by
  unfold collatzStep
  have hodd : (128*e+59) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem one_ninety_two_e_plus_eighty_nine_step_eq (e : Nat) :
    collatzStep (192*e+89) = 4*(144*e+67) := by
  unfold collatzStep
  have hodd : (192*e+89) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem one_twenty_eight_e_plus_fifty_nine_step2_eq (e : Nat) :
    iterateNat collatzStep 2 (128*e+59) = 192*e+89 := by
  simp [iterateNat, one_twenty_eight_e_plus_fifty_nine_step1_eq, step_2_mul_any_eq]

theorem one_ninety_two_e_plus_eighty_nine_step3_eq (e : Nat) :
    iterateNat collatzStep 3 (192*e+89) = 144*e+67 := by
  calc
    iterateNat collatzStep 3 (192*e+89)
        = iterateNat collatzStep 2 (collatzStep (192*e+89)) := by
            simp [iterateNat]
    _ = iterateNat collatzStep 2 (4*(144*e+67)) := by
            rw [one_ninety_two_e_plus_eighty_nine_step_eq]
    _ = 144*e+67 := by
            rw [iterate_two_on_four_mul_eq]

theorem one_forty_four_e_plus_sixty_seven_step_eq (e : Nat) :
    collatzStep (144*e+67) = 2*(216*e+101) := by
  unfold collatzStep
  have hodd : (144*e+67) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem one_forty_four_e_plus_sixty_seven_step2_eq (e : Nat) :
    iterateNat collatzStep 2 (144*e+67) = 216*e+101 := by
  simp [iterateNat, one_forty_four_e_plus_sixty_seven_step_eq, step_2_mul_any_eq]

theorem two_sixteen_e_plus_one_hundred_one_step_eq (e : Nat) :
    collatzStep (216*e+101) = 8*(81*e+38) := by
  unfold collatzStep
  have hodd : (216*e+101) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem two_sixteen_e_plus_one_hundred_one_step4_eq (e : Nat) :
    iterateNat collatzStep 4 (216*e+101) = 81*e+38 := by
  calc
    iterateNat collatzStep 4 (216*e+101)
        = iterateNat collatzStep 3 (collatzStep (216*e+101)) := by
            simp [iterateNat]
    _ = iterateNat collatzStep 3 (8*(81*e+38)) := by
            rw [two_sixteen_e_plus_one_hundred_one_step_eq]
    _ = 81*e+38 := by
            rw [iterate_three_on_eight_mul_eq]

theorem one_twenty_eight_e_plus_fifty_nine_step5_eq (e : Nat) :
    iterateNat collatzStep 5 (128*e+59) = 144*e+67 := by
  calc
    iterateNat collatzStep 5 (128*e+59)
        = iterateNat collatzStep 3 (iterateNat collatzStep 2 (128*e+59)) := by
            simpa using (iterateNat_add collatzStep 2 3 (128*e+59)).symm
    _ = iterateNat collatzStep 3 (192*e+89) := by
            rw [one_twenty_eight_e_plus_fifty_nine_step2_eq]
    _ = 144*e+67 := by
            rw [one_ninety_two_e_plus_eighty_nine_step3_eq]

theorem one_twenty_eight_e_plus_fifty_nine_step11_eq (e : Nat) :
    iterateNat collatzStep 11 (128*e+59) = 81*e+38 := by
  calc
    iterateNat collatzStep 11 (128*e+59)
        = iterateNat collatzStep 6 (iterateNat collatzStep 5 (128*e+59)) := by
            simpa using (iterateNat_add collatzStep 5 6 (128*e+59))
    _ = iterateNat collatzStep 6 (144*e+67) := by
            rw [one_twenty_eight_e_plus_fifty_nine_step5_eq]
    _ = iterateNat collatzStep 4 (216*e+101) := by
            calc
              iterateNat collatzStep 6 (144*e+67)
                  = iterateNat collatzStep 4 (iterateNat collatzStep 2 (144*e+67)) := by
                      simpa using (iterateNat_add collatzStep 2 4 (144*e+67))
              _ = iterateNat collatzStep 4 (216*e+101) := by
                      rw [one_forty_four_e_plus_sixty_seven_step2_eq]
    _ = 81*e+38 := by
            rw [two_sixteen_e_plus_one_hundred_one_step4_eq]

theorem one_twenty_eight_e_plus_fifty_nine_descent (e : Nat) :
    ∃ k, PositiveDescentAt (128*e+59) k := by
  refine ⟨11, ?_, ?_⟩
  · rw [one_twenty_eight_e_plus_fifty_nine_step11_eq]
    omega
  · rw [one_twenty_eight_e_plus_fifty_nine_step11_eq]
    omega

def CoveredByConcreteExit (n : Nat) : Prop :=
  (∃ q, q > 0 ∧ n = 2*q) ∨
  (∃ a, a > 0 ∧ n = 4*a+1) ∨
  (∃ c, n = 16*c+3) ∨
  (∃ d, n = 32*d+11) ∨
  (∃ d, n = 32*d+23) ∨
  (∃ e, n = 128*e+7) ∨
  (∃ e, n = 128*e+15) ∨
  (∃ e, n = 128*e+59)

theorem concrete_exit_sound_for_covered (n : Nat)
    (hCovered : CoveredByConcreteExit n) :
    ∃ k, PositiveDescentAt n k := by
  cases hCovered with
  | inl hEven =>
      obtain ⟨q, hq, hn⟩ := hEven
      subst hn
      exact even_param_descent q hq
  | inr hOdd =>
      cases hOdd with
      | inl hOneModFour =>
          obtain ⟨a, ha, hn⟩ := hOneModFour
          subst hn
          exact odd_one_mod_four_descent a ha
      | inr hSixteen =>
          cases hSixteen with
          | inl hThreeModSixteen =>
              obtain ⟨c, hn⟩ := hThreeModSixteen
              subst hn
              exact sixteen_c_plus_three_descent c
          | inr hModThirtyTwo =>
              cases hModThirtyTwo with
              | inl hEleven =>
                  obtain ⟨d, hn⟩ := hEleven
                  subst hn
                  exact thirty_two_d_plus_eleven_descent d
              | inr hTwentyThree =>
                  cases hTwentyThree with
                  | inl hTwentyThree =>
                      obtain ⟨d, hn⟩ := hTwentyThree
                      subst hn
                      exact thirty_two_d_plus_twenty_three_descent d
                  | inr hOneTwentyEight =>
                      cases hOneTwentyEight with
                      | inl hSeven =>
                          obtain ⟨e, hn⟩ := hSeven
                          subst hn
                          exact one_twenty_eight_e_plus_seven_descent e
                      | inr hTail =>
                          cases hTail with
                          | inl hFifteen =>
                              obtain ⟨e, hn⟩ := hFifteen
                              subst hn
                              exact one_twenty_eight_e_plus_fifteen_descent e
                          | inr hFiftyNine =>
                              obtain ⟨e, hn⟩ := hFiftyNine
                              subst hn
                              exact one_twenty_eight_e_plus_fifty_nine_descent e

theorem three_has_concrete_descent :
    PositiveDescentAt 3 6 := by
  unfold PositiveDescentAt
  native_decide

theorem seven_has_concrete_descent :
    PositiveDescentAt 7 11 := by
  unfold PositiveDescentAt
  native_decide

theorem twenty_seven_not_covered_by_parametric_exit_families :
    Not (CoveredByConcreteExit 27) := by
  intro h
  cases h with
  | inl hEven =>
      obtain ⟨q, hq, h27⟩ := hEven
      omega
  | inr hOdd =>
      cases hOdd with
      | inl hOneModFour =>
          obtain ⟨a, ha, h27⟩ := hOneModFour
          omega
      | inr hSixteen =>
          cases hSixteen with
          | inl hThreeModSixteen =>
              obtain ⟨c, h27⟩ := hThreeModSixteen
              omega
          | inr hModThirtyTwo =>
              cases hModThirtyTwo with
              | inl hEleven =>
                  obtain ⟨d, h27⟩ := hEleven
                  omega
              | inr hTwentyThree =>
                  cases hTwentyThree with
                  | inl hTwentyThree =>
                      obtain ⟨d, h27⟩ := hTwentyThree
                      omega
                  | inr hOneTwentyEight =>
                      cases hOneTwentyEight with
                      | inl hSeven =>
                          obtain ⟨e, h27⟩ := hSeven
                          omega
                      | inr hTail =>
                          cases hTail with
                          | inl hFifteen =>
                              obtain ⟨e, h27⟩ := hFifteen
                              omega
                          | inr hFiftyNine =>
                              obtain ⟨e, h27⟩ := hFiftyNine
                              omega
""".strip()


RAW_ODD_THREE_MOD_FOUR_FAMILY = (
    CONCRETE_EXIT_CASES
    + r"""

theorem odd_three_mod_four_family_descent_raw (a : Nat) :
    ∃ k, PositiveDescentAt (4*a+3) k := by
  refine ⟨0, ?_⟩
"""
)


def run_lean(name: str, source: str) -> dict[str, object]:
    result = subprocess.run(
        ["lean", "--stdin"],
        input=source,
        text=True,
        capture_output=True,
        timeout=90,
    )
    return {
        "name": name,
        "returncode": result.returncode,
        "ok": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def excerpt_failure(check: dict[str, object]) -> str:
    text = f"{check.get('stdout', '')}\n{check.get('stderr', '')}"
    lines = []
    for line in str(text).splitlines():
        if (
            "unsolved goals" in line
            or "⊢" in line
            or "PositiveDescentAt" in line
            or "4 * a + 3" in line
        ):
            lines.append(line.rstrip())
    return "\n".join(lines[:16])


def main() -> int:
    checks = [
        run_lean("concrete_exit_cases", CONCRETE_EXIT_CASES),
        run_lean("raw_odd_three_mod_four_family", RAW_ODD_THREE_MOD_FOUR_FAMILY),
    ]
    concrete = checks[0]
    raw_odd = checks[1]
    payload = {
        "verdict": "first_concrete_exit_bridge_hardened",
        "concrete_exit_cases_compile": concrete["ok"],
        "raw_odd_three_mod_four_family_compiles": raw_odd["ok"],
        "raw_odd_three_mod_four_failure_excerpt": excerpt_failure(raw_odd),
        "proved_now": [
            "Every positive even number 2*q descends in one Collatz step.",
            "Every number 4*a+1 with a>0 descends in three Collatz steps.",
            "Every number 16*c+3 descends in six Collatz steps.",
            "Every number 32*d+11 descends in eight Collatz steps.",
            "Every number 32*d+23 descends in eight Collatz steps.",
            "Every number 128*e+7 descends in eleven Collatz steps.",
            "Every number 128*e+15 descends in eleven Collatz steps.",
            "Every number 128*e+59 descends in eleven Collatz steps.",
            "The covered concrete exit families imply an actual Nat-level positive descent.",
            "The specific 3 and 7 cases have explicit descent witnesses.",
            "n=27 is not covered by the current parametric exit families.",
        ],
        "remaining_gap": (
            "The full parametric odd 4*a+3 family is still uncovered, but several mod-128 "
            "subfamilies are now proved. "
            "The first unresolved odd residues at the current frontier are "
            "27, 31, 39, 47, 63, 71, 79, 91, 95, 103, 111, 123, and 127 mod 128."
        ),
        "next_action": (
            "Continue the parity-block decomposition on the remaining unresolved mod-128 "
            "families, or extract the well-founded measure that makes their repeated expansion terminate."
        ),
        "checks": checks,
    }
    print(json.dumps(payload, indent=2))
    return 0 if concrete["ok"] and not raw_odd["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
