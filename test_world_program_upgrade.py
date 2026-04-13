#!/usr/bin/env python
"""Test the world program upgrade implementation."""

from app.schemas import (
    TheoremDelta,
    CompressionPrinciple,
    BridgePlan,
    ReductionCertificate,
    WorldProgram,
    ProofDebtItem,
    ManagerDecision,
    CampaignRecord,
    FormalObligationSpec,
    CandidateAnswer,
    Alternative,
    UpdateRules,
    SelfImprovementNote,
    ManagerReadReceipt,
    MemoryState,
    FrontierNode,
)
from datetime import datetime


def test_theorem_delta():
    """Test TheoremDelta model."""
    delta = TheoremDelta(
        delta_type="strengthen_hypothesis",
        source_claim="For all n, P(n) holds",
        transformed_claim="For all n > 10, P(n) holds",
        distance_from_target=0.2,
        bridge_back_claim="If P(n) for n > 10, then check base cases separately",
        estimated_proof_gain=0.7,
        estimated_bridge_cost=0.3,
    )
    assert delta.delta_type == "strengthen_hypothesis"
    assert delta.distance_from_target == 0.2
    print("✓ TheoremDelta works")


def test_world_program():
    """Test WorldProgram model."""
    world = WorldProgram(
        label="Test micro-world",
        family_tags=["bridge"],
        mode="micro",
        thesis="Reduce to bounded case",
        ontology=["bounded_domain"],
        compression_principles=[
            CompressionPrinciple(name="descent", description="Use descent argument")
        ],
        bridge_to_target=BridgePlan(
            bridge_claim="If bounded case holds, extend to full",
            bridge_obligations=["Prove extension lemma"],
            estimated_cost=0.4,
        ),
        reduction_certificate=ReductionCertificate(
            closure_items=["Bounded case proved"],
            bridge_items=["Extension lemma"],
            support_items=[],
            total_debt_count=2,
        ),
    )
    assert world.mode == "micro"
    assert len(world.compression_principles) == 1
    print("✓ WorldProgram works")


def test_proof_debt_item():
    """Test ProofDebtItem model."""
    debt = ProofDebtItem(
        world_id="W-test123",
        role="closure",
        statement="Prove the bounded case",
        depends_on=[],
        critical=True,
        status="open",
        priority=1.0,
    )
    assert debt.role == "closure"
    assert debt.critical is True
    print("✓ ProofDebtItem works")


def test_formal_obligation_from_debt():
    """Test FormalObligationSpec.from_debt_item."""
    debt = ProofDebtItem(
        world_id="W-test123",
        role="bridge",
        statement="Prove the bridge lemma",
        depends_on=[],
        critical=True,
        status="open",
        priority=0.9,
    )
    
    spec = FormalObligationSpec.from_debt_item(debt)
    assert spec.channel_hint == "proof"
    assert spec.goal_kind == "theorem"
    assert spec.metadata["debt_role"] == "bridge"
    assert spec.metadata["debt_critical"] is True
    print("✓ FormalObligationSpec.from_debt_item works")


def test_manager_decision_with_world():
    """Test ManagerDecision with world program fields."""
    world = WorldProgram(
        label="Test world",
        family_tags=["direct"],
        mode="macro",
        thesis="Direct proof approach",
    )
    
    debt = ProofDebtItem(
        world_id=world.id,
        role="support",
        statement="Prove supporting lemma",
        critical=True,
    )
    
    decision = ManagerDecision(
        candidate_answer=CandidateAnswer(
            stance="likely_true",
            summary="Test summary",
            confidence=0.6,
        ),
        alternatives=[],
        target_frontier_node="F-test",
        world_family="direct",
        bounded_claim="Test claim",
        formal_obligations=["Test obligation"],
        expected_information_gain="High",
        why_this_next="Testing",
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
            problem_summary="Test problem",
            target_node_id_confirmed="F-test",
            target_node_text_confirmed="Test text",
            why_not_other_frontier_nodes="Test reason",
        ),
        global_thesis="Test global thesis",
        primary_world=world,
        proof_debt=[debt],
        critical_next_debt_id=debt.id,
    )
    
    assert decision.primary_world is not None
    assert decision.primary_world.id == world.id
    assert len(decision.proof_debt) == 1
    assert decision.critical_next_debt_id == debt.id
    print("✓ ManagerDecision with world program works")


def test_campaign_record_with_world():
    """Test CampaignRecord with world program fields."""
    campaign = CampaignRecord(
        id="C-test",
        title="Test Campaign",
        problem_statement="Test problem",
        status="running",
        auto_run=True,
        operator_notes=[],
        frontier=[
            FrontierNode(
                text="Test node",
                status="open",
            )
        ],
        memory=MemoryState(),
        tick_count=0,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        manager_backend="rules",
        executor_backend="mock",
        current_world_program={"id": "W-test", "label": "Test"},
        proof_debt_ledger=[{"id": "D-test", "statement": "Test debt"}],
        resolved_debt_ids=["D-old"],
        active_world_id="W-test",
    )
    
    assert campaign.current_world_program is not None
    assert campaign.active_world_id == "W-test"
    assert len(campaign.proof_debt_ledger) == 1
    assert len(campaign.resolved_debt_ids) == 1
    print("✓ CampaignRecord with world program works")


def test_memory_state_with_diagnostics():
    """Test MemoryState with world diagnostics."""
    memory = MemoryState()
    memory.world_diagnostics["W-test"] = {
        "debt_total": 5,
        "debt_proved": 2,
        "critical_total": 3,
        "critical_proved": 1,
        "bridge_failures": 0,
        "closure_failures": 0,
        "evidence_hits": 4,
        "proof_hits": 2,
    }
    
    assert "W-test" in memory.world_diagnostics
    assert memory.world_diagnostics["W-test"]["debt_total"] == 5
    print("✓ MemoryState with world diagnostics works")


def test_backward_compatibility():
    """Test that old-style decisions still work."""
    decision = ManagerDecision(
        candidate_answer=CandidateAnswer(
            stance="undecided",
            summary="Old style",
            confidence=0.5,
        ),
        alternatives=[],
        target_frontier_node="F-old",
        world_family="direct",
        bounded_claim="Old claim",
        formal_obligations=["Old obligation"],
        expected_information_gain="Medium",
        why_this_next="Old reason",
        update_rules=UpdateRules(
            if_proved="Close",
            if_refuted="Refute",
            if_blocked="Split",
            if_inconclusive="Retry",
        ),
        self_improvement_note=SelfImprovementNote(
            proposal="None",
            reason="Old",
        ),
        manager_read_receipt=ManagerReadReceipt(
            problem_summary="Old problem",
            target_node_id_confirmed="F-old",
            target_node_text_confirmed="Old text",
            why_not_other_frontier_nodes="Old reason",
        ),
    )
    
    # Should work without world program fields
    assert decision.primary_world is None
    assert len(decision.proof_debt) == 0
    assert decision.critical_next_debt_id is None
    print("✓ Backward compatibility works")


if __name__ == "__main__":
    print("Testing world program upgrade...")
    print()
    
    test_theorem_delta()
    test_world_program()
    test_proof_debt_item()
    test_formal_obligation_from_debt()
    test_manager_decision_with_world()
    test_campaign_record_with_world()
    test_memory_state_with_diagnostics()
    test_backward_compatibility()
    
    print()
    print("✅ All tests passed!")
