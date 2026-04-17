
## Read This First 2026-04-16

This file is the cumulative fact log.

If you only need the current state, read this section first, then:

```text
docs/COLLATZ_ROADMAP.md
docs/COLLATZ_EXIT_BRIDGE_HARDENING.md
docs/COLLATZ_DESCENT_EXTENSION_HARDENING.md
docs/COLLATZ_AFFINE_REWRITE_COMPASS.md
docs/COLLATZ_AFFINE_REFINEMENT_COMPASS.md
docs/COLLATZ_REFINEMENT_PARTITION_AUDIT.md
docs/COLLATZ_PROOF_DEBT_AUDIT.md
docs/COLLATZ_FRONTIER128_SPLIT_HARDENING.md
docs/COLLATZ_SCC_KERNEL_ENDGAME.md
docs/COLLATZ_REFINEMENT_SIGNATURE_AUDIT.md
docs/COLLATZ_KERNEL_REFINEMENT_AUDIT.md
```

Current status:

```text
Collatz is not proved.

The proof architecture has been compressed to one central target:
for every n > 1, prove there exists k such that
0 < collatz^[k](n) < n.

If that target is proved, ordinary Collatz termination follows by strong induction.

The latest 13-job Aristotle final-closure tranche reconciles as 13 / 13 Lean-clean
artifact bundles. That means the pressure-height endgame architecture is now
verified as a coherent proof spine, not just a story.

But that still does not prove Collatz, because those final-closure theorems are
theorem-shape / certificate-architecture facts. They do not yet fully expand the
remaining pressure-height certificate fields into concrete Nat-level arithmetic.
```

What is theorem-level today:

```text
descent core over Nat: proved locally in Lean

concrete exit families proved locally in Lean:
- even n
- n ≡ 1 mod 4, n > 1
- n ≡ 3 mod 16
- n ≡ 11 or 23 mod 32
- n ≡ 7, 15, or 59 mod 128
- n ≡ 287, 347, 367, 423, 507, 575, 583, 735, 815, 923, 975, or 999 mod 1024
- n ≡ 383, 615, or 2587 mod 4096

these are actual iterateNat / collatzStep statements, not Bool certificate fields
```

What is not theorem-level yet:

```text
the full odd 4*a+3 family
the final pressure-height scaffold elimination
the fully expanded Nat-level pullback from the pressure-height route
the concrete arithmetic theorem making the final pressure-height closure objects true
for actual Collatz dynamics rather than only as verified certificate architecture
```

Current exact local frontier:

```text
direct-family theorem frontier:
27, 31, 39, 47, 63, 71, 79, 91, 95, 103, 111, 123, 127 mod 128

single-family affine rewrite frontier:
27, 31, 47, 63, 71, 91, 103, 111, 127 mod 256
```

Newest kernel compression:

```text
The theorem-backed mod-128 child-reduction hardening and the search-backed
mod-256 signature audit now line up.

K1 roots at mod 256:
27, 103, 127

K2 roots at mod 256:
31, 47, 63, 71, 91, 111

And the theorem-backed mod-128 reduction targets
167, 47, 71, 207, 91, 223, 251
all land in the same K2 signature class.

So the remaining odd obstruction now looks less like "13 separate roots" and
more like a 2-class finite kernel with one smaller K1 branch and one larger K2 branch.
This is still not theorem-level exactness or drift. It is a stronger audit signal
for what the last finite object probably is.
```

Newest theorem-level factorization hardening:

```text
The unresolved frontier is now packaged theorem-level across two refinement layers.

At mod 128:
each of the 13 frontier families is proved to factor through either
- one open mod-256 child when the sibling already descends, or
- both mod-256 children when neither sibling is yet proved

At mod 256:
every surviving open family is proved to factor through both of its mod-512 children.
No one-bit reduction remains at this layer under the current direct descent facts.

At mod 512:
12 open families now reduce to a single mod-1024 child because the sibling child
already has a verified direct descent theorem.
```

Newest search-only kernel signal:

```text
The deeper lift-signature audit now shows:

open mod-256 residue set -> 3 coarse classes
open mod-512 residue set -> 4 coarse classes

This does not prove closure.
It does strengthen the finite-kernel thesis by showing that one deeper unresolved layer
still compresses to a tiny number of repeating state types.
```

Newest search-only mod-1024 kernel signal:

```text
Under the current direct-descent search budget, the open mod-1024 frontier has 65 residues.

Ignoring the trivial residue 1, it compresses into:
- 3 nontrivial coarse child-count signatures
- 3 nontrivial exact local-profile classes

This is still not a proof artifact.
It is stronger evidence that the unresolved frontier is finite-state enough to support a
kernel exactness/drift theorem rather than residue-by-residue sprawl.
```

Current problem-solving approach:

```text
1. Keep theorem-level Lean facts and search compasses separate.
2. Promote only Lean-clean family theorems into the proof layer.
3. Use compasses only to choose the next theorem candidates.
4. Prefer proof hardening and scaffold elimination over new invention waves.
5. If residue-family promotion stalls, prove a well-founded dyadic refinement + affine rewrite theorem instead of enumerating forever.
```

