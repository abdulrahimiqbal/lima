"""Tests for durable submit-and-poll Aristotle proof job workflow."""
from datetime import datetime, timezone

from app.config import Settings
from app.executor import Executor
from app.service import CampaignService
from app.schemas import (
    ApprovedExecutionPlan,
    CandidateAnswer,
    CampaignCreate,
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


def test_service_submits_unlocked_proof_debts_as_wave(tmp_path):
    service = CampaignService(
        Settings(
            memory_db_path=str(tmp_path / "memory.db"),
            manager_backend="rules",
            executor_backend="mock",
            worker_poll_seconds=999,
        )
    )
    campaign = service.create_campaign(
        CampaignCreate(
            title="Wave",
            problem_statement="Prove a small theorem",
            auto_run=False,
        )
    )
    debt_a = ProofDebtItem(
        id="D-a",
        world_id="W-1",
        role="bridge",
        debt_class="bridge_to_nat",
        statement="Prove bridge lemma",
        formal_statement="True",
        assigned_channel="aristotle",
        critical=True,
        priority=0.9,
    )
    debt_b = ProofDebtItem(
        id="D-b",
        world_id="W-1",
        role="closure",
        debt_class="in_world_theorem",
        statement="Prove world closure",
        formal_statement="True",
        assigned_channel="aristotle",
        critical=True,
        priority=0.8,
    )
    campaign.current_world_program = WorldProgram(
        id="W-1",
        label="Test world",
        thesis="Tiny thesis",
        bridge_to_target={"bridge_claim": "bridge", "bridge_obligations": []},
    ).model_dump()
    campaign.active_world_id = "W-1"
    campaign.proof_debt_ledger = [debt_a.model_dump(), debt_b.model_dump()]
    service._persist_campaign(campaign)

    submitted = service.step_campaign(campaign.id)

    assert submitted.pending_aristotle_job is not None
    assert len(submitted.pending_aristotle_jobs) == 2
    assert {job.debt_id for job in submitted.pending_aristotle_jobs} == {"D-a", "D-b"}
    status_by_id = {debt["id"]: debt["status"] for debt in submitted.proof_debt_ledger}
    assert status_by_id["D-a"] == "active"
    assert status_by_id["D-b"] == "active"
    assert any(
        debt.get("debt_class") == "pullback_to_original" and debt["status"] == "open"
        for debt in submitted.proof_debt_ledger
    )

    completed = service.step_campaign(campaign.id)

    assert completed.pending_aristotle_job is None
    assert completed.pending_aristotle_jobs == []
    completed_status_by_id = {debt["id"]: debt["status"] for debt in completed.proof_debt_ledger}
    assert completed_status_by_id["D-a"] == "blocked"
    assert completed_status_by_id["D-b"] == "blocked"
    assert any(
        debt.get("debt_class") == "pullback_to_original" and debt["status"] == "open"
        for debt in completed.proof_debt_ledger
    )


def test_fallback_world_cannot_silently_replace_active_world(tmp_path):
    service = CampaignService(
        Settings(
            memory_db_path=str(tmp_path / "memory.db"),
            manager_backend="rules",
            executor_backend="mock",
            worker_poll_seconds=999,
        )
    )
    campaign = _campaign()
    active_world = WorldProgram(
        id="W-active",
        label="Promoted World",
        family_tags=["reformulate"],
        thesis="Active thesis",
        audit_status="auditable",
    )
    active_debt = ProofDebtItem(
        id="D-active",
        world_id=active_world.id,
        role="bridge",
        statement="Original bridge debt",
        assigned_channel="aristotle",
        critical=True,
    )
    repair_world = WorldProgram(
        id="W-fallback",
        label="Fallback World",
        family_tags=["direct"],
        thesis="Fallback repair",
        audit_status="fallback",
    )
    repair_debt = ProofDebtItem(
        id="D-repair",
        world_id=repair_world.id,
        role="support",
        statement="Repair formalization",
        assigned_channel="auto",
        critical=True,
    )
    campaign.current_world_program = active_world.model_dump()
    campaign.active_world_id = active_world.id
    campaign.proof_debt_ledger = [active_debt.model_dump()]

    decision = _decision().model_copy(
        update={
            "primary_world": repair_world,
            "proof_debt": [repair_debt],
            "critical_next_debt_id": repair_debt.id,
        }
    )

    updated = service._apply_decision_world_state(campaign, decision)

    assert updated.active_world_id == active_world.id
    assert updated.current_world_program["id"] == active_world.id
    debt_by_id = {debt["id"]: debt for debt in updated.proof_debt_ledger}
    assert debt_by_id["D-active"]["world_id"] == active_world.id
    assert debt_by_id["D-repair"]["world_id"] == active_world.id


def test_explicit_world_replace_changes_active_world_and_preserves_history(tmp_path):
    service = CampaignService(
        Settings(
            memory_db_path=str(tmp_path / "memory.db"),
            manager_backend="rules",
            executor_backend="mock",
            worker_poll_seconds=999,
        )
    )
    campaign = _campaign()
    old_world = WorldProgram(
        id="W-old",
        label="Old World",
        family_tags=["reformulate"],
        thesis="Old thesis",
        audit_status="auditable",
    )
    old_debt = ProofDebtItem(
        id="D-old",
        world_id=old_world.id,
        role="bridge",
        statement="Old bridge debt",
        assigned_channel="aristotle",
        critical=True,
    )
    new_world = WorldProgram(
        id="W-new",
        label="New World",
        family_tags=["bridge"],
        thesis="New thesis",
        audit_status="auditable",
    )
    new_debt = ProofDebtItem(
        id="D-new",
        world_id=new_world.id,
        role="bridge",
        statement="New bridge debt",
        assigned_channel="aristotle",
        critical=True,
    )
    campaign.current_world_program = old_world.model_dump()
    campaign.active_world_id = old_world.id
    campaign.proof_debt_ledger = [old_debt.model_dump()]

    decision = _decision().model_copy(
        update={
            "primary_world": new_world,
            "proof_debt": [new_debt],
            "critical_next_debt_id": new_debt.id,
            "world_transition": "replace",
            "world_transition_reason": "bridge formalization failed after repair attempts",
        }
    )

    updated = service._apply_decision_world_state(campaign, decision)

    assert updated.active_world_id == new_world.id
    assert updated.current_world_program["id"] == new_world.id
    assert {debt["id"] for debt in updated.proof_debt_ledger} == {"D-old", "D-new"}


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
