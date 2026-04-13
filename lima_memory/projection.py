from __future__ import annotations

from typing import Any

from .store import KnowledgeStore

def project_campaign_summary(store: KnowledgeStore, campaign_id: str) -> dict[str, Any]:
    campaigns = store.list_nodes(campaign_id, node_type="Campaign", limit=1)
    problems = store.list_nodes(campaign_id, node_type="Problem", limit=1)
    frontier = store.list_nodes(campaign_id, node_type="FrontierNode", limit=50)
    answers = store.list_nodes(campaign_id, node_type="CandidateAnswer", limit=3)
    worlds = store.list_nodes(campaign_id, node_type="WorldModel", limit=10)
    results = store.list_nodes(campaign_id, node_type="ExecutionResult", limit=10)

    return {
        "campaign": campaigns[0].asdict() if campaigns else None,
        "problem": problems[0].asdict() if problems else None,
        "current_candidate_answer": answers[0].asdict() if answers else None,
        "frontier": [node.asdict() for node in frontier],
        "worlds": [node.asdict() for node in worlds],
        "recent_results": [node.asdict() for node in results],
    }
