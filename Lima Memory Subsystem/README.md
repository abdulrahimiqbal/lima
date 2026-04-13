# LIMA Memory Subsystem

This is a self-contained knowledge / memory layer designed to sit at the repo root of the `lima` codebase.

It is intentionally independent from the current `app/` runtime so you can adopt it gradually.

## What it stores

It treats research state as four things:

1. **Events**
   - what happened and when
2. **Graph nodes / edges**
   - problems, frontier nodes, worlds, claims, obligations, results, blockers, paper units
3. **Artifacts**
   - raw Aristotle requests/responses, Lean snippets, paper passages, notes
4. **Manager packets**
   - compact, structured context assembled from the above

## Why this fits LIMA

LIMA's ethos is:
- hallucinate boldly
- ground ruthlessly
- learn structurally

That means memory cannot just be a blob of app state.
It needs to preserve:
- provenance
- status
- versionable world models
- structured links between claims, obligations, results, and papers

## How it integrates into the current repo

The best seam is `app/service.py`:

- `create_campaign()`
  - mirror campaign creation into `MemoryService.create_campaign()`
  - mirror frontier seed into `MemoryService.seed_frontier()`

- `_build_context()`
  - replace the current campaign-row-only context builder
  - use `MemoryService.get_manager_packet()` to build richer manager context

- `step_campaign()`
  - right after `manager.decide(context)`, call `record_manager_decision()`
  - right after `executor.run(...)`, call `record_execution_result()`
  - continue updating the legacy `CampaignRecord` as a projection during migration

## Deployment recommendation

### Main app
Keep the FastAPI app on Railway.

### Canonical database
Use Railway Postgres for the long-term canonical memory store.

### Heavy artifact / paper parsing
Optional separate service later if needed.

This package includes:
- a working SQLite implementation for fast integration/testing
- a Postgres schema for the production migration path

## Migration strategy

1. Mirror writes into `lima_memory` while keeping the current SQLite campaign row.
2. Change `_build_context()` to read from the memory subsystem.
3. Gradually make frontier / learner logic consume memory-layer projections.
4. Move to Postgres as the source of truth.
