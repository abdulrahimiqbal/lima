from datetime import datetime, timezone

from app.frontier import apply_execution_result
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
        frontier=[
            FrontierNode(id="F-root", text="root"),
            FrontierNode(
                id="F-existing",
                text="Retry with a smaller bounded reduction step for: root",
                parent_id="F-root",
                kind="lemma",
                status="open",
            ),
        ],
        memory=MemoryState(),
        current_candidate_answer=CandidateAnswer(stance="undecided", summary="x", confidence=0.4),
        tick_count=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        manager_backend="rules",
        executor_backend="aristotle",
    )


def _decision() -> ManagerDecision:
    return ManagerDecision(
        candidate_answer=CandidateAnswer(stance="undecided", summary="x", confidence=0.2),
        alternatives=[],
        target_frontier_node="F-root",
        world_family="bridge",
        bounded_claim="c",
        formal_obligations=["o"],
        expected_information_gain="g",
        why_this_next="w",
        update_rules=UpdateRules(if_proved="a", if_refuted="b", if_blocked="c", if_inconclusive="d"),
        self_improvement_note=SelfImprovementNote(proposal="p", reason="r"),
    )


def test_timeout_spawn_deduplicates_existing_retry_node() -> None:
    campaign = _campaign()
    result = ExecutionResult(
        status="inconclusive",
        failure_type="timeout",
        notes="t",
        executor_backend="aristotle",
    )
    updated = apply_execution_result(campaign, _decision(), result)
    matches = [n for n in updated.frontier if n.text == "Retry with a smaller bounded reduction step for: root"]
    assert len(matches) == 1
