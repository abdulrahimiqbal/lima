# Collatz Refinement Partition Audit

Date: 2026-04-16

Command:

```text
.venv_test/bin/python scripts/run_collatz_refinement_partition_audit.py
```

## What This Is

This is a theorem-level Lean audit for the missing refinement bridge.

It does not prove Collatz. It proves the generic closure mechanism we need if we want
to turn a dyadic refinement tree into a proof.

## New Lean-Clean Theorems

The audit proves:

```text
If both one-bit children of an affine family descend, then the parent family descends.

If all 2^m dyadic children of an affine family descend, then the parent family descends.
```

Here a family means:

```text
n = a*t + b
```

and child closure is over the standard dyadic split of the parameter `t`.

## Why This Matters

This is the first general proof theorem on the route from finite branch data to a
universal statement.

Before this, we only had:

```text
many concrete exit lemmas
```

Now we also have:

```text
a theorem saying how those child lemmas would combine into a parent theorem
```

## Concrete Instantiations

The audit also proves the exact compression shape for current hard parents:

```text
if all 16 mod-4096 children of 256*t+31 descend, then 256*t+31 descends
if all 16 mod-4096 children of 256*t+27 descend, then 256*t+27 descends
```

So the remaining proof target is no longer vague.

## Main Lesson

The open problem now has a clean form:

```text
prove enough child-closure facts, or prove a well-founded measure on unresolved children,
so that the partition theorem can be applied recursively.
```
