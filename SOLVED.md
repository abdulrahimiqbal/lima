
## Rank/Certificate Hunt Facts Added 2026-04-15

These facts come from rank/certificate hunt run `RH-3959e21bac` on world `W-0273193499`.

### R1. RankCertificate And BoundedCertificate Types Are Definable

Lima successfully formalized certificate containers without assuming Collatz:

```lean
def rankHuntRank := Nat -> Nat

def rankHuntStrictDescent (rank : rankHuntRank) : Prop :=
  forall n : Nat, n > 1 -> rank (rankHuntStep n) < rank n

structure RankCertificate where
  rank : rankHuntRank
  descent : rankHuntStrictDescent rank

structure BoundedCertificate (n : Nat) where
  steps : Nat
  reaches : Nat.iterate rankHuntStep steps n = 1
```

Status:

```text
proved / Lean-clean in rank certificate hunt
```

Interpretation:

```text
The certificate language is formalizable. The hard part is existence, not syntax.
```

### R2. Bounded Certificates Soundly Imply Reachability

A bounded certificate directly proves `reachesOne n` by existential introduction over its `steps` field.

Status:

```text
proved by Aristotle in rank certificate hunt
```

Interpretation:

```text
If Lima can produce concrete bounded certificates, their soundness is easy. The problem is producing them uniformly.
```

### R3. The Identity Rank Decreases On Even Steps But Fails Globally

Lima verified both sides of the naive identity-rank story:

```text
identity rank decreases on even branch: yes
identity rank is global descent: no
```

The obstruction is odd-step growth, witnessed by the probe around `n = 3`.

Status:

```text
proved by Aristotle in rank certificate hunt
```

Interpretation:

```text
A useful rank must absorb odd growth, not merely measure numeric size.
```

### R4. A Strict Descent Certificate Would Be Sufficient

Lima proved the conditional theorem shape:

```text
if there is a rank that strictly decreases for every n > 1 under CollatzStep,
then every positive n reaches 1.
```

Status:

```text
proved by Aristotle in rank certificate hunt
```

Interpretation:

```text
The proof architecture is now clear: find the rank/certificate object. The soundness route is not the bottleneck.
```

### R5. Unconditional Local Certificate Transformers Are Too Strong

The local certificate transformer probe produced diagnostics indicating the original unconditional statement is false at zero-measure/base cases.

Status:

```text
supported by Aristotle diagnostic from rank certificate hunt
```

Interpretation:

```text
Future transformer probes need explicit base-case or positive-measure preconditions. Otherwise they ask for an impossible strictly decreasing natural measure from 0.
```

## Current Bottleneck After Rank Hunt

The remaining decisive job is:

```text
rank_certificate_exists: invent the non-circular strict descent rank itself
```

Current state:

```text
still running as of latest poll
```

Decision implication:

```text
We can move on to designing candidate rank/certificate families, but should keep this job running in the background. If it proves, inspect immediately.
```

### R6. The Direct Strict-Descent Rank Existence Probe Failed

The decisive rank-hunt probe attempted to prove:

```lean
theorem rank_certificate_exists :
  Exists fun cert : RankCertificate => True := by
  sorry
```

Aristotle completed with errors / partial proof and left the core existence claim as `sorry`.

Status:

```text
blocked / partial_proof in digest PD-a9a5cb4fb4
```

Interpretation:

```text
The current system did not invent a non-circular strict descent rank. This confirms that rank/certificate existence is the hard missing object, not certificate syntax or soundness.
```

Decision implication:

```text
Do not retry the same abstract `exists strict descent rank` probe unchanged. Move to concrete candidate rank families and falsify/mutate them one at a time.
```

### R7. Candidate Rank-Family Gauntlet Narrowed The Search

These facts come from candidate rank-family run `CR-ac5fcfe426` on world `W-0273193499`, digested in `PD-f60693b1a3`.

Verified probe outcomes:

```text
identity rank fails on odd branch at n = 3: proved
identity rank decreases on even positive inputs: proved
simple parity-penalty linear rank fails at n = 3: proved
two-step identity rank still fails at n = 3: proved
small linear penalties cannot replace a useful non-circular rank: proved
bounded certificate soundness remains trivial and useful: proved
explicit bounded certificate for n = 3: proved
positive-measure precondition fixes the local transformer zero-measure issue: proved
```

