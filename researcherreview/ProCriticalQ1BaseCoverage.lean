import Std

open Std

set_option maxRecDepth 1000000

def collatzStep (n : Nat) : Nat :=
  if n % 2 = 0 then n / 2 else 3 * n + 1

def iterateNat (f : Nat → Nat) : Nat → Nat → Nat
  | 0, n => n
  | k + 1, n => iterateNat f k (f n)

def kernelBound : Nat := 256

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
