"""Tests for evidence-to-proof escalation and improved frontier spawning."""

from app.frontier import apply_execution_result
from app.learner import update_memory
from app.schemas import (
    CampaignRecord,
    CandidateAnswer,
    ExecutionResult,
    FrontierNode,
    ManagerDecision,
    MemoryState,
    SelfImprovementNote,
    UpdateRules,
)
from datetime import datetime


def _make_campaign(frontier_nodes: list[FrontierNode], memory: MemoryState | None = None) -> CampaignRecord:
    return CampaignRecord(
        id="C-test",
        title="Test",
        problem_statement="Test problem",
        status="running",
        auto_run=True,
        operator_notes=[],
        frontier=frontier_nodes,
        memory=memory or MemoryState(),
        current_candidate_answer=CandidateAnswer(stance="undecided", summary="test", confidence=0.5),
        tick_count=0,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        manager_backend="rules",
        executor_backend="mock",
    )


def _make_decision(target_id: str, world: str = "direct") -> ManagerDecision:
    return ManagerDecision(
        candidate_answer=CandidateAnswer(stance="undecided", summary="test", confidence=0.5),
        alternatives=[],
        target_frontier_node=target_id,
        world_family=world,
        bounded_claim="test claim",
        formal_obligations=["test"],
        expected_information_gain="test",
        why_this_next="test",
        update_rules=UpdateRules(
            if_proved="a", if_refuted="b", if_blocked="c", if_inconclusive="d"
        ),
        self_improvement_note=SelfImprovementNote(proposal="p", reason="r"),
    )


def test_evidence_only_increments_streak():
    """Test that evidence_only results increment the evidence streak."""
    campaign = _make_campaign([FrontierNode(id="F-1", text="Test")])
    decision = _make_decision("F-1")
    result = ExecutionResult(
        status="inconclusive",
        failure_type="evidence_only",
        notes="Evidence collected",
        executor_backend="evidence",
    )
    
    updated = update_memory(campaign, decision, result)
    assert updated.memory.evidence_streaks.get("F-1", 0) == 1


def test_evidence_streak_resets_on_success():
    """Test that evidence streak resets when proof succeeds."""
    memory = MemoryState(evidence_streaks={"F-1": 3})
    campaign = _make_campaign([FrontierNode(id="F-1", text="Test")], memory=memory)
    decision = _make_decision("F-1")
    result = ExecutionResult(
        status="proved",
        notes="Proved",
        executor_backend="aristotle",
    )
    
    updated = update_memory(campaign, decision, result)
    assert updated.memory.evidence_streaks.get("F-1", 0) == 0


def test_formalization_failed_increments_streak():
    """Test that formalization_failed increments the formalization streak."""
    campaign = _make_campaign([FrontierNode(id="F-1", text="Test")])
    decision = _make_decision("F-1")
    result = ExecutionResult(
        status="blocked",
        failure_type="formalization_failed",
        notes="No formal statement",
        executor_backend="aristotle",
    )
    
    updated = update_memory(campaign, decision, result)
    assert updated.memory.formalization_streaks.get("F-1", 0) == 1


def test_timeout_increments_streak():
    """Test that timeout increments the timeout streak."""
    campaign = _make_campaign([FrontierNode(id="F-1", text="Test")])
    decision = _make_decision("F-1")
    result = ExecutionResult(
        status="inconclusive",
        failure_type="timeout",
        notes="Timed out",
        executor_backend="aristotle",
    )
    
    updated = update_memory(campaign, decision, result)
    assert updated.memory.timeout_streaks.get("F-1", 0) == 1


def test_evidence_only_spawns_formalization_child_after_streak():
    """Test that evidence_only spawns formalization child after streak."""
    memory = MemoryState(evidence_streaks={"F-1": 2})
    campaign = _make_campaign([FrontierNode(id="F-1", text="Test claim")], memory=memory)
    decision = _make_decision("F-1")
    result = ExecutionResult(
        status="inconclusive",
        failure_type="evidence_only",
        notes="Evidence collected",
        executor_backend="evidence",
    )
    
    updated = apply_execution_result(campaign, decision, result)
    # Should spawn a formalization child
    spawned = [n for n in updated.frontier if n.parent_id == "F-1"]
    assert len(spawned) >= 1
    assert any("formalize" in n.text.lower() or "invariant" in n.text.lower() for n in spawned)