Status:

```text
8 / 8 candidate-rank probes Lean-clean and proved in digest PD-f60693b1a3
```

Interpretation:

```text
The system has now verified that the naive numeric-size family is dead, even after two-step and simple parity-penalty repairs. The viable direction is not "rank by size plus tiny parity correction". It must be a richer certificate/rank object that encodes trajectory structure, residue/valuation behavior, inverse-tree position, parity grammar, or another nonlocal invariant.
```

Decision implication:

```text
Next mutation wave should stop testing tiny linear penalties and instead generate structured rank/certificate families: accelerated odd-map potentials, residue-class potentials, inverse-tree certificates, parity-word grammar ranks, and 2-adic shadow measures. Each family must come with explicit small falsifiers and one soundness/bridge probe before any global closure attempt.
```

### R8. Structured Rank-Family Wave Confirmed Structure Beats Scalar Potentials

These facts come from structured rank-family run `SR-e78685fea7` on world `W-0273193499`, digested in `PD-f8040a6688`.

Verified probe outcomes:

```text
accelerated odd-map potential is definable: proved
accelerated odd-map still grows at n = 3: proved
simple residue-class potential still fails on a small odd witness: proved
inverse-tree witness 10 <- 3 is representable as a concrete certificate: proved
parity-word grammar records the odd-to-even transition at n = 3: proved
2-adic shadow decreases on an even input witness: proved
2-adic shadow still grows on the odd witness n = 3: proved
inverse-tree witnesses transport to one-step Collatz simulation: proved
parity-word data is a trace, not a proof of descent by itself: proved
bounded inverse-tree certificates can package concrete reachability data: proved
```

Status:

```text
10 / 10 structured-rank probes Lean-clean and proved in digest PD-f8040a6688
```

Interpretation:

```text
Lima has now verified a sharper picture. Richer structural objects are formalizable, but the scalar versions of those ideas are still too weak. One-step odd acceleration is not enough. Simple residue-class penalties are not enough. Simple 2-adic shadow measures are not enough. The promising ingredients are inverse-tree certificates and parity/trace objects, but they do not yet constitute a global non-circular descent invariant.
```

Decision implication:

```text
The next mutation wave should not ask for another single numeric rank. It should search for a hybrid nonlocal object: an inverse-tree/parity-grammar/valuation certificate system with explicit local transport lemmas and a bounded proof-debt story. This is the first wave that gives positive evidence for where new mathematics, if needed, would likely have to live: not in syntax, but in the design of a new structured invariant class.
```

### R9. Hybrid Certificate Wave Promoted Local Syntax, Not Global Compression

These facts come from hybrid certificate-family run `HC-b28fc66d40` on world `W-0273193499`, digested in `PD-9a8e910233`.

Verified probe outcomes:

```text
inverse-tree + parity + valuation certificate is definable around 10 <- 3: proved
inverse-tree witness transport recovers the one-step Collatz move: proved
valuation data is available on the even root of the local certificate: proved
coarse parity/residue/valuation signatures can collide: proved
the same coarse signature does not determine the next state: proved
bounded hybrid certificates can package concrete reachability for n = 3: proved
bounded hybrid certificates still imply ordinary reachability: proved
parity grammar remains trace data, not descent proof by itself: proved
inverse-tree, trace, and valuation data can coexist in one certificate object: proved
the certificate stores the odd-to-even trace for 3 -> 10: proved
```

Status:

```text
10 / 10 hybrid-certificate probes Lean-clean and proved in digest PD-9a8e910233
overall latest digest: 45 proved, 3 blocked, 0 inconclusive across 48 mapped probes
```

Interpretation:

```text
The hybrid language is real: inverse-tree data, parity traces, residue tags, valuation witnesses, bounded reachability, and local transport can all coexist without smuggling the full Collatz theorem. But the wave also proved that coarse finite signatures are not complete: they collide while failing to determine the next state. The object is therefore a valid local certificate language, not yet a global invariant or descent mechanism.
```

Decision implication:

