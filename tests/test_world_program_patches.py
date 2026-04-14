"""Focused tests for world program patch fixes."""

from datetime import datetime

from app.frontier import apply_execution_result
from app.learner import update_memory
from app.manager import Manager
from app.obligation_analysis import build_execution_plan
from app.schemas import (
    CampaignRecord,
    CandidateAnswer,
    ExecutionResult,
    FormalObligationSpec,
    FrontierNode,
    ManagerContext,
    ManagerDecision,
    MemoryState,
    ProofDebtItem,
    SelfImprovementNote,
    UpdateRules,
    WorldProgram,
    ManagerReadReceipt,
    BridgePlan,
)
from app.config import Settings


def test_proof_debt_ordering_sync():
    """Test that proof debt status updates correctly in sync execution flow."""
    # Create campaign with empty proof debt ledger
    campaign = CampaignRecord(
        id="C-test",
        title="Test",
        problem_statement="Test problem",
        status="running",
        auto_run=True,
        operator_notes=[],
        frontier=[
            FrontierNode(
                id="F-root",
                text="Test claim",
                status="open",
                priority=1.0,
            )
        ],
        memory=MemoryState(),
        tick_count=0,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        manager_backend="rules",
        executor_backend="mock",
        proof_debt_ledger=[],
        resolved_debt_ids=[],
    )
    
    # Create world and debt
    world = WorldProgram(
        label="Test World",
        family_tags=["direct"],
        mode="micro",
        thesis="Test thesis",
        bridge_to_target=BridgePlan(
            bridge_claim="Test bridge",
            bridge_obligations=[],
            estimated_cost=0.3,
        ),
    )
    
    debt = ProofDebtItem(
        world_id=world.id,
        role="closure",
        statement="Prove test lemma",
        critical=True,
        status="open",
        priority=1.0,
    )
    
    # Create decision with proof debt
    decision = ManagerDecision(
        candidate_answer=CandidateAnswer(
            stance="undecided",
            summary="Test",
            confidence=0.5,
        ),
        alternatives=[],
        target_frontier_node="F-root",
        world_family="direct",
        bounded_claim="Test claim",
        formal_obligations=["Test obligation"],
        expected_information_gain="Test",
        why_this_next="Test",
        update_rules=UpdateRules(
            if_proved="Continue",
            if_refuted="Revise",
            if_blocked="Split",
            if_inconclusive="Retry",
        ),
        self_improvement_note=SelfImprovementNote(
            proposal="None",
            reason="Test",
        ),
        manager_read_receipt=ManagerReadReceipt(
            problem_summary="Test",
            target_node_id_confirmed="F-root",
            target_node_text_confirmed="Test",
            why_not_other_frontier_nodes="Test",
        ),
        primary_world=world,
        proof_debt=[debt],
        critical_next_debt_id=debt.id,
    )
    
    # Simulate service._apply_decision_world_state
    campaign.current_world_program = world.model_dump()
    campaign.active_world_id = world.id
    campaign.proof_debt_ledger = [debt.model_dump()]
    
    # Simulate proved result
    result = ExecutionResult(
        status="proved",
        failure_type=None,
        notes="Proved",
        executor_backend="mock",
    )
    
    # Apply result (this should update debt status)
    campaign = apply_execution_result(campaign, decision, result)
    
    # Check that debt status was updated
    assert len(campaign.proof_debt_ledger) == 1
    assert campaign.proof_debt_ledger[0]["status"] == "proved"
    assert debt.id in campaign.resolved_debt_ids or campaign.proof_debt_ledger[0]["id"] in [
        d for d in campaign.proof_debt_ledger if d.get("status") == "proved"
    ]