Current search-only signal:

```text
The single-family affine rewrite compass is not a proof, but it already shows that some
unresolved mod-128 roots, including 39, 79, 95, and 123, admit composed descent
certificates from the currently proved family rules.

The new refinement compass is stronger conceptually:
the 1024 and 4096 extension rules harden refined children of the unresolved mod-256
parents, and those parents now cluster into two visible refinement archetypes.

This suggests the right missing object is not just a theorem about affine-family
rewriting, but a theorem about a dyadic refinement plus affine rewrite system.
```

Additional update:

```text
That object is now split cleanly into:
1. a proved Lean partition theorem saying child closure implies parent closure
2. a search-only transition compass suggesting the unresolved tree compresses into
   a small number of profile classes rather than exploding arbitrarily
```

Newest local hardening signal:

```text
The nine concrete parent-closure Aristotle probes for
27, 31, 47, 63, 71, 91, 103, 111, 127 mod 256
now compile locally in Lean as honest files:

- each file contains the general dyadic partition theorem
- each file contains fully checked direct mod-4096 child proofs already known locally
- the only remaining holes are the genuinely unresolved mod-4096 child closures

This means the remaining frontier is now packaged as a finite theorem family, not just a compass.

Aristotle submission is currently account-blocked by:
"too many requests in progress"
so this is a live-queue issue, not evidence that the probe shape is wrong.
```

## Exit-Bridge Extension Facts Added 2026-04-16

### E1. Nine New Refined Descent Families Compile In Lean

Status:

```text
proved locally in Lean via scripts/run_collatz_descent_extension_hardening.py
```

New theorem-backed families:

```text
1024*t + 287  -> 729*t + 205
1024*t + 815  -> 729*t + 581
1024*t + 575  -> 729*t + 410
1024*t + 583  -> 729*t + 416
1024*t + 347  -> 729*t + 248
1024*t + 367  -> 729*t + 262
4096*t + 2587 -> 2187*t + 1382
4096*t + 615  -> 2187*t + 329
4096*t + 383  -> 2187*t + 205
```

Interpretation:

```text
The researcher extension was real. These are valid new concrete exit theorems.
```

### E2. Adding Those Rules Does Not Change The Root-Level Rewrite Frontier

Status:

```text
verified by scripts/run_collatz_affine_rewrite_compass.py
```

Interpretation:

```text
This is not bad news. It means the new rules only become visible after residue refinement.
The missing object is larger than a single-family rewrite search.
```

### E3. The Remaining Object Is A Refinement Tree Theorem

Status:

```text
sharpened by scripts/run_collatz_affine_refinement_compass.py
```

Signal:

```text
parents 31, 47, 63, 71, 91, 111 share one refinement profile
parents 27, 103, 127 share another refinement profile
```

Interpretation:

```text
The remaining proof target is now best described as:
prove a well-founded dyadic refinement + affine rewrite closure theorem.
```

### E4. A General Dyadic Partition Theorem Now Compiles In Lean

Status:

```text
proved locally in Lean via scripts/run_collatz_refinement_partition_audit.py
```

What it says:

```text
if both one-bit children descend, then the parent descends
if all 2^m dyadic children descend, then the parent descends
```

Interpretation:

```text
This is the first general theorem that turns finite child closure into a parent theorem.
It is the proof-side bridge from branch data to universal descent.
```

### E5. The Unresolved Tree Now Has A Small Transition Compass

Status:

```text
search-only signal via scripts/run_collatz_refinement_transition_compass.py
```

Signal:

```text
across moduli 4096, 8192, and 16384, the unresolved tree compresses into
eight local profile classes under a four-level child-count signature
```

Interpretation:

```text
This does not prove well-foundedness, but it is the first concrete sign that the
remaining search may be describable by a finite-state closure theorem.
```

### E6. Simple Local State Measures Still Do Not Close The Tree

Status:

```text
search-only signal via scripts/run_collatz_refinement_measure_search.py
```

What was checked:

```text
Search for lexicographic measures built from:
- resolved-child counts over the next four refinement levels
- recursive unresolved-leaf counts over the next four refinement levels
```

Result:

```text
No exact lexicographic measure of that simple form decreases on every unresolved edge
across the 4096 / 8192 / 16384 refinement transition graph.
```

Interpretation:

```text
The final well-founded state cannot be just
"how many children close nearby."

The remaining theorem almost certainly needs a richer state description than the
current local profile / leaf-count signatures.
```

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

### R18. Height-Lifted Dynamic Pressure Automaton Separates Ghost Recurrence From Dangerous Recurrence

These facts come from dynamic-pressure automaton run `DP-a6492d7a9e` on world `W-0273193499`, local campaign `C-af92e2e76951`, submitted in Aristotle bake `PB-cb871a4bee`, and digested in `PD-ce1e80a9f6`.

