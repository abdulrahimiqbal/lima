# Lima Learning - Production Ready

A production-ready LIMA (Language Interface for Mathematical Analysis) service designed for deployment on Railway and integration with the Aristotle formal verifier.

## Core Features

- **Speculative Strategist Manager**: The manager (LLM) aggressively proposes candidate answers, worlds, and claims, reducing them into formal obligations.
- **Obligation Analysis + Submission Gate**: Every obligation is analyzed for scope, runtime risk, and channel before execution.
- **Separated Execution Channels**: Small proof jobs go to Aristotle; bounded finite checks run through a computational evidence channel.
- **Runtime-Aware Learning**: Timeout, excessive-scope, and mixed-channel failures are recorded and used to force claim shrinking.
- **Self-Improvement Loop**: A separate loop reviews campaign history and proposes policy patches to optimize strategy.
- **Persistent State**: Full campaign state persistence (frontier, memory, candidate answers, policy history) using SQLite.
- **Deployment Ready**: Configured for Railway with health checks, readiness probes, and connectivity smoke tests.

## System Architecture

The LIMA system operates as a closed loop between strategic speculation and formal verification:

1.  **Manager**: Uses `MANAGER_CONSTITUTION.md` and `MANAGER_POLICY.json` to speculate on the problem frontier.
2.  **Submission Gate**: Analyzes obligations, rejects excessive scope, splits proof from bounded evidence jobs, and caps proof jobs per step.
3.  **Executor**: Runs approved proof jobs via Aristotle and approved bounded checks via a local computational evidence path.
4.  **Learner**: Updates campaign memory, confidence, and world-family priors based on execution results.
5.  **Self-Improvement**: Periodically reviews history to patch the local policy.

## Root Configuration Files

-   `MANAGER_CONSTITUTION.md`: Fixed core ethos and decision rules.
-   `MANAGER_POLICY.json`: Mutable strategy layer (biases, rewards, penalties).
-   `MANAGER_DECISION_SCHEMA.json`: The formal contract for manager outputs.
-   `SELF_IMPROVEMENT_PROMPT.md`: Guidelines for the self-improvement loop.

## Aristotle Integration

The Aristotle adapter is configured via environment variables and communicates over a compact job-based protocol.

### Adapter Contract (Inferred)
-   **Endpoint**: `POST ${ARISTOTLE_BASE_URL}/verify`
-   **Auth**: `Authorization: Bearer ${ARISTOTLE_API_KEY}`
-   **Payload**: Includes `campaign_id`, `jobs` (obligations), and problem context.
-   **Response**: Expected to return status (`proved`, `refuted`, `blocked`, `inconclusive`), notes, and optionally `spawned_nodes`.

## Production Readiness Checklist

1.  **Environment Variables**:
    -   `MANAGER_BACKEND`: Set to `llm` for real reasoning.
    -   `LLM_API_KEY`: Required for `llm` backend.
    -   `EXECUTOR_BACKEND`: Set to `http` for real Aristotle verification.
    -   `ARISTOTLE_BASE_URL`: Required for `http` executor.
    -   `STRICT_LIVE_ARISTOTLE`: Set to `true` to fail readiness if Aristotle is down.
    -   `ENABLE_SELF_IMPROVEMENT`: Set to `true` to activate the policy-patching loop.
2.  **Deployment**:
    -   Deploy to Railway.
    -   Verify `/healthz` (Process OK).
    -   Verify `/readyz` (DB + Config + Aristotle connectivity).
    -   Check `/api/system/status` for detailed component states.
    -   Run `POST /api/system/smoke/aristotle` to confirm verification connectivity.

## Local Development

```bash
# Set up environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run tests
pytest tests/

# Start the service
uvicorn app.main:app --reload
```

## Health and Monitoring
-   `GET /healthz`: Basic process check.
-   `GET /readyz`: Readiness check (DB + strict Aristotle sanity).
-   `GET /api/system/status`: Detailed system configuration and connectivity report.
-   `POST /api/system/smoke/aristotle`: Manual Aristotle smoke test.

## Self-Improvement
When `ENABLE_SELF_IMPROVEMENT=true`, the system can periodically review recent campaign history and generate a JSON policy patch. This patch modifies allowed areas like `world_family_priors`, `failure_penalties`, and `confidence_rules`. Snapshots of all policies are persisted in the database.
