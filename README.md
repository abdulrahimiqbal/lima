# Lima Learning

Lima Learning is an experimental research-loop service for conjecture exploration. A manager proposes bounded next moves, a submission gate constrains scope/channel risk, and an executor records outcomes (formal or evidence-only) into the `lima_memory` store. It is deployable and actively tested, but it is not a guaranteed theorem prover and should be treated as an evolving system.

## Recent Changes (v1.1.0)

The system has been transformed from a bounded evidence collector into a more credible theorem-search loop:

- **Honest Formalization**: Natural-language obligations are no longer converted into fake `theorem ... : True := by` stubs. Obligations without formal statements fail honestly with `formalization_failed`.
- **Fixed Verdict Semantics**: Aristotle `FAILED` status now produces `blocked/proof_failed` instead of `refuted`. Only explicit counterexample evidence produces mathematical refutation.
- **Mixed Obligation Splitting**: Mixed proof+compute obligations are automatically split into separate proof and evidence obligations instead of being rejected.
- **Evidence-to-Proof Escalation**: After repeated `evidence_only` results (default: 3 in a row), the system spawns proof-oriented formalization work.
- **Adaptive Budgeting**: Proof and evidence budgets adapt based on recent failure patterns (evidence streaks, formalization failures, timeouts).
- **Improved Frontier Spawning**: Different failure modes (`evidence_only`, `formalization_failed`, `proof_failed`, `timeout`) trigger targeted child nodes.
- **Structured Obligations**: New `FormalObligationSpec` model supports explicit statements, imports, variables, assumptions, and Lean declarations. Backward compatible with string obligations.

## Maturity

- Stage: prototype with production-style deployment plumbing.
- Stable for iterative experimentation.
- Not a safety-certified or proof-complete system.

## Architecture Overview

1. Manager (`app/manager.py`): creates `ManagerDecision` from context and policy.
2. Submission gate (`app/obligation_analysis.py`): classifies obligations, splits mixed obligations, enforces channel/complexity limits with adaptive budgeting.
3. Executor (`app/executor.py`): runs proof jobs through a proof adapter and bounded evidence jobs locally. Fails honestly when formalization is incomplete.
4. Learning (`app/learner.py`, `app/frontier.py`): updates memory/frontier state from verdicts, tracks evidence/formalization/timeout streaks, spawns targeted follow-up work.
5. Canonical storage (`lima_memory/*`): campaigns, frontier nodes, events, candidate answers, policy snapshots.

## Key Behavioral Changes

### Formalization
- Obligations must contain structured formal statements or valid Lean code to be sent to Aristotle.
- Unstructured natural-language obligations return `blocked/formalization_failed` instead of generating meaningless theorems.
- After formalization failures, the system spawns "state clean formal claim" child nodes.

### Verdict Semantics
- `proved`: Aristotle completed successfully without `sorry`.
- `refuted`: Only when explicit counterexample evidence is found.
- `blocked/proof_failed`: Aristotle could not find a proof (does NOT mean the theorem is false).
- `blocked/formalization_failed`: Obligation lacks formal statement.
- `blocked/partial_proof`: Aristotle completed but output contains `sorry`.
- `inconclusive/evidence_only`: Bounded evidence collected, not a formal proof.
- `inconclusive/timeout`: Proof attempt timed out (rare with new polling system).
- `inconclusive/budget_exhausted`: Aristotle ran out of budget.
- `inconclusive/canceled`: Aristotle job was canceled.

### Evidence-to-Proof Escalation
- System tracks `evidence_streaks` per frontier node.
- After 3 consecutive `evidence_only` results, spawns "formalize the invariant" child node.
- Evidence budget is reduced after evidence streaks to reserve capacity for proof work.

### Adaptive Budgeting
- Proof budget reduced after repeated timeouts.
- Evidence budget reduced after repeated evidence-only results.
- Budget decisions recorded in plan metadata for transparency.

## Runtime Modes

- `rules + mock`
  - `MANAGER_BACKEND=rules`
  - `EXECUTOR_BACKEND=mock`
  - No live Aristotle calls.
  - Mock mode never returns fake formal `proved`/`refuted` outcomes.
- `llm + mock`
  - `MANAGER_BACKEND=llm`, `LLM_API_KEY` set
  - `EXECUTOR_BACKEND=mock`
  - Real planning, non-formal execution outcomes.
- `llm + live Aristotle`
  - `MANAGER_BACKEND=llm`, `LLM_API_KEY` set
  - `EXECUTOR_BACKEND=aristotle` (or legacy alias `http`)
  - `ARISTOTLE_API_KEY` required
  - `aristotlelib` required (installed via `requirements.txt`)

## Aristotle Integration (Actual)

- Integration path: `aristotlelib` SDK (not a direct repository-level HTTP verify adapter).
- Executor uses a small proof adapter boundary:
  - `MockProofAdapter`
  - `AristotleSdkProofAdapter`
- **Durable Submit-and-Poll Workflow**: Aristotle proof jobs are now long-running external jobs that survive process restarts:
  - Proof jobs are submitted once and return immediately without blocking
  - Job state is persisted in campaign payload as `pending_aristotle_job`
  - Future `step_campaign()` calls poll the existing job until completion
  - While a proof job is in-flight, no new manager decision is created for that campaign
  - Only terminal results (complete, failed, out_of_budget, etc.) finalize memory/frontier updates
  - `ARISTOTLE_TIMEOUT_SECONDS` is now used only for individual network requests, not proof completion deadlines
  - `ARISTOTLE_POLL_INTERVAL_SECONDS` controls polling cadence (default: 10s)