This wave changed the discovery method. Instead of hand-picking local pressure examples, it built a finite residue automaton for actual Collatz residue dynamics. Even steps are modeled soundly with hidden high-bit splitting, so the automaton over-approximates positive integer behavior rather than cheating by using a deterministic low-bit projection.

Local search before Aristotle:

```text
windows checked locally: 1 through 7
window 1: acyclic bad subgraph
window 2: recurrent bad components exist, all height-expanding
window 3: acyclic bad subgraph
window 4: recurrent bad components exist, all height-expanding
window 5: recurrent bad SCC size 997, minimum cycle-mean height drift positive
window 6: recurrent bad components exist, all height-expanding
window 7: recurrent bad SCC size 2581, minimum cycle-mean height drift positive
dangerous nonexpanding recurrent components found: 0
```

Verified probe outcomes:

```text
pressure rule separates one-even from two-even recovery: proved
even residue step must split on the hidden high bit: proved
acyclic reports carry a finite bad-rank witness: proved
sound residue relation exposes the 2-adic ghost cycle: proved
the ghost cycle is bad for the pressure rule: proved
ghost obstruction is a negative residue-class phenomenon: proved
height lift removes the first recurrent bad ghost: proved
pressure-bad and height-expanding are separate exits: proved
```

Status:

```text
8 / 8 dynamic-pressure automaton probes Lean-clean and proved in digest PD-ce1e80a9f6
blocked: 0
inconclusive: 0
pending Aristotle jobs: 0
```

Interpretation:

```text
This is a stronger signal than the previous static pressure waves.

Pure residue pressure is not enough: it sees recurrent bad cycles, including the 2-adic negative ghost cycle -2 <-> -1. That prevents a naive "bad pressure graph is acyclic" theorem.

But the height lift explains the failure rather than merely exposing it. The checked recurrent bad components are pressure-bad but Archimedean-height-expanding. In particular, the bad residue recurrences look like ghosts/escape channels, not bounded positive-integer survivor cycles.

The most important new distinction is:

pressure recovery and height escape are separate exits.

So the route has narrowed again. The missing theorem is no longer just dynamic-admissibility-to-forcing. The sharper target is:

every dynamically admissible persistent bad-pressure recurrence either gets pressure recovery or has positive height escape; height escape is incompatible with a minimal persistent survivor.
```

Decision implication:

```text
Promote the pressure route one more level, but only as pressure-plus-height.

Do not chase pure 2-adic pressure as the final invariant. It has real residue ghost recurrences.

The next named theorem gate is now:

pressure-bad recurrence + positive height drift
-> no persistent minimal survivor / density obstruction closes.

If that gate can be verified locally and then parameterized, this becomes the first genuinely theorem-shaped bridge from the automaton evidence toward Collatz. If height escape cannot be connected to minimal-survivor closure, then this route stalls despite the good automaton signal.
```

### R19. Pressure-Plus-Height Survivor Closure Passes The Local Win Gate

These facts come from pressure-height survivor closure run `PH-53e964f582` on world `W-0273193499`, local campaign `C-73032c066a12`, submitted in Aristotle bake `PB-4e58efa7c1`, and digested in `PD-ebd3a2a4fb`.

This wave tested the exact gate created by R18. The question was not whether height escape can be named, but whether it actually does logical work against a minimal persistent survivor while preserving adversarial guardrails.

Verified probe outcomes:

```text
pressure-bad alone can still persist: proved
height escape contradicts minimal persistence: proved
checked ghost block is pressure-bad but not persistent: proved
composite exit kills minimal bad obstruction: proved
nonexpanding pressure-bad block remains obstruction: proved
checked frontier has no dangerous survivor component: proved
pressure recovery is an independent closure exit: proved
survivor drop is an independent closure exit: proved
target is counting-height only: proved
all-checked height escape implies no dangerous survivor: proved
```

Status:

```text
10 / 10 pressure-height survivor closure probes Lean-clean and proved in digest PD-ebd3a2a4fb
blocked: 0
inconclusive: 0
pending Aristotle jobs: 0
```

Interpretation:

```text
This is the win we were looking for at the local theorem-gate level.

The positive result is not merely "height escape exists." The verified local closure is:

height escape contradicts minimal persistence;
pressure-bad plus height-escaping is not a persistent survivor;
pressure recovery, height escape, and survivor drop form independent closure exits;
if all checked recurrent bad components height-escape, then no dangerous survivor remains.

The adversarial result is equally important:

pressure-bad alone can still persist;
nonexpanding pressure-bad blocks remain obstructions.

So the wave did not prove a vacuous story. It proved exactly why height is necessary and exactly where it helps.
```

Decision implication:

```text
Promote the route from "height-lifted signal" to "local pressure-plus-height survivor closure."

This is still not Collatz. The remaining gap is global and parameterized:

for all legal Collatz pressure frontiers, every recurrent bad component either
  recovers pressure,
  height-escapes,
  or triggers survivor drop;
then the density/minimal-survivor obstruction closes;
then the sound pullback proves ordinary Collatz termination.

The next wave should not invent a new object. It should globalize this local closure:

bounded-to-parameterized pressure-plus-height frontier theorem
-> global Composite Scarcity / density-zero closure
-> pullback target.
```

