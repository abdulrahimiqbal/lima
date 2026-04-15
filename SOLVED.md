# Lima Collatz Verified Facts Ledger

This file is deliberately conservative. It is not a solution log and it must not contain narrative confidence as truth.

A fact may be added here only if it is one of:

```text
- formally proved by Lean/Aristotle,
- directly witnessed by deterministic computation with stated bounds,
- a negative/process fact about a failed proof attempt that is supported by diagnostics.
```

## Current Status

```text
Collatz solved: no
Active campaign: C-fbfa819eec15 / Collatz World Evolution Test 002
Active world: W-0273193499 / Alien State-Space Encoding 1
Current bottleneck: non-circular rank/certificate/descent object
```

## Verified Formal Contact Facts

These facts show that Lima can express the promoted world in Lean and connect it to the standard Collatz step. They do not prove Collatz.

### F1. Collatz Step Is Lean-Definable

Lima has repeatedly compiled/proved Lean definitions of the Collatz step shape:

```lean
def collatzStep (n : Nat) : Nat :=
  if n % 2 = 0 then n / 2 else 3*n + 1
```

Status:

```text
verified by Aristotle probe digestion
```

### F2. Encoding/Decoding The Promoted World Is Definable

For the promoted world `W-0273193499`, Lima proved that a simple fiber encoding/decoding skeleton is Lean-clean.

Representative shape:

```lean
structure FinalFiber where
  value : Nat

def encode (n : Nat) : FinalFiber := { value := n }
def decode (s : FinalFiber) : Nat := s.value

theorem decode_encode (n : Nat) : decode (encode n) = n := by
  rfl
```

Status:

```text
proved in final experiment controls
```

### F3. One-Step World Simulation Is Definitional For The Current Encoding

The promoted encoding can simulate one Collatz step by construction:

```lean
def worldStep (s : FinalFiber) : FinalFiber :=
  encode (collatzStep (decode s))

theorem one_step_simulation (n : Nat) :
  decode (worldStep (encode n)) = collatzStep n := by
  rfl
```

Status:

```text
proved in final experiment controls
```

Interpretation:

```text
This confirms formal contact, not mathematical leverage.
```

### F4. Odd-Branch Shape Is Lean-Proveable

The final experiment proved the odd branch shape for the encoded Collatz step.

Status:

```text
proved by Aristotle in final experiment
```

Interpretation:

```text
This is a useful sanity check but not a route to Collatz by itself.
```

### F5. The Simple Bridge From World Terminality To Reachability Is Proveable

Given a hypothesis that every encoded positive natural is world-terminal, Lima proved the pullback shape to reachability.

Status:

```text
proved by Aristotle in final experiment
```

Interpretation:

```text
This bridge is structurally clean, but the hypothesis still contains the hard work.
```

### F6. Circular/Smuggled Bridges Can Be Detected As Identity Bridges

Lima proved a probe showing that defining terminality as reachability is merely an identity bridge.

Status:

```text
proved by Aristotle in final experiment
```

Interpretation:

```text
This is a useful anti-smuggling test. It does not solve Collatz; it protects the system from fake bridges.
```

### F7. Positivity Of One-Step Collatz Trajectories Is Proveable

The final experiment proved that positive inputs remain positive after one Collatz step.

Status:

```text
proved by Aristotle in final experiment
```

Interpretation:

```text
This removes one possible escape hatch for descent arguments, but it is not enough for global termination.
```

## Verified Negative / Bottleneck Facts

### N1. The Exact Pullback Target Remains Unproved

The direct theorem shape remains blocked:

```lean
theorem collatz_pullback_target :
  forall n : Nat, n > 0 -> reachesOne n := by
  sorry
```

Status:

```text
blocked / partial_proof in final experiment digest
```

Interpretation:

```text
The system has not solved Collatz. Any result claiming otherwise is invalid unless this debt is closed non-circularly.
```

### N2. Encoding Alone Is Not A Solution

The promoted world can encode and simulate Collatz, but this only moves the problem unless it provides a non-circular descent/certificate/invariant.

Status:

```text
supported by final experiment: controls proved, exact target blocked
```

### N3. Current Main Missing Object Is A Non-Circular Rank/Certificate

The strongest current reduction is:

```text
Find a rank/certificate/invariant that descends or certifies reachability without assuming reachability.
```

Status:

```text
supported by world-evolution failure mode `unproved_global_descent` and final experiment results
```

## Open / Not Yet Verified

These are not facts yet.

```text
- Existence of a strict descent rank for Collatz.
- Existence of a non-circular certificate transformer.
- A proof that a proposed rank/certificate implies eventual reachability.
- Any global proof that all positive integers reach 1.
```

## Current Experiment Queue

Rank/certificate hunt submitted on 2026-04-15:

```text
run_id: RH-3959e21bac
new Aristotle jobs: 8
purpose: falsify naive ranks and force a non-circular descent/certificate candidate
```

One previous final-rank job is also still running in the background.

## Roadmap Link

See the zoom-out flow and decision gates:

```text
docs/COLLATZ_ROADMAP.md
```