```text
Do not pivot away from structured certificates yet. Pivot away from coarse one-step signatures. The next wave should test whether local hybrid certificates compose: certificate extension, pruning/normal-form rules, block-level parity grammar, and a well-founded complexity measure on certificate transformations. The missing mathematical object is now sharper: a compositional certificate calculus with a coverage theorem, not just a local certificate record.
```

### R10. Compositional Certificates Expose The Coverage Gap

These facts come from compositional certificate-family runs `CC-cb23563506` / `CC-1abec63d05` on world `W-0273193499`, digested in `PD-b057ba472c`.

Verified probe outcomes:

```text
one-step hybrid segment certificates are definable: proved
adjacent local certificates compose into a two-step certificate: proved
block parity grammar records the 3 -> 10 -> 5 block: proved
composed certificates preserve concrete trajectory soundness: proved
two-step odd-even composition is still not a descent proof: proved
three primitive steps from 3 still grow, so short blocks are not enough: proved
even-root pruning has a concrete decreasing example: proved
certificate complexity decreases only for pruning, not composition: proved
coarse composition signatures still do not determine descent: proved
local extension is formalizable but creates a coverage obligation: proved
```

Status:

```text
compositional probes Lean-clean in digest PD-b057ba472c
latest overall digest: 58 proved, 3 blocked, 7 inconclusive across 68 mapped probes
inconclusive compositional entries were rate-limit/submission artifact gaps; duplicate live probes resolved the same shapes as proved
```

Interpretation:

```text
The local certificate calculus is now formalizable beyond one-step records: segments compose, block traces work, and concrete pruning can decrease. But the decisive gates are negative for a near-term solve: two-step and three-step blocks from n = 3 still grow, simple certificate complexity increases under composition, and coarse composition signatures still do not imply descent. The remaining missing object is not syntax, not local soundness, and not bounded examples. It is a global coverage/normalization theorem strong enough to guarantee recurring pruning or descent.
```

Decision implication:

```text
This is not the final pre-solution step. It is the last clear decision gate for the current Alien State-Space / hybrid-certificate lineage. Continue only if the next mutation can propose a genuine coverage theorem: every admissible parity/residue block either normalizes, prunes, or extends to a lower-complexity certificate. If the next wave again proves only local examples and small anti-descent facts, pivot to a different world family such as Tao-informed density/measure transport, inverse-tree normal forms, or minimal-counterexample ecology.
```

### R11. Coverage-Normalization Hunt Exhausted The Current Hybrid Lineage

These facts come from coverage-normalization run `CN-65c74f5756` on world `W-0273193499`, digested in `PD-2fa0becd77`.

Verified probe outcomes:

```text
admissible parity/residue blocks are definable without reachability: proved
concrete pruning subblock detection works on a mixed block: proved
all-odd blocks are admissible obstructions to immediate pruning: proved
appending an even prune bit normalizes a concrete obstruction block: proved
trivial extension coverage is too weak because it ignores dynamics: proved
immediate pruning coverage is false for an admissible all-odd block: proved
short-block coverage still sees the 3 -> 10 -> 5 growth obstruction: proved
even-root pruning remains a genuine local descent witness: proved
block complexity can increase when extending to find pruning: proved
obstruction classes can be stated as a smaller named target: proved
density-weakened coverage can be stated without proving full Collatz: proved
forced-extension coverage is not enough unless the extension is dynamically admissible: proved
```

Status:

```text
12 / 12 coverage-normalization probes Lean-clean and proved in digest PD-2fa0becd77
latest overall digest: 70 proved, 3 blocked, 7 inconclusive across 80 mapped probes
```

Interpretation:

```text
The current hybrid lineage has now clarified its own limit. We can define admissible block languages, pruning predicates, obstruction classes, forced extensions, and density-weakened coverage statements without directly assuming Collatz. But the decisive gates show the proposed coverage mechanism is syntactic rather than dynamic: forced extension can append a prune bit without proving that Collatz dynamics permits or benefits from that extension, all-odd blocks obstruct immediate pruning, short blocks still grow from n = 3, and complexity can increase while searching for pruning.
```

Decision implication:

```text
Pivot away from the current Alien State-Space / hybrid-certificate lineage. Do not spend another wave on local certificate syntax, local composition, forced extension, or short-block pruning. The next serious path should change world family: Tao-informed density/measure transport, inverse-tree normal forms with dynamic admissibility, or minimal-counterexample ecology. If certificates return, they should be subordinate to one of those global mechanisms rather than the main object.
```

