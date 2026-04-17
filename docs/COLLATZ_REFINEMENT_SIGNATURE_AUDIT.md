# Collatz Refinement Signature Audit

Date: 2026-04-16

Commands:

```text
.venv_test/bin/python scripts/run_collatz_refinement_signature_audit.py
.venv_test/bin/python scripts/run_collatz_refinement_arithmetic_measure_search.py
.venv_test/bin/python scripts/run_collatz_cylinder_persistence_audit.py
```

## What This Is

This is a stronger search audit of the unresolved direct-descent frontier.

The earlier transition compass only tracked local resolved/unresolved child counts.
This audit asks two harder questions:

```text
1. does the unresolved tree collapse if we track the exact resolved/unresolved dyadic tree
   out to a fixed horizon?
2. if not, do arithmetic residue features reveal a more meaningful organizing principle?
```

It is still a search audit, not a proof artifact.

## Exact Signature Result

Using exact resolved/unresolved binary refinement trees out to depth 5 across moduli

```text
4096
8192
16384
```

the audit finds:

```text
signature_count: 171
recurrent_component_count: 1
largest_recurrent_component_size: 67 signatures
largest_recurrent_component_member_count: 483 states
```

So pure finite-horizon tree shape is **not** enough to isolate a tiny closed obstruction.

The largest recurrent component contains signatures with only four coarse stat types:

```text
resolved_leaves=4, unresolved_leaves=25, branching_nodes=28
resolved_leaves=1, unresolved_leaves=30, branching_nodes=30
resolved_leaves=1, unresolved_leaves=31, branching_nodes=31
resolved_leaves=0, unresolved_leaves=32, branching_nodes=31
```

This is a meaningful negative result:

```text
the missing theorem is not just "look at the next finite resolved/unresolved tree shape"
```

## Arithmetic Signal

Projecting the recurrent component back to residues modulo 128 gives exactly the current
unresolved direct-family frontier:

```text
27, 31, 39, 47, 63, 71, 79, 91, 95, 103, 111, 123, 127 mod 128
```

That means the recurrent core does not spread across arbitrary residue classes.
It lives inside the same 13 unresolved residue cylinders that the direct Lean hardening
already identified.

This is the strongest current direct-descent signal:

```text
the remaining obstruction is not an arbitrary residue explosion;
it is a persistent self-similar unresolved branch structure inside 13 fixed mod-128 cylinders
```

## Cylinder Persistence

The cylinder persistence audit pushes those same 13 residue classes deeper, through:

```text
128
256
512
1024
2048
4096
8192
16384
32768
65536
```

None of the 13 cylinders dies out by depth `65536`.

More importantly, they collapse into exactly **three** growth archetypes:

```text
A = 27, 31, 63, 103, 111
sequence: 1, 2, 4, 7, 14, 25, 41, 82, 145, 237

B = 39, 47, 71, 79, 91, 95, 123
sequence: 1, 1, 2, 3, 6, 10, 15, 30, 51, 79

C = 127
sequence: 1, 2, 4, 8, 16, 31, 57, 114, 213, 376
```

So the remaining odd frontier is not 13 unrelated cases.
It is:

```text
three exact persistence archetypes inside 13 residue cylinders
```

This is the strongest finite-kernel signal yet.

## Arithmetic Measure Search

The arithmetic-augmented measure search mixed:

```text
residue
residue bucket
distance to top of the modulus interval
v2(residue + 1)
v2(3*residue + 1)
popcount(residue)
first resolved depth at horizon 5
horizon-5 signature stats
```

with lexicographic edge checks on unresolved parent -> unresolved child transitions.

It found exact edge-monotone orders, for example:

```text
(residue, distance_to_top)
```

with both coordinates oriented as "larger is better".

But this is **not yet** a proof measure, because:

```text
distance_to_top grows with modulus under left-child refinement,
so this edge order is not obviously well-founded on Nat-valued state
```

Interpretation:

```text
arithmetic position really does organize the unresolved tree better than pure local shape,
but the current arithmetic features still do not directly give a terminating rank
```

## Main Lesson

The search has now separated two possibilities:

```text
1. a finite-state combinatorial closure theorem is too weak by itself
2. the missing theorem probably needs an arithmetic / 2-adic cylinder ingredient
3. the unresolved cylinders themselves compress to only three exact growth archetypes
```

The direct unresolved branches are better thought of as nested dyadic cylinders than as
mere finite branching trees.

## Sharpened Missing Object

The likely direct-route missing theorem is now:

```text
for each of the 13 unresolved residue cylinders mod 128,
there is no infinite dyadic refinement branch that stays unresolved forever
```

Equivalently:

```text
every infinite unresolved branch inside one of those cylinders must eventually hit
a proved descent family or contradiction
```

This is closer to a 2-adic / cylinder exclusion theorem than to a short local rank.

The persistence audit sharpens this again:

```text
it may be enough to prove that no infinite unresolved branch exists for the
three cylinder-growth archetypes A, B, and C
```

## Roadmap Consequence

The next direct-route probes should not ask for:

```text
another shallow child-count profile
another architecture-only theorem
another broad residue wave
```

They should ask for one of:

```text
1. a theorem excluding infinite unresolved branches in one archetype A/B/C
2. a theorem extracting a well-founded quantity from the cylinder arithmetic
3. a theorem showing an archetype eventually forces a currently proved exit family
```

If those fail uniformly, the pressure-height scaffold-elimination route becomes the only
remaining serious endgame.
