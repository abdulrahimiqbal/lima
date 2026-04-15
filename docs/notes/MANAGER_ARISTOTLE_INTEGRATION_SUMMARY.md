# Manager-Aristotle Integration: Complete Analysis & Improvements

## The Core Question

**Does the Manager know how to make best use of Aristotle?**

**Answer**: Not fully. The Manager had the architecture but lacked explicit guidance on formalization requirements.

---

## Problems Identified

### 1. Manager Lacks Formalization Guidance

**Issue**: The Manager (LLM decision-maker) was not explicitly told that Aristotle requires structured formal obligations.

**Evidence**:
- Constitution mentions "formal obligations" but doesn't explain what makes them formal
- Policy has "formalization-aware" but no concrete examples
- No guidance on Lean syntax requirements
- No examples of well-formed vs poorly-formed obligations

**Result**: Manager likely creates obligations like:
```json
{
  "formal_obligations": [
    "Prove the base case",
    "Show the inductive step holds"
  ]
}
```

These fail with `formalization_failed` because they lack Lean statements.

### 2. Executor Context Was Minimal

**Issue**: Even when obligations were well-formed, Aristotle received minimal context.

**Evidence** (from `app/executor.py`):
```python
prompt = "\n".join([
    "Fill in all Lean sorries in this project.",
    "Preserve theorem names where possible.",
    f"World family: {decision.world_family}",
    f"Bounded claim: {decision.bounded_claim}",
])
```

**Missing**:
- Global thesis/strategy
- World program explanation
- Proof debt role
- Tactic hints
- Assumptions

---

## Solutions Implemented

### 1. Created Comprehensive Formalization Guide

**File**: `MANAGER_FORMALIZATION_GUIDE.md`

**Contents**:
- Explanation of why formalization matters
- Required vs optional fields
- Complete examples by goal kind (theorem, lemma, sanity_check, etc.)
- Common mistakes to avoid
- Integration with world programs
- Manager checklist

**Key Examples**:

✅ **Good Obligation**:
```json
{
  "source_text": "Prove n^2 > 2n for n > 2",
  "goal_kind": "theorem",
  "theorem_name": "n_squared_gt_2n",
  "statement": "∀ n : ℕ, n > 2 → n^2 > 2*n",
  "tactic_hints": ["Use induction on n"],
  "channel_hint": "proof",
  "requires_proof": true
}
```

❌ **Bad Obligation**:
```json
{
  "formal_obligations": ["Prove the base case"]
}
```

### 2. Updated Manager Constitution

**File**: `MANAGER_CONSTITUTION.md`

**Added Section 1c**: "Formalize obligations properly for Aristotle"

**Key Points**:
- Natural language obligations will FAIL
- Must provide `statement` with valid Lean syntax OR `lean_declaration`
- Lists recommended fields (imports, variables, assumptions, tactic_hints)
- Provides concrete example
- References the full guide

### 3. Updated Manager Policy

**File**: `MANAGER_POLICY.json`

**Enhanced `prompt_insertions`**:
- Added "formalization_requirements" section with critical guidance
- Updated existing prompts to emphasize formal statements
- Added explicit Lean syntax examples

**New Insertion**:
```json
"formalization_requirements": "CRITICAL: Every proof obligation MUST include a 'statement' field with valid Lean syntax (e.g., '∀ n : ℕ, n > 2 → n^2 > 2*n') OR a 'lean_declaration' with complete Lean code. Natural language alone will fail. Include 'tactic_hints' when you have strategic insight. Link obligations to proof debt via 'metadata'."
```

### 4. Enhanced Manager LLM Prompt

**File**: `app/manager.py`

**Added**:
- New `_formalization_requirements()` method that returns detailed guidance
- Injected this guidance into the LLM prompt before the schema
- Includes concrete examples and field explanations

**Prompt Now Includes**:
```
FORMALIZATION REQUIREMENTS (CRITICAL):
Aristotle requires structured formal obligations. Natural language alone will FAIL.

For PROOF obligations, you MUST provide:
- 'statement': Valid Lean syntax with explicit types and quantifiers
  Example: "∀ n : ℕ, n > 2 → n^2 > 2*n"
- OR 'lean_declaration': Complete Lean code

[... detailed field descriptions and examples ...]
```

### 5. Enhanced Executor Context to Aristotle

**File**: `app/executor.py`

**Improved Prompt Construction**:
- Now includes problem context section
- Adds overall strategy (global thesis)
- Includes world program details (ID, mode, thesis, bridge)
- Adds proof debt context (role, criticality)
- Includes tactic hints
- Includes assumptions

**Before**:
```python
prompt = "\n".join([
    "Fill in all Lean sorries in this project.",
    "Preserve theorem names where possible.",
    f"World family: {decision.world_family}",
    f"Bounded claim: {decision.bounded_claim}",
])
```

