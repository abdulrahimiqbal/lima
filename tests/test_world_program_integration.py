#!/usr/bin/env python
"""Integration test demonstrating world-program flow."""

from app.schemas import (
    WorldProgram,
    ProofDebtItem,
    ManagerDecision,
    CampaignRecord,
    FrontierNode,
    MemoryState,
    ExecutionResult,
    CandidateAnswer,
    Alternative,
    UpdateRules,
    SelfImprovementNote,
    ManagerReadReceipt,
    CompressionPrinciple,
    BridgePlan,
    SoundnessCertificate,
    ReductionCertificate,
)
from app.frontier import apply_execution_result
from app.learner import update_memory
from datetime import datetime


def test_world_program_flow():
    """Test complete flow: decision with world → execution → debt tracking → solved check."""
    
    # 1. Create a campaign with initial frontier
    campaign = CampaignRecord(
        id="C-test",
        title="Test Collatz Conjecture",
        problem_statement="Prove that the Collatz sequence reaches 1 for all positive integers",
        status="running",
        auto_run=True,
        operator_notes=[],
        frontier=[
            FrontierNode(
                id="F-root",
                text="Prove that the Collatz sequence reaches 1 for all positive integers",
                status="open",
                priority=1.0,
                kind="claim",
            )
        ],
        memory=MemoryState(),
        tick_count=0,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        manager_backend="rules",
        executor_backend="mock",
    )
    
    # 2. Create a world program (micro-world: bounded case)
    world = WorldProgram(
        label="Bounded Collatz World",
        family_tags=["bridge"],
        mode="micro",
        thesis="Prove Collatz for n ≤ 1000, then extend",
        ontology=["bounded_domain"],
        compression_principles=[
            CompressionPrinciple(
                name="bounded_verification",
                description="Verify all cases up to bound computationally"
            ),
            CompressionPrinciple(
                name="inductive_extension",
                description="Extend from bounded to unbounded via descent"
            ),
        ],
        bridge_to_target=BridgePlan(
            bridge_claim="If Collatz holds for n ≤ 1000 and descent argument works, then Collatz holds for all n",
            bridge_obligations=[
                "Verify Collatz for n ≤ 1000",
                "Prove descent lemma: if Collatz(n) for n > 1000, then Collatz(m) for some m < n",
            ],
            estimated_cost=0.4,
        ),
        soundness_certificate=SoundnessCertificate(
            source_world_statement="Prove Collatz for n ≤ 1000, then extend",
            target_statement="Collatz holds for all positive integers",
            interpretation_claim="Bounded verification plus descent is interpreted over the standard natural-number Collatz map.",
            soundness_debt_ids=["D-sound"],
        ),
        reduction_certificate=ReductionCertificate(
            closure_items=["Bounded verification complete"],
            bridge_items=["Descent lemma proved", "Soundness transfer proved"],
            support_items=[],
            total_debt_count=3,
        ),
    )
    
    # 3. Create proof debt
    debt_bounded = ProofDebtItem(
        world_id=world.id,
        role="closure",
        statement="Verify Collatz sequence reaches 1 for all n ≤ 1000",
        depends_on=[],
        critical=True,
        status="open",
        priority=1.0,
    )
    
    debt_descent = ProofDebtItem(
        id="D-descent",
        world_id=world.id,
        role="bridge",
        statement="Prove descent lemma: if n > 1000, Collatz(n) reduces to Collatz(m) for m < n",
        depends_on=[debt_bounded.id],
        critical=True,
        status="open",
        priority=0.9,
    )

    debt_soundness = ProofDebtItem(
        id="D-sound",
        world_id=world.id,
        role="bridge",
        debt_class="pullback_to_original",
        statement="Prove bounded verification plus descent implies classical Collatz over standard natural numbers",
        depends_on=[debt_bounded.id, debt_descent.id],
        critical=True,
        status="open",
        priority=0.85,
    )
    
    # 4. Create manager decision with world program
    decision = ManagerDecision(
        candidate_answer=CandidateAnswer(
            stance="likely_true",
            summary="Bounded verification should succeed, then extend via descent",
            confidence=0.7,
        ),
        alternatives=[],
        target_frontier_node="F-root",
        world_family="bridge",
        bounded_claim="Verify Collatz for n ≤ 1000",
        formal_obligations=["Computationally verify Collatz sequence for all n ≤ 1000"],
        expected_information_gain="High confidence in bounded case, foundation for extension",
        why_this_next="Start with bounded verification to build confidence before tackling full proof",
        update_rules=UpdateRules(
            if_proved="Proceed to descent lemma",
            if_refuted="Counterexample found - conjecture false",
            if_blocked="Reduce bound or check implementation",
            if_inconclusive="Increase bound or refine verification",
        ),
        self_improvement_note=SelfImprovementNote(
            proposal="Consider parallel verification strategies",
            reason="Bounded verification is embarrassingly parallel",
        ),
        manager_read_receipt=ManagerReadReceipt(
            problem_summary="Collatz conjecture for all positive integers",
            target_node_id_confirmed="F-root",
            target_node_text_confirmed="Prove that the Collatz sequence reaches 1 for all positive integers",
            why_not_other_frontier_nodes="Only one frontier node available",
        ),
        global_thesis="Reduce infinite problem to bounded verification + descent argument",
        primary_world=world,
        proof_debt=[debt_bounded, debt_descent, debt_soundness],
        critical_next_debt_id=debt_bounded.id,
    )
    
    # 5. Persist world program to campaign
    campaign.current_world_program = world.model_dump()
    campaign.proof_debt_ledger = [
        debt_bounded.model_dump(),
        debt_descent.model_dump(),
        debt_soundness.model_dump(),
    ]
    campaign.active_world_id = world.id
    
    print("✓ Created campaign with world program")
    print(f"  World: {world.label} (mode={world.mode})")
    print(f"  Thesis: {world.thesis}")
    print(f"  Critical debt items: {len([d for d in decision.proof_debt if d.critical])}")
    print()
    
    # 6. Simulate execution result: bounded verification succeeds
    result_bounded = ExecutionResult(
        status="proved",
        failure_type=None,
        notes="Computational verification complete: all n ≤ 1000 reach 1",
        artifacts=["verification_log.txt"],
        spawned_nodes=[],
        executor_backend="computational_evidence",
        channel_used="computational_evidence",
    )
    
    # 7. Apply result and update memory
    campaign = apply_execution_result(campaign, decision, result_bounded)
    campaign = update_memory(campaign, decision, result_bounded, policy={})
    
    print("✓ Applied bounded verification result")
    print(f"  Root node status: {campaign.frontier[0].status}")
    print(f"  Campaign status: {campaign.status}")
    
    # Check debt ledger updated
    debt_ledger = campaign.proof_debt_ledger
    bounded_debt = next(d for d in debt_ledger if d["id"] == debt_bounded.id)
    print(f"  Bounded debt status: {bounded_debt['status']}")
    assert bounded_debt["status"] == "proved", "Bounded debt should be marked proved"
    print()
    
    # 8. Campaign should NOT be solved yet (bridge debt still open)
    assert campaign.status == "running", "Campaign should still be running (bridge debt open)"
    print("✓ Campaign correctly remains running (bridge debt not yet proved)")
    print()
    
    # 9. Create second decision for descent lemma
    decision2 = ManagerDecision(
        candidate_answer=CandidateAnswer(
            stance="likely_true",
            summary="Descent lemma should close the proof",
            confidence=0.8,
        ),
        alternatives=[],
        target_frontier_node="F-root",
        world_family="bridge",
        bounded_claim="Prove descent lemma",
        formal_obligations=["Prove: if n > 1000, Collatz(n) reduces to Collatz(m) for m < n"],
        expected_information_gain="Completes bridge to full theorem",
        why_this_next="Final critical debt item",
        update_rules=UpdateRules(
            if_proved="Campaign solved",
            if_refuted="Bridge failed, need new world",
            if_blocked="Split into smaller lemmas",
            if_inconclusive="Strengthen assumptions",
        ),
        self_improvement_note=SelfImprovementNote(
            proposal="None",
            reason="Final step",
        ),
        manager_read_receipt=ManagerReadReceipt(
            problem_summary="Collatz conjecture",
            target_node_id_confirmed="F-root",
            target_node_text_confirmed="Prove Collatz",
            why_not_other_frontier_nodes="Focused on critical debt",
        ),
        primary_world=world,
        proof_debt=[debt_bounded, debt_descent, debt_soundness],
        critical_next_debt_id=debt_descent.id,
    )
    
    # Update debt ledger with current status
    campaign.proof_debt_ledger = [
        {**debt_bounded.model_dump(), "status": "proved"},
        {**debt_descent.model_dump(), "status": "open"},
        {**debt_soundness.model_dump(), "status": "open"},
    ]
    
    # 10. Simulate execution result: descent lemma proved
    result_descent = ExecutionResult(
        status="proved",
        failure_type=None,
        notes="Descent lemma proved via Lean",
        artifacts=["descent_proof.lean"],
        spawned_nodes=[],
        executor_backend="aristotle_proof",
        channel_used="aristotle_proof",
    )
    
    # 11. Apply result
    campaign = apply_execution_result(campaign, decision2, result_descent)
    campaign = update_memory(campaign, decision2, result_descent, policy={})
    
    print("✓ Applied descent lemma result")
    print(f"  Root node status: {campaign.frontier[0].status}")
    print(f"  Campaign status: {campaign.status}")
    
    # Check debt ledger
    descent_debt = next(d for d in campaign.proof_debt_ledger if d["id"] == debt_descent.id)
    print(f"  Descent debt status: {descent_debt['status']}")
    assert descent_debt["status"] == "proved", "Descent debt should be marked proved"
    print()
    
    # 12. Campaign should NOT be solved yet (soundness transfer still open)
    assert campaign.status == "running", "Campaign should still be running (soundness debt open)"
    print("✓ Campaign correctly remains running (soundness transfer not yet proved)")
    print()

    # 13. Prove the soundness transfer back to standard Collatz
    decision3 = ManagerDecision(
        candidate_answer=CandidateAnswer(
            stance="likely_true",
            summary="Soundness transfer should close the proof",
            confidence=0.85,
        ),
        alternatives=[],
        target_frontier_node="F-root",
        world_family="bridge",
        bounded_claim="Prove soundness transfer",
        formal_obligations=[
            "Prove bounded verification plus descent implies classical Collatz over standard natural numbers"
        ],
        expected_information_gain="Transfers the world result back to the original theorem",
        why_this_next="Final critical soundness debt item",
        update_rules=UpdateRules(
            if_proved="Campaign solved",
            if_refuted="Soundness bridge failed, need new world",
            if_blocked="Split transfer theorem",
            if_inconclusive="Refine interpretation",
        ),
        self_improvement_note=SelfImprovementNote(
            proposal="None",
            reason="Final transfer step",
        ),
        manager_read_receipt=ManagerReadReceipt(
            problem_summary="Collatz conjecture",
            target_node_id_confirmed="F-root",
            target_node_text_confirmed="Prove Collatz",
            why_not_other_frontier_nodes="Focused on critical soundness debt",
        ),
        primary_world=world,
        proof_debt=[debt_bounded, debt_descent, debt_soundness],
        critical_next_debt_id=debt_soundness.id,
    )

    campaign.proof_debt_ledger = [
        {**debt_bounded.model_dump(), "status": "proved"},
        {**debt_descent.model_dump(), "status": "proved"},
        {**debt_soundness.model_dump(), "status": "open"},
    ]

    result_soundness = ExecutionResult(
        status="proved",
        failure_type=None,
        notes="Soundness transfer proved via Lean",
        artifacts=["soundness_transfer.lean"],
        spawned_nodes=[],
        executor_backend="aristotle_proof",
        channel_used="aristotle_proof",
    )

    campaign = apply_execution_result(campaign, decision3, result_soundness)
    campaign = update_memory(campaign, decision3, result_soundness, policy={})

    # 14. Campaign should NOW be solved (closure + bridge + soundness proved)
    assert campaign.status == "solved", "Campaign should be solved (closure, bridge, and soundness proved)"
    print("✓ Campaign correctly marked SOLVED")
    print("  All critical debt items proved")
    print("  Valid bridge to target exists")
    print("  Soundness transfer to the original theorem is proved")
    print("  World-aware solved criterion satisfied")
    print()
    
    # 15. Check world diagnostics
    world_diag = campaign.memory.world_diagnostics.get(world.id, {})
    print("✓ World diagnostics tracked:")
    print(f"  Proof hits: {world_diag.get('proof_hits', 0)}")
    print(f"  Evidence hits: {world_diag.get('evidence_hits', 0)}")
    print(f"  Critical proved: {world_diag.get('critical_proved', 0)}/{world_diag.get('critical_total', 0)}")
    print()


