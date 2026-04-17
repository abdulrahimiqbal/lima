# Collatz Critical Q1 Kernel Audit

Date: 2026-04-17

## What This Adds

This memo records the strongest finite-kernel sharpening currently visible in the repo.

It does **not** prove Collatz.
It does identify a much smaller exact endgame object:

```text
a phase-aware finite quotient of the unresolved frontier,
plus a critical Q1 branch whose arithmetic shadow already obeys
exact finite child-count and scarcity laws
```

## Current Kernel Picture

Validated locally by:

```text
scripts/run_collatz_scc_kernel_candidate_inventory.py
scripts/run_collatz_scc_kernel_graph.py
scripts/run_collatz_scc_kernel_phase_cycle_audit.py
scripts/run_collatz_scc_kernel_template_rarity_audit.py
scripts/run_collatz_scc_kernel_weighted_contraction_audit.py
scripts/run_collatz_scc_kernel_deep_extension_audit.py
```

What survives validation:

```text
1. the unresolved search-defined frontier collapses to a 9-state coarse quotient
   through moduli 1024, 2048, and 4096

2. extending the same profile logic through modulus 8192 keeps that quotient closed

3. the nontrivial unresolved dynamics sit inside one 8-state SCC:
   Q1, Q2, Q3, Q4, Q5, Q6, Q7, Q8

4. the trivial residue-1 behavior is isolated as the one-state class Q9
```

The coarse transition graph is:

```text
Q1 -> Q1, Q2
Q2 -> Q1, Q2, Q3, Q4
Q3 -> Q2, Q5
Q4 -> Q3, Q6
Q5 -> Q4, Q7
Q6 -> Q5, Q8
Q7 -> Q6
Q8 -> Q7
Q9 -> Q9
```

This is already a real finite quotient candidate, not just an informal clustering.

## Phase-Aware Refinement

The 9-state quotient is not the final object.

The deeper extension audit shows:

```text
the quotient stays coherent through modulus 16384,
but refines to 10 states by modulus 32768
```

So the current evidence points to:

```text
the final kernel should be phase-aware,
not a frozen one-layer local-profile quotient
```

This is good news, not bad news.
It means the remaining structure is still finite and periodic, but one layer deeper
than the first coarse 9-state view.

## Phase-Cycle Scarcity Signal

The phase-cycle audit groups the kernel by the natural dyadic phase pattern:

```text
phase0 at mod 1024 : Q1, Q3, Q6
phase1 at mod 2048 : Q1, Q2, Q5, Q8
phase2 at mod 4096 : Q1, Q2, Q4, Q7
```

The resulting three-step return operators are already strictly subcritical after
dyadic density normalization:

```text
phase0 return radius < 0.75
phase1 return radius < 0.76
```

The weighted contraction audit sharpens this further.
Using the positive vectors extracted from those return operators, every observed
source family contracts strictly in weighted dyadic density.

Worst explicit bound seen so far:

```text
global uniform upper bound < 0.952
```

So the finite kernel is already carrying:

```text
exact finite states
exact finite transitions
explicit positive weights
strict weighted contraction bounds
```

The only remaining failure mode inside this audited model is a very small explicit
critical self-cloning branch.

## Critical Q1 Frontier Shadow

Validated locally by:

```text
scripts/run_collatz_critical_q1_frontier_bridge_audit.py
scripts/run_collatz_critical_q1_child_law_audit.py
scripts/run_collatz_critical_q1_class_density_audit.py
scripts/run_collatz_critical_q1_density_persistence_audit.py
scripts/run_collatz_critical_q1_child_law_hardening.py
```

This is the strongest current bridge from the finite phase-kernel picture back to
the actual arithmetic frontier.

What the bridge says:

```text
the rare Q1 -> Q1,Q1 self-cloning branch is not an unrelated phase artifact

by source moduli 16384 and 32768,
the residues that realize that critical branch project onto exactly the
19 open mod-256 frontier classes
```

Those 19 open mod-256 classes are:

```text
27, 31, 47, 63, 71, 91, 103, 111, 127,
155, 159, 167, 191, 207, 223, 231, 239, 251, 255
```

So the critical Q1 branch is now tied directly to the live arithmetic frontier.

## Exact Child Laws on the Critical Shadow

Once the Q1 shadow stabilizes onto the full open mod-256 frontier, the child counts
fall into only three exact archetypes.

From modulus 16384 to 32768:

```text
12 singleton classes:
1 -> 1

6 seven-classes:
7 -> 8

1 heavy class:
22 -> 29
```

From modulus 32768 to 65536:

```text
12 singleton classes:
1 -> 1

6 seven-classes:
8 -> 9

1 heavy class:
29 -> 37
```

And the bifurcation law is exact:

```text
singleton classes: every source residue has exactly one critical child

7/8/9 classes: exactly one source residue bifurcates and the rest have one critical child

heavy class 255: the number of bifurcating sources matches the current seven-class size
```

So the observed recurrence is:

```text
a_(n+1) = a_n
b_(n+1) = b_n + 1
c_(n+1) = c_n + b_n

with observed counts
a = 1, 1, 1
b = 7, 8, 9
c = 22, 29, 37
```

This is no longer a vague “kernel signal.”
It is an exact finite arithmetic law on the critical frontier shadow.

## Classwise Scarcity

After the natural dyadic normalization by `1/2`, the exact classwise density factors are:

```text
singleton classes: 1/2
seven classes:     4/7, then 9/16
heavy class 255:   29/44, then 37/58
```

Every one of these is strictly below `1`.

