from __future__ import annotations

from copy import deepcopy

from .schemas import CampaignRecord, ExecutionResult, FrontierNode, ManagerDecision


def seed_frontier(problem_statement: str) -> list[FrontierNode]:
    root_claim = _extract_root_claim(problem_statement)
    return [
        FrontierNode(
            text=root_claim,
            status="open",
            priority=1.0,
            kind="claim",
        )
    ]


def _extract_root_claim(problem_statement: str) -> str:
    text = problem_statement.strip()
    if not text:
        return text

    for marker in ("\n\nResearch brief:", "\nResearch brief:", "\n\nWhat I want:", "\nWhat I want:"):
        if marker in text:
            candidate = text.split(marker, 1)[0].strip()
            if candidate:
                return candidate

    return text


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
        
        # Update proof debt ledger if this was a debt-driven obligation
        if decision.proof_debt and decision.critical_next_debt_id:
            for debt_dict in updated.proof_debt_ledger:
                if debt_dict.get("id") == decision.critical_next_debt_id:
                    debt_dict["status"] = "proved"
                    if debt_dict["id"] not in updated.resolved_debt_ids:
                        updated.resolved_debt_ids.append(debt_dict["id"])
                    break
    elif result.status == "refuted":
        # Only true counterexample should reach here
        target.status = "refuted"
        target.priority = 0.0
        
        # Update proof debt ledger
        if decision.proof_debt and decision.critical_next_debt_id:
            for debt_dict in updated.proof_debt_ledger:
                if debt_dict.get("id") == decision.critical_next_debt_id:
                    debt_dict["status"] = "refuted"
                    break
        
        # Kill descendants
        def kill_descendants(parent_id: str):
            for n in updated.frontier:
                if n.parent_id == parent_id and n.status not in {"proved", "refuted"}:
                    n.status = "blocked"
                    n.evidence.append(f"Parent {parent_id} refuted by counterexample.")
                    kill_descendants(n.id)
        kill_descendants(target.id)

    elif result.status == "blocked":
        target.status = "blocked"
        target.failure_count += 1
        target.priority = max(0.1, target.priority - 0.05)
        
        # Update proof debt ledger
        if decision.proof_debt and decision.critical_next_debt_id:
            for debt_dict in updated.proof_debt_ledger:
                if debt_dict.get("id") == decision.critical_next_debt_id:
                    debt_dict["status"] = "blocked"
                    break
    else:
        # Inconclusive
        target.status = "open"
        target.failure_count += 1
        target.priority = max(0.2, target.priority - 0.02)

    # Spawn nodes from proof debt if available
    if decision.proof_debt and not result.spawned_nodes:
        _spawn_from_debt(updated, decision, result, target)
    
    # Spawn nodes based on failure type (existing logic)
    if result.failure_type == "evidence_only" and not result.spawned_nodes:
        # After evidence_only, spawn formalization-oriented child
        evidence_streak = updated.memory.evidence_streaks.get(target.id, 0)
        if evidence_streak >= 2:
            formalize_text = f"Formalize the invariant suggested by bounded evidence for: {target.text}"
            if not _has_similar_open_child(updated.frontier, target.id, "lemma", formalize_text):
                result.spawned_nodes.append(
                    FrontierNode(
                        text=formalize_text,
                        status="open",
                        priority=max(0.3, target.priority),
                        parent_id=target.id,
                        kind="lemma",
                    )
                )
    elif result.failure_type == "formalization_failed" and not result.spawned_nodes:
        # Spawn "encode cleanly" child
        encode_text = f"State a clean formal Lean-compatible claim for: {target.text}"
        if not _has_similar_open_child(updated.frontier, target.id, "lemma", encode_text):
            result.spawned_nodes.append(
                FrontierNode(
                    text=encode_text,
                    status="open",
                    priority=max(0.3, target.priority),
                    parent_id=target.id,
                    kind="lemma",
                )
            )
    elif result.failure_type == "proof_failed" and not result.spawned_nodes:
        # Spawn "identify missing lemma" child
        lemma_text = f"Identify and prove a missing lemma needed for: {target.text}"
        if not _has_similar_open_child(updated.frontier, target.id, "lemma", lemma_text):
            result.spawned_nodes.append(
                FrontierNode(
                    text=lemma_text,
                    status="open",
                    priority=max(0.3, target.priority),
                    parent_id=target.id,
                    kind="lemma",
                )
            )
    elif result.failure_type == "missing_lemma" and not result.spawned_nodes:
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
        timeout_streak = updated.memory.timeout_streaks.get(target.id, 0)
        if timeout_streak >= 2:
            # Spawn smaller bounded reduction
            retry_text = f"Prove a smaller bounded reduction lemma for: {target.text}"
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

    # World-aware solved check
    world = updated.current_world_program
    if world:
        # Use world-aware solved logic only
        ledger = updated.proof_debt_ledger
        has_bridge = world.get("bridge_to_target") is not None
        soundness_certificate = world.get("soundness_certificate") or {}
        soundness_debt_ids = set(soundness_certificate.get("soundness_debt_ids") or [])
        ledger_by_id = {d.get("id"): d for d in ledger}
        soundness_debt_proved = bool(soundness_certificate) and (
            soundness_certificate.get("status") == "proved"
            or (
                bool(soundness_debt_ids)
                and all(
                    ledger_by_id.get(debt_id, {}).get("status") == "proved"
                    for debt_id in soundness_debt_ids
                )
            )
        )
        if soundness_debt_ids:
            if all(
                ledger_by_id.get(debt_id, {}).get("status") == "proved"
                for debt_id in soundness_debt_ids
            ):
                soundness_certificate["status"] = "proved"
            elif any(
                ledger_by_id.get(debt_id, {}).get("status") == "blocked"
                for debt_id in soundness_debt_ids
            ):
                soundness_certificate["status"] = "blocked"
            elif any(
                ledger_by_id.get(debt_id, {}).get("status") == "proved"
                for debt_id in soundness_debt_ids
            ):
                soundness_certificate["status"] = "partially_proved"
            world["soundness_certificate"] = soundness_certificate
        critical_debt = [d for d in ledger if d.get("critical")]
        
        if critical_debt:
            # Check if all critical debt is proved and no live falsifiers
            all_critical_proved = all(d.get("status") == "proved" for d in critical_debt)
            critical_falsifiers = [d for d in critical_debt if d.get("role") == "falsifier"]
            no_live_falsifiers = all(
                d.get("status") in {"proved", "refuted", "blocked"} 
                for d in critical_falsifiers
            )
            
            if has_bridge and soundness_debt_proved and all_critical_proved and no_live_falsifiers:
                updated.status = "solved"
        else:
            # No critical debt - only allow solved if world explicitly has zero debt
            rc = world.get("reduction_certificate") or {}
            if has_bridge and soundness_debt_proved and int(rc.get("total_debt_count", 1)) == 0:
                updated.status = "solved"
    else:
        # Fallback to old behavior when no world program exists
        if updated.frontier[0].status == "proved":
            updated.status = "solved"
        elif updated.frontier[0].status == "refuted":
            updated.status = "failed"

    return updated


