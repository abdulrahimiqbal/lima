# Aristotle Context Improvements

## Analysis Summary

After reviewing the Aristotle integration, I found that while the **architecture is solid** (durable submit-and-poll, honest formalization, proper error handling), the **context being sent to Aristotle was minimal**.

## Issues Found

### 1. Minimal Prompt Context

**Before**: The prompt sent to Aristotle only included:
```python
prompt = "\n".join([
    "Fill in all Lean sorries in this project.",
    "Preserve theorem names where possible.",
    f"World family: {decision.world_family}",
    f"Bounded claim: {decision.bounded_claim}",
])
```

**Problems**:
- No global strategy context
- No world program explanation
- No proof debt role information
- No tactic hints
- No assumptions context
- Missing useful lemmas from memory

### 2. Lean Code Lacked Context Comments

The generated Lean code had minimal comments, making it harder for Aristotle to understand:
- What the theorem is trying to prove
- Why it matters in the larger proof strategy
- What domain constraints apply

## Improvements Made

### 1. Enhanced Prompt Context (`app/executor.py`)

Now includes:
- **Problem Context**: Bounded claim and world family
- **Overall Strategy**: Global thesis if available
- **World Program**: World ID, mode, thesis, and bridge to target
- **Proof Debt Context**: Role (closure/bridge/support/boundary/falsifier) and criticality
- **Tactic Hints**: Specific tactics that might help
- **Assumptions**: Relevant assumptions for the proof

Example enhanced prompt:
```
Fill in all Lean sorries in this project.
Preserve theorem names where possible.

=== PROBLEM CONTEXT ===
Bounded claim: For all n > 2, n^2 > 2n
World family: direct

=== OVERALL STRATEGY ===
Prove by induction on n, establishing base case and inductive step

=== WORLD PROGRAM ===
World ID: W-abc123
Mode: micro
Thesis: Direct proof via mathematical induction
Bridge to target: Inductive step reduces to algebraic inequality

=== PROOF DEBT CONTEXT ===
Role: closure
Critical: True

=== TACTIC HINTS ===
- Use induction on n
- Apply ring normalization for algebraic steps

=== ASSUMPTIONS ===
- n is a natural number
- n > 2
```

### 2. Enhanced Lean Code Comments

Now includes:
- Source text context (first 200 chars)
- Proof debt role if applicable
- Bounded domain description
- Structured context in Lean doc comments

Example:
```lean
/-
Source: Prove that for all n > 2, n^2 > 2n
Proof debt role: closure
Bounded domain: Natural numbers greater than 2
-/

theorem n_squared_gt_2n (n : ℕ) (h : n > 2) : n^2 > 2*n := by
  -- Hint: Use induction on n
  -- Hint: Apply ring normalization for algebraic steps
  sorry
```

## Expected Benefits

1. **Better Proof Success Rate**: Aristotle has more context about what to prove and why
2. **More Targeted Tactics**: Tactic hints guide the proof search
3. **Clearer Intent**: World program context explains the proof strategy
4. **Reduced Failures**: Understanding proof debt roles helps prioritize approaches
5. **Better Debugging**: When proofs fail, the context helps understand why

## Backward Compatibility

- All changes are additive - they only add context when available
- If fields are missing (e.g., no global_thesis), the prompt gracefully omits them
- Existing campaigns and obligations continue to work
- No schema changes required

## Testing Recommendations

1. **Monitor Success Rates**: Track proof success rates before/after
2. **Check Prompt Quality**: Review actual prompts sent to Aristotle via logs
3. **Verify Context Propagation**: Ensure world programs and debt context flow through
4. **Test Edge Cases**: Obligations without structured specs should still work

## Future Enhancements

Consider adding:
1. **Useful Lemmas**: Include relevant lemmas from memory that might help
2. **Recent Failures**: Context about what approaches have already failed
3. **Blocked Patterns**: Patterns to avoid based on past failures
4. **Evidence Context**: For evidence-to-proof escalation, include the evidence found
5. **Counterexample Hints**: For refutation attempts, include suspected counterexamples

## Files Modified

- `app/executor.py`: Enhanced prompt construction and Lean code generation
  - Lines 373-378 → Lines 373-430 (prompt enhancement)
  - Lines 600-630 → Lines 600-640 (Lean code comments)
