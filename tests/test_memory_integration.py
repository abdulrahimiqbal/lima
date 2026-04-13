from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.schemas import (
    ApprovedExecutionPlan,
    CampaignCreate,
    CampaignUpdateNotes,
    CandidateAnswer,
    ExecutionResult,
    ManagerDecision,
    SelfImprovementNote,
    UpdateRules,
)
from app.service import CampaignService


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        memory_db_path=str(tmp_path / "memory.db"),
        worker_poll_seconds=999,
        manager_backend="rules",
        executor_backend="mock",
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


def test_memory_campaign_creation_is_canonical(tmp_path: Path) -> None:
    service = CampaignService(_settings(tmp_path))
    campaign = service.create_campaign(
        CampaignCreate(
            title="Memory canonical campaign",
            problem_statement="Prove a bounded lemma.",
            operator_notes=["Prefer tiny jobs"],
            auto_run=False,
        )
    )

    packet = service.get_memory_packet(campaign.id)
    assert packet["campaign"]["id"] == campaign.id
    assert packet["problem"]["payload"]["statement"] == "Prove a bounded lemma."
    assert packet["active_frontier"][0]["id"] == campaign.frontier[0].id


def test_manager_and_execution_are_mirrored_to_memory(tmp_path: Path, monkeypatch) -> None:
    service = CampaignService(_settings(tmp_path))
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
    app = create_app(_settings(tmp_path))
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


def test_service_crud_events_notes_pause_resume_step(tmp_path: Path, monkeypatch) -> None:
    service = CampaignService(_settings(tmp_path))
    created = service.create_campaign(
        CampaignCreate(
            title="Full flow",
            problem_statement="Check full memory flow",
            operator_notes=["start note"],
            auto_run=False,
        )
    )
    fetched = service.get_campaign(created.id)
    assert fetched.id == created.id

    updated_notes = service.update_notes(
        created.id, payload=CampaignUpdateNotes(operator_notes=["n1", "n2"])
    )
    assert updated_notes.operator_notes == ["n1", "n2"]

    paused = service.pause_campaign(created.id)
    assert paused.status == "paused"
    resumed = service.resume_campaign(created.id)
    assert resumed.status == "running"

    decision = _decision(target_frontier_node=resumed.frontier[0].id)
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
            notes="Evidence only",
            artifacts=["artifact"],
            executor_backend="evidence",
        ),
    )
    stepped = service.step_campaign(created.id)
    assert stepped.tick_count == 1

    events = service.list_events(created.id, limit=50)
    kinds = {event.kind for event in events}
    assert "campaign_created" in kinds
    assert "operator_notes_updated" in kinds
    assert "campaign_paused" in kinds
    assert "campaign_resumed" in kinds
    assert "manager_decision" in kinds
    assert "execution_result" in kinds


def test_context_is_memory_backed_only(tmp_path: Path, monkeypatch) -> None:
    service = CampaignService(_settings(tmp_path))
    campaign = service.create_campaign(
        CampaignCreate(
            title="Memory context path",
            problem_statement="Read from memory context.",
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


def test_frontier_and_candidate_persist_across_reload(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    service = CampaignService(settings)
    campaign = service.create_campaign(
        CampaignCreate(
            title="Persistence regression",
            problem_statement="Keep frontier stable across reload",
            operator_notes=[],
            auto_run=False,
        )
    )
    root_id = campaign.frontier[0].id
    decision = _decision(target_frontier_node=root_id)

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
            status="blocked",
            failure_type="missing_lemma",
            notes="Need child lemma",
            artifacts=["trace"],
            spawned_nodes=[
                {
                    "id": "F-child-fixed",
                    "text": "Child lemma node",
                    "status": "open",
                    "priority": 0.7,
                    "parent_id": root_id,
                    "kind": "lemma",
                    "failure_count": 0,
                    "evidence": [],
                }
            ],
            executor_backend="evidence",
        ),
    )
    stepped = service.step_campaign(campaign.id)
    assert stepped.current_candidate_answer is not None
    assert {node.id for node in stepped.frontier} >= {root_id, "F-child-fixed"}

    # Reconstruct from storage with a fresh service instance.
    reloaded_service = CampaignService(settings)
    reloaded = reloaded_service.get_campaign(campaign.id)
    assert reloaded.current_candidate_answer is not None
    by_id = {node.id: node for node in reloaded.frontier}
    assert root_id in by_id
    assert "F-child-fixed" in by_id
    assert by_id["F-child-fixed"].parent_id == root_id
    assert by_id["F-child-fixed"].status == "open"

    # Additional step should keep prior nodes and candidate answer visible.
    monkeypatch.setattr(reloaded_service.manager, "decide", lambda _context: decision)
    monkeypatch.setattr(
        reloaded_service.executor,
        "run",
        lambda _campaign, _decision, _plan: ExecutionResult(
            status="inconclusive",
            failure_type="evidence_only",
            notes="Second pass",
            artifacts=[],
            executor_backend="evidence",
        ),
    )
    stepped_again = reloaded_service.step_campaign(campaign.id)
    assert stepped_again.current_candidate_answer is not None
    assert {node.id for node in stepped_again.frontier} >= {root_id, "F-child-fixed"}
