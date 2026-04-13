Use this prompt in your IDE agent to transition the current `lima` repo to the new memory subsystem surgically.

---

You are modifying the repo `abdulrahimiqbal/lima`.

A new top-level subsystem has been added at repo root:

- `lima_memory/`
- `README.md`
- `INTEGRATION_PLAN.md`

Your job is to integrate it surgically into the existing app without rewriting the app.

## Current repo facts
The current app flow is:
- `app/main.py` creates `Database`, `CampaignService`, and `CampaignWorker`
- `app/service.py` drives the campaign loop
- `app/manager.py` builds manager decisions
- `app/executor.py` runs Aristotle/mock execution
- `app/db.py` stores `CampaignRecord` plus events and policy snapshots in SQLite JSON blobs

## Goal
Make the new memory subsystem the canonical research-state layer gradually, while keeping the existing app stable.

## Rules
- Do not rewrite the entire app.
- Do not delete the existing `Database` yet.
- Keep the current API and UI working.
- Integrate the new subsystem through `CampaignService`.
- Mirror writes first, then change reads.
- Keep deployment Railway-friendly.

## Exact implementation steps

### 1. Add config
In `app/config.py`, add:
- `MEMORY_DB_PATH` with default `./data/lima_memory.db`
- optional `MEMORY_DATABASE_URL` placeholder for later Postgres migration

Do not remove `DATABASE_PATH` yet.

### 2. Instantiate the memory subsystem
In `app/service.py`:
- import `MemoryService` and `SqliteKnowledgeStore` from the new root package
- in `CampaignService.__init__`, create:
  - `self.memory_store = SqliteKnowledgeStore(settings.memory_db_path)`
  - `self.memory = MemoryService(self.memory_store)`

### 3. Mirror campaign creation
In `create_campaign()`:
- after `self.db.create_campaign(...)`, call:
  - `self.memory.create_campaign(campaign_id=campaign.id, title=campaign.title, problem_statement=campaign.problem_statement, operator_notes=campaign.operator_notes)`
- then seed the root frontier into memory:
  - for each frontier node in `campaign.frontier`, call `self.memory.seed_frontier(...)`
- add a normal event as already done

### 4. Mirror manager decisions
In `step_campaign()`:
- after `decision = self.manager.decide(context)`, call:
  - `self.memory.record_manager_decision(campaign_id=campaign.id, tick=campaign.tick_count + 1, decision=decision.model_dump())`

### 5. Mirror execution results
Still in `step_campaign()`:
- after `result = self.executor.run(campaign, decision)`, call:
  - `self.memory.record_execution_result(campaign_id=campaign.id, tick=campaign.tick_count + 1, decision=decision.model_dump(), result=result.model_dump())`

If raw Aristotle request/response are available, pass them too.

### 6. Add memory-backed context building
Do not remove the current context builder immediately.
Instead:
- add a new helper in `CampaignService`, e.g. `_build_context_from_memory(campaign)`
- use `self.memory.get_manager_packet(campaign.id)`
- convert that packet into the existing `ManagerContext`
- include:
  - frontier from `active_frontier`
  - current candidate answer in the problem/context payload if useful
  - operator notes from memory packet
  - recent results / paper units folded into memory.policy_notes or an added field if you extend `ManagerContext`

Then:
- behind a small feature flag like `USE_MEMORY_CONTEXT`, switch `step_campaign()` to use the memory-backed context builder

### 7. Add inspection endpoints
In `app/main.py`, add:
- `GET /api/campaigns/{campaign_id}/memory-summary`
- `GET /api/campaigns/{campaign_id}/memory-packet`

These should return:
- `self.memory.project_campaign_summary(campaign_id)`
- `self.memory.get_manager_packet(campaign_id).asdict()`

Do not break existing endpoints.

### 8. Preserve legacy projection
Continue writing:
- `CampaignRecord`
- `last_manager_context`
- `last_manager_decision`
- `last_execution_result`

The legacy campaign row remains the projection/cache for now.

### 9. Tests
Add focused tests:
- memory campaign creation mirror
- manager decision mirror
- execution result mirror
- memory summary endpoint
- memory packet endpoint
- feature-flagged memory-backed context path

### 10. Railway
Keep the main app on Railway.
For now:
- the main app remains one service
- the new memory DB can be SQLite during transition
- long term, move `lima_memory` to Postgres

Do not force Postgres in this patch unless it is already easy in the repo.

## Final output required from you
After implementing, report:
1. files changed
2. exact integration points
3. feature flags added
4. new endpoints added
5. tests added and passing
6. any TODOs for Postgres migration
