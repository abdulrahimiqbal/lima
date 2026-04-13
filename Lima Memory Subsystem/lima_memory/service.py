from __future__ import annotations

from typing import Any

from .models import (
    ArtifactRecord,
    EdgeRecord,
    EventRecord,
    ManagerPacket,
    NodeRecord,
    make_id,
)
from .projection import project_campaign_summary
from .store import KnowledgeStore

class MemoryService:
    """Independent knowledge/memory layer for LIMA.

    This stores canonical research state as:
    - events
    - graph nodes / edges
    - artifacts
    """

    def __init__(self, store: KnowledgeStore) -> None:
        self.store = store
        self.store.init()

    def create_campaign(self, *, campaign_id: str, title: str, problem_statement: str, operator_notes: list[str] | None = None) -> dict[str, str]:
        operator_notes = operator_notes or []
        campaign_node = NodeRecord(
            id=campaign_id,
            campaign_id=campaign_id,
            node_type="Campaign",
            title=title,
            summary="LIMA campaign root",
            status="active",
            payload={"operator_notes": operator_notes},
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
        self.store.add_edge(EdgeRecord(
            id=make_id("E"),
            campaign_id=campaign_id,
            src_id=campaign_id,
            edge_type="HAS_PROBLEM",
            dst_id=problem_id,
        ))
        self.store.add_event(EventRecord(
            id=make_id("EV"),
            campaign_id=campaign_id,
            tick=0,
            event_type="campaign_created",
            payload={"title": title, "problem_statement": problem_statement},
        ))
        return {"campaign_id": campaign_id, "problem_id": problem_id}

    def seed_frontier(self, *, campaign_id: str, frontier_text: str, kind: str = "claim", parent_id: str | None = None) -> str:
        frontier_id = make_id("F")
        node = NodeRecord(
            id=frontier_id,
            campaign_id=campaign_id,
            node_type="FrontierNode",
            title=frontier_text[:80],
            summary=frontier_text,
            status="open",
            payload={"kind": kind, "parent_id": parent_id},
        )
        self.store.upsert_node(node)
        self.store.add_edge(EdgeRecord(
            id=make_id("E"),
            campaign_id=campaign_id,
            src_id=campaign_id,
            edge_type="HAS_FRONTIER",
            dst_id=frontier_id,
        ))
        if parent_id:
            self.store.add_edge(EdgeRecord(
                id=make_id("E"),
                campaign_id=campaign_id,
                src_id=parent_id,
                edge_type="SPAWNS",
                dst_id=frontier_id,
            ))
        return frontier_id

    def record_manager_decision(self, *, campaign_id: str, tick: int, decision: dict[str, Any]) -> dict[str, str]:
        candidate_answer_id = make_id("A")
        world_id = make_id("W")
        claim_id = make_id("C")

        candidate = decision.get("candidate_answer") or {}
        self.store.upsert_node(NodeRecord(
            id=candidate_answer_id,
            campaign_id=campaign_id,
            node_type="CandidateAnswer",
            title=candidate.get("summary", "Candidate answer"),
            summary=candidate.get("summary", ""),
            status="speculative",
            confidence=candidate.get("confidence"),
            payload=candidate,
        ))

        self.store.upsert_node(NodeRecord(
            id=world_id,
            campaign_id=campaign_id,
            node_type="WorldModel",
            title=decision.get("world_family", "world"),
            summary=decision.get("why_this_next", ""),
            status="speculative",
            payload={
                "family": decision.get("world_family"),
                "expected_information_gain": decision.get("expected_information_gain"),
            },
        ))

        self.store.upsert_node(NodeRecord(
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
        ))

        self.store.add_edge(EdgeRecord(
            id=make_id("E"),
            campaign_id=campaign_id,
            src_id=campaign_id,
            edge_type="CURRENT_ANSWER",
            dst_id=candidate_answer_id,
        ))
        self.store.add_edge(EdgeRecord(
            id=make_id("E"),
            campaign_id=campaign_id,
            src_id=world_id,
            edge_type="PROPOSES_CLAIM",
            dst_id=claim_id,
        ))

        target_id = decision.get("target_frontier_node")
        if target_id:
            self.store.add_edge(EdgeRecord(
                id=make_id("E"),
                campaign_id=campaign_id,
                src_id=claim_id,
                edge_type="TARGETS_FRONTIER",
                dst_id=target_id,
            ))

        obligation_ids: list[str] = []
        for obligation in decision.get("formal_obligations", []):
            obligation_id = make_id("O")
            obligation_ids.append(obligation_id)
            self.store.upsert_node(NodeRecord(
                id=obligation_id,
                campaign_id=campaign_id,
                node_type="FormalObligation",
                title=obligation[:120],
                summary=obligation,
                status="open",
                payload={},
            ))
            self.store.add_edge(EdgeRecord(
                id=make_id("E"),
                campaign_id=campaign_id,
                src_id=claim_id,
                edge_type="GENERATES_OBLIGATION",
                dst_id=obligation_id,
            ))

        self.store.add_artifact(ArtifactRecord(
            id=make_id("AR"),
            campaign_id=campaign_id,
            artifact_type="manager_decision",
            title=f"manager-decision-{tick}",
            content_text=str(decision),
            metadata={"tick": tick},
        ))
        self.store.add_event(EventRecord(
            id=make_id("EV"),
            campaign_id=campaign_id,
            tick=tick,
            event_type="manager_decision_recorded",
            payload={
                "candidate_answer_id": candidate_answer_id,
                "world_id": world_id,
                "claim_id": claim_id,
                "obligation_ids": obligation_ids,
            },
        ))
        return {
            "candidate_answer_id": candidate_answer_id,
            "world_id": world_id,
            "claim_id": claim_id,
            "obligation_ids": obligation_ids,
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
        self.store.upsert_node(NodeRecord(
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
        ))

        claim_title = decision.get("bounded_claim", "")
        claims = self.store.list_nodes(campaign_id, node_type="Claim", limit=50)
        matched_claim = next((c for c in claims if c.summary == claim_title), None)
        if matched_claim:
            edge_type = "SUPPORTS" if status == "proved" else "REFUTES" if status == "refuted" else "BLOCKS"
            self.store.add_edge(EdgeRecord(
                id=make_id("E"),
                campaign_id=campaign_id,
                src_id=result_id,
                edge_type=edge_type,
                dst_id=matched_claim.id,
                payload={"failure_type": failure_type},
            ))

        for artifact_text in result.get("artifacts", []):
            self.store.add_artifact(ArtifactRecord(
                id=make_id("AR"),
                campaign_id=campaign_id,
                artifact_type="execution_result",
                title=f"execution-result-{tick}",
                content_text=artifact_text,
                metadata={"tick": tick, "status": status},
            ))

        if raw_request:
            self.store.add_artifact(ArtifactRecord(
                id=make_id("AR"),
                campaign_id=campaign_id,
                artifact_type="aristotle_request",
                title=f"aristotle-request-{tick}",
                content_text=raw_request,
                metadata={"tick": tick},
            ))
        if raw_response:
            self.store.add_artifact(ArtifactRecord(
                id=make_id("AR"),
                campaign_id=campaign_id,
                artifact_type="aristotle_response",
                title=f"aristotle-response-{tick}",
                content_text=raw_response,
                metadata={"tick": tick},
            ))

        spawned = result.get("spawned_nodes", [])
        for spawned_node in spawned:
            child_id = self.seed_frontier(
                campaign_id=campaign_id,
                frontier_text=spawned_node.get("text", "Spawned frontier"),
                kind=spawned_node.get("kind", "exploration"),
                parent_id=decision.get("target_frontier_node"),
            )
            self.store.add_edge(EdgeRecord(
                id=make_id("E"),
                campaign_id=campaign_id,
                src_id=result_id,
                edge_type="SPAWNS",
                dst_id=child_id,
            ))

        self.store.add_event(EventRecord(
            id=make_id("EV"),
            campaign_id=campaign_id,
            tick=tick,
            event_type="execution_result_recorded",
            payload={"result_id": result_id, "status": status, "failure_type": failure_type},
        ))
        return result_id

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
            self.store.upsert_node(NodeRecord(
                id=paper_id,
                campaign_id=campaign_id,
                node_type="Paper",
                title=paper_title,
                summary=paper_title,
                status="supported",
                payload={"metadata": metadata},
            ))

        unit_id = make_id("UNIT")
        self.store.upsert_node(NodeRecord(
            id=unit_id,
            campaign_id=campaign_id,
            node_type="PaperUnit",
            title=title,
            summary=text[:500],
            status="supported",
            payload={"unit_type": unit_type, "metadata": metadata, "full_text": text},
        ))
        self.store.add_edge(EdgeRecord(
            id=make_id("E"),
            campaign_id=campaign_id,
            src_id=unit_id,
            edge_type="DERIVED_FROM_PAPER",
            dst_id=paper_id,
        ))
        self.store.add_artifact(ArtifactRecord(
            id=make_id("AR"),
            campaign_id=campaign_id,
            artifact_type="paper_unit",
            title=title,
            content_text=text,
            metadata={"unit_type": unit_type, **metadata},
        ))
        return {"paper_id": paper_id, "paper_unit_id": unit_id}

    def get_manager_packet(self, *, campaign_id: str, limit: int = 5) -> ManagerPacket:
        campaign = self.store.list_nodes(campaign_id, node_type="Campaign", limit=1)
        problem = self.store.list_nodes(campaign_id, node_type="Problem", limit=1)
        answers = self.store.list_nodes(campaign_id, node_type="CandidateAnswer", limit=1)
        frontier = self.store.list_nodes(campaign_id, node_type="FrontierNode", limit=limit)
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