### R20. Pressure-Height Frontier Certificates Verify The Uniform No-Dangerous-Frontier Calculus

These facts come from pressure-height frontier certificate run `FC-2779e9f64f` on world `W-0273193499`, campaign `C-d8cccdd7e4b2`, submitted in Aristotle bake `PB-943580ec29`, and digested in `PD-fdbfaa6100`.

This wave tested the exact next gate after R19. The question was not whether a checked local component can close, but whether the closure exits can be packaged into a uniform frontier certificate theorem with adversarial guardrails.

Raw Aristotle project statuses were mixed:

```text
7 COMPLETE
5 COMPLETE_WITH_ERRORS
```

However, the digest reconciled all mapped probes as proved and reported no detected Lean/math error:

```text
probe_count: 12
proved_count: 12
blocked_count: 0
inconclusive_count: 0
reconciled_pending_job_count: 0
```

Verified probe outcomes:

```text
component certificate format records pressure, height, and survivor-drop exits: proved
component certificate excludes danger: proved
all-certified frontier has no dangerous component: proved
checked frontier packages as all-certified: proved
checked certificate has no dangerous survivor: proved
uncertified frontier can contain danger: proved
pressure-bad alone is not a certificate: proved
one height escape without frontier coverage is insufficient: proved
sound certificate gives density closure: proved
target is counting-height only: proved
checked certificate is sound: proved
certificate theorem is uniform over frontiers: proved
```

Status:

```text
12 / 12 pressure-height frontier certificate probes Lean-clean after digest reconciliation in PD-fdbfaa6100
blocked: 0
inconclusive: 0
pending Aristotle jobs: 0
```

Interpretation:

```text
This is a real theorem-gate win, not just another vocabulary wave.

R19 showed that pressure recovery, height escape, and survivor drop close local bad components. R20 shows that those exits can be assembled into a uniform frontier certificate calculus:

if every component in a frontier is certified by one of the closure exits,
then the frontier has no dangerous component,
and this soundness theorem is uniform over arbitrary component lists.

The guardrails matter:

pressure-bad alone is not accepted as a certificate;
a single height escape without coverage is not enough;
an uncertified frontier can still contain danger;
the target is counting/height data, not hidden reachability.

So the pressure-plus-height route is now coherent at the certificate-calculus level.
```

Decision implication:

```text
Promote the route from "local survivor closure" to "frontier certificate theorem hunt."

This still does not prove Collatz. The verified theorem is conditional:

all components certified
-> no dangerous frontier
-> density/minimal-survivor closure target.

The remaining hard theorem is the existence/completeness theorem:

every dynamically legal Collatz pressure-height frontier is all-certified,
meaning every recurrent bad component either
  recovers pressure,
  height-escapes,
  or triggers survivor drop.

The next wave should attack this directly. It should not add a new metaphor or another local object. It should build the bounded-to-parameterized frontier-completeness bridge:

1. generate legal pressure-height frontiers from actual Collatz residue dynamics;
2. classify every recurrent bad component by the three exits;
3. prove that unchecked/nonexpanding dangerous components cannot persist under the legal generator;
4. expose a concrete counterexample if such a component exists.

If this completeness bridge succeeds, the route moves to the final proof architecture: density-zero/minimal-survivor closure and sound pullback to ordinary Collatz. If it fails by finding a real legal dangerous component, the route must pivot or add a genuinely new invariant.
```

### R21. Bounded Pressure-Height Frontier Completeness Survives The Window-8 Kill Test

These facts come from pressure-height frontier completeness run `FK-b1d610b515` on world `W-0273193499`, campaign `C-395c6fd53b6b`, submitted in Aristotle bake `PB-5c0f6a71bc`, and digested in `PD-23276c8c3a`.

This wave was deliberately framed as a bounded kill test rather than another vocabulary wave. It generated pressure-height frontiers from the actual Collatz residue automaton through window 8 and asked whether the generated recurrent bad components were covered by the R20 certificate exits.

Local generation before Aristotle:

```text
windows checked: 1 through 8
window 1: acyclic bad subgraph
window 2: 2 recurrent bad components, 2 height-escaping, 0 dangerous, 0 unchecked
window 3: acyclic bad subgraph
window 4: 2 recurrent bad components, 2 height-escaping, 0 dangerous, 0 unchecked
window 5: 1 recurrent bad component, 1 height-escaping, 0 dangerous, 0 unchecked
window 6: 2 recurrent bad components, 2 height-escaping, 0 dangerous, 0 unchecked
window 7: 1 recurrent bad component, 1 height-escaping, 0 dangerous, 0 unchecked
window 8: 2 recurrent bad components, 2 height-escaping, 0 dangerous, 0 unchecked
```

Aristotle status:

```text
probe_count: 15
proved_count: 13
blocked_count: 0
inconclusive_count: 2
reconciled_pending_job_count: 0
```

The two inconclusive probes were submission-cap artifacts from the original Aristotle concurrency limit, not Lean/math failures:

