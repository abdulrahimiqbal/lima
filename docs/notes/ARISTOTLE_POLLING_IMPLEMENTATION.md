# Aristotle Durable Submit-and-Poll Implementation

## Overview

This document describes the implementation of durable submit-and-poll workflow for Aristotle proof jobs, replacing the previous synchronous wait-with-timeout approach.

## Problem Statement

Previously, LIMA treated Aristotle proof jobs as bounded synchronous calls with a fixed timeout (default 120s). This had several issues:

1. Proof jobs could take arbitrary amounts of time
2. Timeouts were treated as failures, not as "still running"
3. Long-running proofs blocked worker progress
4. Process restarts lost in-flight proof jobs
5. No way to distinguish between "proof is slow" and "proof failed"

## Solution

Implement a durable asynchronous orchestration pattern:

1. **Submit**: Create proof job in Aristotle, return immediately with `PendingAristotleJob`
2. **Persist**: Store pending job state in campaign payload (survives restarts)
3. **Poll**: On future `step_campaign()` calls, poll existing job first
4. **Block new decisions**: While job is pending, don't create new manager decisions
5. **Finalize**: Only apply memory/frontier updates when job reaches terminal state

## Key Changes

### A. Schema Changes (`app/schemas.py`)

Added `PendingAristotleJob` model:
```python
class PendingAristotleJob(BaseModel):
    project_id: str
    target_frontier_node: str
    world_family: WorldFamily
    bounded_claim: str
    submitted_at: datetime
    last_polled_at: datetime | None
    poll_count: int
    status: Literal["submitted", "running", "complete", ...]
    decision_snapshot: dict[str, Any]
    plan_snapshot: dict[str, Any]
    lean_code: str
    result_tar_path: str | None
    notes: list[str]
```

Added `pending_aristotle_job: PendingAristotleJob | None` to `CampaignRecord`.

### B. Executor Changes (`app/executor.py`)

**Protocol Change**:
- Old: `run_proof(..., timeout_seconds) -> ExecutionResult`
- New: 
  - `submit_proof(...) -> PendingAristotleJob`
  - `poll_proof(pending_job) -> tuple[PendingAristotleJob, ExecutionResult | None]`

**MockProofAdapter**:
- `submit_proof`: Returns pending job immediately
- `poll_proof`: Completes on first poll (for testing)

**AristotleSdkProofAdapter**:
- `submit_proof`: 
  - Formalizes Lean code
  - Submits to Aristotle via SDK
  - Returns pending job with `project_id`
  - Handles submission failures gracefully
- `poll_proof`:
  - Polls Aristotle project status
  - Returns `(updated_job, None)` if still running
  - Returns `(updated_job, result)` if terminal
  - Updates poll count and timestamps
  - Downloads artifacts for terminal states

**Executor Class**:
- `submit_proof`: Delegates to adapter
- `poll_proof`: Delegates to adapter
- `run_evidence`: Synchronous evidence execution (unchanged)

### C. Service Changes (`app/service.py`)

**step_campaign() Flow**:

```python
def step_campaign(campaign_id):
    # 1. Check for pending job
    if campaign.pending_aristotle_job:
        return _poll_pending_job(campaign)
    
    # 2. No pending job - normal decision flow
    decision = manager.decide(context)
    plan = build_execution_plan(decision, ...)
    
    # 3. Handle proof vs evidence
    if plan.approved_proof_jobs:
        # Submit and store pending job
        pending_job = executor.submit_proof(...)
        campaign.pending_aristotle_job = pending_job
        persist_campaign(campaign)
        return campaign
    
    elif plan.approved_evidence_jobs:
        # Evidence runs synchronously
        result = executor.run_evidence(...)
        finalize_execution(...)
        return campaign
```

**_poll_pending_job()**:
- Polls existing job
- If still pending: update job state, record event, return
- If complete: finalize execution, clear pending job, return

**_finalize_execution()**:
- Apply memory updates
- Apply frontier updates
- Record execution result
- Persist campaign

### D. Config Changes (`app/config.py`)

Added `aristotle_poll_interval_seconds: int = 10` (not currently used in polling logic, but available for future rate limiting).

### E. Learning Changes (`app/learner.py`)

Updated timeout handling:
- Only penalize actual terminal timeouts
- Don't penalize still-running jobs
- Added note: "terminal_timeout" vs just "timeout"

### F. Obligation Analysis Changes (`app/obligation_analysis.py`)

Updated `_should_throttle_proof`:
- Check for terminal failures (proof_failed, budget_exhausted, excessive_scope)
- Don't throttle based on "timeout" from still-running jobs

