from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.schemas import (
    CampaignCreate,
    CandidateAnswer,
    FormalObligationSpec,
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


def test_invention_lab_batch_distill_falsify_and_promote(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    client = TestClient(app)

    created = client.post(
        "/api/campaigns",
        json={
            "title": "Collatz invention prelaunch",
            "problem_statement": "Prove the Collatz conjecture over positive integers.",
            "operator_notes": ["Run wild invention before proof debt baking."],
            "auto_run": False,
        },
    )
    assert created.status_code == 200
    campaign_id = created.json()["id"]

    batch_response = client.post(
        f"/api/campaigns/{campaign_id}/invention/batches",
        json={"requested_worlds": 8, "wildness": "high", "mode": "wild"},
    )
    assert batch_response.status_code == 200
    batch = batch_response.json()
    assert batch["status"] == "generated"
    assert len(batch["raw_world_ids"]) == 8

    distill_response = client.post(
        f"/api/campaigns/{campaign_id}/invention/batches/{batch['id']}/distill"
    )
    assert distill_response.status_code == 200
    distilled = distill_response.json()
    assert distilled
    assert distilled[0]["world_program"]["bridge_to_target"] is not None
    assert distilled[0]["proof_debt"]

    falsify_response = client.post(
        f"/api/campaigns/{campaign_id}/invention/batches/{batch['id']}/falsify"
    )
    assert falsify_response.status_code == 200
    falsifiers = falsify_response.json()
    assert falsifiers

    lab_response = client.get(f"/api/campaigns/{campaign_id}/invention/lab")
    assert lab_response.status_code == 200
    lab = lab_response.json()
    assert lab["summary"]["raw_world_count"] == 8
    assert lab["summary"]["distilled_world_count"] == 8
    assert lab["summary"]["proof_debt_count"] >= 8

    promising = [
        node for node in lab["distilled_worlds"]
        if node["payload"]["status"] in {"promising", "candidate"}
    ]
    assert promising

    promote_response = client.post(
        f"/api/campaigns/{campaign_id}/invention/worlds/promote",
        json={"distilled_world_id": promising[0]["id"]},
    )
    assert promote_response.status_code == 200
    promoted = promote_response.json()
    assert promoted["current_world_program"] is not None
    assert promoted["proof_debt_ledger"]
    assert promoted["active_world_id"] == promoted["current_world_program"]["id"]


def test_operator_brief_includes_invention_summary(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    client = TestClient(app)

    created = client.post(
        "/api/campaigns",
        json={
            "title": "Brief invention",
            "problem_statement": "Explore Collatz.",
            "operator_notes": [],
            "auto_run": False,
        },
    )
    campaign_id = created.json()["id"]
    batch = client.post(
        f"/api/campaigns/{campaign_id}/invention/batches",
        json={"requested_worlds": 3},
    ).json()
    client.post(f"/api/campaigns/{campaign_id}/invention/batches/{batch['id']}/distill")
    client.post(f"/api/campaigns/{campaign_id}/invention/batches/{batch['id']}/falsify")

    brief = client.get(f"/api/campaigns/{campaign_id}/operator-brief").json()

    assert "invention" in brief
    assert brief["invention"]["batch_count"] == 1
    assert brief["invention"]["raw_world_count"] == 3
    assert "promising_worlds" in brief["invention"]


def test_memory_records_structured_obligations(tmp_path: Path) -> None:
    service = CampaignService(_settings(tmp_path))
    campaign = service.create_campaign(
        CampaignCreate(
            title="Structured obligation memory",
            problem_statement="Prove True.",
            auto_run=False,
        )
    )
    decision = ManagerDecision(
        candidate_answer=CandidateAnswer(stance="undecided", summary="s", confidence=0.1),
        alternatives=[],
        target_frontier_node=campaign.frontier[0].id,
        world_family="direct",
        bounded_claim="Tiny structured claim",
        formal_obligations=[
            FormalObligationSpec(
                source_text="Prove True in Lean",
                statement="True",
                theorem_name="true_claim",
                channel_hint="proof",
                requires_proof=True,
            )
        ],
        expected_information_gain="Checks structured persistence.",
        why_this_next="Regression coverage.",
        update_rules=UpdateRules(
            if_proved="close",
            if_refuted="switch",
            if_blocked="repair",
            if_inconclusive="retry",
        ),
        self_improvement_note=SelfImprovementNote(proposal="none", reason="test"),
    )

    service.memory.record_manager_decision(
        campaign_id=campaign.id,
        tick=1,
        decision=decision.model_dump(),
    )

    obligations = service.memory.list_research_nodes(
        campaign.id,
        node_type="FormalObligation",
        limit=10,
    )
    assert obligations
    assert obligations[0].summary == "Prove True in Lean"
    assert obligations[0].payload["statement"] == "True"
