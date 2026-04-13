# Manager Formalization Guide

## Critical: How to Create Aristotle-Compatible Obligations

The Manager must understand that **Aristotle requires properly structured formal obligations**. Natural language obligations will fail with `formalization_failed`.

---

## The Problem

Currently, the Manager often creates obligations like:
```json
{
  "formal_obligations": [
    "Prove that n^2 > 2n for all n > 2",
    "Show the base case holds",
    "Verify the inductive step"
  ]
}
```

**These will ALL fail** because they lack formal Lean statements.

---

## The Solution: Use FormalObligationSpec

The Manager should create **structured obligations** with explicit formal content:

### Minimal Working Example

```json
{
  "formal_obligations": [
    {
      "source_text": "Prove that n^2 > 2n for all n > 2",
      "goal_kind": "theorem",
      "theorem_name": "n_squared_gt_2n",
      "statement": "∀ n : ℕ, n > 2 → n^2 > 2*n",
      "channel_hint": "proof",
      "requires_proof": true
    }
  ]
}
```

### Full Featured Example

```json
{
  "formal_obligations": [
    {
      "source_text": "Prove that n^2 > 2n for all n > 2",
      "goal_kind": "theorem",
      "theorem_name": "n_squared_gt_2n",
      "imports": ["Mathlib.Data.Nat.Basic", "Mathlib.Tactic"],
      "variables": ["(n : ℕ)"],
      "assumptions": ["n > 2"],
      "statement": "n^2 > 2*n",
      "tactic_hints": [
        "Use induction on n",
        "Apply ring normalization for algebraic steps",
        "Consider cases n = 3 and n > 3"
      ],
      "bounded_domain_description": "Natural numbers greater than 2",
      "channel_hint": "proof",
      "requires_proof": true,
      "metadata": {
        "debt_id": "D-abc123",
        "debt_role": "closure",
        "debt_critical": true
      }
    }
  ]
}
```

---

## Required Fields for Proof Obligations

### Absolutely Required
- `source_text`: Natural language description
- `statement`: **The formal Lean statement** (e.g., `"∀ n : ℕ, n > 2 → n^2 > 2*n"`)

### Highly Recommended
- `goal_kind`: "theorem", "lemma", "sanity_check", etc.
- `theorem_name`: Valid Lean identifier (e.g., `"n_squared_gt_2n"`)
- `channel_hint`: "proof" for Aristotle, "evidence" for computational checks
- `requires_proof`: `true` for proof obligations

### Optional But Valuable
- `imports`: List of Lean imports needed (e.g., `["Mathlib.Data.Nat.Basic"]`)
- `variables`: Variable declarations (e.g., `["(n : ℕ)", "(m : ℕ)"]`)
- `assumptions`: Hypotheses as strings (e.g., `["n > 2", "m > 0"]`)
- `tactic_hints`: Specific tactics that might help
- `bounded_domain_description`: Explain the domain constraints
- `metadata`: Link to proof debt, world program, etc.

### Alternative: Provide Complete Lean Code
Instead of `statement`, you can provide:
- `lean_declaration`: Complete Lean code including theorem declaration

```json
{
  "source_text": "Prove n^2 > 2n for n > 2",
  "lean_declaration": "theorem n_squared_gt_2n (n : ℕ) (h : n > 2) : n^2 > 2*n := by\n  sorry"
}
```

---

## Common Mistakes to Avoid

### ❌ BAD: Natural Language Only
```json
{
  "formal_obligations": [
    "Prove the base case",
    "Show the inductive step holds"
  ]
}
```
**Result**: `formalization_failed` - no formal statement

### ❌ BAD: Vague Statement
```json
{
  "formal_obligations": [
    {
      "source_text": "Prove the theorem",
      "statement": "the theorem is true"
    }
  ]
}
```
**Result**: Invalid Lean syntax

### ❌ BAD: Missing Type Information
```json
{
  "formal_obligations": [
    {
      "source_text": "Prove n > 0",
      "statement": "n > 0"
    }
  ]
}
```
**Result**: Lean can't infer what `n` is

### ✅ GOOD: Complete Type Information
```json
{
  "formal_obligations": [
    {
      "source_text": "Prove n > 0 for positive n",
      "statement": "∀ n : ℕ, n > 0 → n > 0",
      "theorem_name": "pos_implies_pos"
    }
  ]
}
```

---

## How to Think About Formalization

### Step 1: Identify What Needs to Be Proved
From your bounded claim and proof debt, extract the precise mathematical statement.

