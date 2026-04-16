import Std

/-!
This file extends the concrete exit-bridge hardening route with additional
explicit affine-family descent lemmas discovered by deterministic search.
It does not prove the full Collatz conjecture; it only hardens further
branches of the unresolved residue tree.
-/

def collatzStep (n : Nat) : Nat :=
  if n % 2 = 0 then n / 2 else 3 * n + 1

def iterateNat (f : Nat -> Nat) : Nat -> Nat -> Nat
  | 0, n => n
  | k + 1, n => iterateNat f k (f n)

def PositiveDescentAt (n k : Nat) : Prop :=
  0 < iterateNat collatzStep k n ∧ iterateNat collatzStep k n < n

-- 1024*t + 287 descends in 16 ordinary Collatz steps to 729*t + 205.
theorem fam_1024_287_step_1_eq (t : Nat) :
    collatzStep (1024*t + 287) = 3072*t + 862 := by
  unfold collatzStep
  have hodd : (1024*t + 287) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_287_step_2_eq (t : Nat) :
    collatzStep (3072*t + 862) = 1536*t + 431 := by
  unfold collatzStep
  have heven : (3072*t + 862) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_287_step_3_eq (t : Nat) :
    collatzStep (1536*t + 431) = 4608*t + 1294 := by
  unfold collatzStep
  have hodd : (1536*t + 431) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_287_step_4_eq (t : Nat) :
    collatzStep (4608*t + 1294) = 2304*t + 647 := by
  unfold collatzStep
  have heven : (4608*t + 1294) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_287_step_5_eq (t : Nat) :
    collatzStep (2304*t + 647) = 6912*t + 1942 := by
  unfold collatzStep
  have hodd : (2304*t + 647) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_287_step_6_eq (t : Nat) :
    collatzStep (6912*t + 1942) = 3456*t + 971 := by
  unfold collatzStep
  have heven : (6912*t + 1942) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_287_step_7_eq (t : Nat) :
    collatzStep (3456*t + 971) = 10368*t + 2914 := by
  unfold collatzStep
  have hodd : (3456*t + 971) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_287_step_8_eq (t : Nat) :
    collatzStep (10368*t + 2914) = 5184*t + 1457 := by
  unfold collatzStep
  have heven : (10368*t + 2914) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_287_step_9_eq (t : Nat) :
    collatzStep (5184*t + 1457) = 15552*t + 4372 := by
  unfold collatzStep
  have hodd : (5184*t + 1457) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_287_step_10_eq (t : Nat) :
    collatzStep (15552*t + 4372) = 7776*t + 2186 := by
  unfold collatzStep
  have heven : (15552*t + 4372) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_287_step_11_eq (t : Nat) :
    collatzStep (7776*t + 2186) = 3888*t + 1093 := by
  unfold collatzStep
  have heven : (7776*t + 2186) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_287_step_12_eq (t : Nat) :
    collatzStep (3888*t + 1093) = 11664*t + 3280 := by
  unfold collatzStep
  have hodd : (3888*t + 1093) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_287_step_13_eq (t : Nat) :
    collatzStep (11664*t + 3280) = 5832*t + 1640 := by
  unfold collatzStep
  have heven : (11664*t + 3280) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_287_step_14_eq (t : Nat) :
    collatzStep (5832*t + 1640) = 2916*t + 820 := by
  unfold collatzStep
  have heven : (5832*t + 1640) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_287_step_15_eq (t : Nat) :
    collatzStep (2916*t + 820) = 1458*t + 410 := by
  unfold collatzStep
  have heven : (2916*t + 820) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_287_step_16_eq (t : Nat) :
    collatzStep (1458*t + 410) = 729*t + 205 := by
  unfold collatzStep
  have heven : (1458*t + 410) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_287_iterate_eq (t : Nat) :
    iterateNat collatzStep 16 (1024*t + 287) = 729*t + 205 := by
  simp [iterateNat,
    fam_1024_287_step_1_eq,
    fam_1024_287_step_2_eq,
    fam_1024_287_step_3_eq,
    fam_1024_287_step_4_eq,
    fam_1024_287_step_5_eq,
    fam_1024_287_step_6_eq,
    fam_1024_287_step_7_eq,
    fam_1024_287_step_8_eq,
    fam_1024_287_step_9_eq,
    fam_1024_287_step_10_eq,
    fam_1024_287_step_11_eq,
    fam_1024_287_step_12_eq,
    fam_1024_287_step_13_eq,
    fam_1024_287_step_14_eq,
    fam_1024_287_step_15_eq,
    fam_1024_287_step_16_eq]

theorem fam_1024_287_descent (t : Nat) :
    ∃ k, PositiveDescentAt (1024*t + 287) k := by
  refine ⟨16, ?_, ?_⟩
  · rw [fam_1024_287_iterate_eq]
    omega
  · rw [fam_1024_287_iterate_eq]
    omega

