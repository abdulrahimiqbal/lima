# Collatz Hard Proof Audit

Date: 2026-04-16

Command:

```text
.venv_test/bin/python scripts/run_collatz_hard_proof_audit.py
```

## Result

```text
verdict: architecture_only_not_full_proof
architecture_compiles_with_named_obligations: true
obligation_names_compile: true
nat_level_theorem_without_obligations_compiles: false
```

The raw Nat-level theorem currently fails with an unsolved Collatz termination goal:

```text
⊢ CollatzTerminates n
```

That is the correct failure. It means the audit did not accidentally prove Collatz from scaffold.

## What This Means

The pressure-height route has a verified proof architecture, but not yet a fully expanded proof.

The architecture composes if these obligations are supplied:

```text
no-dangerous-frontier
-> density-zero / Composite Scarcity
-> finite/base coverage
-> survivor-family elimination
-> ordinary Nat-level pullback
```

The full Nat-level theorem does not yet compile without those obligations.

## Scaffold Fields Still Present

The audit found scaffold/certificate fields in `app/service.py`:

```text
densityZero : Bool
compositeScarcity : Bool
finiteBaseCoverage : Bool
positiveDrift : Bool
exactCoverage : Bool
hiddenReachability : Bool
hiddenTermination : Bool
unprovedDensityAssumption : Bool
```

These are acceptable inside discovery waves, but they are not acceptable in a final proof.

## Actual Remaining Proof Debt

The next work is not another broad Aristotle wave. It is scaffold elimination:

```text
1. Expand density-zero / Composite Scarcity into concrete counting and scarcity predicates.
2. Prove no-dangerous-frontier implies the concrete density/scarcity closure.
3. Prove finite/base coverage as an explicit arithmetic theorem, not a Bool field.
4. Prove survivor-family elimination from concrete density plus finite/base coverage.
5. Prove the ordinary Nat-level pullback: any nonterminating Collatz orbit induces the forbidden pressure-height object.
```

## Next Action

Start with the largest unexpanded field:

```text
densityZero / CompositeScarcity
```

The next hardening step should replace those Bool fields with concrete predicates and prove one real implication from the existing pressure-height machinery.
