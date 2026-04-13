from __future__ import annotations

import re
from typing import Any

from .schemas import (
    AnalyzedObligation,
    ApprovedExecutionPlan,
    FormalObligationSpec,
    ManagerDecision,
)


BOUNDED_CUES = (
    "<=",
    "≤",
    "up to",
    "at most",
    "within",
    "for n =",
    "for n in",
    "base case",
    "first ",
)
UNBOUNDED_CUES = ("for all", "every", "all integers", "all n", "for any")
COMPUTE_CUES = (
    "compute",
    "check",
    "search",
    "enumerate",
    "simulate",
    "test",
    "verify computational",
)
COUNTEREXAMPLE_CUES = ("counterexample", "cycle", "diverge", "non-trivial cycle")
REDUCTION_CUES = ("reduces", "reduction", "smaller", "less than", "decrease", "descend")
PROOF_CUES = ("prove", "lemma", "theorem", "show that", "establish")


def analyze_obligation(obligation: str | FormalObligationSpec) -> AnalyzedObligation:
    """Analyze an obligation and determine its properties."""
    if isinstance(obligation, FormalObligationSpec):
        text = obligation.source_text
    else:
        text = obligation.strip()
    
    lowered = text.lower()
    has_bound = _has_bounded_cue(lowered)
    has_unbounded = _has_unbounded_cue(lowered)
    has_compute = any(cue in lowered for cue in COMPUTE_CUES)
    has_counterexample = any(cue in lowered for cue in COUNTEREXAMPLE_CUES)
    has_reduction = any(cue in lowered for cue in REDUCTION_CUES)
    has_proof = any(cue in lowered for cue in PROOF_CUES)

    if has_counterexample:
        obligation_type = "counterexample_search"
    elif has_compute or ("finite" in lowered and "check" in lowered):
        obligation_type = "finite_check"
    elif has_reduction:
        obligation_type = "reduction_check"
    elif "sanity" in lowered or "base case" in lowered:
        obligation_type = "sanity_check"
    else:
        obligation_type = "proof"

    if has_unbounded and ("mod " in lowered or "residue class" in lowered):
        scope = "semi_global"
    elif has_unbounded:
        scope = "global"
    else:
        scope = "local"

    if has_bound and has_unbounded:
        if _looks_bounded_universal(lowered):
            quantifier_profile = "bounded"
        else:
            quantifier_profile = "mixed"
    elif has_bound:
        quantifier_profile = "bounded"
    else:
        quantifier_profile = "unbounded"

    complexity_class = _estimate_complexity(
        lowered=lowered,
        scope=scope,
        quantifier_profile=quantifier_profile,
        obligation_type=obligation_type,
    )
    expected_runtime_class = _estimate_runtime(complexity_class)

    submission_channel = "aristotle_proof"
    allowed = True
    rejection_reason = None

    # Check for mixed channels - will be split instead of rejected
    if has_compute and has_proof:
        submission_channel = "reject"
        allowed = False
        rejection_reason = "mixed_channels"
    elif quantifier_profile == "mixed":
        submission_channel = "reject"
        allowed = False
        rejection_reason = "mixed_channels"
    elif obligation_type in {"finite_check", "counterexample_search", "sanity_check"}:
        submission_channel = "computational_evidence"
    elif scope == "global" and quantifier_profile == "unbounded":
        submission_channel = "reject"
        allowed = False
        rejection_reason = "excessive_scope"
    elif complexity_class in {"large", "unsafe"}:
        submission_channel = "reject"
        allowed = False
        rejection_reason = "excessive_scope"
    return AnalyzedObligation(
        text=text,
        obligation_type=obligation_type,  # type: ignore[arg-type]
        scope=scope,  # type: ignore[arg-type]
        quantifier_profile=quantifier_profile,  # type: ignore[arg-type]
        complexity_class=complexity_class,  # type: ignore[arg-type]
        expected_runtime_class=expected_runtime_class,  # type: ignore[arg-type]
        submission_channel=submission_channel,  # type: ignore[arg-type]
        allowed_in_default_loop=allowed,
        rejection_reason=rejection_reason,
    )


