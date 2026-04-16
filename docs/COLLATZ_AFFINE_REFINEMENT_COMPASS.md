# Collatz Affine Refinement Compass

Date: 2026-04-16

Command:

```text
.venv_test/bin/python scripts/run_collatz_affine_refinement_compass.py
```

## What This Is

This is a search compass, not a proof artifact.

It starts from the unresolved parent roots

```text
27, 31, 47, 63, 71, 91, 103, 111, 127 mod 256
```

and repeatedly refines them into dyadic child families:

```text
256*t+b -> 512*u+(b or b+256) -> ...
```

Each child is then tested against the current theorem-backed affine rewrite rules.

The proof-side partner of this file is now:

```text
docs/COLLATZ_REFINEMENT_PARTITION_AUDIT.md
```

## Core Signal

The new 1024 and 4096 theorems do not close parent roots directly.
They close refined children.

That means the real proof object is not:

```text
one rewrite path per parent family
```

but:

```text
a branching dyadic refinement tree with rewrite closure at the leaves
```

## Parent Archetypes

The current parent roots split into two visible profile clusters:

```text
parents 31, 47, 63, 71, 91, 111:
1/4 -> 6/16 -> 17/32 -> 34/64 children resolved

parents 27, 103, 127:
0/4 -> 1/16 -> 6/32 -> 12/64 children resolved
```

Those counts are for moduli:

```text
1024 -> 4096 -> 8192 -> 16384
```

So the unresolved frontier is not random noise. It already shows a small number of
repeating refinement archetypes.

## Global Resolution Fractions

Under the current theorem-backed rule inventory, the refinement compass resolves:

```text
1821 / 2047 odd roots modulo 4096
3728 / 4095 odd roots modulo 8192
7457 / 8191 odd roots modulo 16384
```

So deeper refinement does help, but it does not yet close everything.

## Transition Compression

A stronger search view now clusters unresolved states by their next four levels of
resolved/unresolved child counts.

Across moduli:

```text
4096
8192
16384
```

the current unresolved tree compresses into only eight local profile classes.

Examples:

```text
S1 = (0,2) -> (0,4) -> (0,8) -> (0,16)
S4 = (0,2) -> (0,4) -> (1,7) -> (3,11)
S7 = (1,1) -> (0,2) -> (1,3) -> (2,4)
```

and the transitions are structured rather than chaotic, for example:

```text
at modulus 4096:
S4 -> {S3, S6}
S7 -> {S6}
S2 -> {S1, S3}
S1 -> {S1, S1}

at modulus 8192:
S3 -> {S2, S5}
S6 -> {S5, S8}
S1 -> {S1, S2} or {S1, S1}
```

This is still only search signal, but it is closer to a finite automaton than to a
random residue explosion.

## What This Means

This is the clearest current statement of the missing theorem:

```text
prove that repeated dyadic refinement plus affine rewrite
is well-founded and eventually closes every branch
```

Without that theorem, we are still doing finite branch hardening.

## Next Step

Promote this from a compass to a theorem target:

1. define the refinement operator formally
2. define what it means for a parent family to be closed by its children
3. replace the profile compass by a real finite-state closure or decreasing measure theorem