### R12. Cylinder-Pressure World Repairs Forced Extension And Produces A Real Pressure Signal

These facts come from cylinder-pressure run `CP-59d4e94bf0` on world `W-0273193499`, submitted to Aristotle in three 4-probe batches including bake runs `PB-1b0594da51` / `PB-25478b5e0c`, and digested in `PD-feec629f25`.

Verified probe outcomes:

```text
2-adic residue cylinders are definable: proved
cylinder membership is residue equality, not reachability: proved
dynamic first-bit admissibility accepts the odd cylinder: proved
forced even extension is rejected on the odd cylinder: proved
the odd-even block has concrete affine transport at n = 3: proved
the short odd-even block is pressure-neutral, not positive: proved
a two-even-after-odd block has positive pressure: proved
all-odd blocks are bad-pressure cylinders: proved
legal cylinder refinement splits mass denominator by two: proved
high child still refines to a concrete residue cylinder: proved
density-style bad bounds are statable without reachesOne: proved
pressure language has no reachability field: proved
```

Status:

```text
12 / 12 cylinder-pressure probes Lean-clean and proved in digest PD-feec629f25
latest overall digest: 82 proved, 3 blocked, 7 inconclusive across 92 mapped probes
```

Interpretation:

```text
This is the first post-pivot wave with a genuinely new global object rather than another local certificate language. The object is a 2-adic residue cylinder carrying dynamic parity admissibility, affine block transport, pressure accounting, legal refinement, and density-style bad-cylinder gates. It fixes the previous forced-extension flaw: syntactically appending an even bit is rejected unless it is dynamically legal. It also avoids reachability smuggling: cylinders and density bounds can be stated without a reachesOne field.

The mathematical signal is positive but not yet decisive. Short odd-even motion is pressure-neutral, so pressure is not a trivial scalar descent. But the two-even-after-odd block has positive pressure, and all-odd blocks are isolated as bad-pressure cylinders. That gives a plausible nonlocal target: prove that bad-pressure cylinder families shrink under legal refinement or have density zero, rather than proving pointwise descent at every step.
```

Decision implication:

```text
There is something worth chasing here. The next wave should not return to certificates as the main object. It should test cylinder-pressure globalization: legal split trees, bad-cylinder mass decay, pressure recovery after bad blocks, and a density-zero exceptional-family theorem. This is not the final step before Collatz is solved; it is the first serious post-pivot candidate for a smaller named theorem than Collatz.
```

### R13. Pressure Globalization Identifies The Real Scarcity Theorem

These facts come from pressure-globalization run `PG-f09bdcc253` on world `W-0273193499`, submitted to Aristotle in three local 4-probe batches because Railway deployment upload was timing out, and digested in `PD-f3ea2f0362`.

Verified probe outcomes:

```text
legal split-tree cylinders are definable: proved
high child gives the expected mod-eight residue: proved
split refinement doubles mass denominator: proved
bad-frontier state has no reachability field: proved
all-odd bad block recovers after four legal even refinements: proved
all-odd extension remains a bad-pressure obstruction: proved
one bad child is not strict mass decay: proved
zero bad children give strict mass decay: proved
density-zero frontier is a formal target: proved
two-level zero-bad frontier has denominator four: proved
pressure recovery target can package horizon and bad frontier: proved
bad-mass decay is stronger than one legal split: proved
```

Status:

```text
12 / 12 pressure-globalization probes Lean-clean and proved in digest PD-f3ea2f0362
local run campaign: C-2342eb43dbc9
Aristotle project ids:
- b8f484a6-00cd-4259-b94f-53a0bcd9dc0b
- e528aafa-c59c-4135-97f2-011942025e03
- 5439ca79-a278-4e4b-a788-36e5e9375eec
- 6e38d8d4-2a08-40e0-9158-8cca52835e5f
- b2a21307-3058-4bf7-ba43-8ec0f8522eef
- 2eac17a5-da3c-406d-a508-d26493ec8a47
- 58a09984-611b-4d6d-b202-16b0167d2996
- 63b9c88e-b825-47f3-bd0d-fe39b64aea26
- 9f7a1082-1189-45e3-a863-bfe25725d778
- d7452f88-bfa1-45f5-8c61-c584e465f1ef
- 5b27fa9d-798f-458c-baea-956bb37acc53
- a59ac272-a21b-43a5-b2a4-08fa4d57b864
```

