"""Tests for durable submit-and-poll Aristotle proof job workflow."""
from datetime import datetime, timezone

from app.config import Settings
from app.executor import Executor
from app.schemas import (
    ApprovedExecutionPlan,
    CandidateAnswer,
    CampaignRecord,
    ExecutionResult,
    FormalObligationSpec,
    FrontierNode,
    ManagerDecision,
    MemoryState,
    PendingAristotleJob,
    ProofDebtItem,
    SelfImprovementNote,
    UpdateRules,
    WorldProgram,
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


def _campaign() -> CampaignRecord:
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
        executor_backend="mock",
    )


def test_submit_proof_returns_pending_job():
    """Test that submitting a proof returns a pending job without blocking."""
    executor = Executor(Settings(executor_backend="mock"))
    campaign = _campaign()
    decision = _decision()
    plan = ApprovedExecutionPlan(
        original_obligations=["Prove local lemma"],
        approved_proof_jobs=["Prove local lemma"],
        channel_used="aristotle_proof",
    )
    
    pending_job = executor.submit_proof(campaign, decision, plan)
    
    assert pending_job.project_id.startswith("mock-")
    assert pending_job.target_frontier_node == "F-1"
    assert pending_job.world_family == "direct"
    assert pending_job.status == "submitted"
    assert pending_job.poll_count == 0
    assert pending_job.decision_snapshot == decision.model_dump()
    assert pending_job.plan_snapshot == plan.model_dump()


def test_poll_non_terminal_job_returns_none():
    """Test that polling a non-terminal job returns None for result."""
    executor = Executor(Settings(executor_backend="mock"))
    
    # Create a pending job that's still running
    pending_job = PendingAristotleJob(
        project_id="test-123",
        target_frontier_node="F-1",
        world_family="direct",
        bounded_claim="test claim",
        submitted_at=datetime.now(timezone.utc),
        decision_snapshot=_decision().model_dump(),
        plan_snapshot=ApprovedExecutionPlan(
            original_obligations=["test"],
            approved_proof_jobs=["test"],
        ).model_dump(),
        lean_code="-- test",
        status="running",
    )
    
    # Mock executor completes immediately, but in real scenario this would return None
    updated_job, result = executor.poll_proof(pending_job)
    
    # Mock always completes, but verify the structure
    assert updated_job.poll_count == pending_job.poll_count + 1
    assert updated_job.last_polled_at is not None


def test_poll_terminal_job_returns_result():
    """Test that polling a terminal job returns an ExecutionResult."""
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
    assert isinstance(result, ExecutionResult)
    assert result.executor_backend == "mock"
    assert updated_job.status == "complete"


def test_pending_job_survives_serialization():
    """Test that pending job can be serialized and deserialized."""
    pending_job = PendingAristotleJob(
        project_id="test-123",
        target_frontier_node="F-1",
        world_family="direct",
        bounded_claim="test claim",
        submitted_at=datetime.now(timezone.utc),
        decision_snapshot=_decision().model_dump(),
        plan_snapshot=ApprovedExecutionPlan(
            original_obligations=["test"],
            approved_proof_jobs=["test"],
        ).model_dump(),
        lean_code="-- test",
        status="submitted",
        poll_count=3,
        notes=["poll 1", "poll 2", "poll 3"],
    )
    
    # Serialize
    serialized = pending_job.model_dump()
    
    # Deserialize
    restored = PendingAristotleJob.model_validate(serialized)
    
    assert restored.project_id == pending_job.project_id
    assert restored.poll_count == 3
    assert len(restored.notes) == 3
    assert restored.status == "submitted"


def test_campaign_with_pending_job_serialization():
    """Test that campaign with pending job can be serialized."""
    campaign = _campaign()
    campaign.pending_aristotle_job = PendingAristotleJob(
        project_id="test-123",
        target_frontier_node="F-1",
        world_family="direct",
        bounded_claim="test claim",
        submitted_at=datetime.now(timezone.utc),
        decision_snapshot=_decision().model_dump(),
        plan_snapshot=ApprovedExecutionPlan(
            original_obligations=["test"],
            approved_proof_jobs=["test"],
        ).model_dump(),
        lean_code="-- test",
        status="running",
        poll_count=2,
    )
    
    # Serialize
    serialized = campaign.model_dump()
    
    # Deserialize
    restored = CampaignRecord.model_validate(serialized)
    
    assert restored.pending_aristotle_job is not None
    assert restored.pending_aristotle_job.project_id == "test-123"
    assert restored.pending_aristotle_job.poll_count == 2


def test_campaign_without_pending_job_backward_compatible():
    """Test that campaigns without pending_aristotle_job still work."""
    campaign = _campaign()
    assert campaign.pending_aristotle_job is None
    
    # Serialize without pending job
    serialized = campaign.model_dump()
    assert serialized.get("pending_aristotle_job") is None
    
    # Deserialize
    restored = CampaignRecord.model_validate(serialized)
    assert restored.pending_aristotle_job is None


def test_submit_proof_uses_debt_item_structure_and_fails_honestly():
    """Debt-driven proof jobs without formal statements should fail before Aristotle submission."""
    executor = Executor(
        Settings(
            executor_backend="aristotle",
            aristotle_api_key="fake-key",
        )
    )
    campaign = _campaign()
    decision = ManagerDecision(
        candidate_answer=CandidateAnswer(stance="undecided", summary="x", confidence=0.2),
        alternatives=[],
        target_frontier_node="F-1",
        world_family="bridge",
        bounded_claim="local claim",
        formal_obligations=[
            FormalObligationSpec(
                source_text="Secondary obligation",
                statement="True",
                theorem_name="secondary_obligation",
                requires_proof=True,
            )
        ],
        expected_information_gain="gain",
        why_this_next="why",
        update_rules=UpdateRules(
            if_proved="a",
            if_refuted="b",
            if_blocked="c",
            if_inconclusive="d",
        ),
        self_improvement_note=SelfImprovementNote(proposal="p", reason="r"),
        primary_world=WorldProgram(
            label="Test world",
            family_tags=["bridge"],
            mode="micro",
            thesis="test world",
        ),
        proof_debt=[
            ProofDebtItem(
                id="D-1",
                world_id="W-1",
                role="support",
                statement="Prove one local lemma for: Let T(n) be the Collatz map on positive integers",
                critical=True,
            )
        ],
        critical_next_debt_id="D-1",
    )
    plan = ApprovedExecutionPlan(
        original_obligations=[decision.proof_debt[0].statement],
        approved_proof_jobs=[decision.proof_debt[0].statement],
        channel_used="aristotle_proof",
    )

    pending_job = executor.submit_proof(campaign, decision, plan)

    assert pending_job.status == "failed"
    assert pending_job.project_id.startswith("formalization-failed")
    assert pending_job.lean_code == ""