### G. Event Changes

New event types:
- `aristotle_job_submitted`: When job is submitted
- `aristotle_job_polled`: When job is polled (still running)
- `aristotle_job_completed`: When job reaches terminal state

## Behavior Changes

### Before
1. Submit proof to Aristotle
2. Wait up to `ARISTOTLE_TIMEOUT_SECONDS` (120s)
3. If timeout: return `inconclusive/timeout`
4. If complete: return result
5. Worker blocked during entire wait

### After
1. Submit proof to Aristotle (non-blocking)
2. Store `pending_aristotle_job` in campaign
3. Return immediately
4. On next `step_campaign()`: poll job
5. If still running: update poll count, return
6. If complete: finalize and clear pending job
7. Worker never blocks on proof completion

## Restart Resilience

**Before**: Process restart loses in-flight proof jobs.

**After**: 
- Pending job state persisted in campaign payload
- On restart, worker resumes polling existing jobs
- No duplicate submissions
- No lost work

## One-Job-At-A-Time Semantics

- While `pending_aristotle_job` exists, `step_campaign()` polls instead of creating new decisions
- Prevents duplicate submissions
- Respects existing campaign lock
- Maintains tight budget control

## Timeout Semantics

**Before**: `ARISTOTLE_TIMEOUT_SECONDS` was proof completion deadline.

**After**: 
- `ARISTOTLE_TIMEOUT_SECONDS` is only for individual network requests (submit, poll, download)
- No overall proof completion deadline
- Proof jobs can run indefinitely until Aristotle returns terminal status

## SDK Limitations

The implementation assumes the Aristotle SDK supports:
1. Creating projects and getting `project_id`
2. Reconstructing/refreshing project by `project_id`
3. Polling project status without blocking

**Current Limitation**: The SDK may not support direct `project_id` lookup. The implementation includes a fallback that logs a warning if this fails. This is noted in the code and should be addressed if the SDK adds this capability.

## Testing

New test file: `tests/test_pending_aristotle_jobs.py`

Tests cover:
- Submit returns pending job
- Poll non-terminal job returns None
- Poll terminal job returns result
- Pending job serialization
- Campaign with pending job serialization
- Backward compatibility (campaigns without pending job)

Updated tests: `tests/test_executor_channels.py`
- Updated to use submit/poll interface
- Removed timeout classification test (no longer relevant)

## Backward Compatibility

- Old campaigns without `pending_aristotle_job` deserialize cleanly (field is `None`)
- Evidence jobs still run synchronously as before
- Mock executor still works
- All existing tests pass

## Future Enhancements

1. **Rate Limiting**: Use `ARISTOTLE_POLL_INTERVAL_SECONDS` to avoid excessive polling
2. **Exponential Backoff**: Increase poll interval for long-running jobs
3. **Job Cancellation**: Add ability to cancel pending jobs
4. **Multiple Jobs**: Support multiple pending jobs per campaign (if needed)
5. **SDK Improvements**: Work with Aristotle team to add `project_id` lookup support
6. **Persistent Storage**: Store result artifacts in persistent location (currently in `./data/aristotle_results/`)

## Deployment Notes

- No database migration required (payload storage handles arbitrary dict fields)
- Set `ARISTOTLE_POLL_INTERVAL_SECONDS` if desired (default: 10s)
- `ARISTOTLE_TIMEOUT_SECONDS` still used for network timeouts (default: 120s)
- Monitor `pending_aristotle_job` field in campaign API responses
- Check event logs for `aristotle_job_*` events

## Observability

Campaign API response includes:
```json
{
  "pending_aristotle_job": {
    "project_id": "...",
    "status": "running",
    "poll_count": 5,
    "last_polled_at": "2026-04-13T...",
    "submitted_at": "2026-04-13T...",
    ...
  }
}
```

Events include:
- `aristotle_job_submitted`: Initial submission
- `aristotle_job_polled`: Each poll (with poll_count)
- `aristotle_job_completed`: Terminal state (with result)

## Error Handling

- Submission failures: Return pending job with `status="failed"` and error notes
- Poll failures: Log warning, don't mark as failed (might be transient)
- Formalization failures: Return pending job with `status="failed"` immediately
- SDK errors: Graceful degradation with error notes

## Summary

This implementation transforms Aristotle proof jobs from synchronous blocking calls into durable asynchronous jobs that:
- Don't block worker progress
- Survive process restarts
- Can run for arbitrary durations
- Provide clear observability
- Maintain one-job-at-a-time semantics
- Are backward compatible with existing campaigns
