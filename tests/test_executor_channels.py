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

    from datetime import datetime, timezone
    from app.schemas import PendingAristotleJob
    
    def fake_submit_proof(c, d, p):
        return PendingAristotleJob(
            project_id="test-project-123",
            target_frontier_node=d.target_frontier_node,
            world_family=d.world_family,
            bounded_claim=d.bounded_claim,
            submitted_at=datetime.now(timezone.utc),
            decision_snapshot=d.model_dump(),
            plan_snapshot=p.model_dump(),
            lean_code="-- test lean",
            status="submitted",
        )
    
    def fake_poll_proof(pending_job):
        updated_job = pending_job.model_copy(deep=True)
        updated_job.poll_count += 1
        updated_job.status = "complete"
        result = ExecutionResult(status="proved", notes="ok", executor_backend="aristotle")
        return updated_job, result

    monkeypatch.setattr(executor._proof_adapter, "submit_proof", fake_submit_proof)
    monkeypatch.setattr(executor._proof_adapter, "poll_proof", fake_poll_proof)
    
    # Test submit
    pending_job = executor.submit_proof(campaign, decision, plan)
    assert pending_job.project_id == "test-project-123"
    assert pending_job.status == "submitted"
    
    # Test poll
    updated_job, result = executor.poll_proof(pending_job)
    assert updated_job.poll_count == 1
    assert updated_job.status == "complete"
    assert result is not None
    assert result.status == "proved"


def test_evidence_channel_path() -> None:
    executor = Executor(Settings(executor_backend="mock"))
    campaign = _campaign()
    decision = _decision()
    plan = ApprovedExecutionPlan(
        original_obligations=["Verify computationally for n <= 100"],
        approved_evidence_jobs=["Verify computationally for n <= 100"],
        channel_used="computational_evidence",
    )
    result = executor.run_evidence(campaign, decision, plan)
    assert result.executor_backend == "evidence"
    assert result.failure_type == "evidence_only"
    assert result.channel_used == "computational_evidence"


def test_mock_proof_never_returns_proved_or_refuted() -> None:
    executor = Executor(Settings(executor_backend="mock"))
    campaign = _campaign()
    decision = _decision()
    plan = ApprovedExecutionPlan(
        original_obligations=["Prove local lemma"],
        approved_proof_jobs=["Prove local lemma"],
        channel_used="aristotle_proof",
    )
    # Submit and poll
    pending_job = executor.submit_proof(campaign, decision, plan)
    updated_job, result = executor.poll_proof(pending_job)
    
    assert result is not None
    assert result.executor_backend == "mock"
    assert result.status in {"inconclusive", "blocked"}
    assert result.status not in {"proved", "refuted"}


def test_executor_backend_alias_http_uses_aristotle_adapter() -> None:
    executor = Executor(
        Settings(
            executor_backend="http",
            aristotle_api_key="k",
            aristotle_base_url="https://example.com",
        )
    )
    assert executor._proof_adapter.name == "aristotle_sdk"
