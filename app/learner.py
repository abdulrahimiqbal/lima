from __future__ import annotations

import logging
from typing import Any

from .schemas import CampaignRecord, ExecutionResult, ManagerDecision

logger = logging.getLogger(__name__)


def update_memory(
    campaign: CampaignRecord,
    decision: ManagerDecision,
    result: ExecutionResult,
    policy: dict[str, Any] = None,
) -> CampaignRecord:
    updated = campaign.model_copy(deep=True)
    scores = updated.memory.world_scores
    world = decision.world_family
    scores.setdefault(world, 0.0)

    # Use policy for rewards/penalties if available, else defaults
    rewards = policy.get("success_rewards", {}) if policy else {}
    penalties = policy.get("failure_penalties", {}) if policy else {}
    conf_rules = policy.get("confidence_rules", {}) if policy else {}

    # 1. Update World Scores
    if result.status == "proved":
        score_gain = rewards.get("successful_reduction", 0.5)
        scores[world] += score_gain
        updated.memory.useful_lemmas.append(decision.bounded_claim)
    elif result.status == "refuted":
        scores[world] -= penalties.get("counterexample_found", 0.5)
    elif result.status == "blocked":
        penalty = penalties.get(result.failure_type, 0.2) if result.failure_type else 0.2
        scores[world] -= penalty
    else:
        scores[world] -= penalties.get("inconclusive_probe", 0.1)

    # 2. Update Confidence
    if updated.current_candidate_answer:
        ca = updated.current_candidate_answer
        if result.status == "proved":
            ca.confidence = min(0.99, ca.confidence + conf_rules.get("increase_on_successful_reduction", 0.05))
        elif result.status == "refuted":
            ca.confidence = max(0.01, ca.confidence - conf_rules.get("decrease_on_counterexample", 0.3))
            if ca.stance == "likely_true":
                ca.stance = "likely_false"
        elif result.status == "inconclusive":
             ca.confidence = max(0.01, ca.confidence - conf_rules.get("decrease_on_repeated_inconclusive", 0.02))

    # 3. Track Failures and Penalties
    if result.failure_type:
        updated.memory.recent_failures.insert(
            0,
            {
                "world": world,
                "failure_type": result.failure_type,
                "claim": decision.bounded_claim,
            },
        )
        updated.memory.recent_failures = updated.memory.recent_failures[:20]

    penalty_key = f"{decision.target_frontier_node}:{world}"
    updated.memory.retry_penalties[penalty_key] = (
        updated.memory.retry_penalties.get(penalty_key, 0) + 1
    )

    if result.failure_type == "bad_world" or result.status == "blocked":
        updated.memory.blocked_patterns.append(
            f"Avoid {world} for node {decision.target_frontier_node} due to {result.failure_type or result.status}"
        )
        updated.memory.blocked_patterns = updated.memory.blocked_patterns[-20:]

    return updated
