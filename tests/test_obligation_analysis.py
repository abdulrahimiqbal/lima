from app.obligation_analysis import analyze_obligation, build_execution_plan
from app.schemas import (
    CandidateAnswer,
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
                "For all integers n, prove the global statement and verify computationally for n <= 10^9.",
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
