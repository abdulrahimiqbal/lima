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


def test_operator_api_key_guards_write_routes(tmp_path: Path) -> None:
    settings = Settings(
        memory_db_path=str(tmp_path / "memory.db"),
        worker_poll_seconds=999,
        manager_backend="rules",
        executor_backend="mock",
        operator_api_key="secret",
    )
    app = create_app(settings)
    client = TestClient(app)

    # Read route stays open.
    health_response = client.get("/healthz")
    assert health_response.status_code == 200

    # Write route is blocked without API key.
    create_response = client.post(
        "/api/campaigns",
        json={
            "title": "Protected campaign",
            "problem_statement": "Prove a simple bounded statement",
            "operator_notes": [],
            "auto_run": False,
        },
    )
    assert create_response.status_code == 401

    # Write route succeeds with matching API key.
    create_response = client.post(
        "/api/campaigns",
        headers={"X-API-Key": "secret"},
        json={
            "title": "Protected campaign",
            "problem_statement": "Prove a simple bounded statement",
            "operator_notes": [],
            "auto_run": False,
        },
    )
    assert create_response.status_code == 200


def test_csrf_blocks_cross_site_write_without_operator_key(tmp_path: Path) -> None:
    settings = Settings(
        memory_db_path=str(tmp_path / "memory.db"),
        worker_poll_seconds=999,
        manager_backend="rules",
        executor_backend="mock",
    )
    app = create_app(settings)
    client = TestClient(app)

    response = client.post(
        "/api/campaigns",
        headers={"Origin": "https://evil.example"},
        json={
            "title": "Blocked by CSRF",
            "problem_statement": "x",
            "operator_notes": [],
            "auto_run": False,
        },
    )
    assert response.status_code == 403


def test_csrf_requires_token_for_same_origin_browser_post(tmp_path: Path) -> None:
    settings = Settings(
        memory_db_path=str(tmp_path / "memory.db"),
        worker_poll_seconds=999,
        manager_backend="rules",
        executor_backend="mock",
    )
    app = create_app(settings)
    client = TestClient(app)

    client.get("/")
    token = client.cookies.get("csrf_token")
    assert token

    missing_token = client.post(
        "/api/campaigns",
        headers={"Origin": "http://testserver"},
        json={
            "title": "Needs token",
            "problem_statement": "x",
            "operator_notes": [],
            "auto_run": False,
        },
    )
    assert missing_token.status_code == 403

    ok = client.post(
        "/api/campaigns",
        headers={"Origin": "http://testserver", "X-CSRF-Token": token},
        json={
            "title": "Valid token",
            "problem_statement": "x",
            "operator_notes": [],
            "auto_run": False,
        },
    )
    assert ok.status_code == 200
