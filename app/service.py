from __future__ import annotations

from typing import Any

from lima_memory import MemoryService, PostgresKnowledgeStore, SqliteKnowledgeStore

from .obligation_analysis import build_execution_plan
from .config import Settings
from .db import Database
from .executor import Executor
from .frontier import apply_execution_result, seed_frontier
from .learner import update_memory
from .manager import Manager, get_policy
from .schemas import (
    CampaignCreate,
    CampaignRecord,
    CampaignUpdateNotes,
    ExecutionResult,
    ManagerContext,
    MemoryState,
)
from .self_improvement import SelfImprovementService


class CampaignService:
    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.manager = Manager(settings)
        self.executor = Executor(settings)
        self.self_improvement = SelfImprovementService(db, settings)
        if settings.memory_database_url:
            self.memory_store = PostgresKnowledgeStore(settings.memory_database_url)
        else:
            self.memory_store = SqliteKnowledgeStore(settings.memory_db_path)
        self.memory = MemoryService(self.memory_store)

    def create_campaign(self, payload: CampaignCreate) -> CampaignRecord:
        campaign = self.db.create_campaign(
            title=payload.title,
            problem_statement=payload.problem_statement,
            operator_notes=payload.operator_notes,
            auto_run=payload.auto_run,
            frontier=seed_frontier(payload.problem_statement),
            memory=MemoryState(),
            manager_backend=self.settings.manager_backend_resolved,
            executor_backend=self.settings.executor_backend,
        )
        self.memory.create_campaign(
            campaign_id=campaign.id,
            title=campaign.title,
            problem_statement=campaign.problem_statement,
            operator_notes=campaign.operator_notes,
        )
        for frontier_node in campaign.frontier:
            self.memory.seed_frontier(
                campaign_id=campaign.id,
                frontier_text=frontier_node.text,
                kind=frontier_node.kind,
                parent_id=frontier_node.parent_id,
            )
        return campaign

    def list_campaigns(self) -> list[CampaignRecord]:
        return self.db.list_campaigns()

    def get_campaign(self, campaign_id: str) -> CampaignRecord:
        return self.db.get_campaign(campaign_id)

    def update_notes(self, campaign_id: str, payload: CampaignUpdateNotes) -> CampaignRecord:
        campaign = self.db.get_campaign(campaign_id)
        campaign.operator_notes = payload.operator_notes
        updated = self.db.update_campaign(campaign)
        self.db.add_event(
            campaign_id=campaign_id,
            tick=updated.tick_count,
            kind="operator_notes_updated",
            payload={"operator_notes": payload.operator_notes},
        )
        return updated

    def pause_campaign(self, campaign_id: str) -> CampaignRecord:
        campaign = self.db.get_campaign(campaign_id)
        campaign.status = "paused"
        campaign.auto_run = False
        updated = self.db.update_campaign(campaign)
        self.db.add_event(campaign_id=campaign_id, tick=updated.tick_count, kind="campaign_paused", payload={})
        return updated

    def resume_campaign(self, campaign_id: str) -> CampaignRecord:
        campaign = self.db.get_campaign(campaign_id)
        if campaign.status not in {"solved", "failed"}:
            campaign.status = "running"
            campaign.auto_run = True
        updated = self.db.update_campaign(campaign)
        self.db.add_event(campaign_id=campaign_id, tick=updated.tick_count, kind="campaign_resumed", payload={})
        return updated

    def build_manager_context(self, campaign_id: str) -> ManagerContext:
        campaign = self.db.get_campaign(campaign_id)
        if self.settings.use_memory_context:
            return self._build_context_from_memory(campaign)
        return self._build_context(campaign)

    def step_campaign(self, campaign_id: str) -> CampaignRecord:
        campaign = self.db.get_campaign(campaign_id)
        if campaign.status in {"solved", "failed", "paused"}:
            return campaign

        if self.settings.use_memory_context:
            context = self._build_context_from_memory(campaign)
        else:
            context = self._build_context(campaign)
        decision = self.manager.decide(context)
        tick = campaign.tick_count + 1
        self.memory.record_manager_decision(
            campaign_id=campaign.id,
            tick=tick,
            decision=decision.model_dump(),
        )

        # Get latest policy for learning
        active_policy = self.db.get_latest_policy() or get_policy()
        plan = build_execution_plan(decision, policy=active_policy, memory=campaign.memory)

        self.db.add_event(
            campaign_id=campaign_id,
            tick=tick,
            kind="obligation_analysis",
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
        raw_payload = result.raw if isinstance(result.raw, dict) else {}
        self.memory.record_execution_result(
            campaign_id=campaign.id,
            tick=tick,
            decision=decision.model_dump(),
            result=result.model_dump(),
            raw_request=raw_payload.get("aristotle_request"),
            raw_response=raw_payload.get("aristotle_response"),
        )

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

        saved = self.db.update_campaign(updated)
        self.db.add_event(
            campaign_id=campaign_id,
            tick=saved.tick_count,
            kind="manager_decision",
            payload=decision.model_dump(),
        )
        self.db.add_event(
            campaign_id=campaign_id,
            tick=saved.tick_count,
            kind="execution_result",
            payload=result.model_dump(),
        )
        return saved

    def auto_step_once(self) -> None:
        campaigns = self.db.list_campaigns()
        stepped = 0
        for campaign in campaigns:
            if stepped >= self.settings.auto_step_limit_per_tick:
                break
            if campaign.auto_run and campaign.status == "running":
                self.step_campaign(campaign.id)
                stepped += 1

    def list_events(self, campaign_id: str, limit: int = 50):
        return self.db.list_events(campaign_id, limit=limit)

    def interfaces(self):
        return self.manager.describe_interfaces()

    def get_memory_summary(self, campaign_id: str) -> dict[str, Any]:
        _ = self.db.get_campaign(campaign_id)
        return self.memory.project_campaign_summary(campaign_id)

    def get_memory_packet(self, campaign_id: str) -> dict[str, Any]:
        _ = self.db.get_campaign(campaign_id)
        return self.memory.get_manager_packet(campaign_id=campaign_id).asdict()

    def system_status(self) -> dict[str, Any]:
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
                "connectivity": self.executor.check_connectivity(),
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

    def smoke_aristotle(self) -> dict[str, Any]:
        return self.executor.check_connectivity()

    def run_self_improvement(self) -> dict[str, Any]:
        return self.self_improvement.run_cycle()

    def _build_context(self, campaign: CampaignRecord) -> ManagerContext:
        return ManagerContext(
            problem={
                "id": campaign.id,
                "title": campaign.title,
                "statement": campaign.problem_statement,
            },
            frontier=campaign.frontier,
            memory=campaign.memory,
            operator_notes=campaign.operator_notes,
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

    def _build_context_from_memory(self, campaign: CampaignRecord) -> ManagerContext:
        packet = self.memory.get_manager_packet(campaign_id=campaign.id)
        if not packet.campaign:
            return self._build_context(campaign)

        legacy_by_text: dict[tuple[str, str, str | None], Any] = {}
        for node in campaign.frontier:
            legacy_by_text[(node.text, node.kind, node.parent_id)] = node

        frontier_nodes = []
        for item in packet.active_frontier:
            payload = item.get("payload") or {}
            key = (
                item.get("summary", ""),
                payload.get("kind", "claim"),
                payload.get("parent_id"),
            )
            legacy_node = legacy_by_text.get(key)
            frontier_nodes.append(
                {
                    "id": legacy_node.id if legacy_node else item.get("id"),
                    "text": item.get("summary") or item.get("title", ""),
                    "status": item.get("status", "open"),
                    "priority": payload.get("priority", 1.0),
                    "parent_id": legacy_node.parent_id if legacy_node else payload.get("parent_id"),
                    "kind": payload.get("kind", "claim"),
                    "failure_count": payload.get("failure_count", 0),
                    "evidence": payload.get("evidence", []),
                }
            )

        context_frontier = (
            [campaign.frontier[0].model_dump()] if not frontier_nodes else frontier_nodes
        )

        memory = campaign.memory.model_copy(deep=True)
        context_notes = list(memory.policy_notes)
        recent_results = [r.get("summary", "") for r in packet.recent_results if r.get("summary")]
        paper_unit_titles = [u.get("title", "") for u in packet.paper_units if u.get("title")]
        if recent_results:
            context_notes.extend([f"recent_result:{item}" for item in recent_results[:3]])
        if paper_unit_titles:
            context_notes.extend([f"paper_unit:{item}" for item in paper_unit_titles[:3]])
        if context_notes:
            memory.policy_notes = context_notes[-20:]

        problem_payload = {
            "id": campaign.id,
            "title": campaign.title,
            "statement": campaign.problem_statement,
        }
        if packet.current_candidate_answer:
            problem_payload["current_candidate_answer"] = packet.current_candidate_answer

        return ManagerContext(
            problem=problem_payload,
            frontier=context_frontier,
            memory=memory,
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