def _split_mixed_obligation(spec: FormalObligationSpec) -> list[FormalObligationSpec]:
    """Split a mixed proof+compute obligation into separate obligations."""
    text = spec.source_text
    lowered = text.lower()
    
    has_compute = any(cue in lowered for cue in COMPUTE_CUES)
    has_proof = any(cue in lowered for cue in PROOF_CUES)
    
    if not (has_compute and has_proof):
        return [spec]  # Not actually mixed
    
    # Create proof-oriented obligation (remove compute cues)
    proof_text = text
    for cue in ["verify computationally", "check", "compute", "test"]:
        proof_text = proof_text.replace(cue, "")
    proof_text = f"Prove: {spec.source_text.split('and')[0].strip()}" if 'and' in text else f"Prove the local lemma: {text[:100]}"
    
    proof_spec = FormalObligationSpec(
        source_text=proof_text,
        channel_hint="proof",
        goal_kind="theorem" if spec.goal_kind == "theorem" else "lemma",
        theorem_name=spec.theorem_name,
        imports=spec.imports,
        variables=spec.variables,
        assumptions=spec.assumptions,
        statement=spec.statement,
        lean_declaration=spec.lean_declaration,
        tactic_hints=spec.tactic_hints,
        requires_proof=True,
        requires_evidence=False,
        metadata={**spec.metadata, "split_from": spec.id or text[:50], "split_type": "proof"},
    )
    
    # Create evidence-oriented obligation (remove proof cues)
    evidence_text = text
    for cue in ["prove", "theorem", "lemma", "show that", "establish"]:
        evidence_text = evidence_text.replace(cue, "")
    # Extract bounded part if present
    if "for n <=" in lowered or "for all n <=" in lowered:
        import re
        match = re.search(r"for (?:all )?n\s*<=\s*\d+", text, re.IGNORECASE)
        if match:
            evidence_text = f"Check computationally {match.group()}"
        else:
            evidence_text = f"Check bounded cases for: {text[:100]}"
    else:
        evidence_text = f"Check bounded cases for: {text[:100]}"
    
    evidence_spec = FormalObligationSpec(
        source_text=evidence_text,
        channel_hint="evidence",
        goal_kind="finite_check",
        bounded_domain_description=spec.bounded_domain_description,
        evidence_plan=spec.evidence_plan,
        requires_proof=False,
        requires_evidence=True,
        metadata={**spec.metadata, "split_from": spec.id or text[:50], "split_type": "evidence"},
    )
    
    return [proof_spec, evidence_spec]


def build_execution_plan(
    decision: ManagerDecision,
    policy: dict[str, Any] | None = None,
    memory: Any | None = None,
) -> ApprovedExecutionPlan:
    policy = policy or {}
    limits = policy.get("complexity_limits", {})
    
    # Adaptive budgeting based on memory
    max_proof, max_evidence, budget_notes = _compute_adaptive_budgets(
        decision, memory, limits
    )

    # Normalize obligations to structured form
    normalized_obligations = decision.get_normalized_obligations()
    
    # Split mixed obligations
    split_obligations: list[FormalObligationSpec] = []
    for spec in normalized_obligations:
        analyzed = analyze_obligation(spec)
        if analyzed.rejection_reason == "mixed_channels":
            # Try to split instead of rejecting
            split_result = _split_mixed_obligation(spec)
            split_obligations.extend(split_result)
        else:
            split_obligations.append(spec)
    
    # Analyze all obligations
    analyzed = [analyze_obligation(ob) for ob in split_obligations]
    approved_proof: list[str] = []
    approved_evidence: list[str] = []
    rejected: list[str] = []
    rejected_reasons: dict[str, str] = {}

    for meta in analyzed:
        if meta.submission_channel == "reject" or not meta.allowed_in_default_loop:
            # For excessive_scope, try to create more informative follow-up
            if meta.rejection_reason == "excessive_scope":
                rejected.append(meta.text)
                rejected_reasons[meta.text] = f"{meta.rejection_reason}:suggest_localized_lemma"
            else:
                rejected.append(meta.text)
                rejected_reasons[meta.text] = meta.rejection_reason or "excessive_scope"
            continue

        if meta.submission_channel == "aristotle_proof":
            if len(approved_proof) < max_proof:
                approved_proof.append(meta.text)
            else:
                rejected.append(meta.text)
                rejected_reasons[meta.text] = "proof_budget_exceeded"
            continue

        if meta.submission_channel == "computational_evidence":
            if len(approved_evidence) < max_evidence:
                approved_evidence.append(meta.text)
            else:
                rejected.append(meta.text)
                rejected_reasons[meta.text] = "evidence_budget_exceeded"

    if _should_throttle_proof(decision, memory):
        rejected.extend(approved_proof)
        for obligation in approved_proof:
            rejected_reasons[obligation] = "proof_timeout_backoff"
        approved_proof = []

    channel_used = "none"
    if approved_proof:
        channel_used = "aristotle_proof"
    elif approved_evidence:
        channel_used = "computational_evidence"

    return ApprovedExecutionPlan(
        original_obligations=[spec.source_text for spec in normalized_obligations],
        analyzed_obligations=analyzed,
        approved_proof_jobs=approved_proof,
        approved_evidence_jobs=approved_evidence,
        rejected_obligations=rejected,
        rejected_reasons=rejected_reasons,
        channel_used=channel_used,  # type: ignore[arg-type]
        max_proof_jobs_per_step=max_proof,
        budget_metadata={
            "max_proof": max_proof,
            "max_evidence": max_evidence,
            "budget_notes": budget_notes,
        },
    )


