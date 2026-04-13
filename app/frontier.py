from __future__ import annotations

from copy import deepcopy

from .schemas import CampaignRecord, ExecutionResult, FrontierNode, ManagerDecision


def seed_frontier(problem_statement: str) -> list[FrontierNode]:
    return [
        FrontierNode(
            text=problem_statement,
            status="open",
            priority=1.0,
            kind="claim",
        )
    ]


def choose_frontier_node(frontier: list[FrontierNode]) -> FrontierNode | None:
    candidates = [
        node
        for node in frontier
        if node.status in {"open", "active", "blocked"}
    ]
    if not candidates:
        return None
    blocked = [node for node in candidates if node.status == "blocked"]
    pool = blocked or candidates
    return sorted(pool, key=lambda item: (-item.priority, item.failure_count, item.id))[0]


def apply_execution_result(
    campaign: CampaignRecord,
    decision: ManagerDecision,
    result: ExecutionResult,
) -> CampaignRecord:
    updated = campaign.model_copy(deep=True)
    target: FrontierNode | None = None
    for node in updated.frontier:
        if node.id == decision.target_frontier_node:
            target = node
            break
    if target is None:
        return updated

    target.evidence.extend(result.artifacts)

    if result.status == "proved":
        target.status = "proved"
        target.priority = 0.0
        # If this was a lemma, maybe it helps parents?
        # For now, we keep it simple as requested.
    elif result.status == "refuted":
        target.status = "refuted"
        target.priority = 0.0
        # "Counterexample can kill a branch"
        # In a tree, if a node is refuted, its descendants (and potentially parents) are affected.
        # For this simple repo, we'll mark all descendants as blocked/refuted if appropriate.
        def kill_descendants(parent_id: str):
            for n in updated.frontier:
                if n.parent_id == parent_id and n.status not in {"proved", "refuted"}:
                    n.status = "blocked"
                    n.evidence.append(f"Parent {parent_id} refuted.")
                    kill_descendants(n.id)
        kill_descendants(target.id)

    elif result.status == "blocked":
        target.status = "blocked"
        target.failure_count += 1
        target.priority = max(0.1, target.priority - 0.05)
    else:
        # Inconclusive
        target.status = "open"
        target.failure_count += 1
        target.priority = max(0.2, target.priority - 0.02)

    # Spawn nodes from result
    if result.failure_type == "missing_lemma" and not result.spawned_nodes:
        new_text = f"Missing lemma discovered while attacking: {target.text}"
        if not _has_similar_open_child(updated.frontier, target.id, "lemma", new_text):
            result.spawned_nodes.append(
                FrontierNode(
                    text=new_text,
                    status="open",
                    priority=max(0.2, target.priority - 0.1),
                    parent_id=target.id,
                    kind="lemma",
                )
            )
    elif result.failure_type in {"excessive_scope", "mixed_channels"} and not result.spawned_nodes:
        lemma_text = f"Shrink the claim into one local lemma for: {target.text}"
        finite_text = f"Isolate one bounded finite check supporting: {target.text}"
        if not _has_similar_open_child(updated.frontier, target.id, "lemma", lemma_text):
            result.spawned_nodes.append(
                FrontierNode(
                    text=lemma_text,
                    status="open",
                    priority=max(0.2, target.priority - 0.05),
                    parent_id=target.id,
                    kind="lemma",
                )
            )
        if not _has_similar_open_child(updated.frontier, target.id, "finite_check", finite_text):
            result.spawned_nodes.append(
                FrontierNode(
                    text=finite_text,
                    status="open",
                    priority=max(0.2, target.priority - 0.1),
                    parent_id=target.id,
                    kind="finite_check",
                )
            )
    elif result.failure_type == "timeout" and not result.spawned_nodes:
        retry_text = f"Retry with a smaller bounded reduction step for: {target.text}"
        if not _has_similar_open_child(updated.frontier, target.id, "lemma", retry_text):
            result.spawned_nodes.append(
                FrontierNode(
                    text=retry_text,
                    status="open",
                    priority=max(0.2, target.priority - 0.08),
                    parent_id=target.id,
                    kind="lemma",
                )
            )

    existing_ids = {node.id for node in updated.frontier}
    for spawned in result.spawned_nodes:
        if spawned.id not in existing_ids and not _has_exact_open_node(updated.frontier, spawned):
            updated.frontier.append(spawned)
            existing_ids.add(spawned.id)

    # Global solved check
    # If the root node is proved/refuted, the campaign is over.
    if updated.frontier[0].status == "proved":
        updated.status = "solved"
    elif updated.frontier[0].status == "refuted":
        updated.status = "failed"
    elif all(node.status in {"proved", "refuted", "blocked"} for node in updated.frontier):
        # If everything is blocked/proved/refuted but root is not conclusive, wait for manual unblock or mark failed
        pass

    return updated


def _has_similar_open_child(
    frontier: list[FrontierNode],
    parent_id: str,
    kind: str,
    text: str,
) -> bool:
    for node in frontier:
        if node.parent_id != parent_id or node.kind != kind:
            continue
        if node.status not in {"open", "active", "blocked"}:
            continue
        if node.text == text:
            return True
    return False


def _has_exact_open_node(frontier: list[FrontierNode], candidate: FrontierNode) -> bool:
    for node in frontier:
        if node.parent_id == candidate.parent_id and node.kind == candidate.kind and node.text == candidate.text:
            if node.status in {"open", "active", "blocked"}:
                return True
    return False
