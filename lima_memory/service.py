from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .models import (
    ArtifactRecord,
    EdgeRecord,
    EventRecord,
    ManagerPacket,
    NodeRecord,
    PolicySnapshotRecord,
    make_id,
)
from .projection import project_campaign_summary
from .store import KnowledgeStore

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _formal_obligation_text(obligation: Any) -> str:
    if isinstance(obligation, str):
        return obligation
    if isinstance(obligation, dict):
        for key in ("source_text", "statement", "theorem_name", "id"):
            value = obligation.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return str(obligation)
    source_text = getattr(obligation, "source_text", None)
    if isinstance(source_text, str) and source_text.strip():
        return source_text.strip()
    statement = getattr(obligation, "statement", None)
    if isinstance(statement, str) and statement.strip():
        return statement.strip()
    return str(obligation)


def _formal_obligation_payload(obligation: Any) -> dict[str, Any]:
    if isinstance(obligation, str):
        return {"source_text": obligation, "representation": "string"}
    if isinstance(obligation, dict):
        return dict(obligation)
    if hasattr(obligation, "model_dump"):
        return obligation.model_dump(mode="json")
    return {"source_text": str(obligation), "representation": type(obligation).__name__}


class MemoryService:
    """Canonical research-state layer for LIMA."""

    def __init__(self, store: KnowledgeStore) -> None:
        self.store = store
        self.store.init()

    def list_campaign_nodes(self, limit: int = 200) -> list[NodeRecord]:
        return self.store.list_campaign_nodes(limit=limit)

    def create_campaign(
        self,
        *,
        campaign_id: str,
        title: str,
        problem_statement: str,
        operator_notes: list[str] | None = None,
    ) -> dict[str, str]:
        operator_notes = operator_notes or []
        now = _utc_now_iso()
        campaign_node = NodeRecord(
            id=campaign_id,
            campaign_id=campaign_id,
            node_type="Campaign",
            title=title,
            summary="LIMA campaign root",
            status="running",
            payload={
                "operator_notes": operator_notes,
                "problem_statement": problem_statement,
                "auto_run": True,
                "tick_count": 0,
                "memory": {},
                "manager_backend": "rules",
                "executor_backend": "mock",
                "last_manager_context": None,
                "last_manager_decision": None,
                "last_execution_result": None,
            },
            created_at=now,
            updated_at=now,
        )
        problem_id = make_id("P")
        problem_node = NodeRecord(
            id=problem_id,
            campaign_id=campaign_id,
            node_type="Problem",
            title=title,
            summary=problem_statement,
            status="open",
            payload={"statement": problem_statement},
        )
        self.store.upsert_node(campaign_node)
        self.store.upsert_node(problem_node)
        self.store.add_edge(
            EdgeRecord(
                id=make_id("E"),
                campaign_id=campaign_id,
                src_id=campaign_id,
                edge_type="HAS_PROBLEM",
                dst_id=problem_id,
            )
        )
        self.add_event(
            campaign_id=campaign_id,
            tick=0,
            event_type="campaign_created",
            payload={"title": title, "problem_statement": problem_statement},
        )
        return {"campaign_id": campaign_id, "problem_id": problem_id}

    def get_campaign_node(self, campaign_id: str) -> NodeRecord | None:
        return self.store.get_node(campaign_id, campaign_id)

    def list_frontier_nodes(self, campaign_id: str, limit: int = 500) -> list[NodeRecord]:
        return self.store.list_nodes(campaign_id, node_type="FrontierNode", limit=limit)

    def get_research_node(self, campaign_id: str, node_id: str) -> NodeRecord | None:
        return self.store.get_node(campaign_id, node_id)

    def list_research_nodes(
        self,
        campaign_id: str,
        *,
        node_type: str | None = None,
        limit: int = 100,
    ) -> list[NodeRecord]:
        return self.store.list_nodes(campaign_id, node_type=node_type, limit=limit)

    def upsert_research_node(
        self,
        *,
        campaign_id: str,
        node_id: str,
        node_type: str,
        title: str,
        summary: str = "",
        status: str = "speculative",
        confidence: float | None = None,
        payload: dict[str, Any] | None = None,
    ) -> NodeRecord:
        existing = self.store.get_node(campaign_id, node_id)
        node = NodeRecord(
            id=node_id,
            campaign_id=campaign_id,
            node_type=node_type,
            title=(title or node_type)[:160],
            summary=summary,
            status=status,
            confidence=confidence,
            payload=payload or {},
            created_at=existing.created_at if existing else _utc_now_iso(),
            updated_at=_utc_now_iso(),
        )
        self.store.upsert_node(node)
        return node

    def add_research_edge(
        self,
        *,
        campaign_id: str,
        src_id: str,
        edge_type: str,
        dst_id: str,
        weight: float = 1.0,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.store.add_edge(
            EdgeRecord(
                id=make_id("E"),
                campaign_id=campaign_id,
                src_id=src_id,
                edge_type=edge_type,
                dst_id=dst_id,
                weight=weight,
                payload=payload or {},
            )
        )

    def update_campaign_payload(
        self,
        campaign_id: str,
        *,
        title: str | None = None,
        status: str | None = None,
        payload_updates: dict[str, Any] | None = None,
    ) -> NodeRecord:
        node = self.get_campaign_node(campaign_id)
        if not node:
            raise KeyError(f"Campaign not found: {campaign_id}")
        payload = dict(node.payload)
        if payload_updates:
            payload.update(payload_updates)
        node = NodeRecord(
            id=node.id,
            campaign_id=node.campaign_id,
            node_type=node.node_type,
            title=title if title is not None else node.title,
            summary=node.summary,
            status=status if status is not None else node.status,
            confidence=node.confidence,
            payload=payload,
            created_at=node.created_at,
            updated_at=_utc_now_iso(),
        )
        self.store.upsert_node(node)
        return node

    def seed_frontier(
        self,
        *,
        campaign_id: str,
        frontier_text: str,
        kind: str = "claim",
        parent_id: str | None = None,
        frontier_id: str | None = None,
        status: str = "open",
        priority: float = 1.0,
        failure_count: int = 0,
        evidence: list[str] | None = None,
    ) -> str:
        return self.upsert_frontier_node(
            campaign_id=campaign_id,
            frontier_text=frontier_text,
            kind=kind,
            parent_id=parent_id,
            frontier_id=frontier_id,
            status=status,
            priority=priority,
            failure_count=failure_count,
            evidence=evidence,
        )

    def upsert_frontier_node(
        self,
        *,
        campaign_id: str,
        frontier_text: str,
        kind: str = "claim",
        parent_id: str | None = None,
        frontier_id: str | None = None,
        status: str = "open",
        priority: float = 1.0,
        failure_count: int = 0,
        evidence: list[str] | None = None,
    ) -> str:
        frontier_id = frontier_id or make_id("F")
        self.upsert_frontier_nodes(
            campaign_id=campaign_id,
            nodes=[
                {
                    "id": frontier_id,
                    "text": frontier_text,
                    "kind": kind,
                    "parent_id": parent_id,
                    "status": status,
                    "priority": priority,
                    "failure_count": failure_count,
                    "evidence": evidence or [],
                }
            ],
        )
        return frontier_id

    def upsert_frontier_nodes(self, *, campaign_id: str, nodes: list[dict[str, Any]]) -> list[str]:
        if not nodes:
            return []
        frontier_ids: list[str] = []
        node_records: list[NodeRecord] = []
        edge_records: list[EdgeRecord] = []
        for item in nodes:
            frontier_id = item.get("id") or make_id("F")
            parent_id = item.get("parent_id")
            frontier_text = item.get("text", "")
            frontier_ids.append(frontier_id)
            node_records.append(
                NodeRecord(
                    id=frontier_id,
                    campaign_id=campaign_id,
                    node_type="FrontierNode",
                    title=frontier_text[:80],
                    summary=frontier_text,
                    status=item.get("status", "open"),
                    payload={
                        "kind": item.get("kind", "claim"),
                        "parent_id": parent_id,
                        "priority": item.get("priority", 1.0),
                        "failure_count": item.get("failure_count", 0),
                        "evidence": item.get("evidence", []),
                    },
                )
            )
            edge_records.append(
                EdgeRecord(
                    id=make_id("E"),
                    campaign_id=campaign_id,
                    src_id=campaign_id,
                    edge_type="HAS_FRONTIER",
                    dst_id=frontier_id,
                )
            )
            if parent_id:
                edge_records.append(
                    EdgeRecord(
                        id=make_id("E"),
                        campaign_id=campaign_id,
                        src_id=parent_id,
                        edge_type="SPAWNS",
                        dst_id=frontier_id,
                    )
                )
        self.store.upsert_nodes(node_records)
        self.store.add_edges(edge_records)
        return frontier_ids

    def record_manager_decision(
        self, *, campaign_id: str, tick: int, decision: dict[str, Any]
    ) -> dict[str, Any]:
        candidate_answer_id = make_id("A")
        world_id = make_id("W")
        claim_id = make_id("C")

        candidate = decision.get("candidate_answer") or {}
        self.store.upsert_node(
            NodeRecord(
                id=candidate_answer_id,
                campaign_id=campaign_id,
                node_type="CandidateAnswer",
                title=candidate.get("summary", "Candidate answer"),
                summary=candidate.get("summary", ""),
                status="speculative",
                confidence=candidate.get("confidence"),
                payload=candidate,
            )
        )

        self.store.upsert_node(
            NodeRecord(
                id=world_id,
                campaign_id=campaign_id,
                node_type="WorldModel",
                title=decision.get("world_family", "world"),
                summary=decision.get("why_this_next", ""),
                status="speculative",
                payload={
                    "family": decision.get("world_family"),
                    "expected_information_gain": decision.get(
                        "expected_information_gain"
                    ),
                },
            )
        )

        self.store.upsert_node(
            NodeRecord(
                id=claim_id,
                campaign_id=campaign_id,
                node_type="Claim",
                title=decision.get("bounded_claim", "")[:120],
                summary=decision.get("bounded_claim", ""),
                status="speculative",
                payload={
                    "why_this_next": decision.get("why_this_next"),
                    "update_rules": decision.get("update_rules", {}),
                },
            )
        )

        self.store.add_edge(
            EdgeRecord(
                id=make_id("E"),
                campaign_id=campaign_id,
                src_id=campaign_id,
                edge_type="CURRENT_ANSWER",
                dst_id=candidate_answer_id,
            )
        )
        self.store.add_edge(
            EdgeRecord(
                id=make_id("E"),
                campaign_id=campaign_id,
                src_id=world_id,
                edge_type="PROPOSES_CLAIM",
                dst_id=claim_id,
            )
        )

        target_id = decision.get("target_frontier_node")
        if target_id:
            self.store.add_edge(
                EdgeRecord(
                    id=make_id("E"),
                    campaign_id=campaign_id,
                    src_id=claim_id,
                    edge_type="TARGETS_FRONTIER",
                    dst_id=target_id,
                )
            )

        obligations: list[dict[str, Any]] = []
        for obligation in decision.get("formal_obligations", []):
            obligation_text = _formal_obligation_text(obligation)
            obligation_payload = _formal_obligation_payload(obligation)
            obligation_id = make_id("O")
            obligations.append({"id": obligation_id, "text": obligation_text, "payload": obligation_payload})
            self.store.upsert_node(
                NodeRecord(
                    id=obligation_id,
                    campaign_id=campaign_id,
                    node_type="FormalObligation",
                    title=obligation_text[:120],
                    summary=obligation_text,
                    status="open",
                    payload=obligation_payload,
                )
            )
            self.store.add_edge(
                EdgeRecord(
                    id=make_id("E"),
                    campaign_id=campaign_id,
                    src_id=claim_id,
                    edge_type="GENERATES_OBLIGATION",
                    dst_id=obligation_id,
                )
            )

        self.store.add_artifact(
            ArtifactRecord(
                id=make_id("AR"),
                campaign_id=campaign_id,
                artifact_type="manager_decision",
                title=f"manager-decision-{tick}",
                content_text=json.dumps(decision),
                metadata={"tick": tick},
            )
        )

        self.add_event(
            campaign_id=campaign_id,
            tick=tick,
            event_type="manager_decision",
            payload={
                "candidate_answer_id": candidate_answer_id,
                "world_id": world_id,
                "claim_id": claim_id,
                "obligations": obligations,
                "world_family": decision.get("world_family"),
                "target_frontier_node": decision.get("target_frontier_node"),
                "bounded_claim": decision.get("bounded_claim"),
                "obligation_count": len(obligations),
                "why_this_next": decision.get("why_this_next"),
            },
        )
        return {
            "candidate_answer_id": candidate_answer_id,
            "world_id": world_id,
            "claim_id": claim_id,
            "obligations": obligations,
            "obligation_ids": [item["id"] for item in obligations],
        }

    def record_execution_result(
        self,
        *,
        campaign_id: str,
        tick: int,
        decision: dict[str, Any],
        result: dict[str, Any],
        raw_request: str | None = None,
        raw_response: str | None = None,
    ) -> str:
        result_id = make_id("R")
        status = result.get("status", "blocked")
        failure_type = result.get("failure_type")
        self.store.upsert_node(
            NodeRecord(
                id=result_id,
                campaign_id=campaign_id,
                node_type="ExecutionResult",
                title=status,
                summary=result.get("notes", ""),
                status=status,
                payload={
                    "failure_type": failure_type,
                    "executor_backend": result.get("executor_backend"),
                    "artifacts": result.get("artifacts", []),
                    "raw": result.get("raw", {}),
                },
            )
        )

        claim_title = decision.get("bounded_claim", "")
        claims = self.store.list_nodes(campaign_id, node_type="Claim", limit=100)
        matched_claim = next((c for c in claims if c.summary == claim_title), None)
        if matched_claim:
            edge_type = (
                "SUPPORTS"
                if status == "proved"
                else "REFUTES"
                if status == "refuted"
                else "BLOCKS"
            )
            self.store.add_edge(
                EdgeRecord(
                    id=make_id("E"),
                    campaign_id=campaign_id,
                    src_id=result_id,
                    edge_type=edge_type,
                    dst_id=matched_claim.id,
                    payload={"failure_type": failure_type},
                )
            )

        for artifact_text in result.get("artifacts", []):
            self.store.add_artifact(
                ArtifactRecord(
                    id=make_id("AR"),
                    campaign_id=campaign_id,
                    artifact_type="execution_result",
                    title=f"execution-result-{tick}",
                    content_text=artifact_text,
                    metadata={"tick": tick, "status": status},
                )
            )

        if raw_request:
            self.store.add_artifact(
                ArtifactRecord(
                    id=make_id("AR"),
                    campaign_id=campaign_id,
                    artifact_type="aristotle_request",
                    title=f"aristotle-request-{tick}",
                    content_text=raw_request,
                    metadata={"tick": tick},
                )
            )
        if raw_response:
            self.store.add_artifact(
                ArtifactRecord(
                    id=make_id("AR"),
                    campaign_id=campaign_id,
                    artifact_type="aristotle_response",
                    title=f"aristotle-response-{tick}",
                    content_text=raw_response,
                    metadata={"tick": tick},
                )
            )

        for spawned_node in result.get("spawned_nodes", []):
            child_id = self.seed_frontier(
                campaign_id=campaign_id,
                frontier_text=spawned_node.get("text", "Spawned frontier"),
                kind=spawned_node.get("kind", "exploration"),
                parent_id=spawned_node.get("parent_id")
                or decision.get("target_frontier_node"),
                frontier_id=spawned_node.get("id"),
                status=spawned_node.get("status", "open"),
                priority=spawned_node.get("priority", 1.0),
                failure_count=spawned_node.get("failure_count", 0),
                evidence=spawned_node.get("evidence", []),
            )
            self.store.add_edge(
                EdgeRecord(
                    id=make_id("E"),
                    campaign_id=campaign_id,
                    src_id=result_id,
                    edge_type="SPAWNS",
                    dst_id=child_id,
                )
            )

        self.add_event(
            campaign_id=campaign_id,
            tick=tick,
            event_type="execution_result",
            payload={
                "result_id": result_id,
                "status": status,
                "failure_type": failure_type,
                "notes": result.get("notes", ""),
                "executor_backend": result.get("executor_backend"),
                "channel_used": result.get("channel_used", "none"),
                "timing_ms": result.get("timing_ms"),
                "approved_jobs_count": result.get("approved_jobs_count", 0),
                "rejected_jobs_count": result.get("rejected_jobs_count", 0),
                "spawned_nodes_count": len(result.get("spawned_nodes", [])),
            },
        )
        return result_id

    def add_event(
        self,
        *,
        campaign_id: str,
        tick: int,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        self.store.add_event(
            EventRecord(
                id=make_id("EV"),
                campaign_id=campaign_id,
                tick=tick,
                event_type=event_type,
                payload=payload,
            )
        )

    def list_events(self, campaign_id: str, *, limit: int = 100) -> list[EventRecord]:
        return self.store.list_events(campaign_id, limit=limit)

    def save_policy_snapshot(
        self,
        policy: dict[str, Any],
        patch: dict[str, Any] | None = None,
        reason: str | None = None,
    ) -> None:
        self.store.add_policy_snapshot(
            PolicySnapshotRecord(
                id=make_id("PS"),
                version=policy.get("version", "unknown"),
                policy_json=json.dumps(policy),
                patch_json=json.dumps(patch or {}),
                reason=reason,
                created_at=_utc_now_iso(),
            )
        )

    def get_latest_policy(self) -> dict[str, Any] | None:
        snapshots = self.store.list_policy_snapshots(limit=50)
        for snapshot in snapshots:
            try:
                return json.loads(snapshot.policy_json or "{}")
            except json.JSONDecodeError:
                continue
        return None

    def list_policy_history(self, limit: int = 20) -> list[dict[str, Any]]:
        notes = self.store.list_policy_snapshots(limit=max(limit * 2, 20))
        history: list[dict[str, Any]] = []
        for note in notes:
            history.append(
                {
                    "version": note.version,
                    "policy_json": note.policy_json,
                    "patch_json": note.patch_json,
                    "reason": note.reason,
                    "created_at": note.created_at,
                }
            )
            if len(history) >= limit:
                break
        return history

    def ingest_paper_unit(
        self,
        *,
        campaign_id: str,
        paper_title: str,
        unit_type: str,
        title: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        metadata = metadata or {}
        paper_id = metadata.get("paper_id") or make_id("PAPER")
        existing = self.store.get_node(campaign_id, paper_id)
        if not existing:
            self.store.upsert_node(
                NodeRecord(
                    id=paper_id,
                    campaign_id=campaign_id,
                    node_type="Paper",
                    title=paper_title,
                    summary=paper_title,
                    status="supported",
                    payload={"metadata": metadata},
                )
            )

        unit_id = make_id("UNIT")
        self.store.upsert_node(
            NodeRecord(
                id=unit_id,
                campaign_id=campaign_id,
                node_type="PaperUnit",
                title=title,
                summary=text[:500],
                status="supported",
                payload={"unit_type": unit_type, "metadata": metadata, "full_text": text},
            )
        )
        self.store.add_edge(
            EdgeRecord(
                id=make_id("E"),
                campaign_id=campaign_id,
                src_id=unit_id,
                edge_type="DERIVED_FROM_PAPER",
                dst_id=paper_id,
            )
        )
        self.store.add_artifact(
            ArtifactRecord(
                id=make_id("AR"),
                campaign_id=campaign_id,
                artifact_type="paper_unit",
                title=title,
                content_text=text,
                metadata={"unit_type": unit_type, **metadata},
            )
        )
        return {"paper_id": paper_id, "paper_unit_id": unit_id}

    def get_manager_packet(self, *, campaign_id: str, limit: int = 100) -> ManagerPacket:
        campaign = self.store.list_nodes(campaign_id, node_type="Campaign", limit=1)
        problem = self.store.list_nodes(campaign_id, node_type="Problem", limit=1)
        answers = self.store.list_nodes(campaign_id, node_type="CandidateAnswer", limit=1)
        frontier_all = self.store.list_nodes(campaign_id, node_type="FrontierNode", limit=500)
        frontier = frontier_all[:limit]
        worlds = self.store.list_nodes(campaign_id, node_type="WorldModel", limit=limit)
        claims = self.store.list_nodes(campaign_id, node_type="Claim", limit=limit)
        results = self.store.list_nodes(campaign_id, node_type="ExecutionResult", limit=limit)
        blockers = self.store.list_nodes(campaign_id, node_type="Blocker", limit=limit)
        paper_units = self.store.list_nodes(campaign_id, node_type="PaperUnit", limit=limit)
        patterns = self.store.list_nodes(campaign_id, node_type="Pattern", limit=limit)

        operator_notes = []
        if campaign:
            operator_notes = campaign[0].payload.get("operator_notes", [])

        return ManagerPacket(
            campaign=campaign[0].asdict() if campaign else {},
            problem=problem[0].asdict() if problem else {},
            current_candidate_answer=answers[0].asdict() if answers else None,
            active_frontier=[node.asdict() for node in frontier],
            relevant_worlds=[node.asdict() for node in worlds],
            recent_claims=[node.asdict() for node in claims],
            recent_results=[node.asdict() for node in results],
            blockers=[node.asdict() for node in blockers],
            paper_units=[node.asdict() for node in paper_units],
            patterns=[node.asdict() for node in patterns],
            operator_notes=operator_notes,
        )

    def project_campaign_summary(self, campaign_id: str) -> dict[str, Any]:
        return project_campaign_summary(self.store, campaign_id)