```text
generated report count matches bounded horizon: artifact_missing
generated frontiers are all certified through bounded horizon: artifact_missing
```

The substantive probes proved:

```text
generated frontiers have no dangerous component: proved
generated frontiers have no unchecked component: proved
generated recurrent bad components are covered by exits: proved
max-window generated frontier is complete: proved
acyclic generated frontier is vacuously complete: proved
recurrent generated frontier is height-certified: proved
bounded certificate declares finite horizon only: proved
generated completeness feeds no-dangerous frontier theorem: proved
parameterized completeness would close danger at every depth: proved
counting target has no reachability field: proved
adversarial dangerous report is not complete: proved
adversarial unchecked report is not complete: proved
dangerous member refutes any completeness proof: proved
```

Interpretation:

```text
This is a real bounded-frontier win, but it is still bounded evidence.

The meaningful positive result is:

actual generated pressure-height frontiers through window 8 have no dangerous or unchecked recurrent bad components,
and every generated recurrent bad component is certified by height escape.

The meaningful guardrail result is:

dangerous or unchecked reports really do refute completeness,
the bounded certificate explicitly declares a finite horizon,
and the counting target has no reachability field.

So the route did not win by smuggling Collatz or by accepting pressure-bad components as certified. It won the bounded generated-frontier kill test.
```

Decision implication:

```text
Do not spend the next wave on larger bounded windows unless debugging a concrete counterexample.

The next serious step must be the parameterized lift:

for every dynamically legal pressure-height frontier generated by Collatz residue dynamics,
every recurrent bad component is certified by pressure recovery, height escape, or survivor drop.

If that parameterized theorem proves, R20/R21 feed directly into no-dangerous-frontier closure. If it fails, the failure should expose either:

1. a legal dangerous non-height-escaping recurrent component;
2. an unchecked component family that escapes finite SCC certification;
3. a flaw in the proposed generator-to-frontier abstraction.

The next Aristotle wave should be capped at 13 probes and must be judged as a parameterized-theorem attempt, not another bounded evidence run.
```

### R22. Parameterized Pressure-Height Completeness Schema Closes Danger Conditionally

These facts come from parameterized pressure-height completeness run `PK-d359fb4828` on world `W-0273193499`, campaign `C-956553836ea9`, submitted in Aristotle bake `PB-38d8bc6556`, and digested in `PD-4d8843e58d`.

This wave was the 13-probe theorem-lift attempt demanded after R21. It did not add larger bounded windows. It asked whether the bounded-frontier story can be expressed as an all-depth theorem schema with an explicit generator invariant and non-vacuous adversarial controls.

Status:

```text
probe_count: 13
proved_count: 13
blocked_count: 0
inconclusive_count: 0
reconciled_pending_job_count: 0
```

Verified probe outcomes:

```text
generator invariant is definable: proved
invariant implies no unchecked component at every depth: proved
invariant covers recurrent bad components by exits: proved
height-escape coverage is a complete report: proved
pressure-recovery coverage is a complete report: proved
survivor-drop coverage is a complete report: proved
invariant implies no dangerous frontier at arbitrary depth: proved
bounded window-8 certificate is an instance of the schema: proved
schema has no reachability or termination field: proved
dangerous generator violates the invariant: proved
unchecked generator violates the invariant: proved
static persistent bad frontier is rejected by dynamic invariant: proved
weak invariant exposes unchecked obstruction: proved
```

Interpretation:

```text
This is a real theorem-shape win, but it is conditional.

R22 proves the all-depth schema:

parameterized generator invariant
-> no unchecked component at every depth
-> recurrent bad components are covered by pressure recovery, height escape, or survivor drop
-> no dangerous frontier at arbitrary depth.

The adversarial controls are important:

dangerous generators violate the invariant;
unchecked generators violate the invariant;
static persistent bad frontiers are rejected;
weak invariants expose a named unchecked obstruction instead of pretending to close the proof.

So the remaining issue is no longer whether the pressure-height theorem can be stated without circularity. It can.
```

Decision implication:

```text
The bottleneck has moved cleanly to the actual-generator bridge:

actual Collatz pressure-height residue generator
-> parameterized generator invariant.

The next wave must not restate the invariant as an assumption. It should reduce the bridge to concrete dynamic facts:

1. actual residue successor relation is the generator transition relation;
2. recurrent bad components correspond to generated SCC/cycle witnesses;
3. non-height-escaping recurrent bad components are exactly nonpositive-drift obstructions;
4. uniform positive drift / exact SCC coverage implies the generator invariant;
5. adversarial static bad generators are rejected as non-generated or as violating the drift/exactness assumptions.

If this bridge proves only conditionally, the named remaining theorem should be:

uniform SCC drift/exactness lemma for actual Collatz pressure-height generator.

If the bridge finds a legal non-height-escaping recurrent bad component, the pressure-height route is in serious trouble.
```

### R23. Actual-Generator Bridge Reduces the Bottleneck to SCC Drift/Exactness