-- 1024*t + 815 descends in 16 ordinary Collatz steps to 729*t + 581.
theorem fam_1024_815_step_1_eq (t : Nat) :
    collatzStep (1024*t + 815) = 3072*t + 2446 := by
  unfold collatzStep
  have hodd : (1024*t + 815) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_815_step_2_eq (t : Nat) :
    collatzStep (3072*t + 2446) = 1536*t + 1223 := by
  unfold collatzStep
  have heven : (3072*t + 2446) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_815_step_3_eq (t : Nat) :
    collatzStep (1536*t + 1223) = 4608*t + 3670 := by
  unfold collatzStep
  have hodd : (1536*t + 1223) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_815_step_4_eq (t : Nat) :
    collatzStep (4608*t + 3670) = 2304*t + 1835 := by
  unfold collatzStep
  have heven : (4608*t + 3670) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_815_step_5_eq (t : Nat) :
    collatzStep (2304*t + 1835) = 6912*t + 5506 := by
  unfold collatzStep
  have hodd : (2304*t + 1835) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_815_step_6_eq (t : Nat) :
    collatzStep (6912*t + 5506) = 3456*t + 2753 := by
  unfold collatzStep
  have heven : (6912*t + 5506) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_815_step_7_eq (t : Nat) :
    collatzStep (3456*t + 2753) = 10368*t + 8260 := by
  unfold collatzStep
  have hodd : (3456*t + 2753) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_815_step_8_eq (t : Nat) :
    collatzStep (10368*t + 8260) = 5184*t + 4130 := by
  unfold collatzStep
  have heven : (10368*t + 8260) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_815_step_9_eq (t : Nat) :
    collatzStep (5184*t + 4130) = 2592*t + 2065 := by
  unfold collatzStep
  have heven : (5184*t + 4130) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_815_step_10_eq (t : Nat) :
    collatzStep (2592*t + 2065) = 7776*t + 6196 := by
  unfold collatzStep
  have hodd : (2592*t + 2065) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_815_step_11_eq (t : Nat) :
    collatzStep (7776*t + 6196) = 3888*t + 3098 := by
  unfold collatzStep
  have heven : (7776*t + 6196) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_815_step_12_eq (t : Nat) :
    collatzStep (3888*t + 3098) = 1944*t + 1549 := by
  unfold collatzStep
  have heven : (3888*t + 3098) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_815_step_13_eq (t : Nat) :
    collatzStep (1944*t + 1549) = 5832*t + 4648 := by
  unfold collatzStep
  have hodd : (1944*t + 1549) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_815_step_14_eq (t : Nat) :
    collatzStep (5832*t + 4648) = 2916*t + 2324 := by
  unfold collatzStep
  have heven : (5832*t + 4648) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_815_step_15_eq (t : Nat) :
    collatzStep (2916*t + 2324) = 1458*t + 1162 := by
  unfold collatzStep
  have heven : (2916*t + 2324) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_815_step_16_eq (t : Nat) :
    collatzStep (1458*t + 1162) = 729*t + 581 := by
  unfold collatzStep
  have heven : (1458*t + 1162) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_815_iterate_eq (t : Nat) :
    iterateNat collatzStep 16 (1024*t + 815) = 729*t + 581 := by
  simp [iterateNat,
    fam_1024_815_step_1_eq,
    fam_1024_815_step_2_eq,
    fam_1024_815_step_3_eq,
    fam_1024_815_step_4_eq,
    fam_1024_815_step_5_eq,
    fam_1024_815_step_6_eq,
    fam_1024_815_step_7_eq,
    fam_1024_815_step_8_eq,
    fam_1024_815_step_9_eq,
    fam_1024_815_step_10_eq,
    fam_1024_815_step_11_eq,
    fam_1024_815_step_12_eq,
    fam_1024_815_step_13_eq,
    fam_1024_815_step_14_eq,
    fam_1024_815_step_15_eq,
    fam_1024_815_step_16_eq]

theorem fam_1024_815_descent (t : Nat) :
    ∃ k, PositiveDescentAt (1024*t + 815) k := by
  refine ⟨16, ?_, ?_⟩
  · rw [fam_1024_815_iterate_eq]
    omega
  · rw [fam_1024_815_iterate_eq]
    omega

