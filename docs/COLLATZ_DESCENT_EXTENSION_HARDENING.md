# Collatz Descent Extension Hardening

Date: 2026-04-16

Command:

```text
.venv_test/bin/python scripts/run_collatz_descent_extension_hardening.py
```

## What This Is

This is a repo-native Lean audit of the researcher extension batch in

```text
researcherreview/Collatz Conjecture Extension.lean
```

The repo does not rely on the raw draft file compiling as one monolith.
Instead, it regenerates each concrete affine family proof as a standalone Lean
check and verifies them individually.

## New Lean-Clean Families

All nine cases compile:

```text
1024*t + 287  -> 729*t + 205   in 16 steps
1024*t + 815  -> 729*t + 581   in 16 steps
1024*t + 575  -> 729*t + 410   in 16 steps
1024*t + 583  -> 729*t + 416   in 16 steps
1024*t + 347  -> 729*t + 248   in 16 steps
1024*t + 367  -> 729*t + 262   in 16 steps
4096*t + 2587 -> 2187*t + 1382 in 19 steps
4096*t + 615  -> 2187*t + 329  in 19 steps
4096*t + 383  -> 2187*t + 205  in 19 steps
```

These become generic rewrite rules of the form:

```text
a ≡ 0 mod M and b ≡ r mod M
=> a*t+b rewrites to a strictly smaller affine family
```

with:

```text
M = 1024 or 4096
```

## Why This Matters

Each new rule closes a refined child of one current unresolved parent root:

```text
27 mod 256  <- 4096*t + 2587
31 mod 256  <- 1024*t + 287
47 mod 256  <- 1024*t + 815
63 mod 256  <- 1024*t + 575
71 mod 256  <- 1024*t + 583
91 mod 256  <- 1024*t + 347
103 mod 256 <- 4096*t + 615
111 mod 256 <- 1024*t + 367
127 mod 256 <- 4096*t + 383
```

That is genuine progress, but it does not yet close the parent roots themselves.

## Main Lesson

These new theorems strengthen the proof route only after residue refinement.
So the missing object is now clearer:

```text
not just a longer affine rewrite list,
but a well-founded dyadic refinement + affine rewrite theorem
```

## Next Use

1. Add these nine rules to the affine rewrite compass.
2. Measure which parent roots remain unresolved at the root level.
3. Study the refinement tree of those parents instead of treating them as single paths.