Interpretation:

```text
The pressure world is no longer only a local formalism. It now has a clean global accounting language: split-tree cylinders, bad-frontier counts, mass denominators, strict mass decay, density-zero targets, and pressure-recovery packages can all be expressed without a reachability field.

The decisive mathematical signal is mixed in the useful way. Zero bad children give strict mass decay, and all-odd bad blocks can recover after four even refinements. But one bad child is not strict mass decay, and one legal split alone does not imply decay. Therefore the next missing theorem is not "refinement decreases bad mass." That is false as a general principle. The missing theorem is a scarcity theorem: along dynamically legal split trees, bad children must be rare enough, or pressure recovery must occur often enough, that the bad-frontier mass tends to zero.
```

Decision implication:

```text
Keep chasing the cylinder-pressure world. The next wave should test quantitative scarcity rather than definability: branching-process bounds, multi-level bad-child counts, recovery-window frequency, and a density-zero theorem schema. The likely smaller named theorem is now: every dynamically admissible bad-pressure frontier has subcritical bad-child branching after bounded recovery windows.
```

### R14. Pivot Portfolio Gives A Real Directional Signal, Not A Finished Theorem

These facts come from pivot-portfolio run `PV-10afc4c4b7` on world `W-0273193499`, local campaign `C-c99c9a92c421`, digested in `PD-1d44e80125`.

The run was intentionally broader than the prior pressure-only waves. It tested five possible pivot lanes:

```text
pressure scarcity
inverse-tree dynamic admissibility
minimal-counterexample ecology
Tao-style density transport
cross-lane bridge / separation gates
```

Verified status:

```text
32 portfolio probes total
26 proved
0 blocked
6 inconclusive

by lane:
- inverse-tree dynamic admissibility: 8 / 8 proved
- minimal-counterexample ecology: 8 / 8 proved
- Tao-style density transport: 6 / 6 proved
- cross-lane bridge / separation gates: 2 / 2 proved
- pressure scarcity: 2 / 8 proved, 6 artifact-missing

The remaining 6 are artifact-missing pressure probes, not Lean/math failures.
```

The proved non-pressure probes include:

```text
inverse-tree dynamic nodes are definable
10 <- 3 is dynamically admissible
fake odd and fake even predecessors are rejected
admissibility is local equality, not reachesOne
minimal-counterexample ecology is definable
dominated candidates can have lower descendant and lower energy
survivor conditions block dominance
dominance target is not termination
exceptional-density states are definable
good transport improves exceptional mass
weak transport does not improve exceptional mass
density bounds are counting data, not reachability
pressure frontiers project to density data
inverse admissibility does not force density improvement
```

Interpretation:

```text
This is a real signal, but it is not a Collatz proof and not yet the final step before a proof.

The portfolio rules out one blind path: inverse-tree admissibility by itself is too local. It can represent legal parent/child data and reject fake witnesses, but it does not force density improvement. That makes it useful bookkeeping, not the main engine.

The portfolio also rules out another blind path: minimal-counterexample ecology by itself is not termination. It can express domination and survivor obstructions without smuggling reachesOne, but a dominance target alone does not collapse the original theorem.

The positive signal is the cross-lane shape:

pressure frontier -> density data
density transport -> exceptional mass improvement
minimal ecology -> survivor obstruction language

That gives a theorem-shaped route rather than a vocabulary-shaped route. The next target is not "invent another world." The next target is a composite scarcity theorem:

every dynamically legal bad-pressure frontier either
1. enters a density-improving transport step, or
2. is explained by a minimal-survivor obstruction that can itself be bounded/eliminated.
```

Decision implication:

```text
Do not spend more effort merely completing definitional coverage unless it is needed for audit completeness.

Completing the remaining 6 pressure probes is useful, but not required to decide the next direction. They are all in the pressure-scarcity lane and are currently artifact-missing rather than mathematically blocked. The roadmap direction is already selected by the 26 proved probes: pursue a density/ecology theorem powered by pressure scarcity.

The next wave should be smaller and sharper, not broader:

pressure scarcity -> density decay -> no persistent minimal survivor

Continue only if the next wave proves or sharply falsifies a named theorem of this kind. If it only proves more local definability facts, this route should be treated as another blind path and pivoted away from.
```