These facts come from pressure-height generator bridge run `GB-e0044e97b7` on world `W-0273193499`, campaign `C-d047c5b28b79`, submitted in Aristotle bake `PB-49bc616259`, and digested in `PD-7e1c3df725`.

All raw Aristotle projects ended with `COMPLETE_WITH_ERRORS`, but the reconciled digest recovered the submitted proof artifacts and found no proof-side failures:

```text
probe_count: 13
proved_count: 13
blocked_count: 0
inconclusive_count: 0
reconciled_pending_job_count: 0
```

Verified probe outcomes:

```text
actual residue successor relation has odd and hidden-even cases: proved
actual generator transitions are residue-successor transitions: proved
generated reports come from legal residue transitions: proved
recurrent bad component reduces to generated cycle witness shape: proved
non-height-escaping bad recurrence is nonpositive-drift obstruction: proved
uniform positive SCC drift excludes dangerous recurrence: proved
exact SCC coverage excludes unchecked recurrence: proved
drift plus exactness imply the R22 generator invariant: proved
bounded window-8 certificate is an instance of bridge assumptions: proved
bridge target has no reachability or termination field: proved
adversarial static bad generator is not actual-generated: proved
weak transition legality does not imply the invariant: proved
remaining obstruction is uniform SCC drift and exactness: proved
```

Interpretation:

```text
This is a real reduction, not a Collatz proof.

R23 proves that the post-R22 bridge can be expressed cleanly:

actual residue successor dynamics
-> pressure-height generator reports
-> recurrent bad components correspond to generated cycle/SCC witnesses
-> non-height-escaping bad recurrence is exactly a nonpositive-drift obstruction
-> uniform positive SCC drift plus exact SCC coverage imply the R22 invariant.

The guardrails also passed:

the target still has no reachability or termination field;
static bad generators are rejected as non-actual;
weak transition legality does not imply the invariant.
```

Decision implication:

```text
The bottleneck is now sharply named:

uniform SCC drift/exactness lemma for the actual Collatz pressure-height generator.

This is stronger than the previous "bridge" bottleneck. We are no longer asking whether the invariant can talk to actual residue dynamics. It can, provided the generator has uniform drift and exact SCC coverage.

The next wave should not invent another broad world. It should attack the named lemma directly:

1. define finite width-k SCCs of the actual residue successor graph;
2. define pressure-height drift around SCC cycles;
3. prove exact coverage for SCC reports, or expose the first unchecked SCC family;
4. prove positive drift for all non-height-escaping SCCs, or expose a zero/nonpositive-drift family;
5. lift the finite-width SCC statement into a parameterized width theorem.

If this named lemma proves, the pressure-height route advances to global density-zero / Composite Scarcity pullback.

If it fails with a genuine non-height-escaping nonpositive-drift SCC, this route has found its real obstruction and should pivot or add a new invariant.
```

### R24. SCC Exactness and Drift Tranches Both Passed

These facts come from the first two tranches of the SCC drift/exactness gauntlet after R23.

Exactness tranche:

```text
campaign: C-fc2998a6f4f9
run_id: SX-8d0b29d2ee
bake_run: PB-4d729fa71b
digest: PD-ca6a5b2b44
probe_count: 13
proved_count: 13
blocked_count: 0
inconclusive_count: 0
reconciled_pending_job_count: 0
```

Drift tranche:

```text
campaign: C-be4986090faf
run_id: SD-c50f253c61
bake_run: PB-d53550b908
digest: PD-06591e0e53
probe_count: 13
proved_count: 13
blocked_count: 0
inconclusive_count: 0
reconciled_pending_job_count: 0
```

Verified exactness outcomes:

```text
finite width-k pressure-height SCC witnesses are definable: proved
SCC edges are actual residue successor edges: proved
generated SCC reports come from actual generator transitions: proved
exact SCC coverage is a concrete coverage predicate: proved
unchecked SCC obstruction is explicitly named: proved
acyclic SCC reports are exact by construction: proved
recurrent reports decompose into covered or unchecked: proved
checked recurrent SCC reports satisfy exact coverage: proved
checked window-8 SCCs are exact: proved
exactness target has no reachability or termination field: proved
adversarial unchecked SCC fails exactness: proved
fake static SCC is rejected as non-actual: proved
weak legality does not imply exact coverage: proved
```

Verified drift outcomes:

```text
pressure-height drift around actual SCC cycles is definable: proved
nonpositive-drift obstruction is explicitly named: proved
height-escaping SCCs are not dangerous minimal survivors: proved
positive-drift SCCs cannot be dangerous recurrent bad components: proved
non-height-escaping recurrent bad implies drift obligation: proved
pressure-recovery exit contributes positive drift: proved
survivor-drop exit contributes positive drift: proved
pure pressure ghost recurrence is killed by height lift: proved
checked window-8 SCCs have positive drift: proved
drift target has no reachability or termination field: proved
adversarial zero-drift SCC fails positive drift: proved
adversarial nonpositive-drift SCC is named obstruction: proved
remaining drift obstruction is concrete nonpositive drift: proved
```