def test_world_failure_classification():
    """Test that world failures are classified correctly."""
    
    campaign = CampaignRecord(
        id="C-test2",
        title="Test World Failure",
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
                kind="claim",
            )
        ],
        memory=MemoryState(),
        tick_count=0,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        manager_backend="rules",
        executor_backend="mock",
    )
    
    world = WorldProgram(
        label="Test World",
        family_tags=["direct"],
        mode="macro",
        thesis="Test thesis",
    )
    
    debt = ProofDebtItem(
        world_id=world.id,
        role="closure",
        statement="Test statement",
        critical=True,
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
    )
    
    campaign.current_world_program = world.model_dump()
    campaign.proof_debt_ledger = [debt.model_dump()]
    campaign.active_world_id = world.id
    
    # Test bad_bridge failure
    result = ExecutionResult(
        status="blocked",
        failure_type="bad_bridge",
        notes="Bridge to target collapsed",
        executor_backend="mock",
    )
    
    campaign = update_memory(campaign, decision, result, policy={})
    
    # Check diagnostics tracked bridge failure
    world_diag = campaign.memory.world_diagnostics.get(world.id, {})
    assert world_diag.get("bridge_failures", 0) > 0, "Bridge failure should be tracked"
    
    print("✓ World failure classification works")
    print(f"  Bridge failures tracked: {world_diag['bridge_failures']}")
    print()


if __name__ == "__main__":
    print("=" * 60)
    print("World Program Integration Test")
    print("=" * 60)
    print()
    
    test_world_program_flow()
    test_world_failure_classification()
    
    print("=" * 60)
    print("✅ All integration tests passed!")
    print("=" * 60)
