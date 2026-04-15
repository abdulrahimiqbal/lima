
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
