import json
from pathlib import Path

from app.config import Settings
from app.manager import Manager, get_policy
from app.schemas import (
    CandidateAnswer,
    FrontierNode,
    ManagerContext,
    ManagerDecision,
    MemoryState,
    SelfImprovementNote,
    UpdateRules,
)


def _context() -> ManagerContext:
    return ManagerContext(
        problem={"id": "C-1", "title": "T", "statement": "S"},
        frontier=[FrontierNode(id="F-1", text="Prove bounded claim")],
        memory=MemoryState(),
        allowed_world_families=["direct", "bridge"],
        tick=0,
    )


def _decision() -> ManagerDecision:
    return ManagerDecision(
        candidate_answer=CandidateAnswer(stance="undecided", summary="s", confidence=0.2),
        alternatives=[],
        target_frontier_node="F-1",
        world_family="direct",
        bounded_claim="Bounded claim",
        formal_obligations=["Prove bounded claim for n <= 10"],
        expected_information_gain="high",
        why_this_next="cheap",
        update_rules=UpdateRules(
            if_proved="close",
            if_refuted="switch",
            if_blocked="split",
            if_inconclusive="retry",
        ),
        self_improvement_note=SelfImprovementNote(proposal="none", reason="test"),
        manager_backend="llm",
    )


def test_llm_repair_pass_recovers(tmp_path: Path, monkeypatch) -> None:
    settings = Settings(
        memory_db_path=str(tmp_path / "memory.db"),
        manager_backend="llm",
        llm_api_key="test-key",
    )
    manager = Manager(settings)
    calls = {"count": 0}

    def fake_call(_messages):
        calls["count"] += 1
        if calls["count"] == 1:
            raise json.JSONDecodeError("bad json", "x", 0)
        return _decision()

    monkeypatch.setattr(manager, "_call_llm_and_parse", fake_call)
    result = manager._decide_with_llm(_context(), get_policy())
    assert result.target_frontier_node == "F-1"
    assert calls["count"] == 2


def test_llm_failure_falls_back_to_rules(tmp_path: Path, monkeypatch) -> None:
    settings = Settings(
        memory_db_path=str(tmp_path / "memory.db"),
        manager_backend="llm",
        llm_api_key="test-key",
    )
    manager = Manager(settings)

    def always_fail(*_args, **_kwargs):
        raise json.JSONDecodeError("bad json", "x", 0)

    monkeypatch.setattr(manager, "_decide_with_llm", always_fail)
    result = manager.decide(_context())
    assert result.manager_backend == "rules_fallback"

