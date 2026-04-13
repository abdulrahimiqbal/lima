from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Database
from app.main import create_app
from app.schemas import (
    ApprovedExecutionPlan,
    CampaignCreate,
    CandidateAnswer,
    ExecutionResult,
    ManagerDecision,
    SelfImprovementNote,
    UpdateRules,
)
from app.service import CampaignService


def _settings(tmp_path: Path, *, use_memory_context: bool = False) -> Settings:
    return Settings(
        database_path=str(tmp_path / "legacy.db"),
        memory_db_path=str(tmp_path / "memory.db"),
        worker_poll_seconds=999,
        manager_backend="rules",
        executor_backend="mock",
        use_memory_context=use_memory_context,
    )


def _decision(target_frontier_node: str) -> ManagerDecision:
    return ManagerDecision(
        candidate_answer=CandidateAnswer(
            stance="undecided",
            summary="Need one local bridge lemma first.",
            confidence=0.3,
        ),
        alternatives=[],
        target_frontier_node=target_frontier_node,
        world_family="bridge",
        bounded_claim="Prove a local bridge lemma for the target node.",
        formal_obligations=["Prove a local bridge lemma for n <= 10."],
        expected_information_gain="Unblocks the current branch quickly.",
        why_this_next="It is a bounded, low-cost obligation.",
        update_rules=UpdateRules(
            if_proved="Close branch.",
            if_refuted="Switch world family.",
            if_blocked="Shrink claim.",
            if_inconclusive="Try alternate lemma.",
        ),
        self_improvement_note=SelfImprovementNote(
            proposal="Prefer small obligations.",
            reason="Runtime is cheaper and more stable.",
        ),
    )


def test_memory_campaign_creation_mirror(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    db = Database(settings.database_path)
    db.init()
    service = CampaignService(db, settings)

    campaign = service.create_campaign(
        CampaignCreate(
            title="Memory mirror campaign",
            problem_statement="Prove a bounded lemma.",
            operator_notes=["Prefer tiny jobs"],
            auto_run=False,
        )
    )

    packet = service.get_memory_packet(campaign.id)
    assert packet["campaign"]["id"] == campaign.id
    assert packet["problem"]["payload"]["statement"] == "Prove a bounded lemma."
    assert packet["active_frontier"]


def test_manager_and_execution_are_mirrored_to_memory(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    db = Database(settings.database_path)
    db.init()
    service = CampaignService(db, settings)

    campaign = service.create_campaign(
        CampaignCreate(
            title="Mirror decision/result",
            problem_statement="Show bounded progress.",
            operator_notes=[],
            auto_run=False,
        )
    )
    decision = _decision(target_frontier_node=campaign.frontier[0].id)

    monkeypatch.setattr(service.manager, "decide", lambda _context: decision)
    monkeypatch.setattr(
        "app.service.build_execution_plan",
        lambda _decision, policy, memory: ApprovedExecutionPlan(
            original_obligations=decision.formal_obligations,
            approved_proof_jobs=decision.formal_obligations[:1],
            channel_used="aristotle_proof",
        ),
    )
    monkeypatch.setattr(
        service.executor,
        "run",
        lambda _campaign, _decision, _plan: ExecutionResult(
            status="inconclusive",
            failure_type="timeout",
            notes="Timed out on first attempt.",
            artifacts=["timeout-log"],
            executor_backend="mock",
            raw={"aristotle_request": "REQ", "aristotle_response": "RESP"},
        ),
    )

    stepped = service.step_campaign(campaign.id)
    assert stepped.tick_count == 1

    packet = service.get_memory_packet(campaign.id)
    assert packet["recent_claims"]
    assert packet["recent_results"]

    summary = service.get_memory_summary(campaign.id)
    assert summary["campaign"]["id"] == campaign.id
    assert summary["recent_results"]


def test_memory_endpoints(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    app = create_app(settings)
    client = TestClient(app)

    create_response = client.post(
        "/api/campaigns",
        json={
            "title": "Endpoint test",
            "problem_statement": "Use memory endpoints",
            "operator_notes": [],
            "auto_run": False,
        },
    )
    campaign_id = create_response.json()["id"]

    summary_response = client.get(f"/api/campaigns/{campaign_id}/memory-summary")
    assert summary_response.status_code == 200
    assert summary_response.json()["campaign"]["id"] == campaign_id

    packet_response = client.get(f"/api/campaigns/{campaign_id}/memory-packet")
    assert packet_response.status_code == 200
    assert packet_response.json()["campaign"]["id"] == campaign_id


def test_feature_flag_uses_memory_backed_context(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path, use_memory_context=True)
    db = Database(settings.database_path)
    db.init()
    service = CampaignService(db, settings)
    campaign = service.create_campaign(
        CampaignCreate(
            title="Memory context path",
            problem_statement="Read from memory context.",
            operator_notes=[],
            auto_run=False,
        )
    )
    decision = _decision(target_frontier_node=campaign.frontier[0].id)

    def fail_if_legacy_builder_used(_campaign):
        raise AssertionError("Legacy context builder should not be used")

    monkeypatch.setattr(service, "_build_context", fail_if_legacy_builder_used)
    monkeypatch.setattr(service.manager, "decide", lambda _context: decision)
    monkeypatch.setattr(
        "app.service.build_execution_plan",
        lambda _decision, policy, memory: ApprovedExecutionPlan(
            original_obligations=decision.formal_obligations,
            approved_evidence_jobs=decision.formal_obligations[:1],
            channel_used="computational_evidence",
        ),
    )
    monkeypatch.setattr(
        service.executor,
        "run",
        lambda _campaign, _decision, _plan: ExecutionResult(
            status="inconclusive",
            failure_type="evidence_only",
            notes="Computed bounded evidence",
            artifacts=[],
            executor_backend="evidence",
        ),
    )

    stepped = service.step_campaign(campaign.id)
    assert stepped.tick_count == 1

