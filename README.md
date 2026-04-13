# Lima Learning

Lima Learning is an experimental research-loop service for conjecture exploration. A manager proposes bounded next moves, a submission gate constrains scope/channel risk, and an executor records outcomes (formal or evidence-only) into the `lima_memory` store. It is deployable and actively tested, but it is not a guaranteed theorem prover and should be treated as an evolving system.

## Maturity

- Stage: prototype with production-style deployment plumbing.
- Stable for iterative experimentation.
- Not a safety-certified or proof-complete system.

## Architecture Overview

1. Manager (`app/manager.py`): creates `ManagerDecision` from context and policy.
2. Submission gate (`app/obligation_analysis.py`): classifies obligations and enforces channel/complexity limits.
3. Executor (`app/executor.py`): runs proof jobs through a proof adapter and bounded evidence jobs locally.
4. Learning (`app/learner.py`, `app/frontier.py`): updates memory/frontier state from verdicts.
5. Canonical storage (`lima_memory/*`): campaigns, frontier nodes, events, candidate answers, policy snapshots.

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
- Mocked / non-formal:
  - Mock proof adapter outcomes
  - Local bounded evidence channel (records evidence, not formal proof)

## Frontier and Candidate Answers

- Canonical frontier state is persisted as `FrontierNode` entries in `lima_memory`.
- Campaign reconstruction loads all persisted frontier nodes with stable IDs.
- Candidate conjecture state is persisted as `current_candidate_answer` on campaign payload and surfaced in:
  - API campaign responses
  - UI “Current candidate answer” panel

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

## Troubleshooting

### Why did my conjecture disappear?

- Check `GET /api/campaigns/{id}` and `GET /api/campaigns/{id}/memory-packet`.
- Frontier IDs are stable and persisted; if UI looks stale, refresh selected campaign.
- Candidate answers are shown separately from frontier nodes in the UI.

### Why is the executor inconclusive?

- Common causes:
  - timeout
  - excessive scope
  - evidence-only execution path
  - mock mode (non-formal by design)
- Inspect `last_execution_result.failure_type`, `rejected_reasons`, and recent events.

### Why does `/readyz` fail in strict live mode?

- `STRICT_LIVE_ARISTOTLE=true` requires:
  - `EXECUTOR_BACKEND=aristotle`
  - valid `ARISTOTLE_API_KEY`
  - successful strict probe to Aristotle reachability/auth path