Interpretation:

```text
This is a strong continuation signal, but still not a Collatz proof.

The two halves of the R23 bottleneck now both have Lean-clean local theorem infrastructure:

exact SCC coverage;
positive SCC drift;
unchecked exactness obstruction;
nonpositive drift obstruction;
anti-smuggling guards for reachability and termination.

The next step is not another SCC sublemma. It is route integration:

exactness + drift
-> R23 bridge assumptions
-> R22 pressure-height invariant
-> no dangerous frontier.
```

Decision implication:

```text
Submit the integration tranche.

The integration tranche must distinguish:

1. proof-spine success: exactness + drift feed R23/R22 and no-dangerous-frontier;
2. remaining proof debt: density-zero / Composite Scarcity and ordinary Collatz pullback;
3. anti-circularity: no reachability or termination field is introduced during integration.

If route integration passes, this pressure-height route has a candidate proof spine, not a finished Collatz proof.
```

### R25. Route Integration Produces a Candidate Proof Spine

These facts come from pressure-height route integration run `RI-0c956a396e` on world `W-0273193499`, campaign `C-0b40d25be898`, submitted in Aristotle bake `PB-eff1191ab8`, and digested in `PD-6141bc819e`.

All raw Aristotle jobs again reported `COMPLETE_WITH_ERRORS`, but the reconciled digest recovered the proof artifacts and found no proof-side failures:

```text
artifact_count: 64
probe_count: 13
proved_count: 13
blocked_count: 0
inconclusive_count: 0
reconciled_pending_job_count: 0
```

Verified route-integration outcomes:

```text
integrated exactness+drift certificate is definable: proved
integrated certificate implies R23 bridge assumptions: proved
R23 bridge assumptions imply R22 pressure-height invariant: proved
R22 invariant implies no dangerous frontier: proved
exactness plus drift compose to no dangerous frontier: proved
window-8 instance composes through the route: proved
unchecked exactness obstruction blocks integration: proved
nonpositive-drift obstruction blocks integration: proved
fake static certificate is rejected: proved
integration target has no reachability or termination field: proved
density-zero Composite Scarcity remains explicit debt: proved
ordinary Collatz pullback remains explicit debt: proved
roadmap state after integration is proof spine not final proof: proved
```

Interpretation:

```text
This is the strongest verified narrowing so far.

The pressure-height route now has a candidate proof spine:

actual SCC exactness + positive SCC drift
-> R23 bridge assumptions
-> R22 pressure-height invariant
-> no dangerous pressure-height frontier.

The integration did not smuggle the final theorem:

reachability is not a field;
termination is not a field;
density-zero / Composite Scarcity is still open;
ordinary Collatz pullback is still open.
```

Decision implication:

```text
The next phase is the final global-closure / pullback phase for this route.

It should not invent another invariant unless the final phase fails. It should test:

1. no dangerous pressure-height frontier implies the density-zero / Composite Scarcity closure;
2. density-zero plus finite/base coverage rules out a nonterminating survivor family;
3. the pressure-height statement soundly pulls back to ordinary Collatz termination;
4. anti-circularity checks confirm that no reachability, termination, or unproved density assumption is hidden.

If this phase passes, we may have a formal proof architecture for Collatz.

If it fails, the failure should name exactly which final bridge is missing:

density closure;
finite exception/base coverage;
or ordinary Collatz pullback.
```

### R26. Final Closure Wave Verifies the Architecture, Not Yet an Expanded Collatz Proof

These facts come from pressure-height final closure run `FC-05860564e3` on world `W-0273193499`, campaign `C-101e19362c8b`, submitted in Aristotle bake `PB-ae72ac8b3d`, and digested in `PD-fb58dbf69e`.

All raw Aristotle jobs again reported `COMPLETE_WITH_ERRORS`, but the reconciled digest recovered the proof artifacts and found no proof-side failures:

```text
artifact_count: 53
probe_count: 13
proved_count: 13
blocked_count: 0
inconclusive_count: 0
reconciled_pending_job_count: 0
```

Direct result-bundle pull on 2026-04-16 confirms the same picture:

```text
13 / 13 local result archives contain ARISTOTLE_SUMMARY.md
13 / 13 summaries report no sorry statements
13 / 13 summaries report Main.lean builds successfully
the dashboard/status layer was misleading here; the proof artifacts themselves are clean
```

Verified final-closure outcomes:

```text
no-dangerous-frontier global closure target is definable: proved
density-zero Composite Scarcity closure is stated without reachability: proved
no dangerous frontier implies no positive-density survivor family: proved
density-zero plus finite-base coverage eliminates survivor families: proved
finite-base coverage is explicit and non-circular: proved
ordinary Collatz pullback target is definable from pressure-height closure: proved
nonterminating ordinary orbit induces dangerous frontier or survivor family: proved
no dangerous frontier plus density closure excludes induced counterexample object: proved
ordinary termination follows from pressure-height closure and base coverage: proved
adversarial density theorem that assumes termination is rejected: proved
adversarial pullback that assumes reachability is rejected: proved
final theorem target has no hidden reachability or termination fields: proved
final roadmap state exposes proved architecture or named gap: proved
```

