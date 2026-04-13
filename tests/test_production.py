import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.manager import Manager, load_root_file, get_constitution
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
    settings = Settings(database_path=str(tmp_path / "test.db"), manager_backend="rules")
    from app.db import Database
    db = Database(settings.database_path)
    db.init()
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
    settings = Settings(database_path=str(tmp_path / "test.db"))
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


def test_executor_http_path(tmp_path: Path):
    
    settings = Settings(
        database_path=str(tmp_path / "test.db"),
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
        
        with patch("app.executor.Executor._run_aristotle") as mock_aristotle:
            mock_aristotle.return_value = ExecutionResult(
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
            assert mock_aristotle.called


def test_self_improvement_logic(tmp_path: Path):
    from app.self_improvement import SelfImprovementService
    from app.db import Database
    
    settings = Settings(
        database_path=str(tmp_path / "test.db"),
        enable_self_improvement=True,
        llm_api_key="fake-key"
    )
    db = Database(settings.database_path)
    db.init()
    service = SelfImprovementService(db, settings)
    
    with patch.object(SelfImprovementService, "_call_llm") as mock_call:
        mock_call.return_value = {
            "patch": {
                "world_family_priors": {"direct": 0.9}
            },
            "reason": "Boosting direct proof prioritisation."
        }
        
        result = service.run_cycle()
        assert result["status"] == "updated"
        
        latest_policy = db.get_latest_policy()
        assert latest_policy["world_family_priors"]["direct"] == 0.9