def _spawn_from_debt(
    campaign: CampaignRecord,
    decision: ManagerDecision,
    result: ExecutionResult,
    target: FrontierNode,
) -> None:
    """Spawn frontier nodes from open proof debt items."""
    # Find open critical debt items not already represented
    for debt_dict in campaign.proof_debt_ledger:
        if debt_dict.get("status") != "open":
            continue
        if not debt_dict.get("critical"):
            continue
        
        # Check if already represented in frontier
        debt_text = debt_dict.get("statement", "")
        if _has_similar_text_in_frontier(campaign.frontier, debt_text):
            continue
        
        # Spawn based on role
        role = debt_dict.get("role", "support")
        if role in {"closure", "bridge", "support"}:
            kind = "lemma"
        elif role == "boundary":
            kind = "finite_check"
        elif role == "falsifier":
            kind = "exploration"
        else:
            kind = "lemma"
        
        result.spawned_nodes.append(
            FrontierNode(
                text=debt_text,
                status="open",
                priority=debt_dict.get("priority", 0.5),
                parent_id=target.id,
                kind=kind,  # type: ignore[arg-type]
            )
        )


def _has_similar_text_in_frontier(frontier: list[FrontierNode], text: str) -> bool:
    """Check if similar text already exists in frontier."""
    text_lower = text.lower()[:100]
    for node in frontier:
        if node.status not in {"open", "active", "blocked"}:
            continue
        if text_lower in node.text.lower() or node.text.lower()[:100] in text_lower:
            return True
    return False


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
