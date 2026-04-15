
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
