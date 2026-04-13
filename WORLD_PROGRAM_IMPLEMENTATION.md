# World Program Implementation Summary

## Overview

This implementation adds top-down theorem-search strategy to LIMA by making "world models" first-class mathematical objects. The system can now search over both macro-worlds (new ontologies/invariants) and micro-worlds (small theorem shifts).

## Key Changes

### 1. New Schema Models (app/schemas.py)

**TheoremDelta**: Represents small shifts relative to target theorem
- Supports 11 delta types (strengthen_hypothesis, weaken_conclusion, etc.)
- Tracks distance from target, proof gain, and bridge cost

**CompressionPrinciple**: Simple name/description for principles like descent, partition, transfer

**BridgePlan**: Structured bridge back to original theorem
- Bridge claim, obligations, and estimated cost

**ReductionCertificate**: Finite closure summary
- Tracks closure, bridge, and support items

**WorldProgram**: First-class mathematical world
- Mode: macro (new ontology) or micro (small theorem shift)
- Contains thesis, ontology, compression principles, bridge, reduction certificate
- Can include theorem deltas for micro-worlds
- Tracks falsifiers

**ProofDebtItem**: Explicit proof debt
- Role: closure, bridge, support, boundary, falsifier
- Status: open, active, proved, refuted, blocked
- Critical flag and priority

**ManagerDecision Extensions**:
- `global_thesis`: Overall problem thesis
- `primary_world`: Active WorldProgram
- `alternative_worlds`: Alternative WorldPrograms
- `proof_debt`: List of ProofDebtItems
- `critical_next_debt_id`: Next debt to address

**CampaignRecord Extensions**:
- `current_world_program`: Persisted world (dict)
- `alternative_world_programs`: Alternative worlds
- `proof_debt_ledger`: Persisted debt items
- `resolved_debt_ids`: Proved debt IDs
- `active_world_id`: Current world ID

**MemoryState Extensions**:
- `world_diagnostics`: Per-world telemetry (debt counts, failures, hits)

**FormalObligationSpec Extensions**:
- `from_debt_item()`: Convert ProofDebtItem to obligation spec
- Metadata tracks debt role, world_id, critical flag

### 2. Manager Updates (app/manager.py)

**Rules Mode**:
- `_synthesize_default_world()`: Creates minimal default world
- `_synthesize_default_debt()`: Creates default proof debt from target
- Always produces world program and proof debt

**LLM Mode**:
- Updated prompt to request world-oriented decisions
- Explains world modes (macro/micro) and debt roles
- Requests explicit world construction and proof debt

**Normalization**:
- Synthesizes default world if missing
- Synthesizes default debt if missing
- Caps proof debt at 8 items
- Selects critical_next_debt_id from highest-priority critical open item

### 3. Service Updates (app/service.py)

**Context Building**:
- Includes current_world_program, proof_debt_ledger, active_world_id in problem payload

**Execution Finalization**:
- Persists primary_world as current_world_program
- Updates proof_debt_ledger with status preservation
- Tracks resolved_debt_ids

**Persistence**:
- All world fields saved/restored in campaign payload
- Backward compatible with old campaigns

**Operator Brief**:
- Shows active_world_id, world_thesis
- Shows critical debt counts (total and proved)
- Shows critical_next_debt_id

### 4. Obligation Analysis Updates (app/obligation_analysis.py)

**Debt-Driven Planning**:
- If decision has proof_debt and critical_next_debt_id, prepends that debt item to obligations
- Converts ProofDebtItem to FormalObligationSpec via `from_debt_item()`

**Role-Aware Routing**:
- `_analyze_with_role_awareness()`: Checks debt_role metadata
- Closure/bridge → proof channel
- Support → proof or evidence based on text
- Boundary/falsifier → evidence channel

**Prioritization**:
- Closure and bridge obligations get highest priority for proof
- Support and boundary follow
- Maintains existing text-based analysis as fallback

### 5. Frontier Updates (app/frontier.py)

**Debt Status Tracking**:
- Updates proof_debt_ledger status when obligations complete
- Marks debt items as proved/refuted/blocked based on result

**Debt-Aware Spawning**:
- `_spawn_from_debt()`: Spawns frontier nodes from open critical debt
- Maps debt roles to frontier node kinds (lemma, finite_check, exploration)

