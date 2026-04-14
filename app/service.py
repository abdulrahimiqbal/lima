from __future__ import annotations

from datetime import datetime
import logging
import threading
import time
from uuid import uuid4

from lima_memory import MemoryService, PostgresKnowledgeStore, SqliteKnowledgeStore

from .config import Settings
from .executor import Executor
from .frontier import apply_execution_result, seed_frontier
from .invention import InventionService
from .learner import update_memory
from .manager import Manager, get_policy
from .obligation_analysis import build_execution_plan
from .schemas import (
    ApprovedExecutionPlan,
    CampaignCreate,
    CampaignEventRecord,
    CampaignRecord,
    CampaignUpdateNotes,
    CandidateAnswer,
    ExecutionResult,
    FrontierNode,
    InventionBatch,
    InventionBatchCreate,
    ManagerContext,
    ManagerDecision,
    MemoryState,
    PendingAristotleJob,
    DistilledWorld,
    ProofDebtItem,
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
        self.invention = InventionService(self.memory, settings)
        self._campaign_locks: dict[str, threading.Lock] = {}
        self._campaign_locks_guard = threading.Lock()

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
        return [self._campaign_header_from_node(node.asdict()) for node in nodes]

    def get_campaign(self, campaign_id: str) -> CampaignRecord:
        return self._campaign_from_memory(campaign_id)

    def update_notes(self, campaign_id: str, payload: CampaignUpdateNotes) -> CampaignRecord:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            campaign.operator_notes = payload.operator_notes
            self._persist_campaign(campaign)
            self.memory.add_event(
                campaign_id=campaign_id,
                tick=campaign.tick_count,
                event_type="operator_notes_updated",
                payload={"operator_notes": payload.operator_notes},
            )
            return campaign

    def pause_campaign(self, campaign_id: str) -> CampaignRecord:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            campaign.status = "paused"
            campaign.auto_run = False
            self._persist_campaign(campaign)
            self.memory.add_event(
                campaign_id=campaign_id, tick=campaign.tick_count, event_type="campaign_paused", payload={}
            )
            return campaign

    def resume_campaign(self, campaign_id: str) -> CampaignRecord:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            if campaign.status not in {"solved", "failed"}:
                campaign.status = "running"
                campaign.auto_run = True
            self._persist_campaign(campaign)
            self.memory.add_event(
                campaign_id=campaign_id, tick=campaign.tick_count, event_type="campaign_resumed", payload={}
            )
            return campaign

    def build_manager_context(self, campaign_id: str) -> ManagerContext:
        _ = self.get_campaign(campaign_id)
        return self._build_context_from_memory(campaign_id)

    def step_campaign(self, campaign_id: str) -> CampaignRecord:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            if campaign.status in {"solved", "failed", "paused"}:
                return campaign

            # Check if there are pending Aristotle jobs.
            if self._pending_jobs(campaign):
                return self._poll_pending_jobs(campaign)

            # No pending job - proceed with normal decision flow
            context = self._build_context_from_memory(campaign_id, campaign=campaign)
            decision = self.manager.decide(context)
            tick = campaign.tick_count + 1

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
                updated = self._finalize_execution(campaign, decision, result, context, tick, active_policy)
                return updated

            # Record decision before execution
            self.memory.record_manager_decision(
                campaign_id=campaign.id,
                tick=tick,
                decision=decision.model_dump(),
            )

            # Handle proof jobs vs evidence jobs differently
            if plan.approved_proof_jobs:
                # Submit every currently unlocked independent proof debt.
                pending_jobs = self._submit_proof_wave(campaign, decision, context, tick, active_policy, plan)
                
                updated = campaign.model_copy(deep=True)
                updated.tick_count = tick
                updated.last_manager_context = context.model_dump()
                updated.last_manager_decision = decision.model_dump()
                updated.manager_backend = decision.manager_backend
                updated.current_candidate_answer = decision.candidate_answer
                updated = self._apply_decision_world_state(updated, decision)
                self._set_pending_jobs(updated, pending_jobs)
                
                for pending_job in pending_jobs:
                    self.memory.add_event(
                        campaign_id=campaign_id,
                        tick=tick,
                        event_type="aristotle_job_submitted",
                        payload={
                            "project_id": pending_job.project_id,
                            "target_frontier_node": pending_job.target_frontier_node,
                            "world_family": pending_job.world_family,
                            "debt_id": pending_job.debt_id,
                            "status": pending_job.status,
                        },
                    )
                
                self._persist_campaign(updated)
                return updated
            
            elif plan.approved_evidence_jobs:
                # Evidence jobs run synchronously as before
                result = self.executor.run_evidence(campaign, decision, plan)
                updated = self._finalize_execution(campaign, decision, result, context, tick, active_policy)
                return updated
            
            else:
                # No jobs approved
                result = ExecutionResult(
                    status="blocked",
                    failure_type="excessive_scope",
                    notes="No approved jobs in execution plan.",
                    executor_backend="gate",
                )
                updated = self._finalize_execution(campaign, decision, result, context, tick, active_policy)
                return updated

    def _poll_pending_jobs(self, campaign: CampaignRecord) -> CampaignRecord:
        """Poll existing pending Aristotle jobs and finalize any terminal results."""
        pending_jobs = self._pending_jobs(campaign)
        if not pending_jobs:
            return campaign

        updated = campaign.model_copy(deep=True)
        still_pending: list[PendingAristotleJob] = []
        active_policy = self.memory.get_latest_policy() or get_policy()

        for pending_job in pending_jobs:
            updated_job, result = self.executor.poll_proof(pending_job)

            if result is None:
                still_pending.append(updated_job)
                self.memory.add_event(
                    campaign_id=campaign.id,
                    tick=campaign.tick_count,
                    event_type="aristotle_job_polled",
                    payload={
                        "project_id": updated_job.project_id,
                        "poll_count": updated_job.poll_count,
                        "status": updated_job.status,
                        "debt_id": updated_job.debt_id,
                    },
                )
                continue

            from .schemas import ApprovedExecutionPlan, ManagerDecision

            decision = ManagerDecision.model_validate(pending_job.decision_snapshot)
            plan = ApprovedExecutionPlan.model_validate(pending_job.plan_snapshot)
            started = time.perf_counter()
            elapsed = int((time.perf_counter() - started) * 1000)
            result = self.executor._attach_plan_metadata(
                result,
                plan,
                elapsed,
                executed_proof_jobs=plan.approved_proof_jobs[:1],
                executed_evidence_jobs=[],
            )

            updated = self._apply_decision_world_state(updated, decision)
            updated = update_memory(updated, decision, result, policy=active_policy)
            updated = apply_execution_result(updated, decision, result)
            updated.last_execution_result = result.model_dump()
            self._recompute_resolved_debt_ids(updated)

            self.memory.add_event(
                campaign_id=campaign.id,
                tick=campaign.tick_count,
                event_type="aristotle_job_completed",
                payload={
                    "project_id": updated_job.project_id,
                    "poll_count": updated_job.poll_count,
                    "status": updated_job.status,
                    "debt_id": updated_job.debt_id,
                    "result_status": result.status,
                    "failure_type": result.failure_type,
                },
            )

            raw_payload = result.raw if isinstance(result.raw, dict) else {}
            self.memory.record_execution_result(
                campaign_id=campaign.id,
                tick=campaign.tick_count,
                decision=decision.model_dump(),
                result=updated.last_execution_result,
                raw_request=raw_payload.get("aristotle_request"),
                raw_response=raw_payload.get("aristotle_response"),
            )

        self._set_pending_jobs(updated, still_pending)
        
        self._persist_campaign(updated)
        return updated

    def _apply_decision_world_state(
        self, campaign: CampaignRecord, decision: ManagerDecision
    ) -> CampaignRecord:
        """Apply world program and proof debt from decision to campaign state."""
        # Install world program
        if decision.primary_world:
            campaign.current_world_program = decision.primary_world.model_dump()
            campaign.active_world_id = decision.primary_world.id
        
        if decision.alternative_worlds:
            campaign.alternative_world_programs = [w.model_dump() for w in decision.alternative_worlds]
        
        # Merge proof debt ledger, preserving statuses from matching IDs
        if decision.proof_debt:
            # Build map of existing debt statuses
            existing_statuses = {}
            for debt_dict in campaign.proof_debt_ledger:
                debt_id = debt_dict.get("id")
                if debt_id:
                    existing_statuses[debt_id] = debt_dict.get("status", "open")
            
            # Replace ledger with new debt, preserving statuses where IDs match
            new_ledger = []
            for debt_item in decision.proof_debt:
                debt_dict = debt_item.model_dump()
                if debt_item.id in existing_statuses:
                    debt_dict["status"] = existing_statuses[debt_item.id]
                new_ledger.append(debt_dict)
            campaign.proof_debt_ledger = new_ledger
        
        return campaign
    
    def _recompute_resolved_debt_ids(self, campaign: CampaignRecord) -> None:
        """Recompute resolved_debt_ids from final ledger state."""
        campaign.resolved_debt_ids = [
            d["id"] for d in campaign.proof_debt_ledger
            if d.get("id") and d.get("status") == "proved"
        ]

    def _pending_jobs(self, campaign: CampaignRecord) -> list[PendingAristotleJob]:
        jobs = list(campaign.pending_aristotle_jobs or [])
        if campaign.pending_aristotle_job and all(
            job.project_id != campaign.pending_aristotle_job.project_id for job in jobs
        ):
            jobs.insert(0, campaign.pending_aristotle_job)
        return jobs

    def _set_pending_jobs(
        self,
        campaign: CampaignRecord,
        jobs: list[PendingAristotleJob],
    ) -> None:
        campaign.pending_aristotle_jobs = jobs
        campaign.pending_aristotle_job = jobs[0] if jobs else None
        active_debt_ids = {job.debt_id for job in jobs if job.debt_id}
        for debt in campaign.proof_debt_ledger:
            if debt.get("id") in active_debt_ids and debt.get("status") == "open":
                debt["status"] = "active"

    def _submit_proof_wave(
        self,
        campaign: CampaignRecord,
        decision: ManagerDecision,
        context: ManagerContext,
        tick: int,
        active_policy: dict,
        base_plan: ApprovedExecutionPlan,
    ) -> list[PendingAristotleJob]:
        ready_debts = self._ready_proof_debts(campaign, decision, active_policy)
        pending_jobs: list[PendingAristotleJob] = []

        if ready_debts:
            ledger = self._ledger_debt_items(campaign, decision)
            for debt in ready_debts:
                debt_decision = decision.model_copy(
                    deep=True,
                    update={
                        "bounded_claim": debt.statement,
                        "formal_obligations": [],
                        "proof_debt": ledger,
                        "critical_next_debt_id": debt.id,
                    },
                )
                plan = build_execution_plan(debt_decision, policy=active_policy, memory=campaign.memory)
                self.memory.add_event(
                    campaign_id=campaign.id,
                    tick=tick,
                    event_type="obligation_analysis",
                    payload={
                        **plan.model_dump(),
                        "wavefront_debt_id": debt.id,
                        "wavefront_debt_class": debt.debt_class,
                    },
                )
                if plan.approved_proof_jobs:
                    pending_jobs.append(self.executor.submit_proof(campaign, debt_decision, plan))
            if pending_jobs:
                self.memory.add_event(
                    campaign_id=campaign.id,
                    tick=tick,
                    event_type="aristotle_wave_submitted",
                    payload={
                        "job_count": len(pending_jobs),
                        "debt_ids": [job.debt_id for job in pending_jobs],
                    },
                )
                return pending_jobs

        for proof_job in base_plan.approved_proof_jobs:
            split_plan = base_plan.model_copy(
                deep=True,
                update={
                    "approved_proof_jobs": [proof_job],
                    "approved_evidence_jobs": [],
                    "channel_used": "aristotle_proof",
                },
            )
            pending_jobs.append(self.executor.submit_proof(campaign, decision, split_plan))
        return pending_jobs

    def _ready_proof_debts(
        self,
        campaign: CampaignRecord,
        decision: ManagerDecision,
        active_policy: dict,
    ) -> list[ProofDebtItem]:
        ledger = self._ledger_debt_items(campaign, decision)
        if not ledger:
            return []

        pending_debt_ids = {job.debt_id for job in self._pending_jobs(campaign) if job.debt_id}
        status_by_id = {debt.id: debt.status for debt in ledger}
        resolved_ids = set(campaign.resolved_debt_ids)
        resolved_ids.update(debt_id for debt_id, status in status_by_id.items() if status == "proved")

        ready = [
            debt
            for debt in ledger
            if debt.status == "open"
            and debt.id not in pending_debt_ids
            and debt.assigned_channel in {"aristotle", "auto"}
            and debt.role in {"closure", "bridge", "support"}
            and all(dep_id in resolved_ids for dep_id in debt.depends_on)
        ]
        ready.sort(key=lambda item: (-item.priority, item.expected_difficulty, item.id))
        limits = active_policy.get("complexity_limits", {})
        max_wave = int(limits.get("parallel_aristotle_jobs_per_wave", limits.get("max_proof_obligations_per_step", 1)))
        return ready[: max(1, max_wave)]

    def _ledger_debt_items(
        self,
        campaign: CampaignRecord,
        decision: ManagerDecision,
    ) -> list[ProofDebtItem]:
        raw_items = campaign.proof_debt_ledger or [item.model_dump() for item in decision.proof_debt]
        items: list[ProofDebtItem] = []
        for raw_item in raw_items:
            try:
                items.append(ProofDebtItem.model_validate(raw_item))
            except Exception:
                logger.warning("Skipping invalid proof debt item in campaign=%s", campaign.id)
        return items

    def _finalize_execution(
        self,
        campaign: CampaignRecord,
        decision: ManagerDecision,
        result: ExecutionResult,
        context: ManagerContext,
        tick: int,
        active_policy: dict,
    ) -> CampaignRecord:
        """Finalize execution by applying memory and frontier updates."""
        updated = campaign.model_copy(deep=True)
        updated.tick_count = tick
        updated.last_manager_context = context.model_dump()
        updated.last_manager_decision = decision.model_dump()
        updated.manager_backend = decision.manager_backend
        updated.executor_backend = result.executor_backend
        updated.current_candidate_answer = decision.candidate_answer
        
        # Install world/debt state BEFORE memory and frontier updates
        updated = self._apply_decision_world_state(updated, decision)
        
        # Now apply memory and frontier updates with current world/debt state
        updated = update_memory(updated, decision, result, policy=active_policy)
        updated = apply_execution_result(updated, decision, result)
        updated.last_execution_result = result.model_dump()
        
        # Recompute resolved debt IDs from final ledger
        self._recompute_resolved_debt_ids(updated)

        raw_payload = result.raw if isinstance(result.raw, dict) else {}
        self.memory.record_execution_result(
            campaign_id=campaign.id,
            tick=tick,
            decision=decision.model_dump(),
            result=updated.last_execution_result,
            raw_request=raw_payload.get("aristotle_request"),
            raw_response=raw_payload.get("aristotle_response"),
        )
        self._persist_campaign(updated)
        return updated

    def auto_step_once(self) -> None:
        campaigns = self.list_campaigns()
        stepped = 0
        for campaign in campaigns:
            if stepped >= self.settings.auto_step_limit_per_tick:
                break
            if campaign.auto_run and campaign.status == "running":
                self.step_campaign(campaign.id)
                stepped += 1

    def list_events(self, campaign_id: str, limit: int = 50) -> list[CampaignEventRecord]:
        _ = self.get_campaign(campaign_id)
        events = self.memory.list_events(campaign_id, limit=limit)
        results: list[CampaignEventRecord] = []
        for idx, event in enumerate(events, start=1):
            results.append(
                CampaignEventRecord(
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

    def get_operator_brief(self, campaign_id: str) -> dict:
        """Assemble a comprehensive operator brief for the UI."""
        campaign = self.get_campaign(campaign_id)
        system = self.system_status()
        invention_lab = self.invention.get_lab(campaign_id)
        
        # Ops section
        executor_conn = system["executor"]["connectivity"]
        ops = {
            "manager_backend": campaign.manager_backend,
            "manager_model": system["manager"].get("model"),
            "executor_backend": campaign.executor_backend,
            "executor_connectivity_status": executor_conn.get("status"),
            "executor_connectivity_reason": executor_conn.get("reason"),
            "database_status": system.get("database"),
            "self_improvement_enabled": system["self_improvement"]["enabled"],
            "campaign_status": campaign.status,
            "tick_count": campaign.tick_count,
        }
        
        # Campaign Now section
        target_node_text = None
        if campaign.last_manager_decision:
            target_id = campaign.last_manager_decision.get("target_frontier_node")
            if target_id:
                for node in campaign.frontier:
                    if node.id == target_id:
                        target_node_text = node.text
                        break
        
        candidate = campaign.current_candidate_answer
        campaign_now = {
            "title": campaign.title,
            "problem_statement": campaign.problem_statement,
            "candidate_stance": candidate.stance if candidate else None,
            "candidate_summary": candidate.summary if candidate else None,
            "candidate_confidence": candidate.confidence if candidate else None,
            "target_frontier_node_id": campaign.last_manager_decision.get("target_frontier_node") if campaign.last_manager_decision else None,
            "target_frontier_node_text": target_node_text,
            "world_family": campaign.last_manager_decision.get("world_family") if campaign.last_manager_decision else None,
            "bounded_claim": campaign.last_manager_decision.get("bounded_claim") if campaign.last_manager_decision else None,
            "active_world_id": campaign.active_world_id,
            "world_thesis": campaign.current_world_program.get("thesis") if campaign.current_world_program else None,
            "critical_debt_count": len([d for d in campaign.proof_debt_ledger if d.get("critical")]) if campaign.proof_debt_ledger else 0,
            "proved_critical_debt_count": len([d for d in campaign.proof_debt_ledger if d.get("critical") and d.get("status") == "proved"]) if campaign.proof_debt_ledger else 0,
            "critical_next_debt_id": campaign.last_manager_decision.get("critical_next_debt_id") if campaign.last_manager_decision else None,
        }
        
        # Manager Understanding section
        manager_understanding = {
            "problem_summary": None,
            "candidate_answer_seen": None,
            "target_node_id_confirmed": None,
            "target_node_text_confirmed": None,
            "operator_notes_seen": [],
            "relevant_memory_seen": {
                "blocked_patterns": [],
                "useful_lemmas": [],
                "recent_failures": [],
            },
            "constraints_seen": [],
            "open_uncertainties": [],
            "why_not_other_frontier_nodes": None,
        }
        
        if campaign.last_manager_decision:
            receipt = campaign.last_manager_decision.get("manager_read_receipt")
            if receipt:
                manager_understanding = {
                    "problem_summary": receipt.get("problem_summary"),
                    "candidate_answer_seen": receipt.get("candidate_answer_seen"),
                    "target_node_id_confirmed": receipt.get("target_node_id_confirmed"),
                    "target_node_text_confirmed": receipt.get("target_node_text_confirmed"),
                    "operator_notes_seen": receipt.get("operator_notes_seen", []),
                    "relevant_memory_seen": receipt.get("relevant_memory_seen", {
                        "blocked_patterns": [],
                        "useful_lemmas": [],
                        "recent_failures": [],
                    }),
                    "constraints_seen": receipt.get("constraints_seen", []),
                    "open_uncertainties": receipt.get("open_uncertainties", []),
                    "why_not_other_frontier_nodes": receipt.get("why_not_other_frontier_nodes"),
                }
        
        # Verification section
        verification = {
            "channel_used": None,
            "status": None,
            "failure_type": None,
            "executor_backend": None,
            "timing_ms": None,
            "notes": None,
            "approved_jobs_count": None,
            "rejected_jobs_count": None,
            "approved_proof_jobs": [],
            "approved_evidence_jobs": [],
            "rejected_obligations": [],
            "rejected_reasons": {},
        }
        
        if campaign.last_execution_result:
            result = campaign.last_execution_result
            verification = {
                "channel_used": result.get("channel_used"),
                "status": result.get("status"),
                "failure_type": result.get("failure_type"),
                "executor_backend": result.get("executor_backend"),
                "timing_ms": result.get("timing_ms"),
                "notes": result.get("notes"),
                "approved_jobs_count": result.get("approved_jobs_count"),
                "rejected_jobs_count": result.get("rejected_jobs_count"),
                "approved_proof_jobs": result.get("approved_proof_jobs", []),
                "approved_evidence_jobs": result.get("approved_evidence_jobs", []),
                "rejected_obligations": result.get("rejected_obligations", []),
                "rejected_reasons": result.get("raw", {}).get("rejected_reasons", {}),
            }
        
        # Discovery section
        spawned_nodes = []
        if campaign.last_execution_result:
            spawned = campaign.last_execution_result.get("spawned_nodes", [])
            spawned_nodes = [
                {"id": n.get("id"), "text": n.get("text"), "kind": n.get("kind")}
                for n in spawned
            ]
        
        discovery = {
            "spawned_nodes_count": len(spawned_nodes),
            "spawned_nodes": spawned_nodes,
            "useful_lemmas": campaign.memory.useful_lemmas,
            "blocked_patterns": campaign.memory.blocked_patterns,
            "recent_failures": campaign.memory.recent_failures,
            "policy_notes": campaign.memory.policy_notes,
            "evidence_streaks": campaign.memory.evidence_streaks,
            "formalization_streaks": campaign.memory.formalization_streaks,
            "timeout_streaks": campaign.memory.timeout_streaks,
        }

        invention = {
            **invention_lab["summary"],
            "latest_batch_id": (
                invention_lab["batches"][0]["id"]
                if invention_lab["batches"]
                else None
            ),
            "promising_worlds": [
                {
                    "id": node["id"],
                    "label": node["title"],
                    "status": node["status"],
                    "novelty_score": node["payload"].get("novelty_score"),
                    "bridge_score": node["payload"].get("bridge_score"),
                }
                for node in invention_lab["distilled_worlds"]
                if node["payload"].get("status") in {"promising", "baking"}
            ][:5],
            "dead_patterns": invention_lab["dead_patterns"][:10],
        }
        
        # Self-Improvement section
        self_improvement = {
            "local_proposal": None,
            "local_reason": None,
            "global_status": None,
            "global_version": None,
            "global_reason": None,
            "global_patch": None,
        }
        
        if campaign.last_manager_decision:
            si_note = campaign.last_manager_decision.get("self_improvement_note")
            if si_note:
                self_improvement["local_proposal"] = si_note.get("proposal")
                self_improvement["local_reason"] = si_note.get("reason")
        
        # Next section
        next_action = {
            "why_this_next": None,
            "expected_information_gain": None,
            "if_proved": None,
            "if_refuted": None,
            "if_blocked": None,
            "if_inconclusive": None,
            "recommended_operator_action": None,
        }
        
        if campaign.last_manager_decision:
            next_action["why_this_next"] = campaign.last_manager_decision.get("why_this_next")
            next_action["expected_information_gain"] = campaign.last_manager_decision.get("expected_information_gain")
            update_rules = campaign.last_manager_decision.get("update_rules", {})
            next_action["if_proved"] = update_rules.get("if_proved")
            next_action["if_refuted"] = update_rules.get("if_refuted")
            next_action["if_blocked"] = update_rules.get("if_blocked")
            next_action["if_inconclusive"] = update_rules.get("if_inconclusive")
        
        # Synthesize recommended operator action
        if campaign.last_execution_result:
            result = campaign.last_execution_result
            failure_type = result.get("failure_type")
            status = result.get("status")
            channel = result.get("channel_used")
            
            if failure_type == "formalization_failed":
                next_action["recommended_operator_action"] = "Rewrite the claim as a clean structured formal obligation and retry."
            elif failure_type == "proof_failed":
                next_action["recommended_operator_action"] = "Split the target into a smaller lemma or add missing assumptions."
            elif failure_type == "timeout":
                next_action["recommended_operator_action"] = "Shrink scope and retry a smaller proof job."
            elif status == "inconclusive" and channel == "computational_evidence":
                next_action["recommended_operator_action"] = "Treat this as discovery, not verification; convert patterns into a formal lemma."
            elif status == "blocked":
                next_action["recommended_operator_action"] = "Adjust scope or split obligations to pass submission gate."
            elif status == "proved":
                next_action["recommended_operator_action"] = "Continue to next frontier node."
            elif status == "refuted":
                next_action["recommended_operator_action"] = "Update candidate answer and explore alternative approaches."
            else:
                next_action["recommended_operator_action"] = "Review result and decide next step based on update rules."
        elif campaign.pending_aristotle_job:
            next_action["recommended_operator_action"] = "Wait for the pending Aristotle proof job to complete or poll it on the next step."
        
        return {
            "ops": ops,
            "campaign_now": campaign_now,
            "manager_understanding": manager_understanding,
            "verification": verification,
            "discovery": discovery,
            "invention": invention,
            "self_improvement": self_improvement,
            "next": next_action,
        }

    def create_invention_batch(
        self,
        campaign_id: str,
        payload: InventionBatchCreate,
    ) -> InventionBatch:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            active_policy = self.memory.get_latest_policy() or get_policy()
            return self.invention.create_batch(campaign, payload, policy=active_policy)

    def distill_invention_batch(
        self,
        campaign_id: str,
        batch_id: str,
    ) -> list[DistilledWorld]:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            return self.invention.distill_batch(campaign, batch_id)

    def falsify_invention_batch(
        self,
        campaign_id: str,
        batch_id: str,
    ) -> list[dict]:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            results = self.invention.falsify_batch(campaign, batch_id)
            return [result.model_dump(mode="json") for result in results]

    def promote_invention_world(
        self,
        campaign_id: str,
        distilled_world_id: str,
    ) -> CampaignRecord:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            world = self.invention.promote_world(campaign, distilled_world_id)
            updated = campaign.model_copy(deep=True)
            updated.current_world_program = world.world_program.model_dump()
            updated.alternative_world_programs = [
                candidate["payload"]["world_program"]
                for candidate in self.invention.get_lab(campaign_id)["distilled_worlds"]
                if candidate["id"] != distilled_world_id
            ][:8]
            updated.proof_debt_ledger = [
                debt.model_dump() for debt in world.proof_debt
            ]
            updated.resolved_debt_ids = [
                debt.id for debt in world.proof_debt if debt.status == "proved"
            ]
            updated.active_world_id = world.world_program.id
            self._persist_campaign(updated)
            return updated

    def get_invention_lab(self, campaign_id: str) -> dict:
        _ = self.get_campaign(campaign_id)
        return self.invention.get_lab(campaign_id)

    def smoke_aristotle(self, *, strict_live_probe: bool = False) -> dict:
        return self.executor.check_connectivity(strict_live_probe=strict_live_probe)

    def run_self_improvement(self) -> dict:
        return self.self_improvement.run_cycle()

    def ping_store(self) -> None:
        _ = self.memory.list_campaign_nodes(limit=1)

    def _build_context_from_memory(
        self, campaign_id: str, *, campaign: CampaignRecord | None = None
    ) -> ManagerContext:
        campaign = campaign or self.get_campaign(campaign_id)
        packet = self.memory.get_manager_packet(campaign_id=campaign.id, limit=100)

        frontier_nodes = []
        for node in campaign.frontier:
            frontier_nodes.append(
                {
                    "id": node.id,
                    "text": node.text,
                    "status": node.status,
                    "priority": node.priority,
                    "parent_id": node.parent_id,
                    "kind": node.kind,
                    "failure_count": node.failure_count,
                    "evidence": node.evidence,
                }
            )

        problem_payload = {
            "id": campaign.id,
            "title": campaign.title,
            "statement": campaign.problem_statement,
        }
        if packet.current_candidate_answer:
            problem_payload["current_candidate_answer"] = packet.current_candidate_answer
        
        # Include current world info if present
        if campaign.current_world_program:
            problem_payload["current_world_program"] = campaign.current_world_program
        if campaign.proof_debt_ledger:
            problem_payload["proof_debt_ledger"] = campaign.proof_debt_ledger
        if campaign.active_world_id:
            problem_payload["active_world_id"] = campaign.active_world_id

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
        payload = packet.campaign.get("payload") or {}
        if not payload.get("problem_statement") and packet.problem:
            problem_payload = packet.problem.get("payload") or {}
            payload["problem_statement"] = problem_payload.get("statement", "")
        return self._campaign_from_node(campaign_id, payload, packet.campaign)

    def _campaign_from_node(
        self,
        campaign_id: str,
        payload: dict,
        campaign_node: dict,
    ) -> CampaignRecord:
        if not campaign_node:
            raise KeyError(f"Campaign not found: {campaign_id}")

        problem_statement = payload.get("problem_statement") or ""

        frontier_nodes = self._load_frontier_nodes(campaign_id)
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
        
        pending_job_payload = payload.get("pending_aristotle_job")
        pending_job = (
            PendingAristotleJob.model_validate(pending_job_payload)
            if pending_job_payload
            else None
        )
        pending_jobs_payload = payload.get("pending_aristotle_jobs") or []
        pending_jobs = [
            PendingAristotleJob.model_validate(job_payload)
            for job_payload in pending_jobs_payload
        ]
        if pending_job and all(job.project_id != pending_job.project_id for job in pending_jobs):
            pending_jobs.insert(0, pending_job)

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
            pending_aristotle_job=pending_job,
            pending_aristotle_jobs=pending_jobs,
            current_world_program=payload.get("current_world_program"),
            alternative_world_programs=payload.get("alternative_world_programs", []),
            proof_debt_ledger=payload.get("proof_debt_ledger", []),
            resolved_debt_ids=payload.get("resolved_debt_ids", []),
            active_world_id=payload.get("active_world_id"),
        )

    def _campaign_header_from_node(self, campaign_node: dict) -> CampaignRecord:
        payload = campaign_node.get("payload") or {}
        status_raw = payload.get("status", campaign_node.get("status", "running"))
        status_normalized = "running" if status_raw == "active" else status_raw
        
        pending_job_payload = payload.get("pending_aristotle_job")
        pending_job = (
            PendingAristotleJob.model_validate(pending_job_payload)
            if pending_job_payload
            else None
        )
        pending_jobs_payload = payload.get("pending_aristotle_jobs") or []
        pending_jobs = [
            PendingAristotleJob.model_validate(job_payload)
            for job_payload in pending_jobs_payload
        ]
        if pending_job and all(job.project_id != pending_job.project_id for job in pending_jobs):
            pending_jobs.insert(0, pending_job)
        
        return CampaignRecord(
            id=campaign_node["id"],
            title=campaign_node.get("title", ""),
            problem_statement=payload.get("problem_statement", ""),
            status=status_normalized,
            auto_run=bool(payload.get("auto_run", True)),
            operator_notes=payload.get("operator_notes", []),
            frontier=[],
            memory=MemoryState.model_validate(payload.get("memory") or MemoryState().model_dump()),
            current_candidate_answer=(
                CandidateAnswer.model_validate(payload["current_candidate_answer"])
                if payload.get("current_candidate_answer")
                else None
            ),
            tick_count=int(payload.get("tick_count", 0)),
            created_at=_parse_dt(campaign_node["created_at"]),
            updated_at=_parse_dt(campaign_node["updated_at"]),
            last_manager_context=payload.get("last_manager_context"),
            last_manager_decision=payload.get("last_manager_decision"),
            last_execution_result=payload.get("last_execution_result"),
            manager_backend=payload.get("manager_backend", self.settings.manager_backend_resolved),
            executor_backend=payload.get("executor_backend", self.settings.executor_backend),
            pending_aristotle_job=pending_job,
            pending_aristotle_jobs=pending_jobs,
            current_world_program=payload.get("current_world_program"),
            alternative_world_programs=payload.get("alternative_world_programs", []),
            proof_debt_ledger=payload.get("proof_debt_ledger", []),
            resolved_debt_ids=payload.get("resolved_debt_ids", []),
            active_world_id=payload.get("active_world_id"),
        )

    def _load_frontier_nodes(self, campaign_id: str) -> list[FrontierNode]:
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
        return frontier_nodes

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
                "pending_aristotle_job": campaign.pending_aristotle_job.model_dump(mode='json')
                if campaign.pending_aristotle_job
                else None,
                "pending_aristotle_jobs": [
                    job.model_dump(mode="json") for job in self._pending_jobs(campaign)
                ],
                "current_world_program": campaign.current_world_program,
                "alternative_world_programs": campaign.alternative_world_programs,
                "proof_debt_ledger": campaign.proof_debt_ledger,
                "resolved_debt_ids": campaign.resolved_debt_ids,
                "active_world_id": campaign.active_world_id,
            },
        )
        self.memory.upsert_frontier_nodes(
            campaign_id=campaign.id,
            nodes=[node.model_dump() for node in campaign.frontier],
        )
        logger.debug(
            "Persisted campaign=%s frontier_nodes=%d tick=%d pending_job=%s world_id=%s",
            campaign.id,
            len(campaign.frontier),
            campaign.tick_count,
            campaign.pending_aristotle_job.project_id if campaign.pending_aristotle_job else None,
            campaign.active_world_id,
        )

    def _campaign_lock(self, campaign_id: str) -> threading.Lock:
        with self._campaign_locks_guard:
            lock = self._campaign_locks.get(campaign_id)
            if lock is None:
                lock = threading.Lock()
                self._campaign_locks[campaign_id] = lock
            return lock