**After**:
```python
prompt_parts = [
    "Fill in all Lean sorries in this project.",
    "Preserve theorem names where possible.",
    "",
    "=== PROBLEM CONTEXT ===",
    f"Bounded claim: {decision.bounded_claim}",
    f"World family: {decision.world_family}",
]

# Add global thesis if available
if hasattr(decision, 'global_thesis') and decision.global_thesis:
    prompt_parts.extend([
        "",
        "=== OVERALL STRATEGY ===",
        decision.global_thesis,
    ])

# Add world program context
# Add proof debt context
# Add tactic hints
# Add assumptions
```

**Enhanced Lean Code Comments**:
- Added doc comments with source context
- Includes proof debt role
- Includes bounded domain description

---

## Expected Impact

### Manager Side

1. **Fewer Formalization Failures**: Manager now knows to provide `statement` fields
2. **Better Structured Obligations**: Explicit guidance on imports, variables, assumptions
3. **Strategic Tactic Hints**: Manager can provide tactics based on world program strategy
4. **Proof Debt Integration**: Obligations properly linked to world program and debt

### Executor Side

1. **Richer Context to Aristotle**: Aristotle understands the broader strategy
2. **Better Proof Success Rate**: More context = better proof search
3. **Clearer Intent**: World program thesis explains why this proof matters
4. **Easier Debugging**: When proofs fail, rich context helps understand why

### System-Wide

1. **Reduced `formalization_failed` Rate**: Manager creates proper obligations
2. **Improved Proof Success Rate**: Aristotle has better context
3. **Better Learning**: Failures are more informative with rich context
4. **Tighter Integration**: World programs flow through to Aristotle

---

## Backward Compatibility

All changes are **fully backward compatible**:

- String obligations still work (converted to `FormalObligationSpec`)
- Missing fields are gracefully omitted from prompts
- Existing campaigns continue to work
- No schema changes required
- No database migrations needed

---

## Testing Recommendations

### 1. Monitor Formalization Failure Rate
Track `formalization_failed` outcomes before/after:
```sql
SELECT 
  COUNT(*) FILTER (WHERE failure_type = 'formalization_failed') as formalization_failures,
  COUNT(*) as total_executions,
  COUNT(*) FILTER (WHERE failure_type = 'formalization_failed')::float / COUNT(*) as failure_rate
FROM execution_results
WHERE created_at > '2026-04-13'
```

### 2. Inspect Manager Decisions
Check if Manager is creating structured obligations:
```python
# Look at recent decisions
decision = manager.decide(context)
for obligation in decision.formal_obligations:
    if isinstance(obligation, dict):
        print(f"✓ Structured: {obligation.get('statement', 'NO STATEMENT')}")
    else:
        print(f"✗ String only: {obligation}")
```

### 3. Review Aristotle Prompts
Check what context is actually being sent:
```python
# In executor, log the full prompt
logger.info(f"Aristotle prompt:\n{prompt}")
```

### 4. Compare Success Rates
Track proof success rates before/after:
- `proved` outcomes
- `blocked/proof_failed` outcomes
- Average time to proof
- Budget exhaustion rate

---

## Next Steps

### Immediate
1. Deploy changes to production
2. Monitor formalization failure rate
3. Review first 10-20 manager decisions for obligation quality
4. Check Aristotle prompts in logs

### Short Term
1. Add useful lemmas from memory to Aristotle context
2. Include recent failures to avoid repeated mistakes
3. Add blocked patterns to guide proof search
4. Consider evidence context for evidence-to-proof escalation

### Long Term
1. Build feedback loop: Aristotle failures → Manager learning
2. Develop obligation quality metrics
3. Create automated obligation validation
4. Consider LLM-based formalization assistance for Manager

---

## Files Modified

1. **MANAGER_FORMALIZATION_GUIDE.md** (new) - Complete guide for Manager
2. **MANAGER_CONSTITUTION.md** - Added section 1c on formalization
3. **MANAGER_POLICY.json** - Enhanced prompt insertions
4. **app/manager.py** - Added `_formalization_requirements()` method and injected into prompt
5. **app/executor.py** - Enhanced prompt construction and Lean code comments
6. **ARISTOTLE_CONTEXT_IMPROVEMENTS.md** (new) - Executor-side improvements
7. **MANAGER_ARISTOTLE_INTEGRATION_SUMMARY.md** (this file) - Complete overview

---

## Key Takeaway

The Manager now has **explicit, concrete guidance** on creating Aristotle-compatible obligations:

- ✅ Knows that natural language alone fails
- ✅ Knows to provide `statement` with Lean syntax
- ✅ Knows what fields to include (imports, variables, tactic_hints)
- ✅ Has concrete examples to follow
- ✅ Understands the connection to world programs and proof debt

Combined with the enhanced executor context, Aristotle now receives:

- ✅ Rich strategic context (global thesis, world program)
- ✅ Tactical guidance (tactic hints, assumptions)
- ✅ Structural context (proof debt role, criticality)
- ✅ Well-formed Lean code with documentation

This should significantly improve the Manager's ability to make effective use of Aristotle.