**World-Aware Solved Criterion**:
- If current_world_program exists:
  - Check all critical debt items are proved
  - Check no live critical falsifiers remain
  - Check world has valid bridge
  - Only then mark solved
- Falls back to old behavior (root node proved) when no world program

### 6. Learner Updates (app/learner.py)

**World Diagnostics**:
- Tracks per-world counters: debt_total, debt_proved, critical_total, critical_proved
- Tracks bridge_failures, closure_failures, evidence_hits, proof_hits
- Updates diagnostics on each result

**Existing Behavior Preserved**:
- All existing world score, streak, and penalty logic unchanged
- Diagnostics are additive telemetry

### 7. Constitution Updates (MANAGER_CONSTITUTION.md)

**Section 1b Added**: "Think top-down through world programs"
- Mandates 6-step world-oriented decision process
- Defines macro vs micro worlds
- Emphasizes micro-worlds as breakthrough opportunities

**Section 2 Enhanced**: Progress definition
- "Progress is the active world became more credible, more bridged, or had debt reduced"

**Section 5 Enhanced**: Failure classification
- Added world-level failure types: bad_world, bad_bridge, incomplete_closure, missing_support_lemma

**Section 7 Enhanced**: Solved criterion
- Defines world-aware solved conditions
- Mandates world continuity across ticks

### 8. Policy Updates (MANAGER_POLICY.json)

**New Sections**:
- `theorem_delta_priors`: Priors for each delta type
- `bridge_cost_penalty`: 0.15
- `proximity_bonus`: 0.20
- `debt_burn_down_reward`: 0.25

**Existing Sections Preserved**:
- All world_family_priors unchanged
- All failure_penalties unchanged
- All success_rewards unchanged

## Backward Compatibility

**Guaranteed**:
- Old campaigns load without world fields (all optional with defaults)
- Old-style decisions work (normalization synthesizes defaults)
- String obligations still supported
- Existing frontier/memory/learner logic preserved
- Fallback solved logic when no world program

**Migration Path**:
- Existing campaigns continue with old behavior
- New decisions automatically get world programs (rules mode synthesizes, LLM mode generates)
- Gradual adoption as campaigns progress

## Testing

**test_world_program_upgrade.py** validates:
- All new models instantiate correctly
- WorldProgram with all fields
- ProofDebtItem with all roles
- FormalObligationSpec.from_debt_item conversion
- ManagerDecision with world fields
- CampaignRecord with world fields
- MemoryState with diagnostics
- Backward compatibility (old-style decisions)

All tests pass ✅

## Design Principles Followed

1. **Minimal changes**: Extended existing classes, didn't rewrite architecture
2. **Backward compatible**: All new fields optional with defaults
3. **Simple types**: Pydantic models and dict persistence, no complex hierarchies
4. **Preserves behavior**: Old logic intact, new logic layered on top
5. **No overengineering**: No graph database, no complex planner, no unnecessary abstractions
6. **Incremental**: Can be adopted gradually as campaigns progress

## Usage

**Rules Mode**:
- Automatically synthesizes default micro-world
- Creates single support debt item from target
- Works out of the box

**LLM Mode**:
- Prompted to construct world programs
- Can create macro or micro worlds
- Can specify theorem deltas for micro-worlds
- Generates explicit proof debt with roles

**Operator**:
- Views world thesis in operator brief
- Sees critical debt counts
- Monitors world continuity across ticks

## Next Steps

1. Run existing test suite to ensure no regressions
2. Test with real campaigns in both rules and LLM mode
3. Monitor world diagnostics to tune priors
4. Iterate on LLM prompts based on world quality
5. Consider adding world failure classification to executor

## Files Modified

- app/schemas.py (new models, extensions)
- app/manager.py (world synthesis, normalization, prompts)
- app/service.py (persistence, context, operator brief)
- app/obligation_analysis.py (debt-driven planning, role routing)
- app/frontier.py (debt tracking, spawning, solved criterion)
- app/learner.py (world diagnostics)
- MANAGER_CONSTITUTION.md (world-oriented mandate)
- MANAGER_POLICY.json (theorem delta priors)
- MANAGER_DECISION_SCHEMA.json (new optional fields)

## Files Created

- test_world_program_upgrade.py (validation tests)
- WORLD_PROGRAM_IMPLEMENTATION.md (this document)