def _compute_adaptive_budgets(
    decision: ManagerDecision,
    memory: Any | None,
    limits: dict[str, Any],
) -> tuple[int, int, list[str]]:
    """Compute adaptive budgets based on recent history."""
    base_proof = int(limits.get("max_proof_obligations_per_step", 1))
    base_evidence = int(limits.get("max_evidence_jobs_per_step", 2))
    notes = []
    
    if memory is None:
        return base_proof, base_evidence, notes
    
    node_key = decision.target_frontier_node
    
    # Check evidence streak
    evidence_streak = memory.evidence_streaks.get(node_key, 0)
    if evidence_streak >= 2:
        # Reduce evidence budget, reserve for proof work
        base_evidence = max(1, base_evidence - 1)
        notes.append(f"reduced_evidence_budget_after_{evidence_streak}_evidence_only_results")
    
    # Check formalization failures
    formalization_streak = memory.formalization_streaks.get(node_key, 0)
    if formalization_streak >= 2:
        # Prioritize formalization work
        notes.append(f"prioritize_formalization_after_{formalization_streak}_failures")
    
    # Check timeout streak
    timeout_streak = memory.timeout_streaks.get(node_key, 0)
    if timeout_streak >= 2:
        # Shrink proof budget
        base_proof = max(1, base_proof - 1)
        notes.append(f"reduced_proof_budget_after_{timeout_streak}_timeouts")
    
    return base_proof, base_evidence, notes


def _should_throttle_proof(decision: ManagerDecision, memory: Any | None) -> bool:
    """Throttle proof submission if there have been repeated terminal failures."""
    if memory is None:
        return False
    penalty_key = f"{decision.target_frontier_node}:{decision.world_family}"
    retries = memory.retry_penalties.get(penalty_key, 0)
    
    # Count actual terminal failures (not timeouts from still-running jobs)
    terminal_failure_hits = 0
    for failure in memory.recent_failures[:10]:
        if (
            failure.get("world") == decision.world_family
            and failure.get("failure_type") in {"proof_failed", "budget_exhausted", "excessive_scope"}
        ):
            terminal_failure_hits += 1
    
    return retries >= 4 or terminal_failure_hits >= 3


def _has_bounded_cue(text: str) -> bool:
    if any(cue in text for cue in BOUNDED_CUES):
        return True
    if re.search(r"\b\d+\b", text):
        return True
    return False


def _has_unbounded_cue(text: str) -> bool:
    return any(cue in text for cue in UNBOUNDED_CUES)


def _looks_bounded_universal(text: str) -> bool:
    return bool(
        re.search(r"\b(for all|every)\b.{0,32}(<=|≤|up to|at most|\b\d+\b)", text)
    )


def _estimate_complexity(
    *,
    lowered: str,
    scope: str,
    quantifier_profile: str,
    obligation_type: str,
) -> str:
    if scope == "global" and quantifier_profile == "unbounded":
        return "unsafe"
    if "for all" in lowered and "cannot exist" in lowered:
        return "large"
    if obligation_type in {"counterexample_search", "finite_check"} and not _has_bounded_cue(lowered):
        return "large"
    if len(lowered) > 220:
        return "large"
    if scope == "semi_global":
        return "medium"
    if quantifier_profile == "bounded" and len(lowered) < 100:
        return "small"
    if len(lowered) < 60:
        return "micro"
    return "medium"


def _estimate_runtime(complexity_class: str) -> str:
    if complexity_class in {"micro", "small"}:
        return "fast"
    if complexity_class == "medium":
        return "moderate"
    if complexity_class in {"large", "unsafe"}:
        return "slow"
    return "unknown"
