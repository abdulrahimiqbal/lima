from app.obligation_analysis import analyze_obligation, build_execution_plan, _split_mixed_obligation
from app.schemas import (
    CandidateAnswer,
    FormalObligationSpec,
    MemoryState,
    ManagerDecision,
    SelfImprovementNote,
    UpdateRules,
)


def _decision(obligations: list[str]) -> ManagerDecision:
    return ManagerDecision(
        candidate_answer=CandidateAnswer(stance="undecided", summary="x", confidence=0.2),
        alternatives=[],
        target_frontier_node="F-1",
        world_family="direct",
        bounded_claim="local claim",
        formal_obligations=obligations,
        expected_information_gain="gain",
        why_this_next="why",
        update_rules=UpdateRules(
            if_proved="a",
            if_refuted="b",
            if_blocked="c",
            if_inconclusive="d",
        ),
        self_improvement_note=SelfImprovementNote(proposal="p", reason="r"),
    )


def test_local_proof_obligation_allowed_for_aristotle() -> None:
    analyzed = analyze_obligation("Prove the local lemma for the selected frontier node.")
    assert analyzed.submission_channel == "aristotle_proof"
    assert analyzed.allowed_in_default_loop is True


def test_bounded_finite_check_goes_to_evidence_channel() -> None:
    analyzed = analyze_obligation("Verify computationally for all n <= 1000 that the invariant holds.")
    assert analyzed.obligation_type == "finite_check"
    assert analyzed.submission_channel == "computational_evidence"


def test_global_universal_is_rejected() -> None:
    analyzed = analyze_obligation("For all integers n, prove the conjecture globally.")
    assert analyzed.submission_channel == "reject"
    assert analyzed.rejection_reason == "excessive_scope"


def test_mixed_bundle_is_rejected() -> None:
    analyzed = analyze_obligation(
        "Prove the theorem and verify computationally for n <= 10^6 in the same obligation."
    )
    assert analyzed.submission_channel == "reject"
    assert analyzed.rejection_reason == "mixed_channels"


def test_submission_gate_caps_proof_jobs_to_one() -> None:
    plan = build_execution_plan(
        _decision(
            [
                "Prove a local lemma for the active case.",
                "Show that the reduced subcase is locally consistent.",
            ]
        ),
        policy={"complexity_limits": {"max_proof_obligations_per_step": 1}},
    )
    assert len(plan.approved_proof_jobs) == 1
    assert len(plan.rejected_obligations) == 1


def test_submission_gate_separates_proof_and_evidence() -> None:
    plan = build_execution_plan(
        _decision(
            [
                "Prove a local lemma for the active case.",
                "Verify computationally for all n <= 200 that this subcase holds.",
            ]
        )
    )
    assert len(plan.approved_proof_jobs) == 1
    assert len(plan.approved_evidence_jobs) == 1
    assert plan.channel_used == "aristotle_proof"


def test_submission_gate_rejects_all_oversized_obligations() -> None:
    plan = build_execution_plan(
        _decision(
            [
                "For every integer m, show universal convergence with no bounded scope.",
            ]
        )
    )
    assert not plan.approved_proof_jobs
    assert not plan.approved_evidence_jobs
    assert plan.rejected_obligations


def test_submission_gate_throttles_proof_after_repeated_timeouts() -> None:
    mem = MemoryState(
        recent_failures=[
            {"world": "direct", "failure_type": "timeout", "claim": "x"},
            {"world": "direct", "failure_type": "timeout", "claim": "y"},
        ],
        retry_penalties={"F-1:direct": 5},
    )
    plan = build_execution_plan(
        _decision(
            [
                "Prove a local lemma for the active case.",
                "Verify computationally for all n <= 50 that this subcase holds.",
            ]
        ),
        memory=mem,
    )
    assert len(plan.approved_proof_jobs) == 0
    assert len(plan.approved_evidence_jobs) == 1
    assert plan.channel_used == "computational_evidence"


def test_mixed_obligation_is_split_not_rejected() -> None:
    """Test that mixed proof+compute obligations are split into separate obligations."""
    plan = build_execution_plan(
        _decision(
            [
                "Prove the theorem and verify computationally for n <= 100 in the same obligation.",
            ]
        )
    )
    # Should have split into proof and evidence
    assert len(plan.approved_proof_jobs) >= 1 or len(plan.approved_evidence_jobs) >= 1
    # Should not be rejected
    assert "mixed_channels" not in str(plan.rejected_reasons.values())


def test_structured_obligation_with_statement() -> None:
    """Test that structured obligations with statements are accepted for proof channel."""
    spec = FormalObligationSpec(
        source_text="Prove addition identity",
        statement="∀ n : ℕ, n + 0 = n",
        theorem_name="add_zero_right",
        goal_kind="theorem",
        lean_declaration="theorem add_zero_right : ∀ n : ℕ, n + 0 = n := by sorry",
    )
    analyzed = analyze_obligation(spec)
    # Should be accepted as proof obligation
    assert analyzed.submission_channel == "aristotle_proof"
    assert analyzed.allowed_in_default_loop is True


def test_adaptive_budgeting_reduces_evidence_after_streak() -> None:
    """Test that evidence budget is reduced after evidence_only streak."""
    mem = MemoryState(
        evidence_streaks={"F-1": 3},
    )
    plan = build_execution_plan(
        _decision(
            [
                "Verify computationally for all n <= 50 that this holds.",
                "Verify computationally for all n <= 100 that this also holds.",
            ]
        ),
        memory=mem,
    )
    # Evidence budget should be reduced
    assert "reduced_evidence_budget" in str(plan.budget_metadata.get("budget_notes", []))


def test_adaptive_budgeting_reduces_proof_after_timeout_streak() -> None:
    """Test that proof budget is reduced after timeout streak."""
    mem = MemoryState(
        timeout_streaks={"F-1": 3},
    )
    plan = build_execution_plan(
        _decision(
            [
                "Prove a local lemma for the active case.",
            ]
        ),
        memory=mem,
    )
    # Proof budget should be reduced
    assert "reduced_proof_budget" in str(plan.budget_metadata.get("budget_notes", []))


def test_split_mixed_obligation_creates_two_specs() -> None:
    """Test that _split_mixed_obligation creates proof and evidence specs."""
    spec = FormalObligationSpec(
        source_text="Prove the theorem and verify computationally for n <= 100",
        channel_hint="auto",
        goal_kind="theorem",
    )
    result = _split_mixed_obligation(spec)
    assert len(result) == 2
    # Check that one is proof-oriented and one is evidence-oriented
    assert any(s.channel_hint == "proof" for s in result)
    assert any(s.channel_hint == "evidence" for s in result)

