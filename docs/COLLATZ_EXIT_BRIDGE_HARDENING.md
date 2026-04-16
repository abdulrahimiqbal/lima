# Collatz Exit Bridge Hardening

Date: 2026-04-16

Command:

```text
.venv_test/bin/python scripts/run_collatz_exit_bridge_hardening.py
```

## Result

```text
verdict: first_concrete_exit_bridge_hardened
concrete_exit_cases_compile: true
raw_odd_three_mod_four_family_compiles: false
```

## Concrete Lean Facts Proved

The first concrete exit families are now arithmetic Lean theorems:

```text
Every positive even number 2*q descends in one Collatz step.
Every number 4*a+1 with a>0 descends in three Collatz steps.
Every number 16*c+3 descends in six Collatz steps.
Every number 32*d+11 descends in eight Collatz steps.
Every number 32*d+23 descends in eight Collatz steps.
The covered concrete exit families imply actual Nat-level positive descent.
The specific 3 and 7 cases have explicit descent witnesses.
n=7 is not covered by the current parametric exit families.
```

These are not Bool certificate fields. They are concrete statements about `iterateNat collatzStep`.

The new `16*c+3` theorem is the first direct bite into the previously uncovered
`4*a+3` family:

```text
iterateNat collatzStep 6 (16*c+3) = 9*c+2
9*c+2 < 16*c+3
```

Two more subfamilies close after the next parity split:

```text
iterateNat collatzStep 8 (32*d+11) = 27*d+10
27*d+10 < 32*d+11

iterateNat collatzStep 8 (32*d+23) = 27*d+20
27*d+20 < 32*d+23
```

## Remaining Gap

The raw parametric theorem for the full odd `3 mod 4` family still fails:

```text
theorem odd_three_mod_four_family_descent_raw (a : Nat) :
    ∃ k, PositiveDescentAt (4*a+3) k
```

Lean leaves the expected unsolved goal:

```text
⊢ PositiveDescentAt (4 * a + 3) 0
```

The attempted witness `0` is intentionally wrong; the important fact is that the family has not been solved by the first concrete exits.

After proving the `16*c+3`, `32*d+11`, and `32*d+23` subfamilies, the first unresolved odd residues are:

```text
n ≡ 7, 15, 27, or 31 mod 32
```

## Why This Matters

The descent core reduced the full Collatz route to:

```text
∀ n > 1, ∃ k, 0 < collatz^[k](n) < n
```

The first concrete exits cover:

```text
even n
odd n ≡ 1 mod 4, n > 1
odd n ≡ 3 mod 16
odd n ≡ 11 or 23 mod 32
```

The remaining parametric obstruction is narrower than before:

```text
odd n ≡ 7, 15, 27, or 31 mod 32
```

That is where the pressure-height machinery must become real arithmetic: repeated parity-block or valuation reasoning must produce a later descent.

## Next Target

Attack the remaining `7/15/27/31 mod 32` families directly.

Candidate routes:

```text
1. Split 32*d+7, 32*d+15, 32*d+27, and 32*d+31 by the next parity/valuation block.
2. Prove the next parametric descent family if one closes arithmetically.
3. If a family expands instead of descending, extract the recurring affine map.
4. Prove that the recurring affine map has a well-founded pressure-height decrease, or identify the exact missing theorem.
```
