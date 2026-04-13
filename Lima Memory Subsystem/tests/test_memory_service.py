from pathlib import Path

from lima_memory import MemoryService, SqliteKnowledgeStore

def test_memory_service_round_trip(tmp_path: Path) -> None:
    store = SqliteKnowledgeStore(str(tmp_path / "memory.db"))
    service = MemoryService(store)

    service.create_campaign(
        campaign_id="C-test123",
        title="Test Campaign",
        problem_statement="Prove or disprove something.",
        operator_notes=["prefer small obligations"],
    )
    frontier_id = service.seed_frontier(
        campaign_id="C-test123",
        frontier_text="Main conjecture",
    )

    decision = {
        "candidate_answer": {
            "stance": "undecided",
            "summary": "Tentative answer",
            "confidence": 0.2,
        },
        "world_family": "bridge",
        "bounded_claim": "A bridge lemma should reduce the target.",
        "formal_obligations": ["prove local bridge lemma", "test bridge on small cases"],
        "why_this_next": "High information gain.",
        "expected_information_gain": "Good",
        "target_frontier_node": frontier_id,
        "update_rules": {
            "if_proved": "descend",
            "if_refuted": "switch worlds",
            "if_blocked": "shrink claim",
            "if_inconclusive": "retry smaller",
        },
    }

    ids = service.record_manager_decision(
        campaign_id="C-test123",
        tick=1,
        decision=decision,
    )
    assert ids["claim_id"].startswith("C-")
    assert len(ids["obligation_ids"]) == 2

    result = {
        "status": "blocked",
        "failure_type": "missing_lemma",
        "notes": "Need sharper local lemma.",
        "artifacts": ["log excerpt"],
        "executor_backend": "mock",
        "spawned_nodes": [{"text": "Find missing lemma", "kind": "lemma"}],
    }

    result_id = service.record_execution_result(
        campaign_id="C-test123",
        tick=1,
        decision=decision,
        result=result,
    )
    assert result_id.startswith("R-")

    packet = service.get_manager_packet(campaign_id="C-test123")
    assert packet.campaign["id"] == "C-test123"
    assert packet.active_frontier
    assert packet.relevant_worlds
    assert packet.recent_claims
    assert packet.recent_results

    summary = service.project_campaign_summary("C-test123")
    assert summary["campaign"]["id"] == "C-test123"