-- 1024*t + 575 descends in 16 ordinary Collatz steps to 729*t + 410.
theorem fam_1024_575_step_1_eq (t : Nat) :
    collatzStep (1024*t + 575) = 3072*t + 1726 := by
  unfold collatzStep
  have hodd : (1024*t + 575) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_575_step_2_eq (t : Nat) :
    collatzStep (3072*t + 1726) = 1536*t + 863 := by
  unfold collatzStep
  have heven : (3072*t + 1726) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_575_step_3_eq (t : Nat) :
    collatzStep (1536*t + 863) = 4608*t + 2590 := by
  unfold collatzStep
  have hodd : (1536*t + 863) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_575_step_4_eq (t : Nat) :
    collatzStep (4608*t + 2590) = 2304*t + 1295 := by
  unfold collatzStep
  have heven : (4608*t + 2590) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_575_step_5_eq (t : Nat) :
    collatzStep (2304*t + 1295) = 6912*t + 3886 := by
  unfold collatzStep
  have hodd : (2304*t + 1295) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_575_step_6_eq (t : Nat) :
    collatzStep (6912*t + 3886) = 3456*t + 1943 := by
  unfold collatzStep
  have heven : (6912*t + 3886) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_575_step_7_eq (t : Nat) :
    collatzStep (3456*t + 1943) = 10368*t + 5830 := by
  unfold collatzStep
  have hodd : (3456*t + 1943) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_575_step_8_eq (t : Nat) :
    collatzStep (10368*t + 5830) = 5184*t + 2915 := by
  unfold collatzStep
  have heven : (10368*t + 5830) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_575_step_9_eq (t : Nat) :
    collatzStep (5184*t + 2915) = 15552*t + 8746 := by
  unfold collatzStep
  have hodd : (5184*t + 2915) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_575_step_10_eq (t : Nat) :
    collatzStep (15552*t + 8746) = 7776*t + 4373 := by
  unfold collatzStep
  have heven : (15552*t + 8746) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_575_step_11_eq (t : Nat) :
    collatzStep (7776*t + 4373) = 23328*t + 13120 := by
  unfold collatzStep
  have hodd : (7776*t + 4373) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_575_step_12_eq (t : Nat) :
    collatzStep (23328*t + 13120) = 11664*t + 6560 := by
  unfold collatzStep
  have heven : (23328*t + 13120) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_575_step_13_eq (t : Nat) :
    collatzStep (11664*t + 6560) = 5832*t + 3280 := by
  unfold collatzStep
  have heven : (11664*t + 6560) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_575_step_14_eq (t : Nat) :
    collatzStep (5832*t + 3280) = 2916*t + 1640 := by
  unfold collatzStep
  have heven : (5832*t + 3280) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_575_step_15_eq (t : Nat) :
    collatzStep (2916*t + 1640) = 1458*t + 820 := by
  unfold collatzStep
  have heven : (2916*t + 1640) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_575_step_16_eq (t : Nat) :
    collatzStep (1458*t + 820) = 729*t + 410 := by
  unfold collatzStep
  have heven : (1458*t + 820) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_575_iterate_eq (t : Nat) :
    iterateNat collatzStep 16 (1024*t + 575) = 729*t + 410 := by
  simp [iterateNat,
    fam_1024_575_step_1_eq,
    fam_1024_575_step_2_eq,
    fam_1024_575_step_3_eq,
    fam_1024_575_step_4_eq,
    fam_1024_575_step_5_eq,
    fam_1024_575_step_6_eq,
    fam_1024_575_step_7_eq,
    fam_1024_575_step_8_eq,
    fam_1024_575_step_9_eq,
    fam_1024_575_step_10_eq,
    fam_1024_575_step_11_eq,
    fam_1024_575_step_12_eq,
    fam_1024_575_step_13_eq,
    fam_1024_575_step_14_eq,
    fam_1024_575_step_15_eq,
    fam_1024_575_step_16_eq]

theorem fam_1024_575_descent (t : Nat) :
    ∃ k, PositiveDescentAt (1024*t + 575) k := by
  refine ⟨16, ?_, ?_⟩
  · rw [fam_1024_575_iterate_eq]
    omega
  · rw [fam_1024_575_iterate_eq]
    omega

-- 1024*t + 583 descends in 16 ordinary Collatz steps to 729*t + 416.
theorem fam_1024_583_step_1_eq (t : Nat) :
    collatzStep (1024*t + 583) = 3072*t + 1750 := by
  unfold collatzStep
  have hodd : (1024*t + 583) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_583_step_2_eq (t : Nat) :
    collatzStep (3072*t + 1750) = 1536*t + 875 := by
  unfold collatzStep
  have heven : (3072*t + 1750) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_583_step_3_eq (t : Nat) :
    collatzStep (1536*t + 875) = 4608*t + 2626 := by
  unfold collatzStep
  have hodd : (1536*t + 875) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_583_step_4_eq (t : Nat) :
    collatzStep (4608*t + 2626) = 2304*t + 1313 := by
  unfold collatzStep
  have heven : (4608*t + 2626) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_583_step_5_eq (t : Nat) :
    collatzStep (2304*t + 1313) = 6912*t + 3940 := by
  unfold collatzStep
  have hodd : (2304*t + 1313) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_583_step_6_eq (t : Nat) :
    collatzStep (6912*t + 3940) = 3456*t + 1970 := by
  unfold collatzStep
  have heven : (6912*t + 3940) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_583_step_7_eq (t : Nat) :
    collatzStep (3456*t + 1970) = 1728*t + 985 := by
  unfold collatzStep
  have heven : (3456*t + 1970) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_583_step_8_eq (t : Nat) :
    collatzStep (1728*t + 985) = 5184*t + 2956 := by
  unfold collatzStep
  have hodd : (1728*t + 985) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_583_step_9_eq (t : Nat) :
    collatzStep (5184*t + 2956) = 2592*t + 1478 := by
  unfold collatzStep
  have heven : (5184*t + 2956) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_583_step_10_eq (t : Nat) :
    collatzStep (2592*t + 1478) = 1296*t + 739 := by
  unfold collatzStep
  have heven : (2592*t + 1478) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_583_step_11_eq (t : Nat) :
    collatzStep (1296*t + 739) = 3888*t + 2218 := by
  unfold collatzStep
  have hodd : (1296*t + 739) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_583_step_12_eq (t : Nat) :
    collatzStep (3888*t + 2218) = 1944*t + 1109 := by
  unfold collatzStep
  have heven : (3888*t + 2218) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_583_step_13_eq (t : Nat) :
    collatzStep (1944*t + 1109) = 5832*t + 3328 := by
  unfold collatzStep
  have hodd : (1944*t + 1109) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_583_step_14_eq (t : Nat) :
    collatzStep (5832*t + 3328) = 2916*t + 1664 := by
  unfold collatzStep
  have heven : (5832*t + 3328) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_583_step_15_eq (t : Nat) :
    collatzStep (2916*t + 1664) = 1458*t + 832 := by
  unfold collatzStep
  have heven : (2916*t + 1664) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_583_step_16_eq (t : Nat) :
    collatzStep (1458*t + 832) = 729*t + 416 := by
  unfold collatzStep
  have heven : (1458*t + 832) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_583_iterate_eq (t : Nat) :
    iterateNat collatzStep 16 (1024*t + 583) = 729*t + 416 := by
  simp [iterateNat,
    fam_1024_583_step_1_eq,
    fam_1024_583_step_2_eq,
    fam_1024_583_step_3_eq,
    fam_1024_583_step_4_eq,
    fam_1024_583_step_5_eq,
    fam_1024_583_step_6_eq,
    fam_1024_583_step_7_eq,
    fam_1024_583_step_8_eq,
    fam_1024_583_step_9_eq,
    fam_1024_583_step_10_eq,
    fam_1024_583_step_11_eq,
    fam_1024_583_step_12_eq,
    fam_1024_583_step_13_eq,
    fam_1024_583_step_14_eq,
    fam_1024_583_step_15_eq,
    fam_1024_583_step_16_eq]

