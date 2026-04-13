from datetime import datetime, timezone

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


def _campaign() -> CampaignRecord:
    return CampaignRecord(
        id="C-1",
        title="t",
        problem_statement="p",
        status="running",
        auto_run=False,
        operator_notes=[],
        frontier=[FrontierNode(id="F-1", text="claim")],
        memory=MemoryState(),
        current_candidate_answer=CandidateAnswer(
            stance="undecided",
            summary="x",
            confidence=0.5,
        ),
        tick_count=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        manager_backend="rules",
        executor_backend="aristotle",
    )


def _decision() -> ManagerDecision:
    return ManagerDecision(
        candidate_answer=CandidateAnswer(stance="undecided", summary="x", confidence=0.2),
        alternatives=[],
        target_frontier_node="F-1",
        world_family="bridge",
        bounded_claim="bounded claim",
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


def test_timeout_updates_penalties_and_shrink_signal() -> None:
    updated = update_memory(
        _campaign(),
        _decision(),
        ExecutionResult(
            status="inconclusive",
            failure_type="timeout",
            notes="t",
            executor_backend="aristotle",
        ),
        policy={"failure_penalties": {"timeout": 0.3}},
    )
    assert updated.memory.retry_penalties["F-1:bridge"] >= 2
    assert any("shrink_required" in note for note in updated.memory.policy_notes)
    assert any("Prefer smaller obligations" in item for item in updated.memory.blocked_patterns)


def test_excessive_scope_repeated_failure_strengthens_penalty() -> None:
    c1 = update_memory(
        _campaign(),
        _decision(),
        ExecutionResult(
            status="blocked",
            failure_type="excessive_scope",
            notes="scope",
            executor_backend="gate",
        ),
        policy={"failure_penalties": {"excessive_scope": 0.25}},
    )
    c2 = update_memory(
        c1,
        _decision(),
        ExecutionResult(
            status="blocked",
            failure_type="excessive_scope",
            notes="scope2",
            executor_backend="gate",
        ),
        policy={"failure_penalties": {"excessive_scope": 0.25}},
    )
    assert c2.memory.retry_penalties["F-1:bridge"] > c1.memory.retry_penalties["F-1:bridge"]
