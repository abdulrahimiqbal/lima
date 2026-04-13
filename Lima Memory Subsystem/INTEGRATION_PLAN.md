# Exact integration plan for the current LIMA repo

Based on the current runtime path:

`FastAPI -> CampaignService -> Manager -> Executor -> Learner/Frontier -> Database`

## Minimal first integration

### File: `app/service.py`
Add a `MemoryService` instance to `CampaignService.__init__`.

Suggested wiring:
- create `SqliteKnowledgeStore` first for easy adoption
- later swap to Postgres-backed implementation

Then patch:
- `create_campaign()`
- `_build_context()`
- `step_campaign()`

### File: `app/config.py`
Add:
- `MEMORY_DB_PATH`
- later `MEMORY_DATABASE_URL`

### File: `app/main.py`
Optionally expose:
- `/api/campaigns/{id}/memory-summary`
- `/api/campaigns/{id}/memory-packet`

## Phase 1: mirror writes only

- Keep existing `Database` class untouched.
- After creating a campaign row, mirror into memory.
- After each manager decision, mirror into memory.
- After each execution result, mirror into memory.

## Phase 2: read manager context from memory

Replace `_build_context()` with:
- `memory.get_manager_packet()`
- transform packet into current `ManagerContext`

## Phase 3: project legacy campaign summary from memory

Keep `CampaignRecord` as a UI/API projection, not the long-term source of truth.

## What not to do yet

- do not delete the current `Database` class immediately
- do not rewrite the entire app around a graph database
- do not move the worker/executor interface first
- do not require every ancillary file to use the new system on day 1
