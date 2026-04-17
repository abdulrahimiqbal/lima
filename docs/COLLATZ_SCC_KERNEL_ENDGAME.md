# Collatz SCC-Kernel Endgame

Date: 2026-04-16

## What This Memo Adds

This memo records the strongest current hybrid endgame visible in the repo:

```text
keep the existing pressure-height proof spine as the global engine,
but compress the remaining odd arithmetic frontier into one finite exact
obstruction kernel
```

This is not a new world family.
It is a proof-hardening agenda over the objects already named in:

```text
docs/COLLATZ_PROOF_DEBT_AUDIT.md
docs/COLLATZ_ROADMAP.md
SOLVED.md
```

## Why A Kernel Object Is Plausible

The repo already has three signals that point in the same direction:

```text
1. the pressure-height route is much farther along than a fresh rank route
2. the direct odd frontier has already shrunk to 13 mod-128 residues,
   then to 9 parent roots mod 256 after composed rewrites
3. the unresolved refinement tree appears to compress into a small number
   of recurrent local profile classes rather than exploding arbitrarily
```

So the missing object no longer looks like:

```text
"invent a brand new global invariant"
```

It looks more like:

```text
"build one finite quotient of the actual unresolved return dynamics, then
 prove exactness and positive drift on that finite object"
```

## New Sharpening

The kernel picture is now tighter than it was when this memo started.

Two separate repo artifacts line up:

```text
1. theorem-backed mod-128 child-reduction hardening
2. search-backed mod-256 refinement-signature clustering
```

The theorem side now shows:

```text
39 mod 128 reduces to the open child 167 mod 256
47 mod 128 reduces to the open child  47 mod 256
71 mod 128 reduces to the open child  71 mod 256
79 mod 128 reduces to the open child 207 mod 256
91 mod 128 reduces to the open child  91 mod 256
95 mod 128 reduces to the open child 223 mod 256
123 mod 128 reduces to the open child 251 mod 256
```

The signature audit now shows that every one of those open-child targets has the
same K2 refinement signature:

```text
resolved counts   = [1, 6, 17, 34]
unresolved counts = [3, 10, 15, 30]
```

So the live odd frontier is now best read as:

```text
K1 = {27, 103, 127}
K2 = {31, 47, 63, 71, 91, 111}

and every theorem-backed mod-128 reduction target from
39, 47, 71, 79, 91, 95, 123
lands inside K2 rather than creating a third coarse class
```

That does not prove the kernel route.
But it does say the frontier compression is stronger than "9 parents" or
"13 cylinders": the actual finite obstruction quotient still looks 2-class at
the coarse signature level.

The newest theorem-level factorization hardenings support the same read:

```text
mod 128 frontier
-> exact factorization into one or two open mod-256 children

mod 256 frontier
-> exact factorization into two open mod-512 children
```

So the repo is no longer guessing that the last object is a binary refinement
kernel. The local Lean artifacts now package the unresolved frontier in that
shape explicitly.

## New Concept

### `SCCKernel`

`SCCKernel` is the one new object this route introduces.

Informally:

```text
a finite quotient of the actual pressure-height states reachable from the
remaining unresolved odd frontier
```

The quotient should remember exactly the data that the repo still needs:

```text
- recurrent unresolved-return successor pattern
- enough dyadic refinement / affine rewrite information to close the
  mod-256 frontier exactly
- lower drift / height data on recurrent returns
```

Lean-facing fields should stay concrete and small:

```text
State
classOf
succ
driftLB
bound
```

The point is not elegance.
The point is to turn the last infinite theorem debt into a finite theorem family.

## Most Plausible Architecture

The best finish visible in the repo is now:

```text
hybrid dominated by scaffold-hardening
```

That means:

```text
1. keep the pressure-height spine:
   SCC exactness + SCC drift
   -> no dangerous frontier
   -> density/scarcity closure
   -> ordinary pullback

2. harden the unresolved odd frontier first:
   13 mod-128 residues
   -> 9 parent roots mod 256
   -> finite SCCKernel

3. state the final bridges directly over explicit kernel predicates,
   not over scaffold-only certificate fields
```

This differs slightly from the earlier roadmap language that treated
refinement closure and pressure-height hardening as two separate endgames.
The current evidence supports a hybrid:

```text
use the odd frontier to define the finite kernel,
then use the pressure-height architecture to kill recurrence on that kernel
```

## Theorem Agenda

### T1. `frontier128_split_or_descend`

Role:

```text
family elimination
```

Target:

```text
turn the current 13 mod-128 frontier into the exact 9 parent roots mod 256
by proving that 39, 79, 95, and 123 already descend by composed family rules
```

