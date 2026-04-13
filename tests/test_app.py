from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_campaign_lifecycle(tmp_path: Path) -> None:
    settings = Settings(
        memory_db_path=str(tmp_path / "memory.db"),
        worker_poll_seconds=999,
        manager_backend="rules",
        executor_backend="mock",
    )
    app = create_app(settings)
    client = TestClient(app)

    create_response = client.post(
        "/api/campaigns",
        json={
            "title": "Test campaign",
            "problem_statement": "Prove a simple bounded statement",
            "operator_notes": ["Prefer smaller jobs"],
            "auto_run": False,
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    campaign_id = created["id"]

    step_response = client.post(f"/api/campaigns/{campaign_id}/step")
    assert step_response.status_code == 200
    stepped = step_response.json()
    assert stepped["tick_count"] == 1
    assert stepped["last_manager_decision"] is not None
    assert stepped["last_execution_result"] is not None

    context_response = client.get(f"/api/campaigns/{campaign_id}/manager-context")
    assert context_response.status_code == 200
    assert context_response.json()["problem"]["id"] == campaign_id

    index_response = client.get("/")
    assert index_response.status_code == 200
    assert "Current candidate answer" in index_response.text
