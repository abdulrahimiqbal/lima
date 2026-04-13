import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
from fastapi.testclient import TestClient
from lima_memory import MemoryService, SqliteKnowledgeStore

from app.config import Settings
from app.main import create_app
from app.manager import Manager, load_root_file, get_constitution
from app.self_improvement import SelfImprovementService
from app.schemas import (
    ManagerContext,
    ManagerDecision,
    CandidateAnswer,
    UpdateRules,
    SelfImprovementNote,
    MemoryState,
    ExecutionResult,
)


def test_root_file_loaders():
    # Test that constitution can be loaded
    constitution = get_constitution()
    assert len(constitution) > 0
    assert "LIMA" in constitution


def test_manager_fallback(tmp_path: Path):
    settings = Settings(memory_db_path=str(tmp_path / "memory.db"), manager_backend="rules")
    manager = Manager(settings)
    
    context = ManagerContext(
        problem={"id": "test", "title": "test", "statement": "test"},
        frontier=[],
        memory=MemoryState(),
        allowed_world_families=["direct"],
        tick=0
    )
    
    # Mock choose_frontier_node to return a mock node
    with patch("app.manager.choose_frontier_node") as mock_choose:
        mock_node = MagicMock()
        mock_node.id = "F-1"
        mock_node.text = "Prove 1+1=2"
        mock_node.status = "open"
        mock_choose.return_value = mock_node
        
        decision = manager.decide(context)
        assert isinstance(decision, ManagerDecision)
        assert decision.candidate_answer.stance == "undecided"
        assert decision.target_frontier_node == "F-1"


def test_health_ready_status(tmp_path: Path):
    settings = Settings(memory_db_path=str(tmp_path / "memory.db"))
    app = create_app(settings)
    client = TestClient(app)
    
    # Health check
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    
    # Ready check
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    
    # System status
    response = client.get("/api/system/status")
    assert response.status_code == 200
    data = response.json()
    assert data["database"] == "ok"
    assert data["manager"]["backend"] == "rules"


def test_readyz_strict_live_mode_fails_on_probe_error(tmp_path: Path, monkeypatch):
    settings = Settings(
        memory_db_path=str(tmp_path / "memory.db"),
        strict_live_aristotle=True,
        executor_backend="aristotle",
    )
    app = create_app(settings)
    client = TestClient(app)
    monkeypatch.setattr(
        app.state.service.executor,
        "check_connectivity",
        lambda strict_live_probe=False: {"status": "disconnected", "error": "probe_failed"},
    )
    response = client.get("/readyz")
    assert response.status_code == 503
    assert "strict probe failed" in response.json()["detail"]


def test_readyz_strict_live_mode_passes_on_connected_probe(tmp_path: Path, monkeypatch):
    settings = Settings(
        memory_db_path=str(tmp_path / "memory.db"),
        strict_live_aristotle=True,
        executor_backend="aristotle",
    )
    app = create_app(settings)
    client = TestClient(app)
    monkeypatch.setattr(
        app.state.service.executor,
        "check_connectivity",
        lambda strict_live_probe=False: {"status": "connected", "probe": "http_healthz"},
    )
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_readyz_strict_live_mode_requires_live_backend(tmp_path: Path):
    settings = Settings(
        memory_db_path=str(tmp_path / "memory.db"),
        strict_live_aristotle=True,
        executor_backend="mock",
    )
    app = create_app(settings)
    client = TestClient(app)
    response = client.get("/readyz")
    assert response.status_code == 503
    assert "requires executor_backend=aristotle" in response.json()["detail"]


