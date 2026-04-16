# Collatz Descent Core Audit

Date: 2026-04-16

Command:

```text
.venv_test/bin/python scripts/run_collatz_descent_core_audit.py
```

## Result

```text
verdict: descent_core_extracted
descent_core_compiles: true
exit_bridge_compression_compiles: true
raw_no_dangerous_to_descent_compiles: false
```

## What We Proved Now

The audit proves the clean induction core:

```text
eventual positive descent below n
-> ordinary Collatz termination
```

In theorem shape:

```text
If for every n > 1 there is some k such that

0 < collatz^[k](n) < n,

then every positive n eventually reaches 1.
```

This is the right compression target because it avoids the density-zero trap. Density-zero alone only says the bad set is sparse; eventual descent says every n reduces to a smaller already-handled case.

## What The Pressure-Height Route Must Supply

The route would imply Collatz if it supplies these two bridge facts:

```text
NoDangerousFrontier
-> for every n > 1, there exists a pressure-height exit for n

PressureHeightExit n k
-> 0 < collatz^[k](n) < n
```

Equivalently, the single compressed target is:

```text
For every n > 1, no-dangerous-frontier must produce a positive iterate below n.
```

## The Raw Bridge Fails, As It Should

The audit intentionally tried to prove:

```text
NoDangerousFrontier -> eventual positive descent
```

without the exit-existence and exit-soundness bridge.

Lean failed with:

```text
⊢ ∃ k, 0 < iterateNat collatzStep k n ∧ iterateNat collatzStep k n < n
```

That is the real remaining gap. This is much sharper than the previous scaffold audit.

## Remaining Bridges

The remaining pressure-height bridges are:

```text
1. Every ordinary n > 1 induces the relevant pressure-height frontier/object.
2. No dangerous frontier forces a pressure-height exit for that object.
3. Every such exit is sound as an actual Nat-level descent below n.
```

## Decision

The next work should not be another architecture wave.

It should be a concrete exit bridge hardening:

```text
define PressureHeightExit n k
prove no-dangerous-frontier gives such an exit
prove the exit gives 0 < collatz^[k](n) < n
```

If this succeeds, the descent core turns it into ordinary Collatz termination by strong induction.