Interpretation:

```text
This verifies the final proof architecture for the pressure-height route.

The architecture now composes:

actual SCC exactness + positive SCC drift
-> R23 bridge assumptions
-> R22 pressure-height invariant
-> no dangerous pressure-height frontier
-> density-zero / Composite Scarcity closure
-> no survivor family
-> ordinary Collatz pullback.

But this is still not a fully expanded Collatz proof.

The final wave proves the architecture is coherent and rejects obvious circular variants. It does not yet replace every certificate field with a fully expanded arithmetic derivation from first principles.
```

Decision implication:

```text
Do not run another broad invention wave.

The next work is proof hardening:

1. inline the certificate fields into concrete definitions;
2. remove scaffold-only fields from the final closure objects;
3. prove the density-zero / Composite Scarcity lemma from the earlier pressure-height machinery, not as a field;
4. prove finite/base coverage concretely;
5. prove the ordinary Collatz pullback as a theorem over Nat, not as a named certificate predicate;
6. keep the anti-circularity tests in place.

If this hardening succeeds, the result may become a genuine formal Collatz proof attempt.

If hardening fails, the failure is no longer "where should we search?" but exactly which certificate field cannot be expanded.
```

### R27. Descent Core Extracted and First Concrete Exit Families Hardened

These facts come from local Lean hardening audits:

```text
scripts/run_collatz_descent_core_audit.py
scripts/run_collatz_exit_bridge_hardening.py
```

Descent-core result:

```text
descent_core_compiles: true
exit_bridge_compression_compiles: true
raw_no_dangerous_to_descent_compiles: false
```

Concrete exit-bridge result:

```text
concrete_exit_cases_compile: true
raw_odd_three_mod_four_family_compiles: false
```

Verified Lean facts:

```text
eventual positive descent below n implies ordinary Collatz termination by strong induction: proved
if the pressure-height route supplies exit existence and exit soundness, Collatz follows: proved
every positive even number 2*q descends in one Collatz step: proved
every number 4*a+1 with a>0 descends in three Collatz steps: proved
every number 16*c+3 descends in six Collatz steps: proved
every number 32*d+11 descends in eight Collatz steps: proved
every number 32*d+23 descends in eight Collatz steps: proved
every number 128*e+7 descends in eleven Collatz steps: proved
every number 128*e+15 descends in eleven Collatz steps: proved
every number 128*e+59 descends in eleven Collatz steps: proved
the covered concrete exit families imply actual Nat-level positive descent: proved
n=3 has an explicit descent witness: proved
n=7 has an explicit descent witness: proved
n=27 is not covered by the current parametric exit families: proved
```

Interpretation:

```text
This is the first hardening step that removes some scaffold rather than adding another architecture layer.

The Collatz proof target has been compressed to:

for every n > 1, produce k such that
0 < collatz^[k](n) < n.

Once that is proved, ordinary Collatz termination follows by strong induction.

The first concrete exits are now real arithmetic Lean theorems, not Bool certificate fields:

even numbers descend immediately;
numbers congruent to 1 mod 4, except n=1, descend after the odd step and two halvings;
numbers congruent to 3 mod 16 descend after six Collatz steps;
numbers congruent to 11 or 23 mod 32 descend after eight Collatz steps:
numbers congruent to 7, 15, or 59 mod 128 descend after eleven Collatz steps:

collatz^[6](16*c+3) = 9*c+2 < 16*c+3.
collatz^[8](32*d+11) = 27*d+10 < 32*d+11.
collatz^[8](32*d+23) = 27*d+20 < 32*d+23.
collatz^[11](128*e+7) = 81*e+5 < 128*e+7.
collatz^[11](128*e+15) = 81*e+10 < 128*e+15.
collatz^[11](128*e+59) = 81*e+38 < 128*e+59.
```

Decision implication:

```text
The remaining hard bridge is now more sharply visible:

the unresolved odd residue branches at the next frontier:
27, 31, 39, 47, 63, 71, 79, 91, 95, 103, 111, 123, and 127 mod 128.

The first two concrete exit rules did not solve the 4*a+3 family, but six infinite odd subfamilies are now closed.
The remaining mod-128 frontier is exactly where repeated parity-block / pressure-height reasoning must produce a later descent.

The next hardening target should be:

prove concrete parity-block descent theorems for the remaining mod-128 frontier,
or extract the affine rewrite system behind those branches and prove its pressure-height measure is well-founded.

Local compass note:

scripts/run_collatz_affine_rewrite_compass.py is not a Lean proof, but it already shows that
some unresolved mod-128 roots, including 39, 79, 95, and 123, admit composed affine certificates
from the currently proved rewrite rules. That is evidence the right object is an affine-family
rewrite system, not just a larger residue table.

Do not return to density-zero-first reasoning unless this descent route fails.
Density-zero can leave sparse counterexamples; eventual descent kills them.
```
