from __future__ import annotations

from datetime import datetime
import logging
from uuid import uuid4

from lima_memory import MemoryService, PostgresKnowledgeStore, SqliteKnowledgeStore

from .config import Settings
from .executor import Executor
from .frontier import apply_execution_result, seed_frontier
from .learner import update_memory
from .manager import Manager, get_policy
from .obligation_analysis import build_execution_plan
from .schemas import (
    CampaignCreate,
    CampaignRecord,
    CampaignUpdateNotes,
    CandidateAnswer,
    EventRecord,
    ExecutionResult,
    FrontierNode,
    ManagerContext,
    MemoryState,
)
from .self_improvement import SelfImprovementService

logger = logging.getLogger(__name__)


def _parse_dt(value: str) -> datetime:
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value)


class CampaignService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.manager = Manager(settings)
        self.executor = Executor(settings)
        if settings.memory_database_url:
            self.memory_store = PostgresKnowledgeStore(settings.memory_database_url)
        else:
            self.memory_store = SqliteKnowledgeStore(settings.memory_db_path)
        self.memory = MemoryService(self.memory_store)
        logger.info(
            "CampaignService initialized with memory backend=%s",
            "postgres" if settings.memory_database_url else "sqlite",
        )
        self.manager.policy_provider = self.memory.get_latest_policy
        self.self_improvement = SelfImprovementService(self.memory, settings)

    def create_campaign(self, payload: CampaignCreate) -> CampaignRecord:
        campaign_id = f"C-{uuid4().hex[:12]}"
        frontier = seed_frontier(payload.problem_statement)

        self.memory.create_campaign(
            campaign_id=campaign_id,
            title=payload.title,
            problem_statement=payload.problem_statement,
            operator_notes=payload.operator_notes,
        )
        for node in frontier:
            self.memory.seed_frontier(
                campaign_id=campaign_id,
                frontier_id=node.id,
                frontier_text=node.text,
                kind=node.kind,
                parent_id=node.parent_id,
                status=node.status,
                priority=node.priority,
                failure_count=node.failure_count,
                evidence=node.evidence,
            )
        self.memory.update_campaign_payload(
            campaign_id,
            status="running",
            payload_updates={
                "auto_run": payload.auto_run,
                "tick_count": 0,
                "memory": MemoryState().model_dump(),
                "manager_backend": self.settings.manager_backend_resolved,
                "executor_backend": self.settings.executor_backend,
                "current_candidate_answer": None,
                "last_manager_context": None,
                "last_manager_decision": None,
                "last_execution_result": None,
                "operator_notes": payload.operator_notes,
            },
        )
        return self.get_campaign(campaign_id)

    def list_campaigns(self) -> list[CampaignRecord]:
        nodes = self.memory.list_campaign_nodes(limit=200)
        return [self._campaign_from_memory(node.id) for node in nodes]

    def get_campaign(self, campaign_id: str) -> CampaignRecord:
        return self._campaign_from_memory(campaign_id)

    def update_notes(self, campaign_id: str, payload: CampaignUpdateNotes) -> CampaignRecord:
        campaign = self.get_campaign(campaign_id)
        campaign.operator_notes = payload.operator_notes
        self._persist_campaign(campaign)
        self.memory.add_event(
            campaign_id=campaign_id,
            tick=campaign.tick_count,
            event_type="operator_notes_updated",
            payload={"operator_notes": payload.operator_notes},
        )
        return self.get_campaign(campaign_id)

    def pause_campaign(self, campaign_id: str) -> CampaignRecord:
        campaign = self.get_campaign(campaign_id)
        campaign.status = "paused"
        campaign.auto_run = False
        self._persist_campaign(campaign)
        self.memory.add_event(
            campaign_id=campaign_id, tick=campaign.tick_count, event_type="campaign_paused", payload={}
        )
        return self.get_campaign(campaign_id)

    def resume_campaign(self, campaign_id: str) -> CampaignRecord:
        campaign = self.get_campaign(campaign_id)
        if campaign.status not in {"solved", "failed"}:
            campaign.status = "running"
            campaign.auto_run = True
        self._persist_campaign(campaign)
        self.memory.add_event(
            campaign_id=campaign_id, tick=campaign.tick_count, event_type="campaign_resumed", payload={}
        )
        return self.get_campaign(campaign_id)

    def build_manager_context(self, campaign_id: str) -> ManagerContext:
        _ = self.get_campaign(campaign_id)
        return self._build_context_from_memory(campaign_id)

    def step_campaign(self, campaign_id: str) -> CampaignRecord:
        campaign = self.get_campaign(campaign_id)
        if campaign.status in {"solved", "failed", "paused"}:
            return campaign

        context = self._build_context_from_memory(campaign_id)
        decision = self.manager.decide(context)
        tick = campaign.tick_count + 1
        self.memory.record_manager_decision(
            campaign_id=campaign.id,
            tick=tick,
            decision=decision.model_dump(),
        )

        active_policy = self.memory.get_latest_policy() or get_policy()
        plan = build_execution_plan(decision, policy=active_policy, memory=campaign.memory)
        self.memory.add_event(
            campaign_id=campaign_id,
            tick=tick,
            event_type="obligation_analysis",
            payload=plan.model_dump(),
        )

        if not plan.approved_proof_jobs and not plan.approved_evidence_jobs:
            failure = "excessive_scope"
            if any(reason == "mixed_channels" for reason in plan.rejected_reasons.values()):
                failure = "mixed_channels"
            result = ExecutionResult(
                status="blocked",
                failure_type=failure,
                notes="Submission gate rejected all obligations. Shrink claim or split channels.",
                executor_backend="gate",
                original_obligations=plan.original_obligations,
                analyzed_obligations=[a.model_dump() for a in plan.analyzed_obligations],
                approved_proof_jobs=[],
                approved_evidence_jobs=[],
                rejected_obligations=plan.rejected_obligations,
                approved_jobs_count=0,
                rejected_jobs_count=len(plan.rejected_obligations),
                channel_used="none",
                raw={"rejected_reasons": plan.rejected_reasons},
            )
        else:
            result = self.executor.run(campaign, decision, plan)

        updated = campaign.model_copy(deep=True)
        updated.tick_count = tick
        updated.last_manager_context = context.model_dump()
        updated.last_manager_decision = decision.model_dump()
        updated.last_execution_result = result.model_dump()
        updated.manager_backend = decision.manager_backend
        updated.executor_backend = result.executor_backend
        updated.current_candidate_answer = decision.candidate_answer
        updated = update_memory(updated, decision, result, policy=active_policy)
        updated = apply_execution_result(updated, decision, result)

        raw_payload = result.raw if isinstance(result.raw, dict) else {}
        self.memory.record_execution_result(
            campaign_id=campaign.id,
            tick=tick,
            decision=decision.model_dump(),
            result=updated.last_execution_result or result.model_dump(),
            raw_request=raw_payload.get("aristotle_request"),
            raw_response=raw_payload.get("aristotle_response"),
        )
        self._persist_campaign(updated)
        return self.get_campaign(campaign_id)

    def auto_step_once(self) -> None:
        campaigns = self.list_campaigns()
        stepped = 0
        for campaign in campaigns:
            if stepped >= self.settings.auto_step_limit_per_tick:
                break
            if campaign.auto_run and campaign.status == "running":
                self.step_campaign(campaign.id)
                stepped += 1

    def list_events(self, campaign_id: str, limit: int = 50) -> list[EventRecord]:
        _ = self.get_campaign(campaign_id)
        events = self.memory.list_events(campaign_id, limit=limit)
        results: list[EventRecord] = []
        for idx, event in enumerate(events, start=1):
            results.append(
                EventRecord(
                    id=idx,
                    campaign_id=event.campaign_id,
                    tick=event.tick,
                    kind=event.event_type,
                    payload=event.payload,
                    created_at=_parse_dt(event.created_at),
                )
            )
        return results

    def interfaces(self):
        return self.manager.describe_interfaces()

    def get_memory_summary(self, campaign_id: str) -> dict:
        _ = self.get_campaign(campaign_id)
        return self.memory.project_campaign_summary(campaign_id)

    def get_memory_packet(self, campaign_id: str) -> dict:
        _ = self.get_campaign(campaign_id)
        return self.memory.get_manager_packet(campaign_id=campaign_id, limit=50).asdict()

    def system_status(self) -> dict:
        return {
            "app_name": self.settings.app_name,
            "environment": self.settings.environment,
            "manager": {
                "backend": self.settings.manager_backend_resolved,
                "model": self.settings.llm_model,
            },
            "executor": {
                "backend": self.settings.executor_backend,
                "aristotle_url": self.settings.aristotle_base_url,
                "connectivity": self.executor.check_connectivity(strict_live_probe=False),
            },
            "submission_gate": {
                "enabled": True,
                "max_proof_jobs_per_step": 1,
            },
            "self_improvement": {
                "enabled": self.settings.enable_self_improvement,
            },
            "database": "ok",
        }

    def smoke_aristotle(self, *, strict_live_probe: bool = False) -> dict:
        return self.executor.check_connectivity(strict_live_probe=strict_live_probe)

    def run_self_improvement(self) -> dict:
        return self.self_improvement.run_cycle()

    def ping_store(self) -> None:
        _ = self.memory.list_campaign_nodes(limit=1)

    def _build_context_from_memory(self, campaign_id: str) -> ManagerContext:
        campaign = self.get_campaign(campaign_id)
        packet = self.memory.get_manager_packet(campaign_id=campaign.id, limit=100)

        frontier_nodes = []
        for item in packet.active_frontier:
            payload = item.get("payload") or {}
            frontier_nodes.append(
                {
                    "id": item["id"],
                    "text": item.get("summary") or item.get("title", ""),
                    "status": item.get("status", "open"),
                    "priority": payload.get("priority", 1.0),
                    "parent_id": payload.get("parent_id"),
                    "kind": payload.get("kind", "claim"),
                    "failure_count": payload.get("failure_count", 0),
                    "evidence": payload.get("evidence", []),
                }
            )

        problem_payload = {
            "id": campaign.id,
            "title": campaign.title,
            "statement": campaign.problem_statement,
        }
        if packet.current_candidate_answer:
            problem_payload["current_candidate_answer"] = packet.current_candidate_answer

        return ManagerContext(
            problem=problem_payload,
            frontier=frontier_nodes or [node.model_dump() for node in campaign.frontier],
            memory=campaign.memory,
            operator_notes=packet.operator_notes or campaign.operator_notes,
            allowed_world_families=[
                "direct",
                "bridge",
                "reformulate",
                "finite_check",
                "counterexample",
                "local_to_global",
                "invariant_lift",
                "structural_case_split",
            ],
            tick=campaign.tick_count,
        )

    def _campaign_from_memory(self, campaign_id: str) -> CampaignRecord:
        packet = self.memory.get_manager_packet(campaign_id=campaign_id, limit=500)
        if not packet.campaign:
            raise KeyError(f"Campaign not found: {campaign_id}")
        campaign_node = packet.campaign
        payload = campaign_node.get("payload") or {}
        problem_payload = packet.problem.get("payload") if packet.problem else {}
        problem_statement = payload.get("problem_statement") or problem_payload.get("statement") or ""

        frontier_nodes: list[FrontierNode] = []
        frontier = self.memory.list_frontier_nodes(campaign_id, limit=500)
        for node in frontier:
            fp = node.payload or {}
            frontier_nodes.append(
                FrontierNode(
                    id=node.id,
                    text=node.summary or node.title,
                    status=node.status,
                    priority=float(fp.get("priority", 1.0)),
                    parent_id=fp.get("parent_id"),
                    kind=fp.get("kind", "claim"),
                    failure_count=int(fp.get("failure_count", 0)),
                    evidence=list(fp.get("evidence", [])),
                )
            )
        frontier_nodes.sort(key=lambda item: (item.parent_id is not None, -item.priority, item.id))
        logger.debug(
            "Loaded campaign=%s frontier_nodes=%d status_raw=%s",
            campaign_id,
            len(frontier_nodes),
            payload.get("status", campaign_node.get("status")),
        )

        memory_state = MemoryState.model_validate(payload.get("memory") or MemoryState().model_dump())
        candidate_answer_payload = payload.get("current_candidate_answer")
        candidate_answer = (
            CandidateAnswer.model_validate(candidate_answer_payload)
            if candidate_answer_payload
            else None
        )

        status_raw = payload.get("status", campaign_node.get("status", "running"))
        status_normalized = "running" if status_raw == "active" else status_raw
        return CampaignRecord(
            id=campaign_node["id"],
            title=campaign_node.get("title", ""),
            problem_statement=problem_statement,
            status=status_normalized,
            auto_run=bool(payload.get("auto_run", True)),
            operator_notes=payload.get("operator_notes", []),
            frontier=frontier_nodes,
            memory=memory_state,
            current_candidate_answer=candidate_answer,
            tick_count=int(payload.get("tick_count", 0)),
            created_at=_parse_dt(campaign_node["created_at"]),
            updated_at=_parse_dt(campaign_node["updated_at"]),
            last_manager_context=payload.get("last_manager_context"),
            last_manager_decision=payload.get("last_manager_decision"),
            last_execution_result=payload.get("last_execution_result"),
            manager_backend=payload.get("manager_backend", self.settings.manager_backend_resolved),
            executor_backend=payload.get("executor_backend", self.settings.executor_backend),
        )

    def _persist_campaign(self, campaign: CampaignRecord) -> None:
        self.memory.update_campaign_payload(
            campaign.id,
            title=campaign.title,
            status=campaign.status,
            payload_updates={
                "problem_statement": campaign.problem_statement,
                "operator_notes": campaign.operator_notes,
                "auto_run": campaign.auto_run,
                "tick_count": campaign.tick_count,
                "memory": campaign.memory.model_dump(),
                "current_candidate_answer": campaign.current_candidate_answer.model_dump()
                if campaign.current_candidate_answer
                else None,
                "last_manager_context": campaign.last_manager_context,
                "last_manager_decision": campaign.last_manager_decision,
                "last_execution_result": campaign.last_execution_result,
                "manager_backend": campaign.manager_backend,
                "executor_backend": campaign.executor_backend,
                "status": campaign.status,
            },
        )
        for node in campaign.frontier:
            self.memory.upsert_frontier_node(
                campaign_id=campaign.id,
                frontier_id=node.id,
                frontier_text=node.text,
                kind=node.kind,
                parent_id=node.parent_id,
                status=node.status,
                priority=node.priority,
                failure_count=node.failure_count,
                evidence=node.evidence,
            )
        logger.debug(
            "Persisted campaign=%s frontier_nodes=%d tick=%d",
            campaign.id,
            len(campaign.frontier),
            campaign.tick_count,
        )
