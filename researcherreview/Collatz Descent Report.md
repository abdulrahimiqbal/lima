# Collatz descent-route extension report

This report summarizes a computational extension of the current `lima` exit-bridge route.
It does **not** certify a full proof of the Collatz conjecture. It extracts additional explicit affine-family descent lemmas that look compatible with the repo's current Lean hardening style.

## What is already proved in the repo

From the repo docs/scripts inspected on 2026-04-16:
- The descent core is proved: if every `n > 1` has some positive iterate strictly below `n`, then Collatz termination follows by strong induction.
- Concrete parametric exit families already hardened in Lean include:
  - `2*q`
  - `4*a+1`
  - `16*c+3`
  - `32*d+11`
  - `32*d+23`
  - `128*e+7`
  - `128*e+15`
  - `128*e+59`
- The public affine rewrite compass resolves roots `39, 79, 95, 123 mod 256` and leaves `27, 31, 47, 63, 71, 91, 103, 111, 127 mod 256` unresolved.

## Search method used here

For a family `n = A*t + B` with even `A`, the parity of each step is determined by `B` as long as the coefficient stays even. So one can deterministically evolve

- `A*t + B -> (A/2)*t + B/2` when `B` is even,
- `A*t + B -> (3A)*t + (3B+1)` when `B` is odd,

until either:
1. a direct descent is reached (`A' < A` and `B' < B`), or
2. the coefficient becomes odd, at which point simple family-uniform evolution stops.

This is exactly the kind of concrete arithmetic family theorem the current repo is already promoting.

## New direct descent families found

Minimal new branch-closing families found in this pass:

- `iterateNat collatzStep 16 (1024*t + 287) = 729*t + 205`
- `iterateNat collatzStep 16 (1024*t + 815) = 729*t + 581`
- `iterateNat collatzStep 16 (1024*t + 575) = 729*t + 410`
- `iterateNat collatzStep 16 (1024*t + 583) = 729*t + 416`
- `iterateNat collatzStep 16 (1024*t + 347) = 729*t + 248`
- `iterateNat collatzStep 16 (1024*t + 367) = 729*t + 262`
- `iterateNat collatzStep 19 (4096*t + 2587) = 2187*t + 1382`
- `iterateNat collatzStep 19 (4096*t + 615) = 2187*t + 329`
- `iterateNat collatzStep 19 (4096*t + 383) = 2187*t + 205`

These are exactly the families drafted in `CollatzDescentExtension.lean`.

## What this does and does not achieve

This materially strengthens the concrete exit-bridge route, but it does **not** finish it.
A deeper recursive search on dyadic residue refinement still leaves many open branches.
At modulus `4096`, direct deterministic descent covers many more odd residues than the repo's current public inventory, but still leaves a substantial unresolved set.

Counts from this pass:
- odd residues `> 1` modulo `4096`: `2047`
- directly descending odd residues modulo `4096` found by deterministic affine evolution: `1821`
- unresolved odd residues modulo `4096` under this direct criterion: `226`

So the strengthened route is real progress, but not yet a universal descent theorem.

## Practical next step

Use `CollatzDescentExtension.lean` to promote the nine new concrete families first.
After that, rerun the affine compass with the new rules included. If the unresolved frontier shrinks to a self-similar core, the next object to prove is still the same one the repo already suspects:

> a well-founded affine-family rewrite theorem

rather than just a longer ad hoc list of residue lemmas.