- Strict live probe (`STRICT_LIVE_ARISTOTLE=true`) performs:
  - SDK import + key presence check
  - lightweight authenticated reachability check to `${ARISTOTLE_BASE_URL}/healthz` when `ARISTOTLE_BASE_URL` is set
- Limitation: strict probe validates reachability/auth path, not a full theorem run.

## Health vs Readiness

- `GET /healthz`
  - Process-level heartbeat.
- `GET /readyz`
  - Memory store must be reachable.
  - If `STRICT_LIVE_ARISTOTLE=true`:
    - executor backend must be live Aristotle mode
    - strict Aristotle probe must pass

## API Protection

- Write endpoints can be protected with `OPERATOR_API_KEY`.
- When set, mutating API routes require header `X-API-Key: <OPERATOR_API_KEY>`.
- Read-only endpoints (`/healthz`, `/readyz`, list/get routes) remain open unless guarded externally.

## What Is Real vs Mocked

- Real:
  - Manager decision loop (rules or LLM)
  - Memory persistence in SQLite/Postgres through `lima_memory`
  - Aristotle SDK path when enabled/configured
  - Honest formalization failure detection
  - Evidence-to-proof escalation logic
  - Adaptive budgeting
- Mocked / non-formal:
  - Mock proof adapter outcomes
  - Local bounded evidence channel (records evidence, not formal proof)

## Data Source of Truth

- Production campaign state (including latest `tick_count`, such as long-running Collatz campaigns) is stored in **Railway Postgres**.
- Local files like `data/lima_memory.db` and `data/lima_learning.db` are local/dev snapshots and can lag behind production.
- If local UI/API output disagrees with Railway (for example, local tick is low but production tick is much higher), treat Railway Postgres as authoritative.

## Frontier and Candidate Answers

- Canonical frontier state is persisted as `FrontierNode` entries in `lima_memory`.
- Campaign reconstruction loads all persisted frontier nodes with stable IDs.
- Candidate conjecture state is persisted as `current_candidate_answer` on campaign payload and surfaced in:
  - API campaign responses
  - UI "Current candidate answer" panel

## Prerequisites for Live Aristotle Mode

- `ARISTOTLE_API_KEY`
- `EXECUTOR_BACKEND=aristotle`
- Optional but recommended for strict readiness: `ARISTOTLE_BASE_URL`
- Optional but recommended in deployment: `STRICT_LIVE_ARISTOTLE=true`
- Network egress to Aristotle service

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. pytest -q
uvicorn app.main:app --reload
```

## GitHub -> Railway Auto Deploy

Pushes to `main` deploy automatically through `.github/workflows/deploy-railway.yml`.

Set these GitHub repository secrets so the workflow can deploy non-interactively:

- `RAILWAY_TOKEN`: project token from Railway
- `RAILWAY_PROJECT_ID`: target Railway project ID
- `RAILWAY_ENVIRONMENT_ID`: target Railway environment ID (for example, production)
- `RAILWAY_SERVICE_ID`: target Railway service ID

## Known Limitations

- A successful Aristotle run can still be incomplete if generated Lean contains unresolved `sorry`; this is mapped to `blocked/partial_proof`.
- Evidence-only and mock paths are intentionally conservative and often return `inconclusive`.
- Strategy quality depends heavily on policy and prompting.
- Natural-language-to-Lean translation is not attempted; obligations must provide structured formal statements.

## Troubleshooting

### Why did my conjecture disappear?

- Check `GET /api/campaigns/{id}` and `GET /api/campaigns/{id}/memory-packet`.
- Frontier IDs are stable and persisted; if UI looks stale, refresh selected campaign.
- Candidate answers are shown separately from frontier nodes in the UI.

### Why is the executor inconclusive?

- Common causes:
  - timeout (rare with new polling system - only for terminal timeouts)
  - excessive scope
  - evidence-only execution path
  - formalization_failed (obligation lacks formal statement)
  - budget_exhausted (Aristotle ran out of budget)
  - mock mode (non-formal by design)
- Inspect `last_execution_result.failure_type`, `rejected_reasons`, and recent events.
- Check for `pending_aristotle_job` in campaign state - if present, the job is still running.

### Why is my campaign stuck with a pending Aristotle job?

- Check `GET /api/campaigns/{id}` for `pending_aristotle_job` field.
- If present, the campaign is waiting for Aristotle to complete the proof.
- The worker polls the job automatically on each tick.
- Check `poll_count` and `last_polled_at` to see polling activity.
- Check `status` field: `submitted`, `running`, `complete`, `failed`, etc.
- If the job appears stuck, check Aristotle service status and logs.

### Why does `/readyz` fail in strict live mode?

- `STRICT_LIVE_ARISTOTLE=true` requires:
  - `EXECUTOR_BACKEND=aristotle`
  - valid `ARISTOTLE_API_KEY`
  - successful strict probe to Aristotle reachability/auth path

### Why are my obligations being rejected as "formalization_failed"?

- The system now requires structured formal statements or valid Lean code.
- Natural-language obligations without formal statements fail honestly.
- Provide obligations with `statement`, `lean_declaration`, or use `FormalObligationSpec` with explicit formal content.
- After formalization failures, the system will spawn child nodes to help state claims cleanly.
