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
n ≡ 287, 347, 367, 423, 507, 575, 583, 735, 815, 923, 975, or 999 mod 1024
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
39, 79, 95, and 123 now have Lean-clean 13-step descent theorems
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

After the theorem-level frontier split, the live parent kernel is sharper still:

```text
A_parent = {27, 31, 63, 103, 111}
B_parent = {47, 71, 91}
C_parent = {127}
```

Newest hybrid sharpening:

```text
the theorem-backed mod-128 child reductions and the mod-256 signature audit now align:

K1 roots = {27, 103, 127}
K2 roots = {31, 47, 63, 71, 91, 111}

and every theorem-backed reduction target from
39, 47, 71, 79, 91, 95, 123 mod 128
lands inside the K2 signature rather than creating a third coarse kernel class
```

So the direct frontier is now supporting a stronger finite-obstruction thesis:

```text
the live odd frontier may factor through a 2-class coarse kernel
before the pressure-height exactness/drift theorems are applied
```

Newest theorem-level hardening beneath that audit:

```text
the exact unresolved frontier now factors theorem-level through two refinement layers:

mod 128 frontier
-> exact factorization into one or two open mod-256 children

mod 256 frontier
-> exact factorization into two open mod-512 children

At the mod-256 layer there is now no one-bit reduction left under the current direct
descent theorems. So the next real proof object is no longer "find a lucky sibling exit";
it is control of the full binary refinement kernel itself.

mod 512 frontier
-> 12 open families already reduce to a single mod-1024 child because the sibling child
   now has a verified direct descent theorem
```

Newest search-only sharpening:

```text
the deeper lift-signature audit still shows small finite-state compression:

open mod-256 residue set -> 3 coarse lift-signature classes
open mod-512 residue set -> 4 coarse lift-signature classes
```

That is not theorem-level closure.
But it is evidence that the binary refinement kernel is still compressing rather than
exploding, which keeps the finite-kernel exactness/drift route alive.

One deeper audit sharpens that again:

```text
the open mod-1024 frontier has 65 residues under the current search budget,
but they collapse into only 3 nontrivial coarse child-count classes
and 3 nontrivial exact local-profile classes
```

That is still search-only.
But it is the strongest current sign that the unresolved kernel continues to admit
finite-state compression after another full refinement layer.

Newest live K2 sharpening:

```text
the completed Aristotle artifact for the representative K2 parent 256*t + 31
does not close the parent, but it does isolate the exact open K2 child family:

open mod-4096 children:
31, 543, 799, 1055, 1567, 2079, 2847, 3103, 3615, 3871

already closed mod-4096 children:
287, 1311, 1823, 2335, 2591, 3359
```

Local deterministic verification sharpens the same obstruction:

```text
4096*t + 31 reaches 19683*t + 155 after 21 deterministic steps,
with coefficient still > 4096 and odd.
```

So the live K2 debt is now more explicit:

```text
the next direct-route object is not the whole parent 256*t+31,
but the recurrent 10-child mod-4096 K2 kernel it generates
```

And even that 10-child kernel already compresses one level further:

```text
20 deterministic steps -> 6561*t + c :
543, 799, 1567, 2079, 3871

21 deterministic steps -> 19683*t + c :
31, 2847, 3103, 3615

22 deterministic steps -> 59049*t + 15227 :
1055
```

So the immediate direct-route target is now:

```text
prove control of the three K2 mod-4096 child archetypes,
not ten unrelated child theorems
```

One parity split deeper, the three archetypes already interact in a highly structured way:

```text
6561  -> 6561 or 19683
19683 -> 19683 or 59049
59049 -> 59049 or 177147
```

That does not prove descent.
But it is the first clean sign that the live K2 kernel may admit
a finite-state 3-adic ladder theorem rather than arbitrary branching.

The branching is also exactly balanced at this first split:

```text
6561  : 5 same-coefficient branches, 5 times-3 branches
19683 : 4 same-coefficient branches, 4 times-3 branches
59049 : 1 same-coefficient branch, 1 times-3 branch
```

So the sharpened direct-route theorem hunt is:

```text
explain why this exact same-or-times-3 ladder law
still forces eventual descent or feeds the pressure-height kernel bound
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
