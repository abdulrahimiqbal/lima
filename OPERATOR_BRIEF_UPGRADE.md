# Operator Brief UI + API Upgrade

## Summary

This upgrade replaces the fragmented campaign display with a single, content-first "System Operator Brief" panel that provides operators with a comprehensive view of campaign state, manager understanding, verification results, discovery, and next actions.

## Changes Made

### 1. Manager Read Receipt (PART 1)

**Files Modified:**
- `app/schemas.py`: Added `ManagerReadReceipt` model
- `MANAGER_DECISION_SCHEMA.json`: Added `manager_read_receipt` as required field
- `app/manager.py`: Updated to populate read receipt in both LLM and rules modes

**Purpose:**
Provides explicit proof that the manager LLM read and understood the live context before making decisions.

**Fields:**
- `problem_summary`: Brief summary of the problem
- `candidate_answer_seen`: Current candidate answer if present
- `target_node_id_confirmed`: Selected frontier node ID
- `target_node_text_confirmed`: Text of selected node
- `operator_notes_seen`: Operator notes considered
- `relevant_memory_seen`: Blocked patterns, useful lemmas, recent failures
- `constraints_seen`: Runtime constraints being followed
- `open_uncertainties`: Any uncertainties the manager has
- `why_not_other_frontier_nodes`: Justification for node selection

### 2. Operator Brief API Endpoint (PART 2)

**Files Modified:**
- `app/service.py`: Added `get_operator_brief()` method
- `app/main.py`: Added `GET /api/campaigns/{campaign_id}/operator-brief` endpoint

**Purpose:**
Single endpoint that assembles all operator-relevant data in a normalized structure.

**Response Structure:**
```json
{
  "ops": {
    "manager_backend": "...",
    "executor_backend": "...",
    "campaign_status": "...",
    "tick_count": 0
  },
  "campaign_now": {
    "title": "...",
    "problem_statement": "...",
    "candidate_stance": "...",
    "target_frontier_node_id": "..."
  },
  "manager_understanding": {
    "problem_summary": "...",
    "target_node_id_confirmed": "...",
    "operator_notes_seen": [],
    "relevant_memory_seen": {},
    "constraints_seen": []
  },
  "verification": {
    "status": "...",
    "channel_used": "...",
    "approved_jobs_count": 0,
    "rejected_jobs_count": 0
  },
  "discovery": {
    "spawned_nodes_count": 0,
    "useful_lemmas": [],
    "blocked_patterns": []
  },
  "self_improvement": {
    "local_proposal": "...",
    "local_reason": "..."
  },
  "next": {
    "recommended_operator_action": "...",
    "expected_information_gain": "...",
    "if_proved": "...",
    "if_refuted": "...",
    "if_blocked": "...",
    "if_inconclusive": "..."
  }
}
```

### 3. UI Replacement (PART 3)

**Files Modified:**
- `app/templates/index.html`: Replaced fragmented panels with single operator brief

**Changes:**
- Removed separate "Manager interface", "Memory", "Decision and result", "Recent events" panels
- Added single full-width "System Operator Brief" panel
- Added CSS classes: `.brief-section`, `.brief-label`, `.brief-value`, `.brief-list`
- Updated JavaScript to fetch and render operator brief
- Preserved campaign creation, list, step/pause/resume functionality

**UI Sections:**
1. **Ops**: System health and connectivity status
2. **Campaign Now**: Current campaign state and target
3. **Manager Read & Understanding**: What the manager actually read
4. **Verification**: Execution results and job approval/rejection
5. **Discovery**: Spawned nodes, lemmas, patterns learned
6. **Self-Improvement**: Local and global improvement proposals
7. **Next**: Recommended operator action and update rules

### 4. Recommended Operator Actions

The system now synthesizes specific operator recommendations based on execution results:

- **formalization_failed** → "Rewrite the claim as a clean structured formal obligation and retry."
- **proof_failed** → "Split the target into a smaller lemma or add missing assumptions."
- **timeout** → "Shrink scope and retry a smaller proof job."
- **inconclusive + computational_evidence** → "Treat this as discovery, not verification; convert patterns into a formal lemma."
- **blocked** → "Adjust scope or split obligations to pass submission gate."
- **proved** → "Continue to next frontier node."
- **refuted** → "Update candidate answer and explore alternative approaches."

## Testing

**New Tests:**
- `tests/test_operator_brief.py`: 4 new tests covering:
  - Operator brief endpoint structure
  - Manager read receipt in rules mode
  - Fallback behavior when no execution
  - Recommended action synthesis

**Updated Tests:**
- `tests/test_app.py`: Updated to check for "System Operator Brief" instead of "Current candidate answer"

**Test Results:**
- All 65 tests pass (excluding production tests)
- No regressions in existing functionality

## Backward Compatibility

- Existing API endpoints remain unchanged
- Campaign data structure unchanged
- Polling behavior preserved
- Old debug endpoints still available but not prominently displayed

## Design Principles Followed

1. **Content-first**: Information over visuals
2. **Minimal styling**: Simple, readable, dark theme
3. **No new frameworks**: Vanilla HTML/CSS/JS only
4. **Preserve existing structure**: No app redesign
5. **Operator-focused**: Answers key operational questions
6. **Easy to iterate**: Simple code, no abstractions

## Usage

After selecting a campaign, the operator brief automatically loads and displays:
- System operational status
- Current campaign activity
- Manager's understanding of the context
- Verification results
- Discovery outcomes
- Self-improvement proposals
- Recommended next actions

The brief refreshes automatically every 10 seconds or manually via the Refresh button.

## Future Enhancements (Optional)

- Add "Show raw details" collapsible for debugging
- Add "last updated" timestamp
- Add `GET /api/system/self-improvement/latest` endpoint for global policy updates
- Add filtering/search within the brief
- Add export functionality for operator reports