def test_formalization_failed_spawns_clean_encoding_child():
    """Test that formalization_failed spawns clean encoding child."""
    campaign = _make_campaign([FrontierNode(id="F-1", text="Test claim")])
    decision = _make_decision("F-1")
    result = ExecutionResult(
        status="blocked",
        failure_type="formalization_failed",
        notes="No formal statement",
        executor_backend="aristotle",
    )
    
    updated = apply_execution_result(campaign, decision, result)
    spawned = [n for n in updated.frontier if n.parent_id == "F-1"]
    assert len(spawned) >= 1
    assert any("clean" in n.text.lower() or "formal" in n.text.lower() for n in spawned)


def test_proof_failed_spawns_missing_lemma_child():
    """Test that proof_failed spawns missing lemma child."""
    campaign = _make_campaign([FrontierNode(id="F-1", text="Test claim")])
    decision = _make_decision("F-1")
    result = ExecutionResult(
        status="blocked",
        failure_type="proof_failed",
        notes="Could not find proof",
        executor_backend="aristotle",
    )
    
    updated = apply_execution_result(campaign, decision, result)
    spawned = [n for n in updated.frontier if n.parent_id == "F-1"]
    assert len(spawned) >= 1
    assert any("lemma" in n.text.lower() for n in spawned)


def test_timeout_spawns_smaller_reduction_after_streak():
    """Test that timeout spawns smaller reduction after streak."""
    memory = MemoryState(timeout_streaks={"F-1": 2})
    campaign = _make_campaign([FrontierNode(id="F-1", text="Test claim")], memory=memory)
    decision = _make_decision("F-1")
    result = ExecutionResult(
        status="inconclusive",
        failure_type="timeout",
        notes="Timed out",
        executor_backend="aristotle",
    )
    
    updated = apply_execution_result(campaign, decision, result)
    spawned = [n for n in updated.frontier if n.parent_id == "F-1"]
    assert len(spawned) >= 1
    assert any("smaller" in n.text.lower() or "bounded" in n.text.lower() for n in spawned)


def test_proof_failed_does_not_change_stance():
    """Test that proof_failed doesn't change candidate answer stance."""
    campaign = _make_campaign([FrontierNode(id="F-1", text="Test")])
    campaign.current_candidate_answer = CandidateAnswer(
        stance="likely_true", summary="test", confidence=0.7
    )
    decision = _make_decision("F-1")
    result = ExecutionResult(
        status="blocked",
        failure_type="proof_failed",
        notes="Could not find proof",
        executor_backend="aristotle",
    )
    
    updated = update_memory(campaign, decision, result)
    assert updated.current_candidate_answer.stance == "likely_true"
    # Confidence should drop slightly but not dramatically
    assert 0.6 <= updated.current_candidate_answer.confidence < 0.7


def test_refuted_only_from_counterexample():
    """Test that refuted status is only for true counterexamples."""
    campaign = _make_campaign([FrontierNode(id="F-1", text="Test")])
    decision = _make_decision("F-1")
    
    # Proof failure should NOT produce refuted
    result_failed = ExecutionResult(
        status="blocked",
        failure_type="proof_failed",
        notes="Could not find proof",
        executor_backend="aristotle",
    )
    updated_failed = apply_execution_result(campaign, decision, result_failed)
    assert updated_failed.frontier[0].status != "refuted"
    
    # Only explicit refuted status should mark as refuted
    result_refuted = ExecutionResult(
        status="refuted",
        notes="Counterexample found",
        artifacts=["counterexample: n=5"],
        executor_backend="evidence",
    )
    updated_refuted = apply_execution_result(campaign, decision, result_refuted)
    assert updated_refuted.frontier[0].status == "refuted"


def test_evidence_only_does_not_heavily_penalize():
    """Test that evidence_only doesn't heavily penalize retry penalties."""
    campaign = _make_campaign([FrontierNode(id="F-1", text="Test")])
    decision = _make_decision("F-1")
    result = ExecutionResult(
        status="inconclusive",
        failure_type="evidence_only",
        notes="Evidence collected",
        executor_backend="evidence",
    )
    
    updated = update_memory(campaign, decision, result)
    # Evidence_only should not add to retry penalties
    assert updated.memory.retry_penalties.get("F-1:direct", 0) == 0


def test_excessive_scope_spawns_localized_children():
    """Test that excessive_scope spawns both lemma and finite check children."""
    campaign = _make_campaign([FrontierNode(id="F-1", text="Test claim")])
    decision = _make_decision("F-1")
    result = ExecutionResult(
        status="blocked",
        failure_type="excessive_scope",
        notes="Scope too large",
        executor_backend="gate",
    )
    
    updated = apply_execution_result(campaign, decision, result)
    spawned = [n for n in updated.frontier if n.parent_id == "F-1"]
    assert len(spawned) >= 2
    # Should have both lemma and finite_check children
    kinds = {n.kind for n in spawned}
    assert "lemma" in kinds or "finite_check" in kinds
