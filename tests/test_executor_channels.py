from app.config import Settings
from app.executor import Executor
from app.schemas import (
    ApprovedExecutionPlan,
    CandidateAnswer,
    ExecutionResult,
    FrontierNode,
    ManagerDecision,
    SelfImprovementNote,
    UpdateRules,
)


def _decision() -> ManagerDecision:
    return ManagerDecision(
        candidate_answer=CandidateAnswer(stance="undecided", summary="x", confidence=0.2),
        alternatives=[],
        target_frontier_node="F-1",
        world_family="direct",
        bounded_claim="local claim",
        formal_obligations=["Prove local lemma"],
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


def _campaign():
    from datetime import datetime, timezone
    from app.schemas import CampaignRecord, MemoryState

    return CampaignRecord(
        id="C-1",
        title="T",
        problem_statement="P",
        status="running",
        auto_run=False,
        operator_notes=[],
        frontier=[FrontierNode(id="F-1", text="claim")],
        memory=MemoryState(),
        tick_count=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        manager_backend="rules",
        executor_backend="aristotle",
    )


def test_proof_channel_path(monkeypatch) -> None:
    executor = Executor(Settings(executor_backend="aristotle", aristotle_api_key="k"))
    campaign = _campaign()
    decision = _decision()
    plan = ApprovedExecutionPlan(
        original_obligations=["Prove local lemma"],
        approved_proof_jobs=["Prove local lemma"],
        channel_used="aristotle_proof",
    )

    def fake_run_aristotle(c, d, p):
        return ExecutionResult(status="proved", notes="ok", executor_backend="aristotle")

    monkeypatch.setattr(executor, "_run_aristotle", fake_run_aristotle)
    result = executor.run(campaign, decision, plan)
    assert result.executor_backend == "aristotle"
    assert result.approved_jobs_count == 1
    assert result.channel_used == "aristotle_proof"


def test_evidence_channel_path() -> None:
    executor = Executor(Settings(executor_backend="mock"))
    campaign = _campaign()
    decision = _decision()
    plan = ApprovedExecutionPlan(
        original_obligations=["Verify computationally for n <= 100"],
        approved_evidence_jobs=["Verify computationally for n <= 100"],
        channel_used="computational_evidence",
    )
    result = executor.run(campaign, decision, plan)
    assert result.executor_backend == "evidence"
    assert result.failure_type == "evidence_only"
    assert result.channel_used == "computational_evidence"


def test_timeout_classification_path() -> None:
    executor = Executor(Settings(executor_backend="mock"))
    analyzed_map = {
        "For all integers n, prove convergence.": type(
            "Meta", (), {"scope": "global", "complexity_class": "unsafe"}
        )()
    }
    failure_type = executor._timeout_failure_type(
        ["For all integers n, prove convergence."],
        analyzed_map,
    )
    assert failure_type == "excessive_scope"