theorem fam_1024_583_descent (t : Nat) :
    ∃ k, PositiveDescentAt (1024*t + 583) k := by
  refine ⟨16, ?_, ?_⟩
  · rw [fam_1024_583_iterate_eq]
    omega
  · rw [fam_1024_583_iterate_eq]
    omega

-- 1024*t + 347 descends in 16 ordinary Collatz steps to 729*t + 248.
theorem fam_1024_347_step_1_eq (t : Nat) :
    collatzStep (1024*t + 347) = 3072*t + 1042 := by
  unfold collatzStep
  have hodd : (1024*t + 347) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_347_step_2_eq (t : Nat) :
    collatzStep (3072*t + 1042) = 1536*t + 521 := by
  unfold collatzStep
  have heven : (3072*t + 1042) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_347_step_3_eq (t : Nat) :
    collatzStep (1536*t + 521) = 4608*t + 1564 := by
  unfold collatzStep
  have hodd : (1536*t + 521) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_347_step_4_eq (t : Nat) :
    collatzStep (4608*t + 1564) = 2304*t + 782 := by
  unfold collatzStep
  have heven : (4608*t + 1564) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_347_step_5_eq (t : Nat) :
    collatzStep (2304*t + 782) = 1152*t + 391 := by
  unfold collatzStep
  have heven : (2304*t + 782) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_347_step_6_eq (t : Nat) :
    collatzStep (1152*t + 391) = 3456*t + 1174 := by
  unfold collatzStep
  have hodd : (1152*t + 391) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_347_step_7_eq (t : Nat) :
    collatzStep (3456*t + 1174) = 1728*t + 587 := by
  unfold collatzStep
  have heven : (3456*t + 1174) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_347_step_8_eq (t : Nat) :
    collatzStep (1728*t + 587) = 5184*t + 1762 := by
  unfold collatzStep
  have hodd : (1728*t + 587) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_347_step_9_eq (t : Nat) :
    collatzStep (5184*t + 1762) = 2592*t + 881 := by
  unfold collatzStep
  have heven : (5184*t + 1762) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_347_step_10_eq (t : Nat) :
    collatzStep (2592*t + 881) = 7776*t + 2644 := by
  unfold collatzStep
  have hodd : (2592*t + 881) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_347_step_11_eq (t : Nat) :
    collatzStep (7776*t + 2644) = 3888*t + 1322 := by
  unfold collatzStep
  have heven : (7776*t + 2644) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_347_step_12_eq (t : Nat) :
    collatzStep (3888*t + 1322) = 1944*t + 661 := by
  unfold collatzStep
  have heven : (3888*t + 1322) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_347_step_13_eq (t : Nat) :
    collatzStep (1944*t + 661) = 5832*t + 1984 := by
  unfold collatzStep
  have hodd : (1944*t + 661) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_347_step_14_eq (t : Nat) :
    collatzStep (5832*t + 1984) = 2916*t + 992 := by
  unfold collatzStep
  have heven : (5832*t + 1984) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_347_step_15_eq (t : Nat) :
    collatzStep (2916*t + 992) = 1458*t + 496 := by
  unfold collatzStep
  have heven : (2916*t + 992) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_347_step_16_eq (t : Nat) :
    collatzStep (1458*t + 496) = 729*t + 248 := by
  unfold collatzStep
  have heven : (1458*t + 496) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_347_iterate_eq (t : Nat) :
    iterateNat collatzStep 16 (1024*t + 347) = 729*t + 248 := by
  simp [iterateNat,
    fam_1024_347_step_1_eq,
    fam_1024_347_step_2_eq,
    fam_1024_347_step_3_eq,
    fam_1024_347_step_4_eq,
    fam_1024_347_step_5_eq,
    fam_1024_347_step_6_eq,
    fam_1024_347_step_7_eq,
    fam_1024_347_step_8_eq,
    fam_1024_347_step_9_eq,
    fam_1024_347_step_10_eq,
    fam_1024_347_step_11_eq,
    fam_1024_347_step_12_eq,
    fam_1024_347_step_13_eq,
    fam_1024_347_step_14_eq,
    fam_1024_347_step_15_eq,
    fam_1024_347_step_16_eq]