Why it matters:

```text
the kernel should be built over the true parent frontier, not over a noisier
search frontier
```

### T2. `frontier256_factors_through_sccKernel`

Role:

```text
finite obstruction compression
```

Target:

```text
prove that all unresolved dynamics generated by the 9 mod-256 parent roots
factor through a finite SCCKernel
```

Why it matters:

```text
this is the exact step that converts an infinite frontier into a finite
proof agenda
```

### T3. `sccKernel_exact_coverage`

Role:

```text
exactness on the finite obstruction object
```

Target:

```text
prove that the kernel has exact recurrent coverage, so no hidden SCC family
survives outside the quotient
```

### T4. `sccKernel_positive_drift`

Role:

```text
drift control on the finite obstruction object
```

Target:

```text
prove that every recurrent bad SCC represented in the kernel has strictly
positive drift / height escape
```

Why T3 and T4 are the decisive pair:

```text
the repo already identifies exactness and positive drift as the live bottleneck
after the actual-generator bridge
```

### T5. `explicit_kernel_control_implies_no_dangerous_frontier`

Role:

```text
Nat-level bridge hardening
```

Target:

```text
replace theorem-shape certificate fields with explicit hypotheses:
kernel coverage + kernel exactness + kernel positive drift
-> no dangerous frontier
```

### T6. `no_dangerous_frontier_implies_density_zero_closure`

Role:

```text
pressure-height closure hardening
```

Target:

```text
derive density-zero / Composite Scarcity directly from no-dangerous-frontier
without leaving scaffold-only density fields in the theorem statement
```

### T7. `kernel_bound_has_finite_base_coverage`

Role:

```text
finite/base coverage
```

Target:

```text
prove explicit descent for all n below the concrete bound induced by the kernel
```

Why this base theorem should be kernel-relative:

```text
once the remaining obstruction has been compressed to a finite kernel, the
natural finite check is "below the kernel bound", not an unrelated small-n list
```

### T8. `pressure_height_scaffold_eliminates`

Role:

```text
anti-circularity audit
```

Target:

```text
show that the remaining scaffold object is equivalent to explicit kernel
predicates plus explicit finite/base coverage
```

This is not strictly needed for the shortest logical route if T5, T6, and T9
are already certificate-free, but it is the cleanest audit theorem in the repo.

### T9. `density_zero_closure_pullback_gives_eventual_descent`

Role:

```text
induction pullback
```

Target:

```text
combine concrete density/scarcity closure with explicit finite/base coverage to
prove:
for every n > 1, there exists k with 0 < collatz^[k](n) < n
```

Why this closes the proof:

```text
the repo already treats universal eventual descent below n as the strong-
induction bridge to full Collatz termination
```

## Minimal Winning Set

The shortest plausible proof-closing subset is:

```text
T1, T2, T3, T4, T5, T6, T7, T9
```

`T8` is still highly desirable because it audits away hidden scaffold debt, but
the logical closure route can already be written without it if the bridge
theorems are stated directly over explicit kernel predicates.

## Recommended Aristotle Order

If Aristotle bandwidth is scarce, the first five runs should be:

```text
1. T2 frontier256_factors_through_sccKernel
2. T3 sccKernel_exact_coverage
3. T4 sccKernel_positive_drift
4. T5 explicit_kernel_control_implies_no_dangerous_frontier
5. T1 frontier128_split_or_descend
```

That order reflects the current bottleneck:

```text
first force the finite object into existence,
then prove its two decisive properties,
then verify that those properties really drive the global bridge,
then clean up the arithmetic frontier if needed
```

## Relationship To Existing Repo Claims

This memo does not claim that Collatz is already proved.

Current honest status:

```text
the pressure-height spine is theorem-shaped and coherent
the direct odd frontier is finite and named
the remaining proof debt still sits exactly at finite compression,
scaffold elimination, density closure, finite/base coverage, and Nat pullback
```

What this memo changes is only the strategic compression:

```text
the most credible finish is no longer
"either direct refinement closure or pressure-height hardening"

it is
"use direct refinement data to define a finite obstruction kernel, then
 complete the pressure-height route on that kernel"
```

## Bottom Line

If the repo proves this agenda in Lean, then it has a formal Collatz proof route:

```text
finite kernel control
-> no dangerous frontier
-> concrete density/scarcity closure
-> universal eventual descent below n
-> Collatz termination by the already proved descent core
```

The remaining unknown is not vague anymore.
It is whether the unresolved odd frontier really factors through a finite exact
kernel with the right drift and closure properties.
