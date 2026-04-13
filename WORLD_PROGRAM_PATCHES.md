# World Program Surgical Patches

## Summary

This document describes the minimal, surgical patches applied to fix concrete gaps in the world-program implementation. All patches maintain backward compatibility and preserve existing interfaces.

## Test Results

- **79 tests pass** (75 original + 4 new)
- **No regressions**
- **Backward compatibility maintained**

## Patches Applied

### Patch 1: Fix closure/bridge prioritization

**File:** `app/obligation_analysis.py`

**Problem:** `_is_closure_or_bridge_role()` always returned False, so role-based prioritization never worked.

**Fix:**
- Changed `build_execution_plan()` to track `(spec, meta)` pairs instead of just `meta`
- Split obligations into `closure_bridge_pairs` and `other_pairs` based on `spec.metadata.get("debt_role")`
- Process closure/bridge pairs first for proof channel
- Removed dead `_is_closure_or_bridge_role()` helper

**Result:** Closure and bridge obligations now correctly get priority over support obligations.

---

### Patch 2 & 3: Fix proof debt ledger update ordering

**File:** `app/service.py`

**Problem:** 
- World/debt state was installed AFTER `update_memory()` and `apply_execution_result()`
- This caused debt status updates to be lost or operate on stale ledger
- Async completion path didn't share the same logic

**Fix:**
- Added `_apply_decision_world_state()` helper to install world/debt state
- Added `_recompute_resolved_debt_ids()` helper for final ledger reconciliation
- Reordered `_finalize_execution()`:
  1. Copy campaign
  2. Set tick/context/decision metadata
  3. **Install world/debt state** (new step)
  4. Call `update_memory()`
  5. Call `apply_execution_result()`
  6. Set last_execution_result
  7. Recompute resolved_debt_ids
  8. Persist
- Updated `_poll_pending_job()` to use same helpers and ordering

**Result:** 
- Debt status updates work correctly on same tick
- Async and sync paths share identical world/debt persistence logic
- `resolved_debt_ids` always matches final ledger state

---

### Patch 4: Recompute resolved debt IDs from final ledger

**File:** `app/service.py`

**Problem:** `resolved_debt_ids` were appended incrementally in multiple places, causing sync issues.

**Fix:**
- Added `_recompute_resolved_debt_ids()` helper
- Called after `apply_execution_result()` in both sync and async paths
- Single source of truth: final ledger state

**Result:** `resolved_debt_ids` always accurate and consistent.

---

### Patch 5: Improve world-aware solved check

**File:** `app/frontier.py`

**Problem:** Solved check logic was fragile and could fall back to old behavior incorrectly.

**Fix:**
- When `current_world_program` exists, use ONLY world-aware logic
- If critical debt exists:
  - Check all critical proved + no live falsifiers + valid bridge → solved
- If no critical debt:
  - Only allow solved if bridge exists AND `total_debt_count == 0`
- Fallback to old root-node logic ONLY when no world program

**Result:** Solved criterion correctly requires all critical debt discharged when world exists.

---

### Patch 6: Add world continuity to manager

**Files:** `app/manager.py`

**Problem:** 
- Rules mode synthesized fresh world every tick
- LLM mode had no continuity bias
- World state was lost across ticks

**Fix:**

**Rules mode:**
- Added `_load_existing_world_from_context()` helper
- Added `_load_existing_open_debt_from_context()` helper
- In `_decide_with_rules()`:
  - Try to load existing world and debt first
  - If found, reuse world ID, label, thesis
  - Choose `critical_next_debt_id` from highest-priority open critical debt
  - Derive `bounded_claim` from that debt item
  - Only synthesize fresh world if no existing world

**LLM mode:**
- Added continuity instruction to prompt: "If current_world_program is present and not structurally broken, continue it"
- Updated `_normalize_decision()` to accept optional `context` parameter
- If `primary_world` is None, try to reuse existing world from context before synthesizing default

**Result:** World programs persist across ticks unless explicitly changed.

---

### Patch 7: Minimal theorem delta scoring

**File:** `app/manager.py`

**Problem:** `theorem_delta_priors`, `bridge_cost_penalty`, `proximity_bonus` existed but were unused.

**Fix:**
- In `_normalize_decision()`, if `primary_world.theorem_deltas` exists:
  - Score each delta: `prior + proximity_bonus * (1 - distance) + proof_gain - penalty * bridge_cost`
  - Sort deltas by score descending
  - Update world's theorem_deltas with sorted list

**Result:** Policy knobs now affect theorem delta ordering without building full optimizer.

---

### Patch 8: Improve learner diagnostics

**File:** `app/learner.py`

**Problem:** World diagnostics counted debt from `decision.proof_debt`, which might not reflect final ledger.

**Fix:**
- In `update_memory()`, when updating world diagnostics:
  - If `active_world_id` matches `decision.primary_world.id` and ledger exists:
    - Use final `proof_debt_ledger` for counts
  - Otherwise fall back to `decision.proof_debt`

**Result:** Diagnostics reflect actual final ledger state.

---

### Patch 9: Add focused tests

**File:** `tests/test_world_program_patches.py`

**Tests added:**

1. **`test_proof_debt_ordering_sync`**
   - Creates campaign with empty ledger
   - Applies decision with proof debt
   - Simulates proved result
   - Verifies debt status updated to "proved"

2. **`test_closure_bridge_prioritization`**
   - Creates support and closure debt items
   - Closure has lower priority but should go first
   - Verifies closure obligation approved before support

3. **`test_world_continuity_rules_mode`**
   - Creates context with existing world and open debt
   - Gets decision in rules mode
   - Verifies existing world ID reused
   - Verifies bounded claim comes from existing debt

4. **`test_world_aware_solved_check`**
   - Creates campaign with world and two critical debt items
   - One proved, one open
   - Proves second debt item
   - Verifies campaign marked solved

**Result:** All 4 new tests pass, validating patch correctness.

---

## Files Modified

1. `app/obligation_analysis.py` - Closure/bridge prioritization fix
2. `app/service.py` - Ordering fixes, helpers for world/debt state
3. `app/frontier.py` - Improved solved check
4. `app/manager.py` - World continuity, theorem delta scoring
5. `app/learner.py` - Diagnostics improvement
6. `tests/test_world_program_patches.py` - New focused tests

## Files NOT Modified

- No changes to executor protocol
- No changes to Aristotle submission
- No changes to frontier architecture
- No new abstractions added
- All existing interfaces preserved

## Acceptance Criteria Met

✅ 1. Closure/bridge prioritization actually works  
✅ 2. Proof debt items correctly become proved/refuted/blocked on same tick  
✅ 3. Async and sync execution share same world/debt persistence logic  
✅ 4. `resolved_debt_ids` always matches final ledger  
✅ 5. World-aware solved checks operate on current ledger state  
✅ 6. Rules mode reuses existing active world/debt when present  
✅ 7. Theorem delta policy knobs affect ordering  
✅ 8. No executor API changes  
✅ 9. Backward compatibility intact (all 75 original tests pass)  

## Implementation Style

- Small helper functions added where needed
- No large refactors
- Preserved public method signatures
- Brief comments only where non-obvious
- No new files except tests
- Minimal, surgical changes only

## Next Steps

The world-program implementation is now in a correctly functioning v1 state. The system can:

1. Prioritize critical debt correctly
2. Track debt status accurately across ticks
3. Maintain world continuity
4. Use policy knobs for theorem deltas
5. Check solved criterion based on critical debt discharge

All with full backward compatibility maintained.