### R15. Composite Scarcity Viability Gate Promotes The Route To A Named Theorem Hunt

These facts come from composite-scarcity viability run `CV-9473e35669` on world `W-0273193499`, local campaign `C-ec81916c03de`, submitted in Aristotle bake `PB-c06a0c33ba`, and digested in `PD-f0f0d82600`.

This was intentionally a kill-or-promote gate. It did not ask for more vocabulary. It asked whether the current route can be forced into a smaller, falsifiable theorem shape before investing more time.

Verified probe outcomes:

```text
exact composite scarcity theorem shape is statable: proved
density-zero target plus no survivor implies final obstruction removal: proved
composite step can feed density decay: proved
statement has no reachability or termination field: proved
small legal frontier does not immediately refute the composite step: proved
restricted quantitative scarcity implies subcriticality: proved
survivor obstruction can strictly decrease: proved
weak scarcity is insufficient for strict decay: proved
```

Status:

```text
8 / 8 composite-scarcity viability probes Lean-clean and proved in digest PD-f0f0d82600
blocked: 0
inconclusive: 0
pending Aristotle jobs: 0
```

Interpretation:

```text
This still does not prove Collatz. It does, however, pass the proof-viability gate we set for ourselves.

The route is no longer justified only by a vibe that pressure/density/ecology "sounds promising." The route now has a precise theorem-shaped spine:

1. formulate a composite scarcity step;
2. show that the step feeds density decay or survivor reduction;
3. show that density zero plus no persistent survivor removes the final obstruction;
4. verify that weak scarcity is not enough, so the theorem must be quantitatively sharp.

The most important positive signal is the restricted quantitative probe: strong scarcity implies subcriticality. That is not the missing global theorem, but it confirms the right kind of inequality can be represented and used in Lean.

The most important negative signal is also valuable: weak scarcity is insufficient. That prevents false hope around an easy mass-accounting argument. Any real theorem must prove a genuinely stronger bad-child scarcity/recovery-frequency bound.
```

Decision implication:

```text
Promote this line from "maybe worth chasing" to "the current named theorem hunt."

The next target is not another exploratory wave. It is the Composite Scarcity Theorem:

For dynamically legal bad-pressure split trees, every persistent bad frontier either enters a density-improving transport step within a bounded window, or maps to a minimal-survivor obstruction whose obstruction measure strictly decreases.

Success would not immediately finish Collatz. Success would reduce the remaining proof debt to:

Composite Scarcity Theorem
-> density-zero exceptional family / no persistent survivor
-> sound pullback to ordinary Collatz termination.

Failure should be crisp: if the next wave cannot prove a nontrivial parameterized scarcity/recovery lemma, or if it exposes a legal persistent bad frontier with no density improvement and no survivor reduction, pivot away rather than adding more definitions.
```

### R16. Composite Scarcity Theorem Wave Proves The Local Parameterized Gates

These facts come from composite-scarcity theorem run `CT-648f0ecd11` on world `W-0273193499`, local campaign `C-a9cd28647133`, submitted in Aristotle bake `PB-8226f6c43a`, and digested in `PD-ea1d823dab`.

This wave tested the first serious theorem-hunt requirements after the viability gate: parameterized scarcity, depth-indexed density contraction, recovery-window arithmetic, adversarial weak-gate failures, survivor descent, and the final obstruction closure shape.

Verified probe outcomes:

```text
parameterized strong scarcity implies subcritical bad mass: proved
depth-indexed scarcity projects to density contraction: proved
bounded recovery beats odd debt with a parameterized margin: proved
equal recovery is insufficient for all-odd debt: proved
weak scarcity is not enough for subcritical mass: proved
composite step closes from density contraction or survivor descent: proved
survivor descent forbids persistent self-loop obstruction: proved
survivor descent composes: proved
density zero and zero survivor remove final obstruction: proved
named target is a counting theorem, not a reachability field: proved
```

Status:

