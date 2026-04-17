# Collatz Kernel Refinement Audit

Date: 2026-04-17

## What This Adds

This audit does not prove new Collatz descent theorems.

It records a new search-only structural signal:

```text
the unresolved kernel keeps compressing under deeper lift-signature audits
instead of exploding arbitrarily
```

That matters because the current endgame thesis is now:

```text
the remaining odd obstruction is a finite binary refinement kernel,
not a grab-bag of unrelated residue lemmas
```

## Current Exact Theorem-Level Base

Already hardened locally in Lean:

```text
13-root mod-128 frontier split
-> 9-parent mod-256 frontier

mod-128 frontier
-> exact factorization into one or two open mod-256 children

mod-256 frontier
-> exact factorization into two open mod-512 children
```

Those results live in:

```text
scripts/run_collatz_frontier_split_hardening.py
scripts/run_collatz_frontier_child_reduction_hardening.py
scripts/run_collatz_frontier128_factorization_hardening.py
scripts/run_collatz_frontier256_factorization_hardening.py
scripts/run_collatz_pro_kernel_audit.py
```

## New Search-Only Signal

The new audit script is:

```text
scripts/run_collatz_kernel_refinement_audit.py
```

It should be read carefully.
It is a lift-signature audit, not an exact theorem about dyadic child closure.

It clusters the already-open residue sets by how many larger lifted families
are resolved by the current composed rewrite search.

### Open Mod-256 Residues

The open mod-256 set:

```text
27, 31, 47, 63, 71, 91, 103, 111, 127,
155, 159, 167, 191, 207, 223, 231, 239, 251, 255
```

compresses into exactly 3 lift-signature classes:

```text
S1 = {127, 159, 239, 255}
     resolved signature   = [0, 0, 0, 1]
     unresolved signature = [2, 4, 8, 15]

S2 = {27, 31, 47, 91, 103, 111, 155, 167, 191, 207, 231, 251}
     resolved signature   = [0, 0, 1, 5]
     unresolved signature = [2, 4, 7, 11]

S3 = {63, 71, 223}
     resolved signature   = [1, 2, 5, 12]
     unresolved signature = [1, 2, 3, 4]
```

### Open Mod-512 Residues

The open mod-512 set compresses into exactly 4 lift-signature classes:

```text
S1 = {159, 239, 447, 511}
     resolved signature   = [0, 0, 0, 0]

S2 = {27, 31, 91, 103, 111, 127, 167, 251, 255, 283, 319, 327, 359, 415, 479, 495}
     resolved signature   = [0, 0, 1, 2]

S3 = {47, 63, 71, 155, 191, 207, 223, 231, 303, 383, 411, 463, 487}
     resolved signature   = [0, 1, 4, 8]

S4 = {287, 347, 367, 423, 507}
     resolved signature   = [2, 4, 8, 16]
```

## Interpretation

The key point is not the exact numbers by themselves.

The key point is:

```text
one deeper layer still compresses to a tiny finite list of coarse state types
```

This is not a proof.
It does not justify claiming exact finite closure.

But it is the strongest current evidence that the remaining kernel may admit a
finite-state exactness/drift theorem rather than requiring unbounded residue
enumeration.

## Caution

This audit must not be over-read.

It does not prove:

```text
all children of each state close
any state is well-founded
the SCC kernel route is complete
```

It only says:

```text
the open residue sets still appear to organize into a very small number of
repeating lift-signature classes
```

That is enough to justify pushing the finite-kernel route harder.
