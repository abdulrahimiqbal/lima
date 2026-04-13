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

    node_key = decision.target_frontier_node
    
    # Update world diagnostics
    if decision.primary_world:
        world_id = decision.primary_world.id
        if world_id not in updated.memory.world_diagnostics:
            updated.memory.world_diagnostics[world_id] = {
                "debt_total": 0,
                "debt_proved": 0,
                "critical_total": 0,
                "critical_proved": 0,
                "bridge_failures": 0,
                "closure_failures": 0,
                "evidence_hits": 0,
                "proof_hits": 0,
            }
        
        diag = updated.memory.world_diagnostics[world_id]
        
        # Prefer using final ledger if world ID matches
        if updated.active_world_id == world_id and updated.proof_debt_ledger:
            ledger = updated.proof_debt_ledger
            diag["debt_total"] = len(ledger)
            diag["debt_proved"] = len([d for d in ledger if d.get("status") == "proved"])
            diag["critical_total"] = len([d for d in ledger if d.get("critical")])
            diag["critical_proved"] = len([d for d in ledger if d.get("critical") and d.get("status") == "proved"])
        elif decision.proof_debt:
            # Fallback to decision proof debt
            diag["debt_total"] = len(decision.proof_debt)
            diag["debt_proved"] = len([d for d in decision.proof_debt if d.status == "proved"])
            diag["critical_total"] = len([d for d in decision.proof_debt if d.critical])
            diag["critical_proved"] = len([d for d in decision.proof_debt if d.critical and d.status == "proved"])
        
        # Update result counters
        if result.status == "proved":
            diag["proof_hits"] = diag.get("proof_hits", 0) + 1
        elif result.status == "inconclusive" and result.channel_used == "computational_evidence":
            diag["evidence_hits"] = diag.get("evidence_hits", 0) + 1
        elif result.status == "blocked":
            if result.failure_type == "bad_bridge" or result.failure_type == "false_bridge":
                diag["bridge_failures"] = diag.get("bridge_failures", 0) + 1
            elif result.failure_type == "bad_world":
                diag["closure_failures"] = diag.get("closure_failures", 0) + 1

    # 1. Update World Scores
    if result.status == "proved":
        score_gain = rewards.get("successful_reduction", 0.5)
        scores[world] += score_gain
        updated.memory.useful_lemmas.append(decision.bounded_claim)
        # Reset streaks on success
        updated.memory.evidence_streaks[node_key] = 0
        updated.memory.formalization_streaks[node_key] = 0
        updated.memory.timeout_streaks[node_key] = 0
    elif result.status == "refuted":
        # Only true counterexample should reach here
        scores[world] -= penalties.get("counterexample_found", 0.5)
        updated.memory.evidence_streaks[node_key] = 0
        updated.memory.formalization_streaks[node_key] = 0
        updated.memory.timeout_streaks[node_key] = 0
    elif result.status == "blocked":
        penalty = penalties.get(result.failure_type, 0.2) if result.failure_type else 0.2
        scores[world] -= penalty
        
        # Track specific failure streaks
        if result.failure_type == "formalization_failed":
            updated.memory.formalization_streaks[node_key] = (
                updated.memory.formalization_streaks.get(node_key, 0) + 1
            )
            updated.memory.evidence_streaks[node_key] = 0
            updated.memory.timeout_streaks[node_key] = 0
        elif result.failure_type == "proof_failed":
            # Proof failure is not refutation - just couldn't find proof
            updated.memory.policy_notes.append(
                f"proof_failed_not_refuted:{node_key}:{world}"
            )
            updated.memory.formalization_streaks[node_key] = 0
            updated.memory.evidence_streaks[node_key] = 0
        else:
            # Other blocked states
            updated.memory.formalization_streaks[node_key] = 0
    else:
        # Inconclusive
        scores[world] -= penalties.get("inconclusive_probe", 0.1)
        
        # Track evidence_only streak
        if result.failure_type == "evidence_only":
            updated.memory.evidence_streaks[node_key] = (
                updated.memory.evidence_streaks.get(node_key, 0) + 1
            )
            updated.memory.formalization_streaks[node_key] = 0
            updated.memory.timeout_streaks[node_key] = 0
        elif result.failure_type == "timeout":
            # Only penalize actual terminal timeouts, not still-running jobs
            # With the new polling system, this should be rare
            updated.memory.timeout_streaks[node_key] = (
                updated.memory.timeout_streaks.get(node_key, 0) + 1
            )
            updated.memory.evidence_streaks[node_key] = 0
            updated.memory.formalization_streaks[node_key] = 0
            updated.memory.policy_notes.append(
                f"terminal_timeout:{node_key}:{world}"
            )
        else:
            # Other inconclusive - don't reset streaks necessarily
            pass

    if result.failure_type in {"timeout", "excessive_scope", "mixed_channels"}:
        scores[world] -= penalties.get(result.failure_type, 0.2)
        updated.memory.policy_notes.append(
            f"shrink_required:{world}:{result.failure_type}:{decision.target_frontier_node}"
        )
        updated.memory.policy_notes = updated.memory.policy_notes[-30:]

    # 2. Update Confidence
    if updated.current_candidate_answer:
        ca = updated.current_candidate_answer
        if result.status == "proved":
            ca.confidence = min(0.99, ca.confidence + conf_rules.get("increase_on_successful_reduction", 0.05))
        elif result.status == "refuted":
            # Only true counterexample
            ca.confidence = max(0.01, ca.confidence - conf_rules.get("decrease_on_counterexample", 0.3))
            if ca.stance == "likely_true":
                ca.stance = "likely_false"
        elif result.status == "blocked" and result.failure_type == "proof_failed":
            # Proof failure doesn't change stance, just slight confidence drop
            ca.confidence = max(0.01, ca.confidence - 0.01)
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
    penalty_bump = 1
    if result.failure_type in {"timeout", "excessive_scope"}:
        penalty_bump = 2
    elif result.failure_type == "evidence_only":
        # Don't penalize evidence_only as heavily
        penalty_bump = 0
    updated.memory.retry_penalties[penalty_key] = updated.memory.retry_penalties.get(penalty_key, 0) + penalty_bump

    if result.failure_type == "bad_world" or (result.status == "blocked" and result.failure_type != "formalization_failed"):
        updated.memory.blocked_patterns.append(
            f"Avoid {world} for node {decision.target_frontier_node} due to {result.failure_type or result.status}"
        )
        updated.memory.blocked_patterns = updated.memory.blocked_patterns[-20:]

    if result.failure_type in {"timeout", "excessive_scope", "mixed_channels"}:
        updated.memory.blocked_patterns.append(
            f"Prefer smaller obligations after {result.failure_type} for node {decision.target_frontier_node}"
        )
        updated.memory.blocked_patterns = updated.memory.blocked_patterns[-20:]

    return updated