theorem fam_1024_347_descent (t : Nat) :
    ∃ k, PositiveDescentAt (1024*t + 347) k := by
  refine ⟨16, ?_, ?_⟩
  · rw [fam_1024_347_iterate_eq]
    omega
  · rw [fam_1024_347_iterate_eq]
    omega

-- 1024*t + 367 descends in 16 ordinary Collatz steps to 729*t + 262.
theorem fam_1024_367_step_1_eq (t : Nat) :
    collatzStep (1024*t + 367) = 3072*t + 1102 := by
  unfold collatzStep
  have hodd : (1024*t + 367) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_367_step_2_eq (t : Nat) :
    collatzStep (3072*t + 1102) = 1536*t + 551 := by
  unfold collatzStep
  have heven : (3072*t + 1102) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_367_step_3_eq (t : Nat) :
    collatzStep (1536*t + 551) = 4608*t + 1654 := by
  unfold collatzStep
  have hodd : (1536*t + 551) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_367_step_4_eq (t : Nat) :
    collatzStep (4608*t + 1654) = 2304*t + 827 := by
  unfold collatzStep
  have heven : (4608*t + 1654) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_367_step_5_eq (t : Nat) :
    collatzStep (2304*t + 827) = 6912*t + 2482 := by
  unfold collatzStep
  have hodd : (2304*t + 827) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_367_step_6_eq (t : Nat) :
    collatzStep (6912*t + 2482) = 3456*t + 1241 := by
  unfold collatzStep
  have heven : (6912*t + 2482) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_367_step_7_eq (t : Nat) :
    collatzStep (3456*t + 1241) = 10368*t + 3724 := by
  unfold collatzStep
  have hodd : (3456*t + 1241) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_367_step_8_eq (t : Nat) :
    collatzStep (10368*t + 3724) = 5184*t + 1862 := by
  unfold collatzStep
  have heven : (10368*t + 3724) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_367_step_9_eq (t : Nat) :
    collatzStep (5184*t + 1862) = 2592*t + 931 := by
  unfold collatzStep
  have heven : (5184*t + 1862) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_367_step_10_eq (t : Nat) :
    collatzStep (2592*t + 931) = 7776*t + 2794 := by
  unfold collatzStep
  have hodd : (2592*t + 931) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_367_step_11_eq (t : Nat) :
    collatzStep (7776*t + 2794) = 3888*t + 1397 := by
  unfold collatzStep
  have heven : (7776*t + 2794) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_367_step_12_eq (t : Nat) :
    collatzStep (3888*t + 1397) = 11664*t + 4192 := by
  unfold collatzStep
  have hodd : (3888*t + 1397) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_1024_367_step_13_eq (t : Nat) :
    collatzStep (11664*t + 4192) = 5832*t + 2096 := by
  unfold collatzStep
  have heven : (11664*t + 4192) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_367_step_14_eq (t : Nat) :
    collatzStep (5832*t + 2096) = 2916*t + 1048 := by
  unfold collatzStep
  have heven : (5832*t + 2096) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_367_step_15_eq (t : Nat) :
    collatzStep (2916*t + 1048) = 1458*t + 524 := by
  unfold collatzStep
  have heven : (2916*t + 1048) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_367_step_16_eq (t : Nat) :
    collatzStep (1458*t + 524) = 729*t + 262 := by
  unfold collatzStep
  have heven : (1458*t + 524) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_1024_367_iterate_eq (t : Nat) :
    iterateNat collatzStep 16 (1024*t + 367) = 729*t + 262 := by
  simp [iterateNat,
    fam_1024_367_step_1_eq,
    fam_1024_367_step_2_eq,
    fam_1024_367_step_3_eq,
    fam_1024_367_step_4_eq,
    fam_1024_367_step_5_eq,
    fam_1024_367_step_6_eq,
    fam_1024_367_step_7_eq,
    fam_1024_367_step_8_eq,
    fam_1024_367_step_9_eq,
    fam_1024_367_step_10_eq,
    fam_1024_367_step_11_eq,
    fam_1024_367_step_12_eq,
    fam_1024_367_step_13_eq,
    fam_1024_367_step_14_eq,
    fam_1024_367_step_15_eq,
    fam_1024_367_step_16_eq]