def test_executor_http_path(tmp_path: Path):
    
    settings = Settings(
        memory_db_path=str(tmp_path / "memory.db"),
        executor_backend="http",
        aristotle_base_url="http://aristotle.local",
        aristotle_api_key="fake-key",
    )
    app = create_app(settings)
    client = TestClient(app)
    
    # Create a campaign
    client.post("/api/campaigns", json={
        "title": "Test",
        "problem_statement": "Problem",
        "auto_run": False
    })
    
    # Step the campaign (this will call the executor)
    # We need to mock the manager too to ensure it gives a valid decision for the executor
    with patch("app.manager.Manager.decide") as mock_decide:
        mock_decide.return_value = ManagerDecision(
            candidate_answer=CandidateAnswer(stance="undecided", summary="...", confidence=0.1),
            alternatives=[],
            target_frontier_node="F-seed",
            world_family="direct",
            bounded_claim="Claim",
            formal_obligations=["Obligation"],
            expected_information_gain="...",
            why_this_next="...",
            update_rules=UpdateRules(if_proved=".", if_refuted=".", if_blocked=".", if_inconclusive="."),
            self_improvement_note=SelfImprovementNote(proposal=".", reason=".")
        )
        
        # We need a node with ID "F-seed" in the frontier
        # The seed_frontier usually creates nodes with random IDs or we can find it
        campaign_id = client.get("/api/campaigns").json()[0]["id"]
        campaign = client.get(f"/api/campaigns/{campaign_id}").json()
        mock_decide.return_value.target_frontier_node = campaign["frontier"][0]["id"]
        
        with patch.object(
            app.state.service.executor._proof_adapter,
            "run_proof",
        ) as mock_run_proof:
            mock_run_proof.return_value = ExecutionResult(
                status="proved",
                notes="Verified by Aristotle",
                artifacts=["artifact-1"],
                spawned_nodes=[],
                executor_backend="aristotle",
            )
            response = client.post(f"/api/campaigns/{campaign_id}/step")
            assert response.status_code == 200
            data = response.json()
            assert data["last_execution_result"]["status"] == "proved"
            assert mock_run_proof.called


def test_self_improvement_logic(tmp_path: Path):
    settings = Settings(
        memory_db_path=str(tmp_path / "memory.db"),
        enable_self_improvement=True,
        llm_api_key="fake-key"
    )
    memory = MemoryService(SqliteKnowledgeStore(settings.memory_db_path))
    memory.create_campaign(
        campaign_id="C-test",
        title="SI campaign",
        problem_statement="Test policy snapshots",
        operator_notes=[],
    )
    service = SelfImprovementService(memory, settings)
    
    with patch.object(SelfImprovementService, "_call_llm") as mock_call:
        mock_call.return_value = {
            "patch": {
                "world_family_priors": {"direct": 0.9}
            },
            "reason": "Boosting direct proof prioritisation."
        }
        
        result = service.run_cycle()
        assert result["status"] == "updated"

        latest_policy = memory.get_latest_policy()
        assert latest_policy["world_family_priors"]["direct"] == 0.9


def test_self_improvement_handles_malformed_llm_payload(tmp_path: Path):
    settings = Settings(
        memory_db_path=str(tmp_path / "memory.db"),
        enable_self_improvement=True,
        llm_api_key="fake-key",
    )
    memory = MemoryService(SqliteKnowledgeStore(settings.memory_db_path))
    memory.create_campaign(
        campaign_id="C-test-malformed",
        title="SI malformed",
        problem_statement="Test malformed llm payload",
        operator_notes=[],
    )
    service = SelfImprovementService(memory, settings)

    with patch.object(SelfImprovementService, "_call_llm") as mock_call:
        mock_call.side_effect = json.JSONDecodeError("bad", "x", 0)
        result = service.run_cycle()

    assert result["status"] == "failed"


def test_self_improvement_handles_llm_rate_limit(tmp_path: Path):
    settings = Settings(
        memory_db_path=str(tmp_path / "memory.db"),
        enable_self_improvement=True,
        llm_api_key="fake-key",
    )
    memory = MemoryService(SqliteKnowledgeStore(settings.memory_db_path))
    memory.create_campaign(
        campaign_id="C-test-rate-limit",
        title="SI rate limit",
        problem_statement="Test rate limit handling",
        operator_notes=[],
    )
    service = SelfImprovementService(memory, settings)

    with patch.object(SelfImprovementService, "_call_llm") as mock_call:
        mock_call.side_effect = requests.HTTPError("429 Too Many Requests")
        result = service.run_cycle()

    assert result["status"] == "failed"
