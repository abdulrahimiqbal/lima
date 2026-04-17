# Collatz Frontier-128 Split Hardening

Date: 2026-04-16

Command:

```text
.venv_test/bin/python scripts/run_collatz_frontier128_split_hardening.py
```

## What This Is

This is a theorem-level hardening of the current odd frontier split.

Before this audit, the reduction

```text
13 unresolved mod-128 residues
-> 9 true parent roots mod 256
```

was only a search-compass fact.

Now the four reducible roots are promoted into concrete Lean-clean descent families.

## New Lean-Clean Families

The audit proves:

```text
256*t + 39  -> 243*t + 38   in 13 steps
256*t + 79  -> 243*t + 76   in 13 steps
256*t + 95  -> 243*t + 91   in 13 steps
256*t + 123 -> 243*t + 118  in 13 steps
```

Each case is checked as an explicit `iterateNat collatzStep` theorem, not as a
search certificate.

## Immediate Consequence

The old direct odd frontier

```text
27, 31, 39, 47, 63, 71, 79, 91, 95, 103, 111, 123, 127 mod 128
```

now becomes the true theorem-level parent frontier

```text
27, 31, 47, 63, 71, 91, 103, 111, 127 mod 256
```

That is the frontier we should now treat as live proof debt.

## Kernel Consequence

Combined with the persistence audit, the remaining 9 parent roots group as:

```text
A = {27, 31, 63, 103, 111}
B = {47, 71, 91}
C = {127}
```

So the direct unresolved kernel is no longer:

```text
13 unresolved residues
```

and not even:

```text
9 unrelated parent roots
```

It is now:

```text
three parent archetypes over nine true parent roots
```

## Why This Matters

This is the first time the kernel route has a theorem-level split rather than only
a search-guided split.

That makes the next theorem target more honest:

```text
exclude infinite unresolved branches for archetypes A, B, and C,
or make the pressure-height spine kill those three archetypes concretely
```
