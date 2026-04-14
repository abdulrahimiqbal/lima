# World Evolution Implementation Summary

## Overview

This upgrade extends Lima from single-world theorem search into a population-level **world-evolution engine under formal pressure**.

The loop is:

```text
invent -> distill -> anti-circularity screen -> falsify -> compile probes -> score -> mutate survivors
```

The purpose is not to claim a theorem solved from invention. The purpose is to let aggressive mathematical imagination generate many worlds, then force those worlds through concrete filters: anti-circularity, falsifiers, Lean-clean probe compilation, fitness scoring, lineage tracking, and scoped proof debt.

## New Endpoint

```http
POST /api/campaigns/{campaign_id}/world-evolution/run
```

Default Collatz-scale request:

```json
{
  "generations": 3,
  "worlds_per_generation": 80,
  "survivors_per_generation": 8,
  "mutations_per_survivor": 6,
  "wildness": "extreme",
  "max_formal_probes_per_generation": 12,
  "max_evidence_probes_per_generation": 20,
  "promote_best_survivor": true
}
```

The endpoint returns a `WorldEvolutionRun` summary with counts for raw worlds, distilled worlds, circular worlds, survivors, formal probes, evidence probes, best world, promoted world, solve status, and learning summary.

Important boundary: `solve_status` remains `not_solved` unless Lima's existing formal solved criteria are satisfied outside this endpoint. In v1, world evolution promotes a survivor and scopes debt; it does not prove Collatz.

## New Models

Added to `app/schemas.py`:

- `MiracleObject`
- `CircularityAssessment`
- `WorldFitness`
- `EvolutionLineage`
- `FormalProbe`
- `WorldMutation`
- `WorldGeneration`
- `WorldEvolutionRunRequest`
- `WorldEvolutionRun`

Extended:

- `RawWorldInvention` now carries optional miracle object, hidden circularity risk, and probe prompts.
- `DistilledWorld` now carries miracle object, anti-circularity assessment, fitness, lineage, and formal probes.
- `DistilledWorldStatus` now includes `circularity_failed`.

## Service Layer

Added `app/world_evolution.py` with `WorldEvolutionService`.

Responsibilities:

- create generation batches through `InventionService`
- distill raw inventions
- run cheap falsifiers
- attach miracle objects
- run deterministic anti-circularity screening
- score fitness
- select survivors
- compile tiny formal probes
- record mutations and lineages
- record run/generation/probe/mutation research nodes
- summarize latest run for the operator brief

`CampaignService` now owns `self.world_evolution` and exposes `run_world_evolution()`.

Promotion behavior:

- installs the best survivor as `current_world_program`
- sets `active_world_id`
- scopes `proof_debt_ledger` to the top 12 active debt items
- recomputes `resolved_debt_ids`
- never marks the campaign solved
- records a `world_evolution_world_promoted` event

## Anti-Circularity

The deterministic checker rejects obvious smuggling patterns:

- empty ontology
- bridge restates target, for example "if Collatz then Collatz"
- target theorem restated under renamed terms
- global descent asserted before the measure/object is defined
- "always decreases" claims without concrete definitions, simulation, encoding, or maps

Worlds with high declared smuggling risk may remain `unclear`, but they are not promotable if the risk is `high`.

## Formal Probes

For each survivor, v1 compiles tiny Lean-clean probes:

- `definition_probe`: can the invented object be stated as a concrete Lean object?
- `simulation_probe`: does the standard Collatz step have a clean one-step shape?
- `bridge_probe`: can the world-to-target bridge be represented as an implication shape?

These probes are recorded as `FormalProbe` research nodes with status `compiled`.

Boundary: v1 compiles and records probes but does not synchronously submit dozens of live Aristotle jobs from one world-evolution request.

## Mutation and Lineage

Each survivor or failed world can produce mutation records. Failure types map to targeted repairs:

- `empty_ontology` -> force concrete objects and definitions
- `bridge_restates_target` -> replace bridge with an explicit interpretation map
- `target_restatement` -> weaken into definability and one-step simulation probes
- `unproved_global_descent` -> replace global descent with local monotonicity probes
- `cheap_falsifier` -> keep high-scoring component and mutate failed prediction
- `survivor_refinement` -> sharpen miracle object and compile a smaller bridge probe

Later generations attach lineage to parent survivor world IDs and record dead patterns avoided.

## Operator Brief and UI

The operator brief now includes:

```json
{
  "world_evolution": {
    "latest_run_id": "WE-...",
    "generations_completed": 3,
    "survivor_count": 8,
    "best_world_label": "...",
    "top_failure_modes": ["bridge_restates_target", "empty_ontology"],
    "promoted_world_id": "W-...",
    "formal_probe_count": 36,
    "circular_world_count": 20,
    "learning_summary": "..."
  }
}
```

The HTML operator panel renders these metrics and includes a guarded "Run world evolution" action using the default Collatz-scale request.

## Constitution and Policy

`MANAGER_CONSTITUTION.md` now requires population-level world evolution under formal pressure and clarifies that "smaller world" means smaller, sharper, or more checkable proof burden, not necessarily a less imaginative ontology.

`MANAGER_POLICY.json` is now version `1.2.0` and includes `world_evolution_policy` defaults for generations, survivor count, probe caps, promotion requirements, and failure-to-mutation mappings.

## Collatz Validation Run

A local Collatz-shaped validation run used:

```json
{
  "generations": 3,
  "worlds_per_generation": 80,
  "survivors_per_generation": 8,
  "mutations_per_survivor": 6,
  "wildness": "extreme",
  "max_formal_probes_per_generation": 12,
  "max_evidence_probes_per_generation": 20,
  "promote_best_survivor": true
}
```

Observed local result:

```json
{
  "solve_status": "not_solved",
  "generations_completed": 3,
  "raw_world_count": 240,
  "distilled_world_count": 240,
  "survivor_count": 8,
  "circular_world_count": 24,
  "formal_probe_count": 36,
  "promoted_world_id": "W-...",
  "critical_debt_count": 8
}
```

This satisfies the v1 acceptance shape: many worlds, multiple survivors, circular worlds killed, formal probes compiled, a survivor promoted, active debt bounded, and no false solved declaration.

## Tests

Added `tests/test_world_evolution.py` covering:

- endpoint run creates generations and promotes scoped debt
- anti-circularity rejects restated Collatz worlds
- formal probe compiler emits Lean-clean probes
- mutations and lineage are recorded

Full suite target:

```bash
PYTHONPATH=. .venv_test/bin/pytest -q
```