So the direct arithmetic shadow of the critical branch is already classwise
subcritical in a very explicit sense.

## Lean-Facing Hardening

The script

```text
scripts/run_collatz_critical_q1_child_law_hardening.py
```

now compiles a Lean-clean finite theorem bundle for the exact child laws:

```text
singleton classes carry the (1,1,1,0) profile
seven classes carry the (7,8,6,1) and (8,9,7,1) profiles
the heavy class 255 carries the (22,29,15,7) and (29,37,21,8) profiles
```

This is not yet a Nat theorem about Collatz descent.
It is a Lean-facing exact package over the finite class partition that the audits expose.

That is the correct shape for the next proof bridge.

The next step has already been partially taken:

```text
scripts/run_collatz_critical_q1_kernel_quotient_hardening.py
```

now compiles a Lean-clean explicit three-state quotient bundle:

```text
CriticalKernelState = A | B | C

A = 12 singleton residue classes
B = 6 medium residue classes with counts 7 -> 8 -> 9
C = heavy class 255 with counts 22 -> 29 -> 37
```

and proves, inside Lean, finite theorem objects for:

```text
critical_q1_kernel_partition
critical_q1_kernel_child_law
critical_q1_kernel_recurrence
critical_q1_kernel_uniform_subcritical
```

This is still not the final Collatz theorem.
But it is the first explicit finite quotient theorem package that looks close to the
actual remaining obstruction instead of to a placeholder certificate shell.

The algebraic side is now pushed one step further:

```text
scripts/run_collatz_critical_q1_recurrence_subcritical_hardening.py
```

compiles a Lean-clean all-depth recurrence/subcriticality bundle for the abstract
three-state A/B/C system:

```text
aSeq is fixed
bSeq(n+1) = bSeq(n) + 1
cSeq(n+1) = cSeq(n) + bSeq(n)
bSeq(n) < cSeq(n) for all n
bSeq(n+1) < 2 * bSeq(n) for all n
cSeq(n+1) < 2 * cSeq(n) for all n
```

So one proof bottleneck is now removed:

```text
the algebra needed for uniform subcriticality is already Lean-clean
once the actual critical shadow is shown to obey the A/B/C recurrence
```

The next phase-aware hardening is also now in hand:

```text
scripts/run_collatz_critical_q1_phase_kernel_hardening.py
```

compiles a Lean-clean phase-prefix bundle through modulus `1048576`:

```text
A : 1 -> 2 -> 3 -> 4 -> 8
B : 9 -> 18 -> 28 -> 39 -> 78
C : 37 -> 74 -> 120 -> 176 -> 352
```

with exact transition laws:

```text
65536  -> 131072   : every source residue bifurcates
131072 -> 262144   : partial return
262144 -> 524288   : partial return
524288 -> 1048576  : every source residue bifurcates
```

and uniform dyadic contraction on both checked return scales:

```text
two-bit return 65536 -> 262144:
3/4, 7/9, 30/37

four-step return 65536 -> 1048576:
1/2, 13/24, 22/37
```

So the right remaining object is now clearer:
not a one-bit child law, but an all-depth phase-aware cycle extending this checked prefix.

The periodicity lane now goes one layer deeper too:

```text
scripts/run_collatz_critical_q1_phase_periodicity_hardening.py
```

compiles a Lean-clean extension through modulus `2097152`:

```text
262144 -> 524288   : mixed
524288 -> 1048576  : all bifurcate
1048576 -> 2097152 : mixed
```

with counts:

```text
A : 3 -> 4 -> 8 -> 13
B : 28 -> 39 -> 78 -> 129
C : 120 -> 176 -> 352 -> 595
```

and checked two-bit return factors:

```text
262144 -> 1048576:
2/3, 39/56, 11/15

524288 -> 2097152:
13/16, 43/52, 595/704
```

So the proof debt is even more specific:
the remaining theorem is best understood as an all-depth alternating mixed /
all-bifurcate phase law, not merely a generic phase-aware refinement statement.

## What This Means For The Proof

The strongest current endgame reading is now:

```text
1. the final kernel should be phase-aware and finite
2. the only explicit obstruction inside the current weighted-contraction story
   is the rare critical Q1 self-cloning template
3. that critical template projects exactly onto the arithmetic open mod-256 frontier
4. on that frontier shadow, the child counts obey exact finite recurrence laws
   and strict classwise scarcity bounds
```

So the next theorem bottleneck is no longer vague.
It is one of these two closely related statements:

```text
either:
prove that the critical Q1 shadow cannot maintain density under the exact
same finite child laws

or:
prove that the phase-aware kernel contraction theorem already rules out the
critical self-cloning branch once projected back to the arithmetic frontier
```

## Exact Remaining Bottlenecks

The proof debt is now best named as:

```text
T1. phase-aware finite kernel exactness
    prove the final finite state space and its exact recurrent coverage;
    the current three-state A/B/C quotient is now a serious candidate local factor

T2. critical Q1 scarcity theorem
    prove that the actual critical Q1 shadow obeys an all-depth alternating
    mixed / all-bifurcate phase cycle extending the checked A/B/C prefix;
    the abstract recurrence-to-subcriticality algebra and the checked phase-prefix
    contraction are now already Lean-clean

T3. kernel rarity / critical-template exclusion
    prove that the rare all-Q1 self-cloning template cannot sustain
    a dangerous frontier

T4. arithmetic pullback
    transfer T1-T3 through the existing pressure-height spine to
    no-dangerous-frontier, finite base coverage, and eventual descent
```

This is much smaller than the earlier proof debt.
It is now a finite-state exactness / scarcity / pullback problem.