theorem fam_1024_367_descent (t : Nat) :
    ∃ k, PositiveDescentAt (1024*t + 367) k := by
  refine ⟨16, ?_, ?_⟩
  · rw [fam_1024_367_iterate_eq]
    omega
  · rw [fam_1024_367_iterate_eq]
    omega

-- 4096*t + 2587 descends in 19 ordinary Collatz steps to 2187*t + 1382.
theorem fam_4096_2587_step_1_eq (t : Nat) :
    collatzStep (4096*t + 2587) = 12288*t + 7762 := by
  unfold collatzStep
  have hodd : (4096*t + 2587) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_4096_2587_step_2_eq (t : Nat) :
    collatzStep (12288*t + 7762) = 6144*t + 3881 := by
  unfold collatzStep
  have heven : (12288*t + 7762) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_2587_step_3_eq (t : Nat) :
    collatzStep (6144*t + 3881) = 18432*t + 11644 := by
  unfold collatzStep
  have hodd : (6144*t + 3881) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_4096_2587_step_4_eq (t : Nat) :
    collatzStep (18432*t + 11644) = 9216*t + 5822 := by
  unfold collatzStep
  have heven : (18432*t + 11644) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_2587_step_5_eq (t : Nat) :
    collatzStep (9216*t + 5822) = 4608*t + 2911 := by
  unfold collatzStep
  have heven : (9216*t + 5822) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_2587_step_6_eq (t : Nat) :
    collatzStep (4608*t + 2911) = 13824*t + 8734 := by
  unfold collatzStep
  have hodd : (4608*t + 2911) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_4096_2587_step_7_eq (t : Nat) :
    collatzStep (13824*t + 8734) = 6912*t + 4367 := by
  unfold collatzStep
  have heven : (13824*t + 8734) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_2587_step_8_eq (t : Nat) :
    collatzStep (6912*t + 4367) = 20736*t + 13102 := by
  unfold collatzStep
  have hodd : (6912*t + 4367) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_4096_2587_step_9_eq (t : Nat) :
    collatzStep (20736*t + 13102) = 10368*t + 6551 := by
  unfold collatzStep
  have heven : (20736*t + 13102) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_2587_step_10_eq (t : Nat) :
    collatzStep (10368*t + 6551) = 31104*t + 19654 := by
  unfold collatzStep
  have hodd : (10368*t + 6551) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_4096_2587_step_11_eq (t : Nat) :
    collatzStep (31104*t + 19654) = 15552*t + 9827 := by
  unfold collatzStep
  have heven : (31104*t + 19654) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_2587_step_12_eq (t : Nat) :
    collatzStep (15552*t + 9827) = 46656*t + 29482 := by
  unfold collatzStep
  have hodd : (15552*t + 9827) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_4096_2587_step_13_eq (t : Nat) :
    collatzStep (46656*t + 29482) = 23328*t + 14741 := by
  unfold collatzStep
  have heven : (46656*t + 29482) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_2587_step_14_eq (t : Nat) :
    collatzStep (23328*t + 14741) = 69984*t + 44224 := by
  unfold collatzStep
  have hodd : (23328*t + 14741) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_4096_2587_step_15_eq (t : Nat) :
    collatzStep (69984*t + 44224) = 34992*t + 22112 := by
  unfold collatzStep
  have heven : (69984*t + 44224) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_2587_step_16_eq (t : Nat) :
    collatzStep (34992*t + 22112) = 17496*t + 11056 := by
  unfold collatzStep
  have heven : (34992*t + 22112) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_2587_step_17_eq (t : Nat) :
    collatzStep (17496*t + 11056) = 8748*t + 5528 := by
  unfold collatzStep
  have heven : (17496*t + 11056) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_2587_step_18_eq (t : Nat) :
    collatzStep (8748*t + 5528) = 4374*t + 2764 := by
  unfold collatzStep
  have heven : (8748*t + 5528) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_2587_step_19_eq (t : Nat) :
    collatzStep (4374*t + 2764) = 2187*t + 1382 := by
  unfold collatzStep
  have heven : (4374*t + 2764) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_2587_iterate_eq (t : Nat) :
    iterateNat collatzStep 19 (4096*t + 2587) = 2187*t + 1382 := by
  simp [iterateNat,
    fam_4096_2587_step_1_eq,
    fam_4096_2587_step_2_eq,
    fam_4096_2587_step_3_eq,
    fam_4096_2587_step_4_eq,
    fam_4096_2587_step_5_eq,
    fam_4096_2587_step_6_eq,
    fam_4096_2587_step_7_eq,
    fam_4096_2587_step_8_eq,
    fam_4096_2587_step_9_eq,
    fam_4096_2587_step_10_eq,
    fam_4096_2587_step_11_eq,
    fam_4096_2587_step_12_eq,
    fam_4096_2587_step_13_eq,
    fam_4096_2587_step_14_eq,
    fam_4096_2587_step_15_eq,
    fam_4096_2587_step_16_eq,
    fam_4096_2587_step_17_eq,
    fam_4096_2587_step_18_eq,
    fam_4096_2587_step_19_eq]