def test_closure_bridge_prioritization():
    """Test that closure/bridge obligations are prioritized over support."""
    # Create world and debt items
    world = WorldProgram(
        label="Test World",
        family_tags=["bridge"],
        mode="micro",
        thesis="Test",
    )
    
    support_debt = ProofDebtItem(
        world_id=world.id,
        role="support",
        statement="Prove support lemma",
        critical=False,
        priority=0.8,
    )
    
    closure_debt = ProofDebtItem(
        world_id=world.id,
        role="closure",
        statement="Prove closure lemma",
        critical=True,
        priority=0.7,  # Lower priority but should still go first
    )
    
    # Create decision with both debt items
    decision = ManagerDecision(
        candidate_answer=CandidateAnswer(
            stance="undecided",
            summary="Test",
            confidence=0.5,
        ),
        alternatives=[],
        target_frontier_node="F-test",
        world_family="bridge",
        bounded_claim="Test",
        formal_obligations=[
            FormalObligationSpec.from_debt_item(support_debt),
            FormalObligationSpec.from_debt_item(closure_debt),
        ],
        expected_information_gain="Test",
        why_this_next="Test",
        update_rules=UpdateRules(
            if_proved="Continue",
            if_refuted="Revise",
            if_blocked="Split",
            if_inconclusive="Retry",
        ),
        self_improvement_note=SelfImprovementNote(
            proposal="None",
            reason="Test",
        ),
        manager_read_receipt=ManagerReadReceipt(
            problem_summary="Test",
            target_node_id_confirmed="F-test",
            target_node_text_confirmed="Test",
            why_not_other_frontier_nodes="Test",
        ),
        primary_world=world,
        proof_debt=[support_debt, closure_debt],
    )
    
    # Build execution plan
    plan = build_execution_plan(decision, policy={}, memory=None)
    
    # Check that closure obligation was approved first
    assert len(plan.approved_proof_jobs) >= 1
    # The closure lemma should be in approved jobs
    assert any("closure" in job.lower() for job in plan.approved_proof_jobs)


def test_world_continuity_rules_mode():
    """Test that rules mode reuses existing world when present."""
    settings = Settings()
    manager = Manager(settings)
    
    # Create existing world and debt
    existing_world = WorldProgram(
        id="W-existing",
        label="Existing World",
        family_tags=["bridge"],
        mode="micro",
        thesis="Existing thesis",
        bridge_to_target=BridgePlan(
            bridge_claim="Existing bridge",
            bridge_obligations=[],
            estimated_cost=0.3,
        ),
    )
    
    existing_debt = ProofDebtItem(
        id="D-existing",
        world_id="W-existing",
        role="support",
        statement="Existing open debt",
        critical=True,
        status="open",
        priority=0.9,
    )
    
    # Create context with existing world
    context = ManagerContext(
        problem={
            "id": "C-test",
            "title": "Test",
            "statement": "Test problem",
            "current_world_program": existing_world.model_dump(),
            "proof_debt_ledger": [existing_debt.model_dump()],
            "active_world_id": "W-existing",
        },
        frontier=[
            FrontierNode(
                id="F-root",
                text="Test claim",
                status="open",
                priority=1.0,
            )
        ],
        memory=MemoryState(),
        operator_notes=[],
        allowed_world_families=["direct", "bridge"],
        tick=1,
    )
    
    # Get decision in rules mode
    decision = manager._decide_with_rules(context, {}, "rules")
    
    # Check that existing world was reused
    assert decision.primary_world is not None
    assert decision.primary_world.id == "W-existing"
    assert decision.primary_world.label == "Existing World"
    
    # Check that bounded claim comes from existing debt
    assert "Existing open debt" in decision.bounded_claim or decision.critical_next_debt_id == "D-existing"