### Step 2: Write the Lean Statement
Think about:
- What are the types? (ℕ, ℤ, ℝ, List, etc.)
- What are the quantifiers? (∀, ∃)
- What are the hypotheses? (conditions that must hold)
- What is the conclusion? (what you're proving)

### Step 3: Add Context
- What imports are needed?
- What variables should be declared?
- What tactics might help?
- What domain constraints apply?

### Step 4: Link to World Program
- Include proof debt metadata
- Reference the world's thesis
- Explain the role (closure, bridge, support)

---

## Examples by Goal Kind

### Theorem (Main Result)
```json
{
  "source_text": "Collatz sequence eventually reaches 1",
  "goal_kind": "theorem",
  "theorem_name": "collatz_reaches_one",
  "statement": "∀ n : ℕ, n > 0 → ∃ k : ℕ, collatz_iterate k n = 1",
  "imports": ["Mathlib.Data.Nat.Basic"],
  "tactic_hints": ["Consider strong induction on n"],
  "channel_hint": "proof",
  "requires_proof": true
}
```

### Lemma (Supporting Result)
```json
{
  "source_text": "Collatz function decreases for large even numbers",
  "goal_kind": "lemma",
  "theorem_name": "collatz_decreases_large_even",
  "statement": "∀ n : ℕ, n > 4 → Even n → collatz_step n < n",
  "imports": ["Mathlib.Data.Nat.Basic", "Mathlib.Data.Nat.Parity"],
  "channel_hint": "proof",
  "requires_proof": true
}
```

### Sanity Check (Boundary Test)
```json
{
  "source_text": "Verify Collatz property for n=1",
  "goal_kind": "sanity_check",
  "theorem_name": "collatz_base_case",
  "statement": "collatz_iterate 0 1 = 1",
  "channel_hint": "evidence",
  "requires_evidence": true
}
```

### Finite Check (Computational Verification)
```json
{
  "source_text": "Check Collatz for all n ≤ 100",
  "goal_kind": "finite_check",
  "bounded_domain_description": "Natural numbers from 1 to 100",
  "evidence_plan": {
    "method": "exhaustive_check",
    "bound": 100
  },
  "channel_hint": "evidence",
  "requires_evidence": true
}
```

### Counterexample Search
```json
{
  "source_text": "Search for Collatz cycles",
  "goal_kind": "counterexample_search",
  "bounded_domain_description": "Numbers up to 10000, sequences up to 1000 steps",
  "evidence_plan": {
    "method": "bounded_search",
    "max_n": 10000,
    "max_steps": 1000
  },
  "channel_hint": "evidence",
  "requires_evidence": true
}
```

---

## Integration with World Programs

When you have an active world program with proof debt, obligations should reference it:

```json
{
  "formal_obligations": [
    {
      "id": "D-closure-1",
      "source_text": "Prove the world's closure property",
      "goal_kind": "theorem",
      "statement": "∀ x ∈ world_domain, world_property x",
      "metadata": {
        "debt_id": "D-closure-1",
        "debt_role": "closure",
        "debt_world_id": "W-abc123",
        "debt_critical": true,
        "world_thesis": "The problem reduces to proving the property holds in the restricted domain"
      },
      "tactic_hints": [
        "Use the world's compression principle",
        "Apply the invariant from the world's ontology"
      ],
      "channel_hint": "proof",
      "requires_proof": true
    }
  ]
}
```

---

## What Aristotle Receives

When you provide a structured obligation, Aristotle receives:

1. **Lean Code** with your statement and context comments
2. **Rich Prompt** including:
   - Your bounded claim
   - World family and thesis
   - Proof debt role
   - Tactic hints
   - Assumptions

This gives Aristotle the best chance of finding a proof.

---

## Summary: Manager Checklist

Before emitting `formal_obligations`, ask:

- [ ] Does each obligation have a `statement` field with valid Lean syntax?
- [ ] OR does it have a `lean_declaration` with complete Lean code?
- [ ] Are types explicit? (ℕ, ℤ, ℝ, etc.)
- [ ] Are quantifiers clear? (∀, ∃)
- [ ] Is `goal_kind` appropriate? (theorem, lemma, sanity_check, etc.)
- [ ] Is `channel_hint` set? ("proof" for Aristotle, "evidence" for computation)
- [ ] Are `tactic_hints` provided when you have strategic insight?
- [ ] Is the obligation linked to proof debt via `metadata`?
- [ ] Would a human mathematician understand what to prove from the `statement` alone?

If any answer is "no", the obligation will likely fail with `formalization_failed`.

---

## Policy Integration

This guide should be referenced in:
- `MANAGER_CONSTITUTION.md` - Add section on formalization requirements
- `MANAGER_POLICY.json` - Add prompt insertion for formalization guidance
- Manager LLM prompt - Include examples of well-formed obligations

The Manager must internalize: **Natural language is for humans. Lean statements are for Aristotle.**