```text
10 / 10 composite-scarcity theorem probes Lean-clean and proved in digest PD-ea1d823dab
blocked: 0
inconclusive: 0
pending Aristotle jobs: 0
```

Interpretation:

```text
This is a real mathematical signal, but it remains local. It does not prove the global Composite Scarcity Theorem and it does not prove Collatz.

The new positive information is that the route has nontrivial parameterized pieces, not just examples:

- strong scarcity uniformly implies subcritical bad mass;
- depth-indexed scarcity projects into density contraction;
- recovery windows can beat odd debt with a parameterized margin;
- survivor descent is well-founded enough to forbid self-loops and compose.

The new negative information is also important:

- equal recovery is insufficient for all-odd debt;
- weak scarcity is insufficient for subcritical mass.

So the theorem cannot be cheap. A proof must show a genuinely stronger, dynamically forced scarcity/recovery-frequency fact along legal Collatz split trees.
```

Decision implication:

```text
Promote again, but only one level.

The current bottleneck is no longer "can the ingredients be stated and used?" That is now passed.

The bottleneck is now:

prove a global dynamic forcing lemma:
every legal bad-pressure split tree eventually satisfies strong scarcity or bounded recovery, unless survivor obstruction strictly decreases.

The next wave should not add new objects. It should attack this global dynamic forcing lemma directly, with adversarial probes for persistent bad frontiers. If a legal persistent bad frontier can avoid strong scarcity, avoid recovery, and avoid survivor descent, this route should pivot.
```

### R17. Global Forcing Hunt Separates Dynamic Forcing From Static Legality

These facts come from global-forcing hunt run `GF-87ff21b23e` on world `W-0273193499`, local campaign `C-61b6f8af00b8`, submitted in Aristotle bake `PB-4aac609e41`, and digested in `PD-16997e6eb6`.

This wave was intentionally adversarial. It did not merely ask whether the local progress exits can be stated. It also asked whether legal bad frontiers can persist when the dynamic forcing alternatives are absent.

Verified probe outcomes:

```text
explicit dynamic alternatives force local progress: proved
bounded target follows from explicit dynamic alternatives: proved
repaired finite search candidates all force progress: proved
all-odd no-recovery candidate is a legal persistent bad frontier: proved
equal recovery remains a legal persistent bad frontier: proved
weak scarcity remains insufficient for local progress: proved
strong scarcity gives density contraction: proved
recovery margin wins for any odd debt bounded by horizon: proved
persistent bad frontier decomposes into all three failures: proved
repaired finite search has no persistent bad frontier: proved
named target is counting-only and has no reachability field: proved
survivor obstruction drop is a local forcing alternative: proved
```

Status:

```text
12 / 12 global-forcing hunt probes Lean-clean and proved in digest PD-16997e6eb6
blocked: 0
inconclusive: 0
pending Aristotle jobs: 0
```

Interpretation:

```text
This is a real signal, but it is not a pure "everything works" signal.

The positive side:

- once explicit dynamic alternatives are available, local progress follows;
- the bounded target follows from those alternatives;
- repaired finite candidates have no persistent bad frontier;
- strong scarcity gives density contraction;
- recovery margin beats odd debt;
- survivor drop is a legitimate forcing exit.

The warning side:

- static legality alone is too weak;
- all-odd with no recovery is a legal persistent bad frontier;
- equal recovery is still a legal persistent bad frontier;
- weak scarcity is still insufficient.

So the route did not die, but it got narrower. The missing theorem is not merely "legal frontiers progress." That is false. The missing theorem is:

dynamically legal Collatz split trees force one of the explicit dynamic alternatives.
```

Decision implication:

```text
Promote the route only under a stricter condition.

Do not run more waves that merely restate local progress. The next proof debt is now exactly the dynamic-admissibility-to-forcing bridge:

Collatz dynamic legality
-> either strong scarcity, sufficient recovery margin, or survivor obstruction drop.

If this bridge cannot be proved, the static pressure/density formulation is too weak. If it can be proved for bounded horizons and then parameterized, it becomes the first serious route toward the global Composite Scarcity Theorem.

The next wave should therefore encode actual parity/residue-block dynamic admissibility into the forcing alternatives, not just assume the alternatives as hypotheses.
```