theorem fam_4096_2587_descent (t : Nat) :
    ∃ k, PositiveDescentAt (4096*t + 2587) k := by
  refine ⟨19, ?_, ?_⟩
  · rw [fam_4096_2587_iterate_eq]
    omega
  · rw [fam_4096_2587_iterate_eq]
    omega

-- 4096*t + 615 descends in 19 ordinary Collatz steps to 2187*t + 329.
theorem fam_4096_615_step_1_eq (t : Nat) :
    collatzStep (4096*t + 615) = 12288*t + 1846 := by
  unfold collatzStep
  have hodd : (4096*t + 615) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_4096_615_step_2_eq (t : Nat) :
    collatzStep (12288*t + 1846) = 6144*t + 923 := by
  unfold collatzStep
  have heven : (12288*t + 1846) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_615_step_3_eq (t : Nat) :
    collatzStep (6144*t + 923) = 18432*t + 2770 := by
  unfold collatzStep
  have hodd : (6144*t + 923) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_4096_615_step_4_eq (t : Nat) :
    collatzStep (18432*t + 2770) = 9216*t + 1385 := by
  unfold collatzStep
  have heven : (18432*t + 2770) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_615_step_5_eq (t : Nat) :
    collatzStep (9216*t + 1385) = 27648*t + 4156 := by
  unfold collatzStep
  have hodd : (9216*t + 1385) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_4096_615_step_6_eq (t : Nat) :
    collatzStep (27648*t + 4156) = 13824*t + 2078 := by
  unfold collatzStep
  have heven : (27648*t + 4156) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_615_step_7_eq (t : Nat) :
    collatzStep (13824*t + 2078) = 6912*t + 1039 := by
  unfold collatzStep
  have heven : (13824*t + 2078) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_615_step_8_eq (t : Nat) :
    collatzStep (6912*t + 1039) = 20736*t + 3118 := by
  unfold collatzStep
  have hodd : (6912*t + 1039) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_4096_615_step_9_eq (t : Nat) :
    collatzStep (20736*t + 3118) = 10368*t + 1559 := by
  unfold collatzStep
  have heven : (20736*t + 3118) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_615_step_10_eq (t : Nat) :
    collatzStep (10368*t + 1559) = 31104*t + 4678 := by
  unfold collatzStep
  have hodd : (10368*t + 1559) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_4096_615_step_11_eq (t : Nat) :
    collatzStep (31104*t + 4678) = 15552*t + 2339 := by
  unfold collatzStep
  have heven : (31104*t + 4678) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_615_step_12_eq (t : Nat) :
    collatzStep (15552*t + 2339) = 46656*t + 7018 := by
  unfold collatzStep
  have hodd : (15552*t + 2339) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_4096_615_step_13_eq (t : Nat) :
    collatzStep (46656*t + 7018) = 23328*t + 3509 := by
  unfold collatzStep
  have heven : (46656*t + 7018) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_615_step_14_eq (t : Nat) :
    collatzStep (23328*t + 3509) = 69984*t + 10528 := by
  unfold collatzStep
  have hodd : (23328*t + 3509) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_4096_615_step_15_eq (t : Nat) :
    collatzStep (69984*t + 10528) = 34992*t + 5264 := by
  unfold collatzStep
  have heven : (69984*t + 10528) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_615_step_16_eq (t : Nat) :
    collatzStep (34992*t + 5264) = 17496*t + 2632 := by
  unfold collatzStep
  have heven : (34992*t + 5264) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_615_step_17_eq (t : Nat) :
    collatzStep (17496*t + 2632) = 8748*t + 1316 := by
  unfold collatzStep
  have heven : (17496*t + 2632) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_615_step_18_eq (t : Nat) :
    collatzStep (8748*t + 1316) = 4374*t + 658 := by
  unfold collatzStep
  have heven : (8748*t + 1316) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_615_step_19_eq (t : Nat) :
    collatzStep (4374*t + 658) = 2187*t + 329 := by
  unfold collatzStep
  have heven : (4374*t + 658) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_615_iterate_eq (t : Nat) :
    iterateNat collatzStep 19 (4096*t + 615) = 2187*t + 329 := by
  simp [iterateNat,
    fam_4096_615_step_1_eq,
    fam_4096_615_step_2_eq,
    fam_4096_615_step_3_eq,
    fam_4096_615_step_4_eq,
    fam_4096_615_step_5_eq,
    fam_4096_615_step_6_eq,
    fam_4096_615_step_7_eq,
    fam_4096_615_step_8_eq,
    fam_4096_615_step_9_eq,
    fam_4096_615_step_10_eq,
    fam_4096_615_step_11_eq,
    fam_4096_615_step_12_eq,
    fam_4096_615_step_13_eq,
    fam_4096_615_step_14_eq,
    fam_4096_615_step_15_eq,
    fam_4096_615_step_16_eq,
    fam_4096_615_step_17_eq,
    fam_4096_615_step_18_eq,
    fam_4096_615_step_19_eq]

theorem fam_4096_615_descent (t : Nat) :
    ∃ k, PositiveDescentAt (4096*t + 615) k := by
  refine ⟨19, ?_, ?_⟩
  · rw [fam_4096_615_iterate_eq]
    omega
  · rw [fam_4096_615_iterate_eq]
    omega

