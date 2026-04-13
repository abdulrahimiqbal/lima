"""Tests for operator brief endpoint and manager read receipt."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_operator_brief_endpoint_shape(tmp_path: Path) -> None:
    """Test that operator brief endpoint returns expected structure."""
    settings = Settings(
        memory_db_path=str(tmp_path / "memory.db"),
        worker_poll_seconds=999,
        manager_backend="rules",
        executor_backend="mock",
    )
    app = create_app(settings)
    client = TestClient(app)

    # Create a campaign
    create_response = client.post(
        "/api/campaigns",
        json={
            "title": "Test operator brief",
            "problem_statement": "Prove that 2 + 2 = 4",
            "operator_notes": ["Prefer local lemmas", "Avoid global unbounded proofs"],
            "auto_run": False,
        },
    )
    assert create_response.status_code == 200
    campaign_id = create_response.json()["id"]

    # Step the campaign to generate decision and result
    step_response = client.post(f"/api/campaigns/{campaign_id}/step")
    assert step_response.status_code == 200

    # Get operator brief
    brief_response = client.get(f"/api/campaigns/{campaign_id}/operator-brief")
    assert brief_response.status_code == 200
    brief = brief_response.json()

    # Verify top-level structure
    assert "ops" in brief
    assert "campaign_now" in brief
    assert "manager_understanding" in brief
    assert "verification" in brief
    assert "discovery" in brief
    assert "self_improvement" in brief
    assert "next" in brief

    # Verify ops section
    ops = brief["ops"]
    assert ops["manager_backend"] == "rules"
    assert ops["executor_backend"] == "mock"
    assert ops["campaign_status"] == "running"
    assert ops["tick_count"] == 1
    assert "database_status" in ops
    assert "self_improvement_enabled" in ops

    # Verify campaign_now section
    campaign_now = brief["campaign_now"]
    assert campaign_now["title"] == "Test operator brief"
    assert campaign_now["problem_statement"] == "Prove that 2 + 2 = 4"
    assert campaign_now["target_frontier_node_id"] is not None
    assert campaign_now["world_family"] is not None

    # Verify manager_understanding section
    manager_understanding = brief["manager_understanding"]
    assert "problem_summary" in manager_understanding
    assert "target_node_id_confirmed" in manager_understanding
    assert "operator_notes_seen" in manager_understanding
    assert "relevant_memory_seen" in manager_understanding
    assert "constraints_seen" in manager_understanding

    # Verify verification section
    verification = brief["verification"]
    assert "status" in verification
    assert "channel_used" in verification
    assert "approved_jobs_count" in verification
    assert "rejected_jobs_count" in verification

    # Verify discovery section
    discovery = brief["discovery"]
    assert "spawned_nodes_count" in discovery
    assert "useful_lemmas" in discovery
    assert "blocked_patterns" in discovery

    # Verify self_improvement section
    self_improvement = brief["self_improvement"]
    assert "local_proposal" in self_improvement
    assert "local_reason" in self_improvement

    # Verify next section
    next_action = brief["next"]
    assert "recommended_operator_action" in next_action
    assert "expected_information_gain" in next_action
    assert "if_proved" in next_action
    assert "if_refuted" in next_action
    assert "if_blocked" in next_action
    assert "if_inconclusive" in next_action


def test_manager_read_receipt_in_rules_mode(tmp_path: Path) -> None:
    """Test that manager read receipt is populated in rules mode."""
    settings = Settings(
        memory_db_path=str(tmp_path / "memory.db"),
        worker_poll_seconds=999,
        manager_backend="rules",
        executor_backend="mock",
    )
    app = create_app(settings)
    client = TestClient(app)

    # Create a campaign with operator notes
    create_response = client.post(
        "/api/campaigns",
        json={
            "title": "Read receipt test",
            "problem_statement": "Prove the Collatz conjecture for n=5",
            "operator_notes": ["Prefer bounded local work", "Avoid repeated blocked worlds"],
            "auto_run": False,
        },
    )
    assert create_response.status_code == 200
    campaign_id = create_response.json()["id"]

    # Step the campaign
    step_response = client.post(f"/api/campaigns/{campaign_id}/step")
    assert step_response.status_code == 200
    stepped = step_response.json()

    # Verify manager_read_receipt exists in decision
    assert stepped["last_manager_decision"] is not None
    decision = stepped["last_manager_decision"]
    assert "manager_read_receipt" in decision
    
    receipt = decision["manager_read_receipt"]
    assert receipt is not None
    assert "problem_summary" in receipt
    assert "target_node_id_confirmed" in receipt
    assert "target_node_text_confirmed" in receipt
    assert "operator_notes_seen" in receipt
    assert "relevant_memory_seen" in receipt
    assert "constraints_seen" in receipt
    assert "why_not_other_frontier_nodes" in receipt

    # Verify operator notes were seen
    assert len(receipt["operator_notes_seen"]) > 0
    
    # Verify constraints include expected items
    constraints = receipt["constraints_seen"]
    assert any("bounded local work" in c.lower() for c in constraints)
    
    # Verify target node confirmation matches decision
    assert receipt["target_node_id_confirmed"] == decision["target_frontier_node"]


def test_operator_brief_fallback_when_no_execution(tmp_path: Path) -> None:
    """Test that operator brief handles campaigns with no execution result yet."""
    settings = Settings(
        memory_db_path=str(tmp_path / "memory.db"),
        worker_poll_seconds=999,
        manager_backend="rules",
        executor_backend="mock",
    )
    app = create_app(settings)
    client = TestClient(app)

    # Create a campaign but don't step it
    create_response = client.post(
        "/api/campaigns",
        json={
            "title": "No execution yet",
            "problem_statement": "Test problem",
            "operator_notes": [],
            "auto_run": False,
        },
    )
    assert create_response.status_code == 200
    campaign_id = create_response.json()["id"]

    # Get operator brief before any execution
    brief_response = client.get(f"/api/campaigns/{campaign_id}/operator-brief")
    assert brief_response.status_code == 200
    brief = brief_response.json()

    # Should have structure but with null/empty values
    assert brief["ops"]["tick_count"] == 0
    assert brief["verification"]["status"] is None
    assert brief["discovery"]["spawned_nodes_count"] == 0
    assert brief["next"]["recommended_operator_action"] is None


def test_recommended_operator_action_synthesis(tmp_path: Path) -> None:
    """Test that recommended operator action is synthesized correctly."""
    settings = Settings(
        memory_db_path=str(tmp_path / "memory.db"),
        worker_poll_seconds=999,
        manager_backend="rules",
        executor_backend="mock",
    )
    app = create_app(settings)
    client = TestClient(app)

    # Create and step a campaign
    create_response = client.post(
        "/api/campaigns",
        json={
            "title": "Action synthesis test",
            "problem_statement": "Test problem",
            "operator_notes": [],
            "auto_run": False,
        },
    )
    assert create_response.status_code == 200
    campaign_id = create_response.json()["id"]

    step_response = client.post(f"/api/campaigns/{campaign_id}/step")
    assert step_response.status_code == 200

    # Get operator brief
    brief_response = client.get(f"/api/campaigns/{campaign_id}/operator-brief")
    assert brief_response.status_code == 200
    brief = brief_response.json()

    # Should have a recommended action
    assert brief["next"]["recommended_operator_action"] is not None
    assert len(brief["next"]["recommended_operator_action"]) > 0
