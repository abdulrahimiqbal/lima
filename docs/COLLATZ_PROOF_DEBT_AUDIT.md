# Collatz Proof-Debt Audit

Date: 2026-04-16

## What This Audit Is

This is the current endgame audit.

It answers one question:

```text
what exact theorem debt remains between the current repo state and a real Collatz proof?
```

## Current Verified Base

The repo now has three different kinds of verified progress:

```text
1. pressure-height architecture
2. descent core over Nat
3. concrete arithmetic descent families
```

Pressure-height architecture:

```text
The final-closure tranche reconciles as 13 / 13 Lean-clean artifact bundles.

That means the pressure-height route has a verified proof spine:

actual SCC exactness + positive SCC drift
-> pressure-height invariant
-> no dangerous frontier
-> density/scarcity closure
-> no survivor family
-> ordinary pullback target
```

Descent core over Nat:

```text
If for every n > 1 there exists k with
0 < collatz^[k](n) < n,
then ordinary Collatz termination follows by strong induction.
```

Concrete arithmetic descent families:

```text
even n
n ≡ 1 mod 4, n > 1
n ≡ 3 mod 16
n ≡ 11 or 23 mod 32
n ≡ 7, 15, or 59 mod 128
n ≡ 287, 347, 367, 575, 583, or 815 mod 1024
n ≡ 383, 615, or 2587 mod 4096
```

General refinement theorem:

```text
if all dyadic children of an affine family descend,
then the parent family descends
```

## What Is Still Missing

The repo does not yet prove Collatz because the following are still open:

```text
1. universal eventual positive descent below n
2. full elimination of scaffold-only pressure-height certificate fields
3. a concrete Nat-level theorem making the pressure-height closure objects true
   for actual Collatz arithmetic
4. closure of the remaining unresolved affine/refinement frontier
```

Equivalent compressed target:

```text
for every n > 1, prove there exists k such that
0 < collatz^[k](n) < n
```

Everything else is now downstream of that target.

## The Two Serious Endgames

There are no longer many plausible endgames in this repo.
There are still two visible theorem families, but the best current finish now
looks like a hybrid of them.

### Route A. Direct Descent / Refinement Closure

Current frontier:

```text
direct-family theorem frontier:
27, 31, 39, 47, 63, 71, 79, 91, 95, 103, 111, 123, 127 mod 128

single-family rewrite frontier:
27, 31, 47, 63, 71, 91, 103, 111, 127 mod 256
```

What is already known:

```text
39, 79, 95, and 123 have composed rewrite certificates
the remaining nine mod-256 parents are packaged as explicit parent-closure obligations
the unresolved refinement tree compresses into a small number of profile classes
simple local child-count measures do not close the tree
```

Most likely missing theorem on this route:

```text
a well-founded dyadic refinement + affine rewrite closure theorem
```

That theorem would say, in substance:

```text
repeated refinement plus theorem-backed rewrite cannot continue forever on an unresolved branch,
so every branch eventually hits a proved descent family
```

If that theorem lands, the partition theorem plus the descent core should finish the proof.

Newest sharpening from the refinement signature audit:

```text
finite-horizon exact resolved/unresolved tree shape is still too weak;
the recurrent core survives as one large signature component.

But that recurrent core projects exactly back to the same 13 unresolved residue cylinders
mod 128.

So the direct-route missing object is now better read as a cylinder exclusion theorem:
for each of those 13 mod-128 cylinders, there is no infinite unresolved refinement branch.

Pushing the cylinders deeper strengthens this:

```text
all 13 cylinders persist through modulus 65536,
but they collapse into exactly three shared growth archetypes:

A = {27, 31, 63, 103, 111}
B = {39, 47, 71, 79, 91, 95, 123}
C = {127}
```

So the likely missing theorem is smaller than "13 unrelated residue cases":
it may be three cylinder-archetype exclusion theorems.
```

### Route B. Pressure-Height Scaffold Elimination

Current verified status:

```text
the pressure-height route has a verified proof architecture
the raw Nat-level theorem without obligations still fails exactly where it should
the remaining fields are named and known
```

Named remaining obligations:

```text
no-dangerous-frontier
-> concrete density/scarcity closure
-> finite/base coverage
-> survivor-family elimination
-> ordinary Nat-level pullback
```

Most likely missing theorem on this route:

```text
a concrete arithmetic theorem showing that actual Collatz dynamics force the
pressure-height exit / closure objects, not just their certificate architecture
```

If that theorem family lands, the pressure-height route can also feed the same descent core.

## What We Have Learned From SOLVED.md

The answer is probably not already present as a finished theorem.
But the file does already encode the main convergence pattern:

```text
the real target is eventual descent below n
the architecture route is real but still conditional
the direct arithmetic route has a finite unresolved frontier
the missing object keeps reappearing as refinement + rewrite closure,
then sharper as a finite obstruction kernel / residue-cylinder problem,
or as a concrete Nat-level realization of the pressure-height exits
```

So the repo is no longer missing a vague "idea."
It is missing one of two explicit theorem families.

## Updated Roadmap To Collatz

The shortest honest roadmap from here is:

```text
1. keep the descent core fixed as the final compression target
2. use the direct arithmetic frontier to define the true finite unresolved kernel
3. use pressure-height scaffold elimination as the global engine on that kernel
4. force every new Aristotle probe to discriminate between those two routes
5. stop broad invention; only attack named remaining obligations
```

In theorem form:

```text
Phase 1: preserve the proved base
- descent core
- concrete exit families
- parent-closure theorem
- pressure-height endgame architecture

Phase 2: close one of the two remaining bridges
- either prove the well-founded refinement + rewrite theorem
- or prove the concrete Nat-level pressure-height pullback/exit theorem

Phase 3: derive universal eventual descent
for every n > 1, ∃ k, 0 < collatz^[k](n) < n

Phase 4: apply the descent core
universal eventual descent -> Collatz termination
```

## What Aristotle Should Be Used For Now

Aristotle should not be used as a broad exploration engine anymore.

Good probes now:

```text
- one parent-closure family with only a small recurrent unresolved child pattern left
- one concrete scaffold-elimination theorem replacing a Bool/certificate field
- one anti-smuggling probe that rejects a fake version of the exact theorem we want
```

Bad probes now:

```text
- another architecture-only wave
- another Boolean report-state theorem
- another broad invention or vocabulary mutation wave
```

## Decision Rule

The next theorem wave is productive only if it does one of these:

```text
1. closes one unresolved parent family
2. names one recurrent unresolved child pattern as the exact missing theorem
3. replaces one scaffold field with a concrete arithmetic theorem
4. kills one whole candidate invariant class cleanly
```

If a wave does not do one of those, it is noise.

## Current Best Bet

The current best bet is:

```text
primary:
finite-state kernel compression of the remaining odd frontier, followed by
pressure-height scaffold hardening on that kernel

The newest direct-route reading of that kernel is:
13 unresolved residue cylinders mod 128,
compressed further into three persistence archetypes A/B/C,
together with an infinite-branch exclusion theorem.

secondary:
standalone well-founded dyadic refinement + affine rewrite closure
```

Why this ordering:

```text
the direct arithmetic route has already shrunk the remaining frontier to a small
named parent set
the pressure-height route already has the stronger global proof spine
the transition compass suggests the unresolved tree may admit finite-state
compression rather than an open-ended new rank
one finite obstruction kernel would let exactness and drift become finite exact
theorems instead of all-depth family debt
```

## Bottom Line

The repo is not "almost magically solved."
But it is also not wandering.

The remaining unknown has compressed to:

```text
either a standalone refinement/rewrite well-foundedness theorem
or a finite exact obstruction kernel that lets the pressure-height bridge
become fully concrete
```

If either of those lands, the descent core turns it into a genuine Collatz proof path.