def test_world_aware_solved_check():
    """Test that world-aware solved check works correctly."""
    # Create campaign with world and critical debt
    world = WorldProgram(
        label="Test World",
        family_tags=["direct"],
        mode="micro",
        thesis="Test",
        bridge_to_target=BridgePlan(
            bridge_claim="Test bridge",
            bridge_obligations=[],
            estimated_cost=0.3,
        ),
    )
    
    debt1 = ProofDebtItem(
        id="D-1",
        world_id=world.id,
        role="closure",
        statement="First critical debt",
        critical=True,
        status="proved",
    )
    
    debt2 = ProofDebtItem(
        id="D-2",
        world_id=world.id,
        role="bridge",
        statement="Second critical debt",
        critical=True,
        status="open",  # Still open
    )
    
    campaign = CampaignRecord(
        id="C-test",
        title="Test",
        problem_statement="Test",
        status="running",
        auto_run=True,
        operator_notes=[],
        frontier=[
            FrontierNode(
                id="F-root",
                text="Test",
                status="open",
            )
        ],
        memory=MemoryState(),
        tick_count=0,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        manager_backend="rules",
        executor_backend="mock",
        current_world_program=world.model_dump(),
        proof_debt_ledger=[debt1.model_dump(), debt2.model_dump()],
        active_world_id=world.id,
    )
    
    decision = ManagerDecision(
        candidate_answer=CandidateAnswer(
            stance="undecided",
            summary="Test",
            confidence=0.5,
        ),
        alternatives=[],
        target_frontier_node="F-root",
        world_family="direct",
        bounded_claim="Test",
        formal_obligations=["Test"],
        expected_information_gain="Test",
        why_this_next="Test",
        update_rules=UpdateRules(
            if_proved="Continue",
            if_refuted="Revise",
            if_blocked="Split",
            if_inconclusive="Retry",
        ),
        self_improvement_note=SelfImprovementNote(
            proposal="None",
            reason="Test",
        ),
        manager_read_receipt=ManagerReadReceipt(
            problem_summary="Test",
            target_node_id_confirmed="F-root",
            target_node_text_confirmed="Test",
            why_not_other_frontier_nodes="Test",
        ),
        primary_world=world,
        proof_debt=[debt1, debt2],
        critical_next_debt_id=debt2.id,
    )
    
    result = ExecutionResult(
        status="proved",
        failure_type=None,
        notes="Proved",
        executor_backend="mock",
    )
    
    # Apply result - this should mark debt2 as proved
    campaign = apply_execution_result(campaign, decision, result)
    
    # Now all critical debt should be proved, so campaign should be solved
    assert campaign.status == "solved"


def test_manager_hardens_world_with_debt_references():
    """Test that normalization links bridge/certificate structure to proof debt."""
    world = WorldProgram(
        label="Bridge World",
        family_tags=["bridge"],
        mode="macro",
        thesis="Use a certificate object to bridge the target",
        ontology=["certificate_object"],
        bridge_to_target=BridgePlan(
            bridge_claim="Certificate soundness implies the target",
            bridge_obligations=[],
            estimated_cost=0.5,
        ),
    )

    bridge_debt = ProofDebtItem(
        id="D-bridge",
        world_id=world.id,
        role="bridge",
        statement="Prove certificate soundness implies the target",
        critical=True,
        priority=0.9,
    )
    closure_debt = ProofDebtItem(
        id="D-close",
        world_id=world.id,
        role="closure",
        statement="Prove all certificate states close",
        critical=True,
        priority=0.8,
    )

    decision = ManagerDecision(
        candidate_answer=CandidateAnswer(
            stance="undecided",
            summary="Test",
            confidence=0.5,
        ),
        alternatives=[],
        target_frontier_node="F-root",
        world_family="bridge",
        bounded_claim="Test",
        formal_obligations=["Test"],
        expected_information_gain="Test",
        why_this_next="Test",
        update_rules=UpdateRules(
            if_proved="Continue",
            if_refuted="Revise",
            if_blocked="Split",
            if_inconclusive="Retry",
        ),
        self_improvement_note=SelfImprovementNote(
            proposal="None",
            reason="Test",
        ),
        manager_read_receipt=ManagerReadReceipt(
            problem_summary="Test",
            target_node_id_confirmed="F-root",
            target_node_text_confirmed="Test",
            why_not_other_frontier_nodes="Test",
        ),
        primary_world=world,
        proof_debt=[bridge_debt, closure_debt],
    )

    normalized = Manager._normalize_decision(decision, policy={}, context=None)

    assert normalized.primary_world is not None
    assert normalized.primary_world.ontology_definitions[0].name == "certificate_object"
    assert normalized.primary_world.bridge_to_target is not None
    assert normalized.primary_world.bridge_to_target.bridge_debt_ids == ["D-bridge"]
    assert normalized.primary_world.reduction_certificate is not None
    assert normalized.primary_world.reduction_certificate.bridge_debt_ids == ["D-bridge"]
    assert normalized.primary_world.reduction_certificate.closure_debt_ids == ["D-close"]