-- 4096*t + 383 descends in 19 ordinary Collatz steps to 2187*t + 205.
theorem fam_4096_383_step_1_eq (t : Nat) :
    collatzStep (4096*t + 383) = 12288*t + 1150 := by
  unfold collatzStep
  have hodd : (4096*t + 383) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_4096_383_step_2_eq (t : Nat) :
    collatzStep (12288*t + 1150) = 6144*t + 575 := by
  unfold collatzStep
  have heven : (12288*t + 1150) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_383_step_3_eq (t : Nat) :
    collatzStep (6144*t + 575) = 18432*t + 1726 := by
  unfold collatzStep
  have hodd : (6144*t + 575) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_4096_383_step_4_eq (t : Nat) :
    collatzStep (18432*t + 1726) = 9216*t + 863 := by
  unfold collatzStep
  have heven : (18432*t + 1726) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_383_step_5_eq (t : Nat) :
    collatzStep (9216*t + 863) = 27648*t + 2590 := by
  unfold collatzStep
  have hodd : (9216*t + 863) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_4096_383_step_6_eq (t : Nat) :
    collatzStep (27648*t + 2590) = 13824*t + 1295 := by
  unfold collatzStep
  have heven : (27648*t + 2590) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_383_step_7_eq (t : Nat) :
    collatzStep (13824*t + 1295) = 41472*t + 3886 := by
  unfold collatzStep
  have hodd : (13824*t + 1295) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_4096_383_step_8_eq (t : Nat) :
    collatzStep (41472*t + 3886) = 20736*t + 1943 := by
  unfold collatzStep
  have heven : (41472*t + 3886) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_383_step_9_eq (t : Nat) :
    collatzStep (20736*t + 1943) = 62208*t + 5830 := by
  unfold collatzStep
  have hodd : (20736*t + 1943) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_4096_383_step_10_eq (t : Nat) :
    collatzStep (62208*t + 5830) = 31104*t + 2915 := by
  unfold collatzStep
  have heven : (62208*t + 5830) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_383_step_11_eq (t : Nat) :
    collatzStep (31104*t + 2915) = 93312*t + 8746 := by
  unfold collatzStep
  have hodd : (31104*t + 2915) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_4096_383_step_12_eq (t : Nat) :
    collatzStep (93312*t + 8746) = 46656*t + 4373 := by
  unfold collatzStep
  have heven : (93312*t + 8746) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_383_step_13_eq (t : Nat) :
    collatzStep (46656*t + 4373) = 139968*t + 13120 := by
  unfold collatzStep
  have hodd : (46656*t + 4373) % 2 ≠ 0 := by omega
  simp [hodd]
  omega

theorem fam_4096_383_step_14_eq (t : Nat) :
    collatzStep (139968*t + 13120) = 69984*t + 6560 := by
  unfold collatzStep
  have heven : (139968*t + 13120) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_383_step_15_eq (t : Nat) :
    collatzStep (69984*t + 6560) = 34992*t + 3280 := by
  unfold collatzStep
  have heven : (69984*t + 6560) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_383_step_16_eq (t : Nat) :
    collatzStep (34992*t + 3280) = 17496*t + 1640 := by
  unfold collatzStep
  have heven : (34992*t + 3280) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_383_step_17_eq (t : Nat) :
    collatzStep (17496*t + 1640) = 8748*t + 820 := by
  unfold collatzStep
  have heven : (17496*t + 1640) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_383_step_18_eq (t : Nat) :
    collatzStep (8748*t + 820) = 4374*t + 410 := by
  unfold collatzStep
  have heven : (8748*t + 820) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_383_step_19_eq (t : Nat) :
    collatzStep (4374*t + 410) = 2187*t + 205 := by
  unfold collatzStep
  have heven : (4374*t + 410) % 2 = 0 := by omega
  simp [heven]
  omega

theorem fam_4096_383_iterate_eq (t : Nat) :
    iterateNat collatzStep 19 (4096*t + 383) = 2187*t + 205 := by
  simp [iterateNat,
    fam_4096_383_step_1_eq,
    fam_4096_383_step_2_eq,
    fam_4096_383_step_3_eq,
    fam_4096_383_step_4_eq,
    fam_4096_383_step_5_eq,
    fam_4096_383_step_6_eq,
    fam_4096_383_step_7_eq,
    fam_4096_383_step_8_eq,
    fam_4096_383_step_9_eq,
    fam_4096_383_step_10_eq,
    fam_4096_383_step_11_eq,
    fam_4096_383_step_12_eq,
    fam_4096_383_step_13_eq,
    fam_4096_383_step_14_eq,
    fam_4096_383_step_15_eq,
    fam_4096_383_step_16_eq,
    fam_4096_383_step_17_eq,
    fam_4096_383_step_18_eq,
    fam_4096_383_step_19_eq]

theorem fam_4096_383_descent (t : Nat) :
    ∃ k, PositiveDescentAt (4096*t + 383) k := by
  refine ⟨19, ?_, ?_⟩
  · rw [fam_4096_383_iterate_eq]
    omega
  · rw [fam_4096_383_iterate_eq]
    omega
