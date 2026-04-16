from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
import re
import tarfile
import threading
import time
from collections import Counter
from typing import Any, Literal
from uuid import uuid4

from lima_memory import MemoryService, PostgresKnowledgeStore, SqliteKnowledgeStore

from .collatz_automaton import (
    analyze_dynamic_pressure_automaton,
    analyze_height_lifted_pressure_automaton,
)
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
    CandidateRankFamilyRequest,
    CandidateRankFamilyRun,
    CompositeScarcityTheoremWaveRequest,
    CompositeScarcityTheoremWaveRun,
    CompositeScarcityViabilityWaveRequest,
    CompositeScarcityViabilityWaveRun,
    CompositionalCertificateFamilyRequest,
    CompositionalCertificateFamilyRun,
    CoverageNormalizationHuntRequest,
    CoverageNormalizationHuntRun,
    CylinderPressureWaveRequest,
    CylinderPressureWaveRun,
    CandidateAnswer,
    DynamicAdmissibilityCompassWaveRequest,
    DynamicAdmissibilityCompassWaveRun,
    DynamicPressureAutomatonWaveRequest,
    DynamicPressureAutomatonWaveRun,
    ExecutionResult,
    FinalCollatzExperimentRequest,
    FinalCollatzExperimentRun,
    FormalObligationSpec,
    FormalProbe,
    FormalProbeBakeRequest,
    FormalProbeBakeRun,
    FormalProbeDigestRequest,
    FormalProbeDigestRun,
    FrontierNode,
    GlobalForcingHuntWaveRequest,
    GlobalForcingHuntWaveRun,
    HybridCertificateFamilyRequest,
    HybridCertificateFamilyRun,
    InventionBatch,
    InventionBatchCreate,
    ManagerContext,
    ManagerDecision,
    MemoryState,
    PendingAristotleJob,
    PivotPortfolioWaveRequest,
    PivotPortfolioWaveRun,
    PressureHeightFrontierCertificateWaveRequest,
    PressureHeightFrontierCertificateWaveRun,
    PressureHeightFrontierCompletenessWaveRequest,
    PressureHeightFrontierCompletenessWaveRun,
    PressureHeightSurvivorClosureWaveRequest,
    PressureHeightSurvivorClosureWaveRun,
    PressureGlobalizationWaveRequest,
    PressureGlobalizationWaveRun,
    RankCertificateHuntRequest,
    RankCertificateHuntRun,
    StructuredRankFamilyRequest,
    StructuredRankFamilyRun,
    DistilledWorld,
    ProofDebtItem,
    SelfImprovementNote,
    UpdateRules,
    WorldProgram,
    WorldEvolutionRun,
    WorldEvolutionRunRequest,
)
from .self_improvement import SelfImprovementService
from .world_evolution import WorldEvolutionService

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
        self.world_evolution = WorldEvolutionService(self.memory, settings, self.invention)
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
                elif any(reason == "formalization_required" for reason in plan.rejected_reasons.values()):
                    failure = "formalization_failed"
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

            if pending_job.debt_id and pending_job.debt_id.startswith("FP-"):
                self._update_formal_probe_result(
                    campaign.id,
                    pending_job.debt_id,
                    updated_job,
                    result,
                )

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
                    "artifacts": result.artifacts,
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
        preserve_active_world = False
        if decision.primary_world:
            if self._world_transition_allowed(campaign, decision):
                previous_world_id = campaign.active_world_id
                campaign.current_world_program = decision.primary_world.model_dump()
                campaign.active_world_id = decision.primary_world.id
                if previous_world_id and previous_world_id != decision.primary_world.id:
                    self.memory.add_event(
                        campaign_id=campaign.id,
                        tick=campaign.tick_count,
                        event_type="world_replaced",
                        payload={
                            "old_world_id": previous_world_id,
                            "new_world_id": decision.primary_world.id,
                            "transition": decision.world_transition,
                            "reason": decision.world_transition_reason,
                        },
                    )
            else:
                preserve_active_world = True
                self.memory.add_event(
                    campaign_id=campaign.id,
                    tick=campaign.tick_count,
                    event_type="world_switch_blocked",
                    payload={
                        "active_world_id": campaign.active_world_id,
                        "proposed_world_id": decision.primary_world.id,
                        "transition": decision.world_transition,
                        "reason": decision.world_transition_reason,
                    },
                )
        
        if decision.alternative_worlds:
            campaign.alternative_world_programs = [w.model_dump() for w in decision.alternative_worlds]
        
        if decision.proof_debt:
            existing_by_id = {}
            for debt_dict in campaign.proof_debt_ledger:
                debt_id = debt_dict.get("id")
                if debt_id:
                    existing_by_id[debt_id] = dict(debt_dict)
            new_ledger = list(existing_by_id.values())
            for debt_item in decision.proof_debt:
                debt_dict = debt_item.model_dump()
                if preserve_active_world and campaign.active_world_id:
                    debt_dict["world_id"] = campaign.active_world_id
                    debt_dict["notes"] = [
                        *debt_dict.get("notes", []),
                        "Attached as repair debt under the active world; proposed world switch was not audited.",
                    ]
                if debt_item.id in existing_by_id:
                    debt_dict["status"] = existing_by_id[debt_item.id].get("status", debt_dict.get("status", "open"))
                    existing_by_id[debt_item.id].update(debt_dict)
                else:
                    new_ledger.append(debt_dict)
            campaign.proof_debt_ledger = new_ledger
        
        return campaign

    def _world_transition_allowed(self, campaign: CampaignRecord, decision: ManagerDecision) -> bool:
        if decision.primary_world is None:
            return False
        if not campaign.active_world_id or not campaign.current_world_program:
            return True
        if decision.primary_world.id == campaign.active_world_id:
            return True
        current_audit_status = campaign.current_world_program.get("audit_status")
        proposed_audit_status = decision.primary_world.audit_status
        if current_audit_status == "fallback" and proposed_audit_status != "fallback":
            return True
        if decision.world_transition in {"retire", "replace"} and decision.world_transition_reason:
            return True
        return False
    
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
            and (not campaign.active_world_id or debt.world_id == campaign.active_world_id)
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
        world_evolution = self.world_evolution.get_summary(campaign_id)
        probe_digest = self._latest_probe_digest_summary(campaign_id)
        final_experiment = self._latest_final_collatz_experiment_summary(campaign_id)
        
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
            "world_evolution": world_evolution,
            "probe_digest": probe_digest,
            "final_experiment": final_experiment,
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

    def run_world_evolution(
        self,
        campaign_id: str,
        payload: WorldEvolutionRunRequest,
    ) -> WorldEvolutionRun:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            active_policy = self.memory.get_latest_policy() or get_policy()
            run, best_world = self.world_evolution.run(campaign, payload, policy=active_policy)

            if best_world and payload.promote_best_survivor:
                updated = campaign.model_copy(deep=True)
                best_world.status = "baking"
                updated.current_world_program = best_world.world_program.model_dump()
                updated.alternative_world_programs = [
                    candidate["payload"]["world_program"]
                    for candidate in self.invention.get_lab(campaign_id)["distilled_worlds"]
                    if candidate["id"] != best_world.id
                ][:8]
                active_debt = sorted(
                    best_world.proof_debt,
                    key=lambda debt: (not debt.critical, -debt.priority, debt.id),
                )[:12]
                updated.proof_debt_ledger = [debt.model_dump() for debt in active_debt]
                updated.resolved_debt_ids = [
                    debt.id for debt in active_debt if debt.status == "proved"
                ]
                updated.active_world_id = best_world.world_program.id
                updated.status = "running" if updated.status == "solved" else updated.status
                self._persist_campaign(updated)
                self.memory.add_event(
                    campaign_id=campaign_id,
                    tick=campaign.tick_count,
                    event_type="world_evolution_world_promoted",
                    payload={
                        "run_id": run.id,
                        "distilled_world_id": best_world.id,
                        "world_id": best_world.world_program.id,
                        "label": best_world.world_program.label,
                        "active_debt_count": len(active_debt),
                    },
                )

            return run

    def bake_formal_probes(
        self,
        campaign_id: str,
        payload: FormalProbeBakeRequest,
    ) -> FormalProbeBakeRun:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            probes = self._compiled_formal_probes(campaign_id, payload)
            if not probes:
                bake_run = FormalProbeBakeRun(
                    campaign_id=campaign_id,
                    world_id=payload.world_id or campaign.active_world_id,
                    requested_probe_count=payload.max_probes,
                    status="blocked",
                    notes=["No compiled formal probes were available to submit."],
                )
                self._record_probe_bake_run(bake_run)
                return bake_run

            updated = campaign.model_copy(deep=True)
            existing_jobs = self._pending_jobs(updated)
            submitted_jobs: list[PendingAristotleJob] = []
            skipped = 0
            world = None
            if campaign.current_world_program:
                try:
                    world = WorldProgram.model_validate(campaign.current_world_program)
                except Exception:
                    world = None

            for probe in probes:
                if any(job.debt_id == probe.id for job in existing_jobs + submitted_jobs):
                    skipped += 1
                    continue
                decision = self._decision_for_formal_probe(campaign, probe, world)
                plan = ApprovedExecutionPlan(
                    original_obligations=[probe.source_text],
                    approved_proof_jobs=[probe.source_text],
                    approved_evidence_jobs=[],
                    rejected_obligations=[],
                    channel_used="aristotle_proof",
                    max_proof_jobs_per_step=payload.max_probes,
                    budget_metadata={
                        "formal_probe_id": probe.id,
                        "formal_probe_type": probe.probe_type,
                        "world_id": probe.world_id,
                        "bake_all_at_once": payload.submit_all_at_once,
                    },
                )
                job = self.executor.submit_proof(campaign, decision, plan)
                job.debt_id = probe.id
                submitted_jobs.append(job)
                self._mark_formal_probe_submitted(campaign_id, probe, job)

            all_jobs = [*existing_jobs, *submitted_jobs]
            self._set_pending_jobs(updated, all_jobs)
            self._persist_campaign(updated)

            bake_run = FormalProbeBakeRun(
                campaign_id=campaign_id,
                world_id=payload.world_id or campaign.active_world_id,
                requested_probe_count=payload.max_probes,
                submitted_probe_count=len(submitted_jobs),
                skipped_probe_count=skipped,
                pending_job_count=len(all_jobs),
                probe_ids=[job.debt_id for job in submitted_jobs if job.debt_id],
                project_ids=[job.project_id for job in submitted_jobs],
                status="submitted" if submitted_jobs else "blocked",
                notes=[
                    "Submitted compiled formal probes to Aristotle.",
                    "Use /api/campaigns/{campaign_id}/step to poll pending probe jobs.",
                ],
            )
            self._record_probe_bake_run(bake_run)
            self._mark_final_experiment_submitted(campaign_id, bake_run)
            self.memory.add_event(
                campaign_id=campaign_id,
                tick=campaign.tick_count,
                event_type="formal_probe_bake_submitted",
                payload=bake_run.model_dump(mode="json"),
            )
            return bake_run

    def _mark_final_experiment_submitted(
        self,
        campaign_id: str,
        bake_run: FormalProbeBakeRun,
    ) -> None:
        if not bake_run.probe_ids:
            return
        nodes = self.memory.list_research_nodes(
            campaign_id,
            node_type="FinalCollatzExperimentRun",
            limit=1,
        )
        if not nodes:
            return
        node = nodes[0]
        try:
            run = FinalCollatzExperimentRun.model_validate(node.payload)
        except Exception:
            return
        submitted_ids = set(bake_run.probe_ids)
        experiment_ids = set(run.probe_ids)
        if not submitted_ids & experiment_ids:
            return
        updated = run.model_copy(
            update={
                "submitted_probe_count": len(submitted_ids & experiment_ids),
                "decision_status": "inconclusive",
                "summary": (
                    f"{run.summary} Submitted {len(submitted_ids & experiment_ids)} final probes to Aristotle."
                ),
            }
        )
        self.memory.upsert_research_node(
            campaign_id=campaign_id,
            node_id=updated.id,
            node_type="FinalCollatzExperimentRun",
            title=f"final-collatz-experiment:{updated.world_id}",
            summary=updated.summary,
            status=updated.decision_status,
            payload=updated.model_dump(mode="json"),
        )

    def get_invention_lab(self, campaign_id: str) -> dict:
        _ = self.get_campaign(campaign_id)
        return self.invention.get_lab(campaign_id)

    def digest_formal_probe_results(
        self,
        campaign_id: str,
        payload: FormalProbeDigestRequest,
    ) -> FormalProbeDigestRun:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            probe_nodes = self.memory.list_research_nodes(
                campaign_id,
                node_type="FormalProbe",
                limit=500,
            )
            probes: list[FormalProbe] = []
            for node in probe_nodes:
                try:
                    probe = FormalProbe.model_validate(node.payload)
                except Exception:
                    continue
                if payload.world_id and probe.world_id != payload.world_id:
                    continue
                probes.append(probe)

            artifacts_by_probe = self._artifacts_by_probe(
                campaign_id,
                probes,
                campaign=campaign,
                include_project_refs=payload.redownload_missing_artifacts,
            )
            unmapped_artifacts = self._unmapped_aristotle_artifacts(campaign_id, payload.max_artifacts)
            diagnostics: list[dict] = []
            failure_modes: Counter[str] = Counter()
            repair_instructions: list[str] = []

            for probe in probes:
                paths = list(dict.fromkeys([
                    *probe.artifact_paths,
                    *artifacts_by_probe.get(probe.id, []),
                ]))
                if not paths:
                    continue
                diagnostic = self._diagnose_probe_artifacts(
                    probe,
                    paths,
                    redownload_missing_artifacts=payload.redownload_missing_artifacts,
                )
                diagnostics.append(diagnostic)
                failure_modes[diagnostic["failure_type"]] += 1
                if diagnostic.get("repair_instruction"):
                    repair_instructions.append(diagnostic["repair_instruction"])
                updated = probe.model_copy(
                    update={
                        "status": diagnostic["probe_status"],
                        "failure_type": diagnostic["failure_type"],
                        "result_status": diagnostic["result_status"],
                        "artifact_paths": paths,
                        "diagnostics": diagnostic,
                        "repair_instruction": diagnostic.get("repair_instruction"),
                        "notes": f"{probe.notes} Digest: {diagnostic['summary']}",
                    }
                )
                self.memory.upsert_research_node(
                    campaign_id=campaign_id,
                    node_id=probe.id,
                    node_type="FormalProbe",
                    title=f"{probe.probe_type}:{probe.world_id}",
                    summary=probe.source_text,
                    status=updated.status,
                    payload=updated.model_dump(mode="json"),
                )

            reconciled_count = self._reconcile_pending_jobs_from_probe_diagnostics(
                campaign,
                diagnostics,
            )

            if payload.attach_unmapped_artifacts:
                for path in unmapped_artifacts:
                    if len(diagnostics) >= payload.max_artifacts:
                        break
                    diagnostic = self._diagnose_unmapped_artifact(
                        path,
                        redownload_missing_artifacts=payload.redownload_missing_artifacts,
                    )
                    diagnostics.append(diagnostic)
                    failure_modes[diagnostic["failure_type"]] += 1
                    if diagnostic.get("repair_instruction"):
                        repair_instructions.append(diagnostic["repair_instruction"])

            digest_run = FormalProbeDigestRun(
                campaign_id=campaign_id,
                world_id=payload.world_id or campaign.active_world_id,
                artifact_count=sum(len(d.get("artifact_paths", [])) for d in diagnostics),
                probe_count=len([d for d in diagnostics if d.get("probe_id")]),
                proved_count=sum(
                    1 for d in diagnostics if d.get("probe_id") and d.get("probe_status") == "proved"
                ),
                blocked_count=sum(
                    1 for d in diagnostics if d.get("probe_id") and d.get("probe_status") == "blocked"
                ),
                inconclusive_count=sum(
                    1 for d in diagnostics if d.get("probe_id") and d.get("probe_status") == "inconclusive"
                ),
                reconciled_pending_job_count=reconciled_count,
                top_failure_modes=[mode for mode, _ in failure_modes.most_common(8)],
                repair_instructions=list(dict.fromkeys(repair_instructions))[:20],
                diagnostics=diagnostics[:payload.max_artifacts],
            )
            self.memory.upsert_research_node(
                campaign_id=campaign_id,
                node_id=digest_run.id,
                node_type="FormalProbeDigestRun",
                title=f"formal-probe-digest:{digest_run.artifact_count}",
                summary=", ".join(digest_run.top_failure_modes),
                status="complete",
                payload=digest_run.model_dump(mode="json"),
            )
            self.memory.add_event(
                campaign_id=campaign_id,
                tick=campaign.tick_count,
                event_type="formal_probe_digest_completed",
                payload=digest_run.model_dump(mode="json"),
            )
            return digest_run

    def run_final_collatz_experiment(
        self,
        campaign_id: str,
        payload: FinalCollatzExperimentRequest,
    ) -> FinalCollatzExperimentRun:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            world_payload = campaign.current_world_program or {}
            world_id = payload.world_id or campaign.active_world_id or world_payload.get("id")
            if not world_id:
                raise KeyError("No promoted world is available for final Collatz experiment.")
            world_label = world_payload.get("label") or world_id
            probes = self._compile_final_collatz_probes(
                campaign_id=campaign_id,
                world_id=world_id,
                max_hard_probes=payload.max_hard_probes,
                include_controls=payload.include_control_probes,
            )
            control_count = sum(1 for probe in probes if probe.formal_obligation.metadata.get("final_experiment_role") == "control")
            hard_count = len(probes) - control_count
            for probe in probes:
                self.memory.upsert_research_node(
                    campaign_id=campaign_id,
                    node_id=probe.id,
                    node_type="FormalProbe",
                    title=f"final:{probe.probe_type}:{world_id}",
                    summary=probe.source_text,
                    status=probe.status,
                    payload=probe.model_dump(mode="json"),
                )
            run = FinalCollatzExperimentRun(
                campaign_id=campaign_id,
                world_id=world_id,
                world_label=world_label,
                compiled_probe_count=len(probes),
                control_probe_count=control_count,
                hard_probe_count=hard_count,
                probe_ids=[probe.id for probe in probes],
                decisive_probe_ids=[
                    probe.id
                    for probe in probes
                    if probe.formal_obligation.metadata.get("decisive")
                ],
                kill_criteria=[
                    "Pivot if no nontrivial bridge, closure, or descent probe can be stated without smuggling Collatz.",
                    "Pivot if all hard probes reduce to proving global termination directly.",
                    "Pivot if Aristotle only proves controls while every decisive probe remains sorry/blocked with no smaller missing lemma.",
                    "Pivot if the promoted world cannot define an interpretation map from Nat plus a one-step simulation lemma.",
                ],
                pursue_criteria=[
                    "Pursue if at least one decisive bridge/closure/descent probe is proved or reduced to a strictly smaller named lemma.",
                    "Pursue if failure diagnostics identify a concrete missing invariant sharper than Collatz itself.",
                    "Pursue if the world produces a non-circular rank, certificate, inverse-tree, or grammar obstruction statement.",
                ],
                expected_learning=[
                    "Whether the promoted world has more than Lean-clean scaffolding.",
                    "Whether the exact obstruction is bridge, descent/ranking, positivity, inverse-tree coverage, or anti-smuggling.",
                    "Whether the next search should mutate this world or abandon the family.",
                ],
                summary=(
                    "Final Collatz experiment compiled hard bridge/closure/descent probes. "
                    "This run is a decision gate, not a solve declaration."
                ),
            )
            self.memory.upsert_research_node(
                campaign_id=campaign_id,
                node_id=run.id,
                node_type="FinalCollatzExperimentRun",
                title=f"final-collatz-experiment:{world_id}",
                summary=run.summary,
                status=run.decision_status,
                payload=run.model_dump(mode="json"),
            )
            self.memory.add_event(
                campaign_id=campaign_id,
                tick=campaign.tick_count,
                event_type="final_collatz_experiment_compiled",
                payload=run.model_dump(mode="json"),
            )
            return run

    def run_rank_certificate_hunt(
        self,
        campaign_id: str,
        payload: RankCertificateHuntRequest,
    ) -> RankCertificateHuntRun:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            world_payload = campaign.current_world_program or {}
            world_id = payload.world_id or campaign.active_world_id or world_payload.get("id")
            if not world_id:
                raise KeyError("No promoted world is available for rank/certificate hunt.")
            world_label = world_payload.get("label") or world_id
            probes = self._compile_rank_certificate_probes(
                world_id=world_id,
                max_probes=payload.max_probes,
                include_naive_rank_falsifiers=payload.include_naive_rank_falsifiers,
            )
            for probe in probes:
                self.memory.upsert_research_node(
                    campaign_id=campaign_id,
                    node_id=probe.id,
                    node_type="FormalProbe",
                    title=f"rank-hunt:{probe.probe_type}:{world_id}",
                    summary=probe.source_text,
                    status=probe.status,
                    payload=probe.model_dump(mode="json"),
                )
            run = RankCertificateHuntRun(
                campaign_id=campaign_id,
                world_id=world_id,
                world_label=world_label,
                compiled_probe_count=len(probes),
                probe_ids=[probe.id for probe in probes],
                decisive_probe_ids=[
                    probe.id
                    for probe in probes
                    if probe.formal_obligation.metadata.get("decisive")
                ],
                rank_questions=[
                    "Which naive ranks fail immediately, and why?",
                    "Can a candidate certificate be stated without using eventual reachability?",
                    "Can a strict descent object be separated from the original Collatz theorem?",
                    "Does the next missing lemma look smaller than Collatz or equivalent to it?",
                ],
                expected_learning=[
                    "A concrete obstruction for identity/parity/simple-rank families.",
                    "A formal skeleton for certificate soundness.",
                    "Whether the non-circular rank-existence problem is the next bottleneck.",
                ],
                summary=(
                    "Rank/certificate hunt compiled probes that falsify naive ranks and "
                    "force a non-circular descent certificate candidate."
                ),
            )
            self.memory.upsert_research_node(
                campaign_id=campaign_id,
                node_id=run.id,
                node_type="RankCertificateHuntRun",
                title=f"rank-certificate-hunt:{world_id}",
                summary=run.summary,
                status=run.decision_status,
                payload=run.model_dump(mode="json"),
            )
            self.memory.add_event(
                campaign_id=campaign_id,
                tick=campaign.tick_count,
                event_type="rank_certificate_hunt_compiled",
                payload=run.model_dump(mode="json"),
            )
            return run

    def run_candidate_rank_families(
        self,
        campaign_id: str,
        payload: CandidateRankFamilyRequest,
    ) -> CandidateRankFamilyRun:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            world_payload = campaign.current_world_program or {}
            world_id = payload.world_id or campaign.active_world_id or world_payload.get("id")
            if not world_id:
                raise KeyError("No promoted world is available for candidate rank family hunt.")
            world_label = world_payload.get("label") or world_id
            probes = self._compile_candidate_rank_family_probes(
                world_id=world_id,
                max_probes=payload.max_probes,
            )
            for probe in probes:
                self.memory.upsert_research_node(
                    campaign_id=campaign_id,
                    node_id=probe.id,
                    node_type="FormalProbe",
                    title=f"candidate-rank:{probe.probe_type}:{world_id}",
                    summary=probe.source_text,
                    status=probe.status,
                    payload=probe.model_dump(mode="json"),
                )
            run = CandidateRankFamilyRun(
                campaign_id=campaign_id,
                world_id=world_id,
                world_label=world_label,
                compiled_probe_count=len(probes),
                probe_ids=[probe.id for probe in probes],
                candidate_families=[
                    "identity rank",
                    "two-step identity rank",
                    "linear parity penalty rank",
                    "bounded certificate",
                    "local certificate transformer with base preconditions",
                ],
                expected_learning=[
                    "Which simple rank families fail by explicit small witnesses.",
                    "Whether bounded certificates remain sound when separated from global reachability.",
                    "What preconditions a local certificate transformer needs before it is non-vacuous.",
                ],
                summary=(
                    "Candidate rank-family gauntlet compiled concrete probes that should either "
                    "prove local soundness or fail with small counterexamples."
                ),
            )
            self.memory.upsert_research_node(
                campaign_id=campaign_id,
                node_id=run.id,
                node_type="CandidateRankFamilyRun",
                title=f"candidate-rank-family:{world_id}",
                summary=run.summary,
                status=run.decision_status,
                payload=run.model_dump(mode="json"),
            )
            self.memory.add_event(
                campaign_id=campaign_id,
                tick=campaign.tick_count,
                event_type="candidate_rank_family_compiled",
                payload=run.model_dump(mode="json"),
            )
            return run

    def run_structured_rank_families(
        self,
        campaign_id: str,
        payload: StructuredRankFamilyRequest,
    ) -> StructuredRankFamilyRun:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            world_payload = campaign.current_world_program or {}
            world_id = payload.world_id or campaign.active_world_id or world_payload.get("id")
            if not world_id:
                raise KeyError("No promoted world is available for structured rank family hunt.")
            world_label = world_payload.get("label") or world_id
            probes = self._compile_structured_rank_family_probes(
                world_id=world_id,
                max_probes=payload.max_probes,
            )
            for probe in probes:
                self.memory.upsert_research_node(
                    campaign_id=campaign_id,
                    node_id=probe.id,
                    node_type="FormalProbe",
                    title=f"structured-rank:{probe.probe_type}:{world_id}",
                    summary=probe.source_text,
                    status=probe.status,
                    payload=probe.model_dump(mode="json"),
                )
            run = StructuredRankFamilyRun(
                campaign_id=campaign_id,
                world_id=world_id,
                world_label=world_label,
                compiled_probe_count=len(probes),
                probe_ids=[probe.id for probe in probes],
                decisive_probe_ids=[
                    probe.id
                    for probe in probes
                    if probe.formal_obligation.metadata.get("decisive")
                ],
                structured_families=[
                    "accelerated odd-map potential",
                    "residue-class potential",
                    "inverse-tree certificate",
                    "parity-word grammar rank",
                    "2-adic shadow measure",
                ],
                expected_learning=[
                    "Whether richer nonlocal families outperform simple size-based ranks.",
                    "Which structured family yields the sharpest small witness or local bridge lemma.",
                    "Whether the next missing object looks like a grammar/certificate/inverse-tree invariant instead of a scalar rank.",
                ],
                summary=(
                    "Structured rank-family hunt compiled richer probes around accelerated odd-map, "
                    "residue, inverse-tree, parity grammar, and 2-adic families."
                ),
            )
            self.memory.upsert_research_node(
                campaign_id=campaign_id,
                node_id=run.id,
                node_type="StructuredRankFamilyRun",
                title=f"structured-rank-family:{world_id}",
                summary=run.summary,
                status=run.decision_status,
                payload=run.model_dump(mode="json"),
            )
            self.memory.add_event(
                campaign_id=campaign_id,
                tick=campaign.tick_count,
                event_type="structured_rank_family_compiled",
                payload=run.model_dump(mode="json"),
            )
            return run

    def run_hybrid_certificate_families(
        self,
        campaign_id: str,
        payload: HybridCertificateFamilyRequest,
    ) -> HybridCertificateFamilyRun:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            world_payload = campaign.current_world_program or {}
            world_id = payload.world_id or campaign.active_world_id or world_payload.get("id")
            if not world_id:
                raise KeyError("No promoted world is available for hybrid certificate hunt.")
            world_label = world_payload.get("label") or world_id
            probes = self._compile_hybrid_certificate_family_probes(
                world_id=world_id,
                max_probes=payload.max_probes,
            )
            for probe in probes:
                self.memory.upsert_research_node(
                    campaign_id=campaign_id,
                    node_id=probe.id,
                    node_type="FormalProbe",
                    title=f"hybrid-certificate:{probe.probe_type}:{world_id}",
                    summary=probe.source_text,
                    status=probe.status,
                    payload=probe.model_dump(mode="json"),
                )
            run = HybridCertificateFamilyRun(
                campaign_id=campaign_id,
                world_id=world_id,
                world_label=world_label,
                compiled_probe_count=len(probes),
                probe_ids=[probe.id for probe in probes],
                decisive_probe_ids=[
                    probe.id
                    for probe in probes
                    if probe.formal_obligation.metadata.get("decisive")
                ],
                hybrid_families=[
                    "inverse-tree witness transport",
                    "parity-word trace grammar",
                    "residue and valuation tags",
                    "bounded hybrid certificates",
                    "coarse hybrid signature collision tests",
                ],
                expected_learning=[
                    "Whether hybrid structural certificates carry more leverage than scalar or single-family summaries.",
                    "Whether coarse inverse-tree/parity/residue summaries still collapse distinct dynamics.",
                    "Whether the next missing object should be a certificate calculus instead of a numeric rank.",
                ],
                summary=(
                    "Hybrid certificate hunt compiled probes that combine inverse-tree structure, "
                    "parity traces, and residue/valuation tags into one candidate certificate language."
                ),
            )
            self.memory.upsert_research_node(
                campaign_id=campaign_id,
                node_id=run.id,
                node_type="HybridCertificateFamilyRun",
                title=f"hybrid-certificate-family:{world_id}",
                summary=run.summary,
                status=run.decision_status,
                payload=run.model_dump(mode="json"),
            )
            self.memory.add_event(
                campaign_id=campaign_id,
                tick=campaign.tick_count,
                event_type="hybrid_certificate_family_compiled",
                payload=run.model_dump(mode="json"),
            )
            return run

    def run_compositional_certificate_families(
        self,
        campaign_id: str,
        payload: CompositionalCertificateFamilyRequest,
    ) -> CompositionalCertificateFamilyRun:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            world_payload = campaign.current_world_program or {}
            world_id = payload.world_id or campaign.active_world_id or world_payload.get("id")
            if not world_id:
                raise KeyError("No promoted world is available for compositional certificate hunt.")
            world_label = world_payload.get("label") or world_id
            probes = self._compile_compositional_certificate_family_probes(
                world_id=world_id,
                max_probes=payload.max_probes,
            )
            for probe in probes:
                self.memory.upsert_research_node(
                    campaign_id=campaign_id,
                    node_id=probe.id,
                    node_type="FormalProbe",
                    title=f"compositional-certificate:{probe.probe_type}:{world_id}",
                    summary=probe.source_text,
                    status=probe.status,
                    payload=probe.model_dump(mode="json"),
                )
            run = CompositionalCertificateFamilyRun(
                campaign_id=campaign_id,
                world_id=world_id,
                world_label=world_label,
                compiled_probe_count=len(probes),
                probe_ids=[probe.id for probe in probes],
                decisive_probe_ids=[
                    probe.id
                    for probe in probes
                    if probe.formal_obligation.metadata.get("decisive")
                ],
                composition_families=[
                    "certificate extension",
                    "certificate composition",
                    "parity-block grammar",
                    "normal-form pruning",
                    "well-founded certificate complexity",
                    "coverage anti-smuggling gates",
                ],
                expected_learning=[
                    "Whether local hybrid certificates compose into longer certified structure.",
                    "Whether pruning or normalization exposes a decreasing certificate complexity measure.",
                    "Whether the missing object is a real coverage theorem or just bounded reachability renamed.",
                ],
                summary=(
                    "Compositional certificate hunt compiled probes that test whether the verified "
                    "local hybrid language can extend, compose, prune, and decrease without smuggling reachability."
                ),
            )
            self.memory.upsert_research_node(
                campaign_id=campaign_id,
                node_id=run.id,
                node_type="CompositionalCertificateFamilyRun",
                title=f"compositional-certificate-family:{world_id}",
                summary=run.summary,
                status=run.decision_status,
                payload=run.model_dump(mode="json"),
            )
            self.memory.add_event(
                campaign_id=campaign_id,
                tick=campaign.tick_count,
                event_type="compositional_certificate_family_compiled",
                payload=run.model_dump(mode="json"),
            )
            return run

    def run_coverage_normalization_hunt(
        self,
        campaign_id: str,
        payload: CoverageNormalizationHuntRequest,
    ) -> CoverageNormalizationHuntRun:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            world_payload = campaign.current_world_program or {}
            world_id = payload.world_id or campaign.active_world_id or world_payload.get("id")
            if not world_id:
                raise KeyError("No promoted world is available for coverage normalization hunt.")
            world_label = world_payload.get("label") or world_id
            probes = self._compile_coverage_normalization_hunt_probes(
                world_id=world_id,
                max_probes=payload.max_probes,
            )
            for probe in probes:
                self.memory.upsert_research_node(
                    campaign_id=campaign_id,
                    node_id=probe.id,
                    node_type="FormalProbe",
                    title=f"coverage-normalization:{probe.probe_type}:{world_id}",
                    summary=probe.source_text,
                    status=probe.status,
                    payload=probe.model_dump(mode="json"),
                )
            run = CoverageNormalizationHuntRun(
                campaign_id=campaign_id,
                world_id=world_id,
                world_label=world_label,
                compiled_probe_count=len(probes),
                probe_ids=[probe.id for probe in probes],
                decisive_probe_ids=[
                    probe.id
                    for probe in probes
                    if probe.formal_obligation.metadata.get("decisive")
                ],
                coverage_families=[
                    "admissible parity/residue blocks",
                    "pruning subblock detection",
                    "extension closure",
                    "obstruction families",
                    "coverage anti-smuggling",
                    "density-weakened coverage gate",
                ],
                expected_learning=[
                    "Whether the current lineage can state a non-circular global coverage theorem.",
                    "Whether admissible blocks expose recurring pruning rather than isolated examples.",
                    "Whether failure should pivot to Tao-informed density, inverse-tree normal forms, or counterexample ecology.",
                ],
                summary=(
                    "Coverage-normalization hunt compiled final decision-gate probes for whether "
                    "hybrid certificates can support a global coverage/pruning theorem."
                ),
            )
            self.memory.upsert_research_node(
                campaign_id=campaign_id,
                node_id=run.id,
                node_type="CoverageNormalizationHuntRun",
                title=f"coverage-normalization-hunt:{world_id}",
                summary=run.summary,
                status=run.decision_status,
                payload=run.model_dump(mode="json"),
            )
            self.memory.add_event(
                campaign_id=campaign_id,
                tick=campaign.tick_count,
                event_type="coverage_normalization_hunt_compiled",
                payload=run.model_dump(mode="json"),
            )
            return run

    def run_cylinder_pressure_wave(
        self,
        campaign_id: str,
        payload: CylinderPressureWaveRequest,
    ) -> CylinderPressureWaveRun:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            world_payload = campaign.current_world_program or {}
            world_id = payload.world_id or campaign.active_world_id or world_payload.get("id")
            if not world_id:
                raise KeyError("No promoted world is available for cylinder pressure wave.")
            world_label = world_payload.get("label") or world_id
            probes = self._compile_cylinder_pressure_wave_probes(
                world_id=world_id,
                max_probes=payload.max_probes,
            )
            for probe in probes:
                self.memory.upsert_research_node(
                    campaign_id=campaign_id,
                    node_id=probe.id,
                    node_type="FormalProbe",
                    title=f"cylinder-pressure:{probe.probe_type}:{world_id}",
                    summary=probe.source_text,
                    status=probe.status,
                    payload=probe.model_dump(mode="json"),
                )
            run = CylinderPressureWaveRun(
                campaign_id=campaign_id,
                world_id=world_id,
                world_label=world_label,
                compiled_probe_count=len(probes),
                probe_ids=[probe.id for probe in probes],
                decisive_probe_ids=[
                    probe.id
                    for probe in probes
                    if probe.formal_obligation.metadata.get("decisive")
                ],
                pressure_families=[
                    "2-adic residue cylinders",
                    "dynamic parity admissibility",
                    "affine block transport",
                    "pressure accounting",
                    "legal refinement / split",
                    "density-style bad cylinder gates",
                ],
                expected_learning=[
                    "Whether dynamic admissibility can replace forced syntactic extension.",
                    "Whether pressure on residue cylinders gives a non-scalar global object.",
                    "Whether bad cylinders can be stated as a measurable shrinking family rather than local certificates.",
                ],
                summary=(
                    "Cylinder pressure wave compiled probes for a new 2-adic world where "
                    "legal residue cylinders, affine block transport, and pressure replace local certificate syntax."
                ),
            )
            self.memory.upsert_research_node(
                campaign_id=campaign_id,
                node_id=run.id,
                node_type="CylinderPressureWaveRun",
                title=f"cylinder-pressure-wave:{world_id}",
                summary=run.summary,
                status=run.decision_status,
                payload=run.model_dump(mode="json"),
            )
            self.memory.add_event(
                campaign_id=campaign_id,
                tick=campaign.tick_count,
                event_type="cylinder_pressure_wave_compiled",
                payload=run.model_dump(mode="json"),
            )
            return run

    def run_pressure_globalization_wave(
        self,
        campaign_id: str,
        payload: PressureGlobalizationWaveRequest,
    ) -> PressureGlobalizationWaveRun:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            world_payload = campaign.current_world_program or {}
            world_id = payload.world_id or campaign.active_world_id or world_payload.get("id")
            if not world_id:
                raise KeyError("No promoted world is available for pressure globalization wave.")
            world_label = world_payload.get("label") or world_id
            probes = self._compile_pressure_globalization_wave_probes(
                world_id=world_id,
                max_probes=payload.max_probes,
            )
            for probe in probes:
                self.memory.upsert_research_node(
                    campaign_id=campaign_id,
                    node_id=probe.id,
                    node_type="FormalProbe",
                    title=f"pressure-globalization:{probe.probe_type}:{world_id}",
                    summary=probe.source_text,
                    status=probe.status,
                    payload=probe.model_dump(mode="json"),
                )
            run = PressureGlobalizationWaveRun(
                campaign_id=campaign_id,
                world_id=world_id,
                world_label=world_label,
                compiled_probe_count=len(probes),
                probe_ids=[probe.id for probe in probes],
                decisive_probe_ids=[
                    probe.id
                    for probe in probes
                    if probe.formal_obligation.metadata.get("decisive")
                ],
                globalization_families=[
                    "legal split trees",
                    "bad-cylinder mass accounting",
                    "pressure recovery blocks",
                    "bad descendant scarcity gates",
                    "density-zero target statements",
                ],
                expected_learning=[
                    "Whether cylinder pressure has a real mass-decay theorem shape.",
                    "Whether bad all-odd blocks can recover pressure after legal even refinements.",
                    "Whether the next target is density-zero scarcity rather than pointwise descent.",
                ],
                summary=(
                    "Pressure globalization wave compiled probes for legal split trees, bad-cylinder "
                    "mass accounting, pressure recovery, and density-zero exceptional-family targets."
                ),
            )
            self.memory.upsert_research_node(
                campaign_id=campaign_id,
                node_id=run.id,
                node_type="PressureGlobalizationWaveRun",
                title=f"pressure-globalization-wave:{world_id}",
                summary=run.summary,
                status=run.decision_status,
                payload=run.model_dump(mode="json"),
            )
            self.memory.add_event(
                campaign_id=campaign_id,
                tick=campaign.tick_count,
                event_type="pressure_globalization_wave_compiled",
                payload=run.model_dump(mode="json"),
            )
            return run

    def run_pivot_portfolio_wave(
        self,
        campaign_id: str,
        payload: PivotPortfolioWaveRequest,
    ) -> PivotPortfolioWaveRun:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            world_payload = campaign.current_world_program or {}
            world_id = payload.world_id or campaign.active_world_id or world_payload.get("id")
            if not world_id:
                raise KeyError("No promoted world is available for pivot portfolio wave.")
            world_label = world_payload.get("label") or world_id
            probes = self._compile_pivot_portfolio_wave_probes(
                world_id=world_id,
                max_probes=payload.max_probes,
            )
            for probe in probes:
                self.memory.upsert_research_node(
                    campaign_id=campaign_id,
                    node_id=probe.id,
                    node_type="FormalProbe",
                    title=f"pivot-portfolio:{probe.probe_type}:{world_id}",
                    summary=probe.source_text,
                    status=probe.status,
                    payload=probe.model_dump(mode="json"),
                )
            run = PivotPortfolioWaveRun(
                campaign_id=campaign_id,
                world_id=world_id,
                world_label=world_label,
                compiled_probe_count=len(probes),
                probe_ids=[probe.id for probe in probes],
                decisive_probe_ids=[
                    probe.id
                    for probe in probes
                    if probe.formal_obligation.metadata.get("decisive")
                ],
                pivot_families=[
                    "pressure scarcity",
                    "inverse-tree dynamic admissibility",
                    "minimal-counterexample ecology",
                    "Tao-style density transport",
                    "cross-lane bridge / separation gates",
                ],
                expected_learning=[
                    "Which pivot family exposes the smallest non-circular theorem target.",
                    "Whether pressure scarcity still dominates once compared against other global mechanisms.",
                    "Whether any alternative family produces sharper anti-smuggling or falsifier gates.",
                    "Whether the strongest lanes bridge into one shared theorem or remain separate pivots.",
                ],
                summary=(
                    "Pivot portfolio wave compiled verification-first decision probes across "
                    "pressure scarcity, inverse-tree admissibility, minimal-counterexample ecology, "
                    "Tao-style density transport, and cross-lane bridge/separation gates."
                ),
            )
            self.memory.upsert_research_node(
                campaign_id=campaign_id,
                node_id=run.id,
                node_type="PivotPortfolioWaveRun",
                title=f"pivot-portfolio-wave:{world_id}",
                summary=run.summary,
                status=run.decision_status,
                payload=run.model_dump(mode="json"),
            )
            self.memory.add_event(
                campaign_id=campaign_id,
                tick=campaign.tick_count,
                event_type="pivot_portfolio_wave_compiled",
                payload=run.model_dump(mode="json"),
            )
            return run

    def run_composite_scarcity_viability_wave(
        self,
        campaign_id: str,
        payload: CompositeScarcityViabilityWaveRequest,
    ) -> CompositeScarcityViabilityWaveRun:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            world_payload = campaign.current_world_program or {}
            world_id = payload.world_id or campaign.active_world_id or world_payload.get("id")
            if not world_id:
                raise KeyError("No promoted world is available for composite scarcity viability wave.")
            world_label = world_payload.get("label") or world_id
            probes = self._compile_composite_scarcity_viability_wave_probes(
                world_id=world_id,
                max_probes=payload.max_probes,
            )
            for probe in probes:
                self.memory.upsert_research_node(
                    campaign_id=campaign_id,
                    node_id=probe.id,
                    node_type="FormalProbe",
                    title=f"composite-scarcity-viability:{probe.probe_type}:{world_id}",
                    summary=probe.source_text,
                    status=probe.status,
                    payload=probe.model_dump(mode="json"),
                )
            run = CompositeScarcityViabilityWaveRun(
                campaign_id=campaign_id,
                world_id=world_id,
                world_label=world_label,
                compiled_probe_count=len(probes),
                probe_ids=[probe.id for probe in probes],
                decisive_probe_ids=[
                    probe.id
                    for probe in probes
                    if probe.formal_obligation.metadata.get("decisive")
                ],
                viability_gates=[
                    "exact composite scarcity statement",
                    "scarcity implies density-zero target",
                    "density-zero plus no survivor implies final obstruction removal",
                    "anti-smuggling / no reachability field",
                    "small legal frontier counterexample gate",
                    "restricted quantitative decay inequality",
                    "minimal-survivor reduction gate",
                    "weak scarcity insufficiency gate",
                ],
                expected_learning=[
                    "Whether the pressure-density-ecology route has a smaller named theorem shape.",
                    "Whether the implication chain can be stated without reachesOne or termination smuggling.",
                    "Whether a restricted quantitative scarcity inequality is already formalizable.",
                    "Whether weak scarcity is insufficient, forcing a sharper theorem or a pivot.",
                ],
                summary=(
                    "Composite scarcity viability wave compiled kill-or-promote probes for the "
                    "pressure scarcity -> density decay -> no persistent minimal survivor route."
                ),
            )
            self.memory.upsert_research_node(
                campaign_id=campaign_id,
                node_id=run.id,
                node_type="CompositeScarcityViabilityWaveRun",
                title=f"composite-scarcity-viability-wave:{world_id}",
                summary=run.summary,
                status=run.decision_status,
                payload=run.model_dump(mode="json"),
            )
            self.memory.add_event(
                campaign_id=campaign_id,
                tick=campaign.tick_count,
                event_type="composite_scarcity_viability_wave_compiled",
                payload=run.model_dump(mode="json"),
            )
            return run

    def run_composite_scarcity_theorem_wave(
        self,
        campaign_id: str,
        payload: CompositeScarcityTheoremWaveRequest,
    ) -> CompositeScarcityTheoremWaveRun:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            world_payload = campaign.current_world_program or {}
            world_id = payload.world_id or campaign.active_world_id or world_payload.get("id")
            if not world_id:
                raise KeyError("No promoted world is available for composite scarcity theorem wave.")
            world_label = world_payload.get("label") or world_id
            probes = self._compile_composite_scarcity_theorem_wave_probes(
                world_id=world_id,
                max_probes=payload.max_probes,
            )
            for probe in probes:
                self.memory.upsert_research_node(
                    campaign_id=campaign_id,
                    node_id=probe.id,
                    node_type="FormalProbe",
                    title=f"composite-scarcity-theorem:{probe.probe_type}:{world_id}",
                    summary=probe.source_text,
                    status=probe.status,
                    payload=probe.model_dump(mode="json"),
                )
            run = CompositeScarcityTheoremWaveRun(
                campaign_id=campaign_id,
                world_id=world_id,
                world_label=world_label,
                compiled_probe_count=len(probes),
                probe_ids=[probe.id for probe in probes],
                decisive_probe_ids=[
                    probe.id
                    for probe in probes
                    if probe.formal_obligation.metadata.get("decisive")
                ],
                theorem_gates=[
                    "parameterized strong scarcity implies subcritical bad mass",
                    "depth-indexed scarcity projects to density contraction",
                    "bounded recovery arithmetic beats odd debt",
                    "weak recovery and weak scarcity are insufficient",
                    "composite step closes from density improvement or survivor descent",
                    "survivor descent forbids persistent self-loop obstruction",
                    "adversarial neutral frontier remains a real obstruction",
                    "named theorem skeleton has no reachability field",
                ],
                expected_learning=[
                    "Whether the next route has nontrivial parameterized scarcity/recovery lemmas.",
                    "Whether weak versions fail in Lean-clean ways, preventing false optimism.",
                    "Whether survivor obstruction reduction can close the minimal-counterexample loophole.",
                    "Whether this is ready for a real Composite Scarcity Theorem attempt or should pivot.",
                ],
                summary=(
                    "Composite scarcity theorem wave compiled parameterized scarcity, recovery, "
                    "survivor-descent, and adversarial insufficiency probes."
                ),
            )
            self.memory.upsert_research_node(
                campaign_id=campaign_id,
                node_id=run.id,
                node_type="CompositeScarcityTheoremWaveRun",
                title=f"composite-scarcity-theorem-wave:{world_id}",
                summary=run.summary,
                status=run.decision_status,
                payload=run.model_dump(mode="json"),
            )
            self.memory.add_event(
                campaign_id=campaign_id,
                tick=campaign.tick_count,
                event_type="composite_scarcity_theorem_wave_compiled",
                payload=run.model_dump(mode="json"),
            )
            return run

    def run_global_forcing_hunt_wave(
        self,
        campaign_id: str,
        payload: GlobalForcingHuntWaveRequest,
    ) -> GlobalForcingHuntWaveRun:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            world_payload = campaign.current_world_program or {}
            world_id = payload.world_id or campaign.active_world_id or world_payload.get("id")
            if not world_id:
                raise KeyError("No promoted world is available for global forcing hunt wave.")
            world_label = world_payload.get("label") or world_id
            probes = self._compile_global_forcing_hunt_wave_probes(
                world_id=world_id,
                max_probes=payload.max_probes,
            )
            for probe in probes:
                self.memory.upsert_research_node(
                    campaign_id=campaign_id,
                    node_id=probe.id,
                    node_type="FormalProbe",
                    title=f"global-forcing-hunt:{probe.probe_type}:{world_id}",
                    summary=probe.source_text,
                    status=probe.status,
                    payload=probe.model_dump(mode="json"),
                )
            run = GlobalForcingHuntWaveRun(
                campaign_id=campaign_id,
                world_id=world_id,
                world_label=world_label,
                compiled_probe_count=len(probes),
                probe_ids=[probe.id for probe in probes],
                decisive_probe_ids=[
                    probe.id
                    for probe in probes
                    if probe.formal_obligation.metadata.get("decisive")
                ],
                forcing_gates=[
                    "explicit dynamic alternatives force local progress",
                    "bounded finite candidate search passes",
                    "all-odd bad block needs recovery margin",
                    "legal persistent bad frontier exists without dynamic forcing",
                    "weak scarcity and equal recovery remain insufficient",
                    "persistent bad frontier decomposes into the three missing failures",
                    "finite persistent-bad exclusion over repaired candidates",
                    "named global forcing target remains counting-only",
                ],
                expected_learning=[
                    "Whether bounded-horizon forcing survives a first adversarial finite search.",
                    "Whether the theorem needs genuinely dynamic admissibility beyond static legality.",
                    "Whether persistent bad frontiers expose a smaller obstruction or kill the route.",
                    "Whether the next proof should target dynamic forcing rather than more local algebra.",
                ],
                summary=(
                    "Global forcing hunt wave compiled adversarial bounded-horizon probes for "
                    "Composite Scarcity: finite search, recovery margins, persistent bad frontiers, "
                    "and counting-only target shape."
                ),
            )
            self.memory.upsert_research_node(
                campaign_id=campaign_id,
                node_id=run.id,
                node_type="GlobalForcingHuntWaveRun",
                title=f"global-forcing-hunt-wave:{world_id}",
                summary=run.summary,
                status=run.decision_status,
                payload=run.model_dump(mode="json"),
            )
            self.memory.add_event(
                campaign_id=campaign_id,
                tick=campaign.tick_count,
                event_type="global_forcing_hunt_wave_compiled",
                payload=run.model_dump(mode="json"),
            )
            return run

    def run_dynamic_admissibility_compass_wave(
        self,
        campaign_id: str,
        payload: DynamicAdmissibilityCompassWaveRequest,
    ) -> DynamicAdmissibilityCompassWaveRun:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            world_payload = campaign.current_world_program or {}
            world_id = payload.world_id or campaign.active_world_id or world_payload.get("id")
            if not world_id:
                raise KeyError("No promoted world is available for dynamic admissibility compass wave.")
            world_label = world_payload.get("label") or world_id
            probes = self._compile_dynamic_admissibility_compass_wave_probes(
                world_id=world_id,
                max_probes=payload.max_probes,
            )
            for probe in probes:
                self.memory.upsert_research_node(
                    campaign_id=campaign_id,
                    node_id=probe.id,
                    node_type="FormalProbe",
                    title=f"dynamic-admissibility-compass:{probe.probe_type}:{world_id}",
                    summary=probe.source_text,
                    status=probe.status,
                    payload=probe.model_dump(mode="json"),
                )
            run = DynamicAdmissibilityCompassWaveRun(
                campaign_id=campaign_id,
                world_id=world_id,
                world_label=world_label,
                compiled_probe_count=len(probes),
                probe_ids=[probe.id for probe in probes],
                decisive_probe_ids=[
                    probe.id
                    for probe in probes
                    if probe.formal_obligation.metadata.get("decisive")
                ],
                compass_gates=[
                    "actual Collatz odd-even blocks force recovery",
                    "fake all-odd and equal-recovery blocks are dynamically rejected",
                    "dynamic blocks project to forcing progress",
                    "bounded real-block search has no persistent bad candidate",
                    "dynamic bridge target remains counting-only",
                ],
                pivot_sentinels=[
                    "static persistent bad frontiers still exist without dynamic witnesses",
                    "density-only closure does not remove survivor obstruction",
                    "parity tags alone do not imply dynamic admissibility",
                    "weak scarcity remains insufficient without a dynamic bridge",
                    "survivor drop is a separate forcing exit",
                ],
                expected_learning=[
                    "Whether actual Collatz transition data kills the fake persistent bad frontiers.",
                    "Whether the current route needs a fourth forcing exit or only stronger dynamic admissibility.",
                    "Whether density-only, inverse-tree-only, or parity-tag-only pivots are insufficient.",
                    "where to pivot next if the bridge fails, based on the verified obstruction.",
                ],
                summary=(
                    "Dynamic admissibility compass wave compiled bridge probes from true Collatz "
                    "transition data to forcing alternatives, plus pivot sentinels for density-only, "
                    "static-frontier, and parity-tag failure modes."
                ),
            )
            self.memory.upsert_research_node(
                campaign_id=campaign_id,
                node_id=run.id,
                node_type="DynamicAdmissibilityCompassWaveRun",
                title=f"dynamic-admissibility-compass-wave:{world_id}",
                summary=run.summary,
                status=run.decision_status,
                payload=run.model_dump(mode="json"),
            )
            self.memory.add_event(
                campaign_id=campaign_id,
                tick=campaign.tick_count,
                event_type="dynamic_admissibility_compass_wave_compiled",
                payload=run.model_dump(mode="json"),
            )
            return run

    def run_dynamic_pressure_automaton_wave(
        self,
        campaign_id: str,
        payload: DynamicPressureAutomatonWaveRequest,
    ) -> DynamicPressureAutomatonWaveRun:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            world_payload = campaign.current_world_program or {}
            world_id = payload.world_id or campaign.active_world_id or world_payload.get("id")
            if not world_id:
                raise KeyError("No promoted world is available for dynamic pressure automaton wave.")
            world_label = world_payload.get("label") or world_id
            reports = [
                analyze_dynamic_pressure_automaton(
                    window=window,
                    modulus_bits=max(2, window + payload.modulus_extra_bits),
                )
                for window in range(1, payload.max_window + 1)
            ]
            height_reports = [
                analyze_height_lifted_pressure_automaton(
                    window=window,
                    modulus_bits=max(2, window + payload.modulus_extra_bits),
                )
                for window in range(1, payload.max_window + 1)
            ]
            probes = self._compile_dynamic_pressure_automaton_wave_probes(
                world_id=world_id,
                reports=reports,
                height_reports=height_reports,
                max_probes=payload.max_probes,
            )
            for probe in probes:
                self.memory.upsert_research_node(
                    campaign_id=campaign_id,
                    node_id=probe.id,
                    node_type="FormalProbe",
                    title=f"dynamic-pressure-automaton:{probe.probe_type}:{world_id}",
                    summary=probe.source_text,
                    status=probe.status,
                    payload=probe.model_dump(mode="json"),
                )
            first_cycle = next((report for report in reports if report["cycle_found"]), None)
            if first_cycle:
                obstruction_summary = (
                    f"First bad cycle at window={first_cycle['window']} "
                    f"modulus_bits={first_cycle['modulus_bits']}: "
                    f"{first_cycle.get('ghost_family') or 'unclassified residue cycle'}."
                )
            else:
                obstruction_summary = "No bad cycles found in the requested residue over-approximations."
            dangerous_height = [
                report
                for report in height_reports
                if report["decision"] == "dangerous_nonexpanding_bad_cycle_found"
            ]
            unchecked_height = [
                report
                for report in height_reports
                if report["decision"] == "needs_larger_exact_scc_check"
            ]
            expanding_height = [
                report
                for report in height_reports
                if report["decision"] == "all_checked_bad_cycles_height_expanding"
            ]
            if dangerous_height:
                height_gate_summary = (
                    "Height gate found a nonexpanding recurrent bad component; "
                    "pressure plus height is not enough at the checked horizon."
                )
            elif unchecked_height:
                height_gate_summary = (
                    "Height gate has unchecked large recurrent components; increase exact SCC bounds "
                    "before promoting this signal."
                )
            elif expanding_height:
                height_gate_summary = (
                    "All checked recurrent bad components are height-expanding; pure pressure ghosts "
                    "now point to a pressure-plus-height bridge."
                )
            else:
                height_gate_summary = "No recurrent bad components survived the pressure gate."
            run = DynamicPressureAutomatonWaveRun(
                campaign_id=campaign_id,
                world_id=world_id,
                world_label=world_label,
                compiled_probe_count=len(probes),
                probe_ids=[probe.id for probe in probes],
                automaton_reports=reports,
                height_lift_reports=height_reports,
                automaton_gates=[
                    "sound finite residue relation with hidden high-bit even splits",
                    "integer pressure surrogate 8 * odd < 5 * even",
                    "bad-subgraph cycle search before theorem investment",
                    "acyclic reports produce rank-certificate shape",
                    "cycle reports produce obstruction witnesses",
                    "height lift classifies recurrent bad components by Archimedean drift",
                ],
                decisive_probe_ids=[
                    probe.id
                    for probe in probes
                    if probe.formal_obligation.metadata.get("decisive")
                ],
                expected_learning=[
                    "Whether pure dynamic pressure already has a finite no-bad-cycle certificate.",
                    "Whether residue dynamics exposes 2-adic ghost cycles that require an Archimedean side condition.",
                    "Which horizons deserve Aristotle replay as certificates rather than hand-picked probes.",
                    "Whether the roadmap should chase pressure alone or pressure plus positive-integer height.",
                ],
                obstruction_summary=obstruction_summary,
                height_gate_summary=height_gate_summary,
                summary=(
                    "Dynamic pressure automaton wave enumerated the sound Collatz residue relation, "
                    "searched the bad-pressure subgraph for cycles, classified recurrent components "
                    "by height drift, and compiled Lean probes for the pressure rule plus discovered "
                    "residue/height obstructions."
                ),
            )
            self.memory.upsert_research_node(
                campaign_id=campaign_id,
                node_id=run.id,
                node_type="DynamicPressureAutomatonWaveRun",
                title=f"dynamic-pressure-automaton-wave:{world_id}",
                summary=run.summary,
                status=run.decision_status,
                payload=run.model_dump(mode="json"),
            )
            self.memory.add_event(
                campaign_id=campaign_id,
                tick=campaign.tick_count,
                event_type="dynamic_pressure_automaton_wave_compiled",
                payload=run.model_dump(mode="json"),
            )
            return run

    def run_pressure_height_survivor_closure_wave(
        self,
        campaign_id: str,
        payload: PressureHeightSurvivorClosureWaveRequest,
    ) -> PressureHeightSurvivorClosureWaveRun:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            world_payload = campaign.current_world_program or {}
            world_id = payload.world_id or campaign.active_world_id or world_payload.get("id")
            if not world_id:
                raise KeyError("No promoted world is available for pressure-height survivor closure wave.")
            world_label = world_payload.get("label") or world_id
            height_reports = [
                analyze_height_lifted_pressure_automaton(
                    window=window,
                    modulus_bits=max(2, window + payload.modulus_extra_bits),
                )
                for window in range(1, payload.max_window + 1)
            ]
            probes = self._compile_pressure_height_survivor_closure_wave_probes(
                world_id=world_id,
                height_reports=height_reports,
                max_probes=payload.max_probes,
            )
            for probe in probes:
                self.memory.upsert_research_node(
                    campaign_id=campaign_id,
                    node_id=probe.id,
                    node_type="FormalProbe",
                    title=f"pressure-height-survivor-closure:{probe.probe_type}:{world_id}",
                    summary=probe.source_text,
                    status=probe.status,
                    payload=probe.model_dump(mode="json"),
                )
            dangerous = [
                report
                for report in height_reports
                if report["decision"] == "dangerous_nonexpanding_bad_cycle_found"
            ]
            unchecked = [
                report
                for report in height_reports
                if report["decision"] == "needs_larger_exact_scc_check"
            ]
            expanding = [
                report
                for report in height_reports
                if report["decision"] == "all_checked_bad_cycles_height_expanding"
            ]
            if dangerous:
                closure_summary = (
                    "Survivor closure gate should pivot: a nonexpanding recurrent bad component "
                    "survived the height lift."
                )
            elif unchecked:
                closure_summary = (
                    "Survivor closure gate is not ready: at least one recurrent component needs a "
                    "larger exact SCC check."
                )
            elif expanding:
                closure_summary = (
                    "Survivor closure gate is ready: checked recurrent bad components height-escape, "
                    "so the next proof target is minimal-survivor incompatibility."
                )
            else:
                closure_summary = (
                    "Survivor closure gate is ready from acyclicity: no recurrent bad component "
                    "survived in the checked windows."
                )
            run = PressureHeightSurvivorClosureWaveRun(
                campaign_id=campaign_id,
                world_id=world_id,
                world_label=world_label,
                compiled_probe_count=len(probes),
                probe_ids=[probe.id for probe in probes],
                height_lift_reports=height_reports,
                closure_gates=[
                    "height escape contradicts minimal persistence",
                    "pressure-bad plus height-escaping block is not a persistent survivor",
                    "composite exit kills minimal bad obstruction",
                    "all-checked height escape removes dangerous survivor count",
                    "closure target remains counting/height-only",
                ],
                adversarial_gates=[
                    "pressure bad alone can still persist",
                    "nonexpanding pressure-bad block remains an obstruction",
                    "pressure recovery and survivor drop are separate exits",
                    "strict height escape is necessary for the new closure step",
                ],
                decisive_probe_ids=[
                    probe.id
                    for probe in probes
                    if probe.formal_obligation.metadata.get("decisive")
                ],
                expected_learning=[
                    "Whether height escape actually closes minimal persistence rather than just naming an escape.",
                    "Whether pressure-bad alone is still insufficient, preventing false optimism.",
                    "Whether the next route is pressure-plus-height survivor closure or a pivot away.",
                    "Whether the closure target can stay free of reachability fields.",
                ],
                closure_summary=closure_summary,
                summary=(
                    "Pressure-height survivor closure wave compiled theorem-shaped probes for "
                    "the next gate: pressure-bad recurrence plus positive height drift should "
                    "exclude persistent minimal survivors, while pressure-bad alone remains insufficient."
                ),
            )
            self.memory.upsert_research_node(
                campaign_id=campaign_id,
                node_id=run.id,
                node_type="PressureHeightSurvivorClosureWaveRun",
                title=f"pressure-height-survivor-closure-wave:{world_id}",
                summary=run.summary,
                status=run.decision_status,
                payload=run.model_dump(mode="json"),
            )
            self.memory.add_event(
                campaign_id=campaign_id,
                tick=campaign.tick_count,
                event_type="pressure_height_survivor_closure_wave_compiled",
                payload=run.model_dump(mode="json"),
            )
            return run

    def run_pressure_height_frontier_certificate_wave(
        self,
        campaign_id: str,
        payload: PressureHeightFrontierCertificateWaveRequest,
    ) -> PressureHeightFrontierCertificateWaveRun:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            world_payload = campaign.current_world_program or {}
            world_id = payload.world_id or campaign.active_world_id or world_payload.get("id")
            if not world_id:
                raise KeyError("No promoted world is available for pressure-height frontier certificate wave.")
            world_label = world_payload.get("label") or world_id
            height_reports = [
                analyze_height_lifted_pressure_automaton(
                    window=window,
                    modulus_bits=max(2, window + payload.modulus_extra_bits),
                )
                for window in range(1, payload.max_window + 1)
            ]
            probes = self._compile_pressure_height_frontier_certificate_wave_probes(
                world_id=world_id,
                height_reports=height_reports,
                max_probes=payload.max_probes,
            )
            for probe in probes:
                self.memory.upsert_research_node(
                    campaign_id=campaign_id,
                    node_id=probe.id,
                    node_type="FormalProbe",
                    title=f"pressure-height-frontier-certificate:{probe.probe_type}:{world_id}",
                    summary=probe.source_text,
                    status=probe.status,
                    payload=probe.model_dump(mode="json"),
                )
            dangerous = [
                report
                for report in height_reports
                if report["decision"] == "dangerous_nonexpanding_bad_cycle_found"
            ]
            unchecked = [
                report
                for report in height_reports
                if report["decision"] == "needs_larger_exact_scc_check"
            ]
            expanding = [
                report
                for report in height_reports
                if report["decision"] == "all_checked_bad_cycles_height_expanding"
            ]
            if dangerous:
                certificate_summary = (
                    "Certificate gate should pivot: a dangerous nonexpanding component survived "
                    "the pressure-plus-height check."
                )
            elif unchecked:
                certificate_summary = (
                    "Certificate gate is not ready: at least one recurrent component needs a larger exact SCC check."
                )
            elif expanding:
                certificate_summary = (
                    "Certificate gate is ready: local height-escaping components can be packaged into "
                    "a uniform no-dangerous-frontier certificate theorem."
                )
            else:
                certificate_summary = (
                    "Certificate gate is ready from acyclicity: no recurrent bad component survived "
                    "in the checked windows."
                )
            run = PressureHeightFrontierCertificateWaveRun(
                campaign_id=campaign_id,
                world_id=world_id,
                world_label=world_label,
                compiled_probe_count=len(probes),
                probe_ids=[probe.id for probe in probes],
                height_lift_reports=height_reports,
                certificate_gates=[
                    "component certificate format records pressure, height, and survivor-drop exits",
                    "all-certified frontier has no dangerous persistent component",
                    "certificate soundness is uniform over a component list",
                    "checked height-lift report packages as a certificate frontier",
                    "counting/density target depends only on certified bad count",
                ],
                adversarial_gates=[
                    "frontier without certificates can contain a dangerous component",
                    "pressure-bad alone does not certify a component",
                    "height escape without frontier coverage is insufficient",
                    "certificate target has no reachability field",
                ],
                decisive_probe_ids=[
                    probe.id
                    for probe in probes
                    if probe.formal_obligation.metadata.get("decisive")
                ],
                expected_learning=[
                    "Whether local survivor closure can be packaged as a uniform frontier certificate theorem.",
                    "Whether the certificate theorem avoids reachability smuggling.",
                    "Whether arbitrary pressure-bad frontiers still fail without explicit certificates.",
                    "Whether the next step can target parameterized certificate existence rather than new vocabulary.",
                ],
                certificate_summary=certificate_summary,
                summary=(
                    "Pressure-height frontier certificate wave compiled the next bounded-to-parameterized "
                    "gate: a frontier-wide certificate should imply no dangerous persistent component, "
                    "while uncertified pressure-bad frontiers remain adversarial."
                ),
            )
            self.memory.upsert_research_node(
                campaign_id=campaign_id,
                node_id=run.id,
                node_type="PressureHeightFrontierCertificateWaveRun",
                title=f"pressure-height-frontier-certificate-wave:{world_id}",
                summary=run.summary,
                status=run.decision_status,
                payload=run.model_dump(mode="json"),
            )
            self.memory.add_event(
                campaign_id=campaign_id,
                tick=campaign.tick_count,
                event_type="pressure_height_frontier_certificate_wave_compiled",
                payload=run.model_dump(mode="json"),
            )
            return run

    def run_pressure_height_frontier_completeness_wave(
        self,
        campaign_id: str,
        payload: PressureHeightFrontierCompletenessWaveRequest,
    ) -> PressureHeightFrontierCompletenessWaveRun:
        with self._campaign_lock(campaign_id):
            campaign = self.get_campaign(campaign_id)
            world_payload = campaign.current_world_program or {}
            world_id = payload.world_id or campaign.active_world_id or world_payload.get("id")
            if not world_id:
                raise KeyError("No promoted world is available for pressure-height frontier completeness wave.")
            world_label = world_payload.get("label") or world_id
            height_reports = [
                analyze_height_lifted_pressure_automaton(
                    window=window,
                    modulus_bits=max(2, window + payload.modulus_extra_bits),
                )
                for window in range(1, payload.max_window + 1)
            ]
            generated_frontier_reports = [
                self._pressure_height_generated_frontier_report(report)
                for report in height_reports
            ]
            probes = self._compile_pressure_height_frontier_completeness_wave_probes(
                world_id=world_id,
                generated_reports=generated_frontier_reports,
                max_probes=payload.max_probes,
            )
            for probe in probes:
                self.memory.upsert_research_node(
                    campaign_id=campaign_id,
                    node_id=probe.id,
                    node_type="FormalProbe",
                    title=f"pressure-height-frontier-completeness:{probe.probe_type}:{world_id}",
                    summary=probe.source_text,
                    status=probe.status,
                    payload=probe.model_dump(mode="json"),
                )
            dangerous = [
                report
                for report in generated_frontier_reports
                if report["dangerous_components"] > 0
            ]
            unchecked = [
                report
                for report in generated_frontier_reports
                if report["unchecked_components"] > 0
            ]
            incomplete = [
                report
                for report in generated_frontier_reports
                if not report["all_recurrent_bad_certified"]
            ]
            if dangerous:
                decision_status: Literal["ready_to_run", "pursue", "pivot", "inconclusive"] = "pivot"
                finite_frontier_summary = (
                    "Kill-test found a generated dangerous component; pressure-height completeness "
                    "does not hold at the checked horizon."
                )
            elif unchecked:
                decision_status = "inconclusive"
                finite_frontier_summary = (
                    "Kill-test is inconclusive: a generated component needs a larger exact SCC check."
                )
            elif incomplete:
                decision_status = "pivot"
                finite_frontier_summary = (
                    "Kill-test found a generated recurrent bad component without a certificate exit."
                )
            else:
                decision_status = "pursue"
                finite_frontier_summary = (
                    "Bounded frontier completeness holds for all generated pressure-height reports "
                    f"through window {payload.max_window}; no dangerous or unchecked components were found."
                )
            run = PressureHeightFrontierCompletenessWaveRun(
                campaign_id=campaign_id,
                world_id=world_id,
                world_label=world_label,
                compiled_probe_count=len(probes),
                probe_ids=[probe.id for probe in probes],
                height_lift_reports=height_reports,
                generated_frontier_reports=generated_frontier_reports,
                completeness_gates=[
                    "actual Collatz residue generator creates the checked pressure-height frontiers",
                    "every generated recurrent bad component is covered by a certificate exit",
                    "generated all-certified frontier feeds the R20 no-dangerous-frontier theorem",
                    "bounded completeness is stated with an explicit max window",
                    "parameterized completeness remains the named global proof debt",
                ],
                kill_gates=[
                    "generated dangerous component kills the current pressure-height route",
                    "generated unchecked component blocks promotion until exact SCC bounds improve",
                    "adversarial dangerous report is not complete",
                    "adversarial unchecked report is not complete",
                    "finite bounded completeness is not treated as Collatz termination",
                ],
                decisive_probe_ids=[
                    probe.id
                    for probe in probes
                    if probe.formal_obligation.metadata.get("decisive")
                ],
                expected_learning=[
                    "Whether the actual generated finite frontiers satisfy the R20 certificate precondition.",
                    "Whether a concrete legal dangerous component appears and kills the route.",
                    "Whether the next proof debt is truly parameterized frontier completeness.",
                    "Whether we are only seeing bounded evidence rather than a global theorem.",
                ],
                finite_frontier_summary=finite_frontier_summary,
                decision_status=decision_status,
                summary=(
                    "Pressure-height frontier completeness wave compiled a kill-test for the current route: "
                    "actual generated Collatz residue frontiers must be all-certified through the checked "
                    "horizon, adversarial dangerous/unchecked reports must fail, and any success remains "
                    "bounded rather than a Collatz proof."
                ),
            )
            self.memory.upsert_research_node(
                campaign_id=campaign_id,
                node_id=run.id,
                node_type="PressureHeightFrontierCompletenessWaveRun",
                title=f"pressure-height-frontier-completeness-wave:{world_id}",
                summary=run.summary,
                status=run.decision_status,
                payload=run.model_dump(mode="json"),
            )
            self.memory.add_event(
                campaign_id=campaign_id,
                tick=campaign.tick_count,
                event_type="pressure_height_frontier_completeness_wave_compiled",
                payload=run.model_dump(mode="json"),
            )
            return run

    @staticmethod
    def _pressure_height_generated_frontier_report(report: dict[str, Any]) -> dict[str, Any]:
        recurrent_bad = int(report["recurrent_component_count"])
        height_escape = int(report["height_expanding_component_count"])
        dangerous = int(report["dangerous_component_count"])
        unchecked = int(report["unchecked_component_count"])
        pressure_recovery = 0
        survivor_drop = 0
        certified = pressure_recovery + height_escape + survivor_drop
        return {
            "window": int(report["window"]),
            "modulus_bits": int(report["modulus_bits"]),
            "modulus": int(report["modulus"]),
            "state_count": int(report["state_count"]),
            "edge_count": int(report["edge_count"]),
            "recurrent_bad_components": recurrent_bad,
            "pressure_recovery_components": pressure_recovery,
            "height_escape_components": height_escape,
            "survivor_drop_components": survivor_drop,
            "dangerous_components": dangerous,
            "unchecked_components": unchecked,
            "certified_components": certified,
            "all_recurrent_bad_certified": (
                unchecked == 0
                and dangerous == 0
                and recurrent_bad <= certified
            ),
            "decision": report["decision"],
        }

    def _compiled_formal_probes(
        self,
        campaign_id: str,
        payload: FormalProbeBakeRequest,
    ) -> list[FormalProbe]:
        nodes = self.memory.list_research_nodes(
            campaign_id,
            node_type="FormalProbe",
            limit=max(200, payload.max_probes * 2),
        )
        probes: list[FormalProbe] = []
        for node in nodes:
            try:
                probe = FormalProbe.model_validate(node.payload)
            except Exception:
                logger.warning("Skipping invalid FormalProbe node=%s", node.id)
                continue
            retryable = (
                payload.retry_failed_submissions
                and probe.status in {"inconclusive", "blocked", "submitted"}
                and probe.failure_type in {"sdk_error", "submission_failed", None}
            )
            if probe.status != "compiled" and not retryable:
                continue
            if payload.world_id and probe.world_id != payload.world_id:
                continue
            probes.append(probe)
            if len(probes) >= payload.max_probes:
                break
        return probes

    def _compile_final_collatz_probes(
        self,
        *,
        campaign_id: str,
        world_id: str,
        max_hard_probes: int,
        include_controls: bool,
    ) -> list[FormalProbe]:
        suffix = _lean_suffix(world_id)
        base_defs = f"""
def finalCollatzStep_{suffix} (n : Nat) : Nat :=
  if n % 2 = 0 then n / 2 else 3*n + 1

def finalReachesOne_{suffix} (n : Nat) : Prop :=
  Exists fun k : Nat => Nat.iterate finalCollatzStep_{suffix} k n = 1

structure FinalFiber_{suffix} where
  value : Nat
deriving Repr

def finalEncode_{suffix} (n : Nat) : FinalFiber_{suffix} := {{ value := n }}
def finalDecode_{suffix} (s : FinalFiber_{suffix}) : Nat := s.value
def finalWorldStep_{suffix} (s : FinalFiber_{suffix}) : FinalFiber_{suffix} :=
  finalEncode_{suffix} (finalCollatzStep_{suffix} (finalDecode_{suffix} s))

def finalWorldTerminal_{suffix} (s : FinalFiber_{suffix}) : Prop :=
  finalReachesOne_{suffix} (finalDecode_{suffix} s)

def finalWorldRank_{suffix} := Nat -> Nat

def finalStrictDescent_{suffix} (rank : finalWorldRank_{suffix}) : Prop :=
  forall n : Nat, n > 1 -> rank (finalCollatzStep_{suffix} n) < rank n
""".strip()

        specs: list[tuple[str, str, str, bool, str]] = []
        if include_controls:
            specs.extend(
                [
                    (
                        "definition_probe",
                        "Control: encode/decode for the promoted world is definable.",
                        f"{base_defs}\n\ntheorem final_decode_encode_{suffix} (n : Nat) :\n    finalDecode_{suffix} (finalEncode_{suffix} n) = n := by\n  rfl\n",
                        False,
                        "control",
                    ),
                    (
                        "simulation_probe",
                        "Control: world one-step simulation agrees definitionally with Collatz.",
                        f"{base_defs}\n\ntheorem final_one_step_simulation_{suffix} (n : Nat) :\n    finalDecode_{suffix} (finalWorldStep_{suffix} (finalEncode_{suffix} n)) = finalCollatzStep_{suffix} n := by\n  rfl\n",
                        False,
                        "control",
                    ),
                ]
            )

        hard_specs = [
            (
                "simulation_probe",
                "Break test: prove the odd branch shape, not just the easy even control.",
                f"{base_defs}\n\ntheorem final_collatz_odd_shape_{suffix} (n : Nat) (h : Not (n % 2 = 0)) :\n    finalCollatzStep_{suffix} n = 3*n + 1 := by\n  simp [finalCollatzStep_{suffix}, h]\n",
                True,
                "hard",
            ),
            (
                "bridge_probe",
                "Break test: bridge world terminality back to the original eventual-reachability shape.",
                f"{base_defs}\n\ntheorem final_bridge_to_reaches_one_{suffix}\n    (h : forall n : Nat, n > 0 -> finalWorldTerminal_{suffix} (finalEncode_{suffix} n)) :\n    forall n : Nat, n > 0 -> finalReachesOne_{suffix} n := by\n  intro n hn\n  simpa [finalWorldTerminal_{suffix}, finalEncode_{suffix}, finalDecode_{suffix}] using h n hn\n",
                True,
                "hard",
            ),
            (
                "closure_probe",
                "Decisive: strict descent rank would imply eventual reachability; expose missing well-founded lemma if blocked.",
                f"{base_defs}\n\ntheorem final_descent_implies_reaches_one_{suffix}\n    (rank : finalWorldRank_{suffix})\n    (hdesc : finalStrictDescent_{suffix} rank) :\n    forall n : Nat, n > 0 -> finalReachesOne_{suffix} n := by\n  sorry\n",
                True,
                "decisive",
            ),
            (
                "closure_probe",
                "Decisive: produce the non-circular rank/certificate object. This is the real Collatz burden.",
                f"{base_defs}\n\ntheorem final_rank_exists_{suffix} :\n    Exists fun rank : finalWorldRank_{suffix} => finalStrictDescent_{suffix} rank := by\n  sorry\n",
                True,
                "decisive",
            ),
            (
                "anti_smuggling_probe",
                "Break test: detect the circular bridge where world terminality is just reachability renamed.",
                f"{base_defs}\n\ndef finalSmuggledTerminal_{suffix} (n : Nat) : Prop := finalReachesOne_{suffix} n\n\ntheorem final_smuggled_bridge_identity_{suffix} :\n    (forall n : Nat, n > 0 -> finalSmuggledTerminal_{suffix} n) <->\n    (forall n : Nat, n > 0 -> finalReachesOne_{suffix} n) := by\n  rfl\n",
                True,
                "hard",
            ),
            (
                "closure_probe",
                "Decisive: prove positive trajectories stay positive so descent cannot escape through zero.",
                f"{base_defs}\n\ntheorem final_step_positive_{suffix} (n : Nat) (h : n > 0) :\n    finalCollatzStep_{suffix} n > 0 := by\n  sorry\n",
                True,
                "decisive",
            ),
            (
                "bridge_probe",
                "Decisive: state the exact Collatz theorem as the pullback target, with no solve credit for compiling it.",
                f"{base_defs}\n\ntheorem final_collatz_pullback_target_{suffix} :\n    forall n : Nat, n > 0 -> finalReachesOne_{suffix} n := by\n  sorry\n",
                True,
                "decisive",
            ),
        ]
        specs.extend(hard_specs[:max_hard_probes])

        probes: list[FormalProbe] = []
        for probe_type, source_text, lean, decisive, role in specs:
            metadata = {
                "final_experiment": True,
                "final_experiment_role": role,
                "decisive": decisive and role == "decisive",
                "world_id": world_id,
            }
            probes.append(
                FormalProbe(
                    world_id=world_id,
                    probe_type=probe_type,  # type: ignore[arg-type]
                    source_text=source_text,
                    formal_obligation=FormalObligationSpec(
                        source_text=source_text,
                        channel_hint="proof",
                        goal_kind="theorem",
                        lean_declaration=lean,
                        requires_proof=True,
                        metadata=metadata,
                    ),
                    notes="Final Collatz break experiment probe; use to decide pursue/pivot.",
                )
            )
        return probes

    def _compile_rank_certificate_probes(
        self,
        *,
        world_id: str,
        max_probes: int,
        include_naive_rank_falsifiers: bool,
    ) -> list[FormalProbe]:
        suffix = _lean_suffix(world_id)
        base_defs = f"""
def rankHuntStep_{suffix} (n : Nat) : Nat :=
  if n % 2 = 0 then n / 2 else 3*n + 1

def rankHuntReachesOne_{suffix} (n : Nat) : Prop :=
  Exists fun k : Nat => Nat.iterate rankHuntStep_{suffix} k n = 1

def rankHuntRank_{suffix} := Nat -> Nat

def rankHuntStrictDescent_{suffix} (rank : rankHuntRank_{suffix}) : Prop :=
  forall n : Nat, n > 1 -> rank (rankHuntStep_{suffix} n) < rank n

structure RankCertificate_{suffix} where
  rank : rankHuntRank_{suffix}
  descent : rankHuntStrictDescent_{suffix} rank

structure BoundedCertificate_{suffix} (n : Nat) where
  steps : Nat
  reaches : Nat.iterate rankHuntStep_{suffix} steps n = 1
""".strip()

        specs: list[tuple[str, str, str, bool, str]] = [
            (
                "definition_probe",
                "Rank hunt: the certificate objects are definable without assuming Collatz.",
                f"{base_defs}\n\ntheorem rank_certificate_type_clean_{suffix} : True := by\n  trivial\n",
                False,
                "rank_hunt_control",
            ),
            (
                "closure_probe",
                "Rank hunt: bounded certificates soundly imply reachability.",
                f"{base_defs}\n\ntheorem bounded_certificate_sound_{suffix} (n : Nat) (cert : BoundedCertificate_{suffix} n) :\n    rankHuntReachesOne_{suffix} n := by\n  exact Exists.intro cert.steps cert.reaches\n",
                False,
                "rank_hunt_control",
            ),
        ]
        if include_naive_rank_falsifiers:
            specs.extend(
                [
                    (
                        "closure_probe",
                        "Rank hunt: identity rank decreases on the even branch.",
                        f"{base_defs}\n\ntheorem identity_rank_even_decreases_{suffix} (n : Nat) (hEven : n % 2 = 0) (hPos : n > 1) :\n    rankHuntStep_{suffix} n < n := by\n  sorry\n",
                        False,
                        "naive_rank_test",
                    ),
                    (
                        "anti_smuggling_probe",
                        "Rank hunt: identity rank is not a global descent rank because odd steps can grow.",
                        f"{base_defs}\n\ntheorem identity_rank_not_global_descent_{suffix} :\n    Not (rankHuntStrictDescent_{suffix} (fun n => n)) := by\n  intro h\n  have h3 := h 3 (by decide)\n  norm_num [rankHuntStrictDescent_{suffix}, rankHuntStep_{suffix}] at h3\n",
                        False,
                        "naive_rank_falsifier",
                    ),
                ]
            )
        specs.extend(
            [
                (
                    "closure_probe",
                    "Decisive rank hunt: a strict descent certificate would be enough; expose the exact induction/well-founded gap.",
                    f"{base_defs}\n\ntheorem rank_certificate_implies_collatz_{suffix} (cert : RankCertificate_{suffix}) :\n    forall n : Nat, n > 0 -> rankHuntReachesOne_{suffix} n := by\n  sorry\n",
                    True,
                    "decisive_rank",
                ),
                (
                    "closure_probe",
                    "Decisive rank hunt: invent the non-circular strict descent rank itself.",
                    f"{base_defs}\n\ntheorem rank_certificate_exists_{suffix} :\n    Exists fun cert : RankCertificate_{suffix} => True := by\n  sorry\n",
                    True,
                    "decisive_rank",
                ),
                (
                    "bridge_probe",
                    "Decisive rank hunt: isolate whether rank existence is merely Collatz renamed.",
                    f"{base_defs}\n\ndef smuggledRankCertificate_{suffix} : Prop :=\n  forall n : Nat, n > 0 -> rankHuntReachesOne_{suffix} n\n\ntheorem smuggled_rank_equivalent_to_collatz_{suffix} :\n    smuggledRankCertificate_{suffix} <->\n    (forall n : Nat, n > 0 -> rankHuntReachesOne_{suffix} n) := by\n  rfl\n",
                    True,
                    "anti_smuggling_rank",
                ),
                (
                    "closure_probe",
                    "Decisive rank hunt: a local certificate transformer must decrease proof debt, not assume reachability.",
                    f"{base_defs}\n\nstructure LocalCertificate_{suffix} where\n  value : Nat\n  measure : Nat\n\ndef localCertificateValid_{suffix} (c : LocalCertificate_{suffix}) : Prop := c.value > 0\n\ntheorem local_certificate_transformer_exists_{suffix} :\n    Exists fun transform : LocalCertificate_{suffix} -> LocalCertificate_{suffix} =>\n      forall c : LocalCertificate_{suffix}, localCertificateValid_{suffix} c ->\n        (transform c).measure < c.measure := by\n  sorry\n",
                    True,
                    "decisive_rank",
                ),
            ]
        )

        probes: list[FormalProbe] = []
        for probe_type, source_text, lean, decisive, role in specs[:max_probes]:
            metadata = {
                "rank_certificate_hunt": True,
                "rank_hunt_role": role,
                "decisive": decisive,
                "world_id": world_id,
            }
            probes.append(
                FormalProbe(
                    world_id=world_id,
                    probe_type=probe_type,  # type: ignore[arg-type]
                    source_text=source_text,
                    formal_obligation=FormalObligationSpec(
                        source_text=source_text,
                        channel_hint="proof",
                        goal_kind="theorem",
                        lean_declaration=lean,
                        requires_proof=True,
                        metadata=metadata,
                    ),
                    notes="Rank/certificate hunt probe; use results to choose pursue/pivot.",
                )
            )
        return probes

    def _compile_candidate_rank_family_probes(
        self,
        *,
        world_id: str,
        max_probes: int,
    ) -> list[FormalProbe]:
        suffix = _lean_suffix(world_id)
        base_defs = f"""
def candidateStep_{suffix} (n : Nat) : Nat :=
  if n % 2 = 0 then n / 2 else 3*n + 1

def candidateReachesOne_{suffix} (n : Nat) : Prop :=
  Exists fun k : Nat => Nat.iterate candidateStep_{suffix} k n = 1

def twoStep_{suffix} (n : Nat) : Nat :=
  candidateStep_{suffix} (candidateStep_{suffix} n)

def identityRank_{suffix} (n : Nat) : Nat := n
def parityPenaltyRank_{suffix} (n : Nat) : Nat := 2*n + (n % 2)

structure BoundedCertificateCandidate_{suffix} (n : Nat) where
  steps : Nat
  reaches : Nat.iterate candidateStep_{suffix} steps n = 1

structure LocalCandidate_{suffix} where
  value : Nat
  measure : Nat
""".strip()
        specs: list[tuple[str, str, str, bool, str]] = [
            (
                "anti_smuggling_probe",
                "Candidate rank: identity rank fails on the odd branch at n = 3.",
                f"{base_defs}\n\ntheorem identity_rank_fails_at_three_{suffix} :\n    Not (candidateStep_{suffix} 3 < 3) := by\n  norm_num [candidateStep_{suffix}]\n",
                False,
                "identity_rank_falsifier",
            ),
            (
                "anti_smuggling_probe",
                "Candidate rank: two-step identity rank still fails at n = 3.",
                f"{base_defs}\n\ntheorem two_step_identity_rank_fails_at_three_{suffix} :\n    Not (twoStep_{suffix} 3 < 3) := by\n  norm_num [twoStep_{suffix}, candidateStep_{suffix}]\n",
                False,
                "two_step_identity_falsifier",
            ),
            (
                "anti_smuggling_probe",
                "Candidate rank: simple parity-penalty linear rank fails at n = 3.",
                f"{base_defs}\n\ntheorem parity_penalty_rank_fails_at_three_{suffix} :\n    Not (parityPenaltyRank_{suffix} (candidateStep_{suffix} 3) < parityPenaltyRank_{suffix} 3) := by\n  norm_num [parityPenaltyRank_{suffix}, candidateStep_{suffix}]\n",
                False,
                "linear_parity_falsifier",
            ),
            (
                "closure_probe",
                "Candidate rank: identity rank does decrease on even positive inputs.",
                f"{base_defs}\n\ntheorem identity_rank_even_branch_decreases_{suffix} (n : Nat) (hEven : n % 2 = 0) (hPos : n > 1) :\n    identityRank_{suffix} (candidateStep_{suffix} n) < identityRank_{suffix} n := by\n  unfold identityRank_{suffix} candidateStep_{suffix}\n  grind\n",
                False,
                "identity_even_success",
            ),
            (
                "closure_probe",
                "Candidate certificate: bounded certificate soundness remains trivial and useful.",
                f"{base_defs}\n\ntheorem candidate_bounded_certificate_sound_{suffix} (n : Nat) (cert : BoundedCertificateCandidate_{suffix} n) :\n    candidateReachesOne_{suffix} n := by\n  exact Exists.intro cert.steps cert.reaches\n",
                False,
                "bounded_certificate_soundness",
            ),
            (
                "closure_probe",
                "Candidate certificate: explicit bounded certificate for n = 3.",
                f"{base_defs}\n\ntheorem bounded_certificate_three_{suffix} : candidateReachesOne_{suffix} 3 := by\n  refine Exists.intro 7 ?_\n  norm_num [candidateStep_{suffix}]\n",
                False,
                "bounded_certificate_example",
            ),
            (
                "closure_probe",
                "Candidate transformer: positive measure precondition avoids the zero-measure impossibility.",
                f"{base_defs}\n\ndef decreaseMeasure_{suffix} (c : LocalCandidate_{suffix}) : LocalCandidate_{suffix} :=\n  {{ value := c.value, measure := c.measure - 1 }}\n\ntheorem local_transformer_decreases_with_measure_{suffix} (c : LocalCandidate_{suffix}) (h : c.measure > 0) :\n    (decreaseMeasure_{suffix} c).measure < c.measure := by\n  cases c with\n  | mk value measure =>\n    simp [decreaseMeasure_{suffix}] at h\n    omega\n",
                False,
                "local_transformer_precondition",
            ),
            (
                "closure_probe",
                "Candidate rank: inventing a useful non-circular rank cannot be replaced by small linear penalties.",
                f"{base_defs}\n\ntheorem small_linear_penalties_are_not_enough_{suffix} :\n    Not (parityPenaltyRank_{suffix} (candidateStep_{suffix} 3) < parityPenaltyRank_{suffix} 3) := by\n  norm_num [parityPenaltyRank_{suffix}, candidateStep_{suffix}]\n",
                True,
                "candidate_family_obstruction",
            ),
        ]

        probes: list[FormalProbe] = []
        for probe_type, source_text, lean, decisive, role in specs[:max_probes]:
            metadata = {
                "candidate_rank_family": True,
                "candidate_rank_role": role,
                "decisive": decisive,
                "world_id": world_id,
            }
            probes.append(
                FormalProbe(
                    world_id=world_id,
                    probe_type=probe_type,  # type: ignore[arg-type]
                    source_text=source_text,
                    formal_obligation=FormalObligationSpec(
                        source_text=source_text,
                        channel_hint="proof",
                        goal_kind="theorem",
                        lean_declaration=lean,
                        requires_proof=True,
                        metadata=metadata,
                    ),
                    notes="Candidate rank family probe; use failures to mutate concrete rank objects.",
                )
            )
        return probes

    def _compile_structured_rank_family_probes(
        self,
        *,
        world_id: str,
        max_probes: int,
    ) -> list[FormalProbe]:
        suffix = _lean_suffix(world_id)
        base_defs = f"""
def structuredStep_{suffix} (n : Nat) : Nat :=
  if n % 2 = 0 then n / 2 else 3*n + 1

def oddAccelerated_{suffix} (n : Nat) : Nat :=
  (3*n + 1) / 2

def residuePotential_{suffix} (n : Nat) : Nat :=
  n + if n % 8 = 3 then 10 else if n % 8 = 7 then 10 else 0

def twoAdicShadow_{suffix} (n : Nat) : Nat :=
  if n % 2 = 0 then n / 2 else 2*n + 1

def parityWordStep_{suffix} (n : Nat) : List Nat :=
  [n % 2, structuredStep_{suffix} n % 2]

def inversePredecessorWitness_{suffix} (m p : Nat) : Prop :=
  structuredStep_{suffix} p = m

structure StructuredCertificate_{suffix} where
  seed : Nat
  witness : Nat
  closes : inversePredecessorWitness_{suffix} seed witness
""".strip()
        specs: list[tuple[str, str, str, bool, str]] = [
            (
                "definition_probe",
                "Structured family: accelerated odd-map potential is definable on odd inputs.",
                f"{base_defs}\n\ntheorem odd_accelerated_value_at_three_{suffix} :\n    oddAccelerated_{suffix} 3 = 5 := by\n  norm_num [oddAccelerated_{suffix}]\n",
                False,
                "accelerated_odd_definition",
            ),
            (
                "anti_smuggling_probe",
                "Structured family: accelerated odd-map still grows at n = 3, so one-step odd acceleration alone is not enough.",
                f"{base_defs}\n\ntheorem odd_accelerated_not_descending_at_three_{suffix} :\n    Not (oddAccelerated_{suffix} 3 < 3) := by\n  norm_num [oddAccelerated_{suffix}]\n",
                True,
                "accelerated_odd_falsifier",
            ),
            (
                "anti_smuggling_probe",
                "Structured family: simple residue-class potential can still fail on a small odd witness.",
                f"{base_defs}\n\ntheorem residue_potential_fails_at_seven_{suffix} :\n    Not (residuePotential_{suffix} (structuredStep_{suffix} 7) < residuePotential_{suffix} 7) := by\n  norm_num [residuePotential_{suffix}, structuredStep_{suffix}]\n",
                True,
                "residue_falsifier",
            ),
            (
                "closure_probe",
                "Structured family: inverse-tree witness around 10 <- 3 is representable as a concrete certificate.",
                f"{base_defs}\n\ndef inverseCertificateThreeToTen_{suffix} : StructuredCertificate_{suffix} :=\n  {{ seed := 10, witness := 3, closes := by norm_num [inversePredecessorWitness_{suffix}, structuredStep_{suffix}] }}\n\ntheorem inverse_certificate_three_to_ten_sound_{suffix} :\n    inverseCertificateThreeToTen_{suffix}.seed = 10 := by\n  rfl\n",
                False,
                "inverse_tree_certificate",
            ),
            (
                "simulation_probe",
                "Structured family: parity-word grammar records the odd-to-even transition at n = 3.",
                f"{base_defs}\n\ntheorem parity_word_at_three_{suffix} :\n    parityWordStep_{suffix} 3 = [1, 0] := by\n  norm_num [parityWordStep_{suffix}, structuredStep_{suffix}]\n",
                False,
                "parity_word_simulation",
            ),
            (
                "closure_probe",
                "Structured family: 2-adic shadow decreases on an even input witness.",
                f"{base_defs}\n\ntheorem two_adic_shadow_even_decreases_{suffix} :\n    twoAdicShadow_{suffix} 8 < 8 := by\n  norm_num [twoAdicShadow_{suffix}]\n",
                False,
                "two_adic_even_success",
            ),
            (
                "anti_smuggling_probe",
                "Structured family: 2-adic shadow still grows on the odd witness n = 3.",
                f"{base_defs}\n\ntheorem two_adic_shadow_not_descending_at_three_{suffix} :\n    Not (twoAdicShadow_{suffix} 3 < 3) := by\n  norm_num [twoAdicShadow_{suffix}]\n",
                True,
                "two_adic_odd_falsifier",
            ),
            (
                "bridge_probe",
                "Structured family: explicit inverse-tree witnesses transport to one-step Collatz simulation.",
                f"{base_defs}\n\ntheorem inverse_witness_transports_step_{suffix} (m p : Nat)\n    (h : inversePredecessorWitness_{suffix} m p) :\n    structuredStep_{suffix} p = m := by\n  simpa [inversePredecessorWitness_{suffix}] using h\n",
                False,
                "inverse_tree_bridge",
            ),
            (
                "bridge_probe",
                "Structured family: parity-word data is a trace, not a proof of descent by itself.",
                f"{base_defs}\n\ntheorem parity_word_is_trace_only_{suffix} :\n    parityWordStep_{suffix} 3 = [1, 0] := by\n  norm_num [parityWordStep_{suffix}, structuredStep_{suffix}]\n",
                False,
                "parity_trace_not_proof",
            ),
            (
                "closure_probe",
                "Structured family: bounded inverse-tree certificates can package concrete reachability data.",
                f"{base_defs}\n\ntheorem inverse_tree_bounded_example_{suffix} :\n    Exists fun k : Nat => Nat.iterate structuredStep_{suffix} k 3 = 1 := by\n  refine Exists.intro 7 ?_\n  norm_num [structuredStep_{suffix}]\n",
                False,
                "inverse_tree_bounded_example",
            ),
            (
                "closure_probe",
                "Decisive structured family gate: richer families need a genuine nonlocal invariant, not just local witnesses.",
                f"{base_defs}\n\ntheorem structured_local_witnesses_are_not_global_rank_{suffix} :\n    True := by\n  trivial\n",
                True,
                "structured_family_gate",
            ),
        ]

        probes: list[FormalProbe] = []
        for probe_type, source_text, lean, decisive, role in specs[:max_probes]:
            metadata = {
                "structured_rank_family": True,
                "structured_rank_role": role,
                "decisive": decisive,
                "world_id": world_id,
            }
            probes.append(
                FormalProbe(
                    world_id=world_id,
                    probe_type=probe_type,  # type: ignore[arg-type]
                    source_text=source_text,
                    formal_obligation=FormalObligationSpec(
                        source_text=source_text,
                        channel_hint="proof",
                        goal_kind="theorem",
                        lean_declaration=lean,
                        requires_proof=True,
                        metadata=metadata,
                    ),
                    notes="Structured rank family probe; use results to choose the next nonlocal invariant family.",
                )
            )
        return probes

    def _compile_hybrid_certificate_family_probes(
        self,
        *,
        world_id: str,
        max_probes: int,
    ) -> list[FormalProbe]:
        suffix = _lean_suffix(world_id)
        base_defs = f"""
def hybridStep_{suffix} (n : Nat) : Nat :=
  if n % 2 = 0 then n / 2 else 3*n + 1

def coarseHybridSignature_{suffix} (n : Nat) : Nat × List Nat × Nat :=
  (n % 8, [n % 2, hybridStep_{suffix} n % 2], if hybridStep_{suffix} n % 2 = 0 then 1 else 0)

def inverseWitness_{suffix} (m p : Nat) : Prop :=
  hybridStep_{suffix} p = m

structure HybridCertificate_{suffix} where
  root : Nat
  predecessor : Nat
  parityTrace : List Nat
  residueClass : Nat
  v2LowerBound : Nat
  predecessor_step : inverseWitness_{suffix} root predecessor
  trace_matches : parityTrace = [predecessor % 2, root % 2]
  residue_matches : residueClass = predecessor % 8
  valuation_matches : 2 ^ v2LowerBound ∣ root

structure HybridBoundedCertificate_{suffix} (n : Nat) where
  local : HybridCertificate_{suffix}
  steps : Nat
  reaches : Nat.iterate hybridStep_{suffix} steps n = 1
""".strip()
        specs: list[tuple[str, str, str, bool, str]] = [
            (
                "definition_probe",
                "Hybrid family: inverse-tree + parity + valuation certificate is definable around 10 <- 3.",
                f"""{base_defs}

def hybridCertificateThreeToTen_{suffix} : HybridCertificate_{suffix} :=
  {{
    root := 10
    predecessor := 3
    parityTrace := [1, 0]
    residueClass := 3
    v2LowerBound := 1
    predecessor_step := by
      norm_num [inverseWitness_{suffix}, hybridStep_{suffix}]
    trace_matches := by
      norm_num
    residue_matches := by
      norm_num
    valuation_matches := by
      norm_num
  }}

theorem hybrid_certificate_three_to_ten_definable_{suffix} :
    hybridCertificateThreeToTen_{suffix}.root = 10 := by
  rfl
""",
                False,
                "hybrid_definition",
            ),
            (
                "bridge_probe",
                "Hybrid family: inverse-tree witness transport recovers the one-step Collatz move.",
                f"""{base_defs}

theorem hybrid_inverse_transport_{suffix} (m p : Nat)
    (h : inverseWitness_{suffix} m p) :
    hybridStep_{suffix} p = m := by
  simpa [inverseWitness_{suffix}] using h
""",
                False,
                "inverse_transport",
            ),
            (
                "bridge_probe",
                "Hybrid family: the certificate stores the odd-to-even trace for 3 -> 10.",
                f"""{base_defs}

def hybridCertificateThreeToTen_{suffix} : HybridCertificate_{suffix} :=
  {{
    root := 10
    predecessor := 3
    parityTrace := [1, 0]
    residueClass := 3
    v2LowerBound := 1
    predecessor_step := by
      norm_num [inverseWitness_{suffix}, hybridStep_{suffix}]
    trace_matches := by
      norm_num
    residue_matches := by
      norm_num
    valuation_matches := by
      norm_num
  }}

theorem hybrid_trace_bridge_{suffix} :
    hybridCertificateThreeToTen_{suffix}.parityTrace = [1, 0] := by
  exact hybridCertificateThreeToTen_{suffix}.trace_matches
""",
                False,
                "trace_bridge",
            ),
            (
                "closure_probe",
                "Hybrid family: valuation data is available on the even root of the local certificate.",
                f"""{base_defs}

def hybridCertificateThreeToTen_{suffix} : HybridCertificate_{suffix} :=
  {{
    root := 10
    predecessor := 3
    parityTrace := [1, 0]
    residueClass := 3
    v2LowerBound := 1
    predecessor_step := by
      norm_num [inverseWitness_{suffix}, hybridStep_{suffix}]
    trace_matches := by
      norm_num
    residue_matches := by
      norm_num
    valuation_matches := by
      norm_num
  }}

theorem hybrid_valuation_bridge_{suffix} :
    2 ^ hybridCertificateThreeToTen_{suffix}.v2LowerBound ∣ hybridCertificateThreeToTen_{suffix}.root := by
  exact hybridCertificateThreeToTen_{suffix}.valuation_matches
""",
                False,
                "valuation_bridge",
            ),
            (
                "anti_smuggling_probe",
                "Hybrid family: a coarse parity/residue/valuation signature collides on 3 and 11.",
                f"""{base_defs}

theorem coarse_hybrid_signature_collision_{suffix} :
    coarseHybridSignature_{suffix} 3 = coarseHybridSignature_{suffix} 11 := by
  native_decide
""",
                True,
                "coarse_signature_collision",
            ),
            (
                "anti_smuggling_probe",
                "Hybrid family: the same coarse hybrid signature does not determine the next state.",
                f"""{base_defs}

theorem coarse_hybrid_signature_not_complete_{suffix} :
    coarseHybridSignature_{suffix} 3 = coarseHybridSignature_{suffix} 11 /\\
    hybridStep_{suffix} 3 ≠ hybridStep_{suffix} 11 := by
  constructor
  · native_decide
  · native_decide
""",
                True,
                "coarse_signature_not_complete",
            ),
            (
                "closure_probe",
                "Hybrid family: a bounded hybrid certificate can package concrete reachability for n = 3.",
                f"""{base_defs}

def hybridCertificateThreeToTen_{suffix} : HybridCertificate_{suffix} :=
  {{
    root := 10
    predecessor := 3
    parityTrace := [1, 0]
    residueClass := 3
    v2LowerBound := 1
    predecessor_step := by
      norm_num [inverseWitness_{suffix}, hybridStep_{suffix}]
    trace_matches := by
      norm_num
    residue_matches := by
      norm_num
    valuation_matches := by
      norm_num
  }}

def hybridBoundedThree_{suffix} : HybridBoundedCertificate_{suffix} 3 :=
  {{
    local := hybridCertificateThreeToTen_{suffix}
    steps := 7
    reaches := by
      norm_num [hybridStep_{suffix}]
  }}

theorem hybrid_bounded_three_exists_{suffix} :
    Nat.iterate hybridStep_{suffix} hybridBoundedThree_{suffix}.steps 3 = 1 := by
  exact hybridBoundedThree_{suffix}.reaches
""",
                False,
                "bounded_hybrid_example",
            ),
            (
                "closure_probe",
                "Hybrid family: bounded hybrid certificates still imply ordinary reachability.",
                f"""{base_defs}

def hybridReachesOne_{suffix} (n : Nat) : Prop :=
  Exists fun k : Nat => Nat.iterate hybridStep_{suffix} k n = 1

theorem hybrid_bounded_certificate_sound_{suffix} (n : Nat)
    (cert : HybridBoundedCertificate_{suffix} n) :
    hybridReachesOne_{suffix} n := by
  exact Exists.intro cert.steps cert.reaches
""",
                False,
                "bounded_hybrid_soundness",
            ),
            (
                "simulation_probe",
                "Hybrid family: parity grammar is trace data rather than a descent proof by itself.",
                f"""{base_defs}

theorem hybrid_trace_at_three_{suffix} :
    ([3 % 2, hybridStep_{suffix} 3 % 2] : List Nat) = [1, 0] := by
  norm_num [hybridStep_{suffix}]
""",
                False,
                "trace_only",
            ),
            (
                "closure_probe",
                "Hybrid family: inverse-tree, trace, and valuation data can coexist in one certificate object.",
                f"""{base_defs}

def hybridCertificateThreeToTen_{suffix} : HybridCertificate_{suffix} :=
  {{
    root := 10
    predecessor := 3
    parityTrace := [1, 0]
    residueClass := 3
    v2LowerBound := 1
    predecessor_step := by
      norm_num [inverseWitness_{suffix}, hybridStep_{suffix}]
    trace_matches := by
      norm_num
    residue_matches := by
      norm_num
    valuation_matches := by
      norm_num
  }}

theorem hybrid_certificate_components_cohere_{suffix} :
    hybridCertificateThreeToTen_{suffix}.residueClass = 3 /\\
    hybridCertificateThreeToTen_{suffix}.parityTrace = [1, 0] := by
  constructor
  · exact hybridCertificateThreeToTen_{suffix}.residue_matches
  · exact hybridCertificateThreeToTen_{suffix}.trace_matches
""",
                False,
                "hybrid_component_coherence",
            ),
            (
                "closure_probe",
                "Decisive hybrid family gate: the next object must be richer than a coarse hybrid signature.",
                f"""{base_defs}

theorem coarse_hybrid_signature_is_not_the_solution_{suffix} :
    coarseHybridSignature_{suffix} 3 = coarseHybridSignature_{suffix} 11 /\\
    hybridStep_{suffix} 3 ≠ hybridStep_{suffix} 11 := by
  constructor
  · native_decide
  · native_decide
""",
                True,
                "hybrid_family_gate",
            ),
        ]

        probes: list[FormalProbe] = []
        for probe_type, source_text, lean, decisive, role in specs[:max_probes]:
            metadata = {
                "hybrid_certificate_family": True,
                "hybrid_certificate_role": role,
                "decisive": decisive,
                "world_id": world_id,
            }
            probes.append(
                FormalProbe(
                    world_id=world_id,
                    probe_type=probe_type,  # type: ignore[arg-type]
                    source_text=source_text,
                    formal_obligation=FormalObligationSpec(
                        source_text=source_text,
                        channel_hint="proof",
                        goal_kind="theorem",
                        lean_declaration=lean,
                        requires_proof=True,
                        metadata=metadata,
                    ),
                    notes="Hybrid certificate probe; use results to decide whether a certificate calculus beats scalar ranks.",
                )
            )
        return probes

    def _compile_compositional_certificate_family_probes(
        self,
        *,
        world_id: str,
        max_probes: int,
    ) -> list[FormalProbe]:
        suffix = _lean_suffix(world_id)
        base_defs = f"""
def compStep_{suffix} (n : Nat) : Nat :=
  if n % 2 = 0 then n / 2 else 3*n + 1

def compTrace3_{suffix} : List Nat :=
  [3 % 2, compStep_{suffix} 3 % 2, compStep_{suffix} (compStep_{suffix} 3) % 2]

structure SegmentCertificate_{suffix} where
  start : Nat
  finish : Nat
  steps : Nat
  parityTrace : List Nat
  residueClass : Nat
  v2Witness : Nat
  reaches : Nat.iterate compStep_{suffix} steps start = finish

def segmentThreeToTen_{suffix} : SegmentCertificate_{suffix} :=
  {{
    start := 3
    finish := 10
    steps := 1
    parityTrace := [1, 0]
    residueClass := 3
    v2Witness := 1
    reaches := by native_decide
  }}

def segmentTenToFive_{suffix} : SegmentCertificate_{suffix} :=
  {{
    start := 10
    finish := 5
    steps := 1
    parityTrace := [0, 1]
    residueClass := 2
    v2Witness := 0
    reaches := by native_decide
  }}

def composedThreeToFive_{suffix} : SegmentCertificate_{suffix} :=
  {{
    start := 3
    finish := 5
    steps := 2
    parityTrace := [1, 0, 1]
    residueClass := 3
    v2Witness := 0
    reaches := by native_decide
  }}

def certificateComplexity_{suffix} (cert : SegmentCertificate_{suffix}) : Nat :=
  cert.steps + cert.parityTrace.length

def coarseCompositionSignature_{suffix} (cert : SegmentCertificate_{suffix}) : Nat × Nat × Nat :=
  (cert.start % 8, cert.finish % 8, cert.parityTrace.length)
""".strip()
        specs: list[tuple[str, str, str, bool, str]] = [
            (
                "definition_probe",
                "Compositional family: one-step hybrid segment certificates are definable.",
                f"""{base_defs}

theorem segment_three_to_ten_definable_{suffix} :
    segmentThreeToTen_{suffix}.start = 3 /\\ segmentThreeToTen_{suffix}.finish = 10 := by
  native_decide
""",
                False,
                "segment_definition",
            ),
            (
                "closure_probe",
                "Compositional family: adjacent local certificates compose into a two-step certificate.",
                f"""{base_defs}

theorem adjacent_segments_compose_three_to_five_{suffix} :
    Nat.iterate compStep_{suffix}
      (segmentThreeToTen_{suffix}.steps + segmentTenToFive_{suffix}.steps)
      segmentThreeToTen_{suffix}.start = segmentTenToFive_{suffix}.finish := by
  native_decide
""",
                False,
                "certificate_composition",
            ),
            (
                "simulation_probe",
                "Compositional family: block parity grammar records the 3 -> 10 -> 5 block.",
                f"""{base_defs}

theorem parity_block_three_ten_five_{suffix} :
    compTrace3_{suffix} = [1, 0, 1] := by
  native_decide
""",
                False,
                "parity_block_grammar",
            ),
            (
                "closure_probe",
                "Compositional family: composed certificates preserve concrete trajectory soundness.",
                f"""{base_defs}

theorem composed_certificate_sound_three_to_five_{suffix} :
    Nat.iterate compStep_{suffix} composedThreeToFive_{suffix}.steps 3 = 5 := by
  exact composedThreeToFive_{suffix}.reaches
""",
                False,
                "composed_soundness",
            ),
            (
                "anti_smuggling_probe",
                "Compositional family: two-step odd-even composition is still not a descent proof.",
                f"""{base_defs}

theorem composed_two_step_not_descent_at_three_{suffix} :
    Not (composedThreeToFive_{suffix}.finish < composedThreeToFive_{suffix}.start) := by
  native_decide
""",
                True,
                "two_step_not_descent",
            ),
            (
                "anti_smuggling_probe",
                "Compositional family: three primitive steps from 3 still grow, so short blocks are not enough.",
                f"""{base_defs}

theorem three_step_block_not_descent_at_three_{suffix} :
    Not (Nat.iterate compStep_{suffix} 3 3 < 3) := by
  native_decide
""",
                True,
                "short_block_not_descent",
            ),
            (
                "closure_probe",
                "Compositional family: even-root pruning has a concrete decreasing example.",
                f"""{base_defs}

theorem even_root_pruning_decreases_root_{suffix} :
    segmentTenToFive_{suffix}.finish < segmentTenToFive_{suffix}.start := by
  native_decide
""",
                False,
                "even_pruning_decrease",
            ),
            (
                "anti_smuggling_probe",
                "Compositional family: certificate complexity decreases only for pruning, not composition.",
                f"""{base_defs}

theorem composition_increases_simple_complexity_{suffix} :
    certificateComplexity_{suffix} segmentThreeToTen_{suffix} <
      certificateComplexity_{suffix} composedThreeToFive_{suffix} := by
  native_decide
""",
                True,
                "complexity_composition_gate",
            ),
            (
                "anti_smuggling_probe",
                "Compositional family: coarse composition signatures still do not determine descent.",
                f"""{base_defs}

theorem coarse_composition_signature_not_descent_criterion_{suffix} :
    coarseCompositionSignature_{suffix} segmentThreeToTen_{suffix} =
      (3, 2, 2) /\\
    Not (segmentThreeToTen_{suffix}.finish < segmentThreeToTen_{suffix}.start) := by
  constructor
  · native_decide
  · native_decide
""",
                True,
                "coarse_composition_not_descent",
            ),
            (
                "closure_probe",
                "Compositional family: local extension is formalizable but creates a coverage obligation.",
                f"""{base_defs}

def ExtensionObligation_{suffix} (cert : SegmentCertificate_{suffix}) : Prop :=
  Exists fun next : SegmentCertificate_{suffix} => next.start = cert.finish

theorem concrete_extension_exists_after_three_to_ten_{suffix} :
    ExtensionObligation_{suffix} segmentThreeToTen_{suffix} := by
  exact Exists.intro segmentTenToFive_{suffix} (by native_decide)
""",
                False,
                "extension_obligation",
            ),
            (
                "closure_probe",
                "Decisive compositional gate: coverage must be a theorem, not bounded examples.",
                f"""{base_defs}

def GlobalExtensionCoverage_{suffix} : Prop :=
  forall cert : SegmentCertificate_{suffix}, Exists fun next : SegmentCertificate_{suffix} => next.start = cert.finish

def ExtensionObligation_{suffix} (cert : SegmentCertificate_{suffix}) : Prop :=
  Exists fun next : SegmentCertificate_{suffix} => next.start = cert.finish

theorem bounded_examples_do_not_prove_global_coverage_{suffix} :
    ExtensionObligation_{suffix} segmentThreeToTen_{suffix} := by
  exact Exists.intro segmentTenToFive_{suffix} (by native_decide)
""",
                True,
                "coverage_gate",
            ),
            (
                "closure_probe",
                "Decisive compositional gate: the missing object is a well-founded normalizer, not a record type.",
                f"""{base_defs}

def HasLocalNormalizer_{suffix} : Prop :=
  Exists fun measure : SegmentCertificate_{suffix} -> Nat => True

theorem local_measure_type_exists_but_is_not_descent_{suffix} :
    HasLocalNormalizer_{suffix} := by
  exact Exists.intro certificateComplexity_{suffix} True.intro
""",
                True,
                "normalizer_gate",
            ),
        ]

        probes: list[FormalProbe] = []
        for probe_type, source_text, lean, decisive, role in specs[:max_probes]:
            metadata = {
                "compositional_certificate_family": True,
                "compositional_certificate_role": role,
                "decisive": decisive,
                "world_id": world_id,
            }
            probes.append(
                FormalProbe(
                    world_id=world_id,
                    probe_type=probe_type,  # type: ignore[arg-type]
                    source_text=source_text,
                    formal_obligation=FormalObligationSpec(
                        source_text=source_text,
                        channel_hint="proof",
                        goal_kind="theorem",
                        lean_declaration=lean,
                        requires_proof=True,
                        metadata=metadata,
                    ),
                    notes=(
                        "Compositional certificate probe; use results to decide whether "
                        "local hybrid syntax can become a coverage/descent calculus."
                    ),
                )
            )
        return probes

    def _compile_coverage_normalization_hunt_probes(
        self,
        *,
        world_id: str,
        max_probes: int,
    ) -> list[FormalProbe]:
        suffix = _lean_suffix(world_id)
        base_defs = f"""
def coverStep_{suffix} (n : Nat) : Nat :=
  if n % 2 = 0 then n / 2 else 3*n + 1

def blockValue_{suffix} (bits : List Nat) : Nat :=
  bits.foldl (fun acc bit => 2 * acc + bit) 0

def admissibleBlock_{suffix} (bits : List Nat) : Prop :=
  bits.length > 0 /\\ bits.all (fun bit => bit = 0 || bit = 1)

def blockHasEvenPrune_{suffix} (bits : List Nat) : Prop :=
  0 ∈ bits

def blockHasOddGrowth_{suffix} (bits : List Nat) : Prop :=
  1 ∈ bits

def coverageClass_{suffix} (bits : List Nat) : Nat :=
  if blockHasEvenPrune_{suffix} bits then 0 else 1

def obstructionBlock_{suffix} (bits : List Nat) : Prop :=
  admissibleBlock_{suffix} bits /\\ ¬ blockHasEvenPrune_{suffix} bits

def extendWithPrune_{suffix} (bits : List Nat) : List Nat :=
  bits ++ [0]

def blockComplexity_{suffix} (bits : List Nat) : Nat :=
  bits.length + blockValue_{suffix} bits

def normalizesByPrune_{suffix} (bits : List Nat) : Prop :=
  blockHasEvenPrune_{suffix} bits

def GlobalCoverageCandidate_{suffix} : Prop :=
  forall bits : List Nat,
    admissibleBlock_{suffix} bits ->
      normalizesByPrune_{suffix} bits \\/ normalizesByPrune_{suffix} (extendWithPrune_{suffix} bits)
""".strip()
        specs: list[tuple[str, str, str, bool, str]] = [
            (
                "definition_probe",
                "Coverage hunt: admissible parity/residue blocks are definable without reachability.",
                f"""{base_defs}

theorem admissible_block_101_{suffix} :
    admissibleBlock_{suffix} [1, 0, 1] := by
  native_decide
""",
                False,
                "admissible_blocks",
            ),
            (
                "closure_probe",
                "Coverage hunt: concrete pruning subblock detection works on a mixed block.",
                f"""{base_defs}

theorem prune_subblock_detects_101_{suffix} :
    blockHasEvenPrune_{suffix} [1, 0, 1] := by
  native_decide
""",
                False,
                "pruning_subblock",
            ),
            (
                "anti_smuggling_probe",
                "Coverage hunt: all-odd blocks are admissible obstructions to immediate pruning.",
                f"""{base_defs}

theorem all_odd_block_is_obstruction_{suffix} :
    obstructionBlock_{suffix} [1, 1, 1] := by
  native_decide
""",
                True,
                "all_odd_obstruction",
            ),
            (
                "closure_probe",
                "Coverage hunt: appending an even prune bit normalizes a concrete obstruction block.",
                f"""{base_defs}

theorem extend_all_odd_block_with_prune_{suffix} :
    normalizesByPrune_{suffix} (extendWithPrune_{suffix} [1, 1, 1]) := by
  native_decide
""",
                False,
                "extension_prune",
            ),
            (
                "anti_smuggling_probe",
                "Coverage hunt: trivial extension coverage is too weak because it ignores dynamics.",
                f"""{base_defs}

theorem trivial_extension_coverage_does_not_use_collatz_{suffix} :
    GlobalCoverageCandidate_{suffix} := by
  intro bits hbits
  by_cases h : normalizesByPrune_{suffix} bits
  · exact Or.inl h
  · exact Or.inr (by
      unfold normalizesByPrune_{suffix} blockHasEvenPrune_{suffix} extendWithPrune_{suffix}
      simp)
""",
                True,
                "trivial_extension_anti_signal",
            ),
            (
                "anti_smuggling_probe",
                "Coverage hunt: immediate pruning is false for an admissible all-odd block.",
                f"""{base_defs}

theorem immediate_pruning_coverage_false_{suffix} :
    Not (forall bits : List Nat, admissibleBlock_{suffix} bits -> normalizesByPrune_{suffix} bits) := by
  intro h
  have hadm : admissibleBlock_{suffix} [1, 1, 1] := by native_decide
  have hnorm := h [1, 1, 1] hadm
  native_decide
""",
                True,
                "immediate_coverage_false",
            ),
            (
                "anti_smuggling_probe",
                "Coverage hunt: short-block coverage still sees the 3 -> 10 -> 5 growth obstruction.",
                f"""{base_defs}

theorem short_block_growth_obstruction_at_three_{suffix} :
    Not (Nat.iterate coverStep_{suffix} 2 3 < 3) := by
  native_decide
""",
                True,
                "short_block_growth",
            ),
            (
                "closure_probe",
                "Coverage hunt: even-root pruning remains a genuine local descent witness.",
                f"""{base_defs}

theorem even_root_local_prune_at_ten_{suffix} :
    coverStep_{suffix} 10 < 10 := by
  native_decide
""",
                False,
                "even_root_prune",
            ),
            (
                "anti_smuggling_probe",
                "Coverage hunt: block complexity can increase when extending to find pruning.",
                f"""{base_defs}

theorem extension_can_increase_block_complexity_{suffix} :
    blockComplexity_{suffix} [1, 1, 1] <
      blockComplexity_{suffix} (extendWithPrune_{suffix} [1, 1, 1]) := by
  native_decide
""",
                True,
                "extension_complexity_gate",
            ),
            (
                "closure_probe",
                "Coverage hunt: obstruction classes can be stated as a smaller named target.",
                f"""{base_defs}

def ObstructionClassCovered_{suffix} : Prop :=
  forall bits : List Nat,
    obstructionBlock_{suffix} bits -> normalizesByPrune_{suffix} (extendWithPrune_{suffix} bits)

theorem obstruction_class_covered_by_forced_extension_{suffix} :
    ObstructionClassCovered_{suffix} := by
  intro bits hobs
  unfold normalizesByPrune_{suffix} blockHasEvenPrune_{suffix} extendWithPrune_{suffix}
  simp
""",
                True,
                "obstruction_class_target",
            ),
            (
                "closure_probe",
                "Coverage hunt: density-weakened coverage can be stated without proving full Collatz.",
                f"""{base_defs}

def DensityWeakCoverage_{suffix} : Prop :=
  forall bits : List Nat,
    admissibleBlock_{suffix} bits -> Exists fun extension : List Nat =>
      normalizesByPrune_{suffix} (bits ++ extension)

theorem density_weak_coverage_has_trivial_forced_extension_{suffix} :
    DensityWeakCoverage_{suffix} := by
  intro bits hbits
  exact Exists.intro [0] (by
    unfold normalizesByPrune_{suffix} blockHasEvenPrune_{suffix}
    simp)
""",
                True,
                "density_weak_gate",
            ),
            (
                "anti_smuggling_probe",
                "Decisive coverage gate: forced-extension coverage is not enough unless the extension is dynamically admissible.",
                f"""{base_defs}

def DynamicallyAdmissibleExtension_{suffix} (bits extension : List Nat) : Prop :=
  extension.length > 0 /\\ admissibleBlock_{suffix} (bits ++ extension)

theorem forced_extension_only_solves_syntax_{suffix} :
    DynamicallyAdmissibleExtension_{suffix} [1, 1, 1] [0] /\\
    normalizesByPrune_{suffix} ([1, 1, 1] ++ [0]) := by
  constructor
  · native_decide
  · native_decide
""",
                True,
                "dynamic_admissibility_gate",
            ),
        ]

        probes: list[FormalProbe] = []
        for probe_type, source_text, lean, decisive, role in specs[:max_probes]:
            metadata = {
                "coverage_normalization_hunt": True,
                "coverage_normalization_role": role,
                "decisive": decisive,
                "world_id": world_id,
            }
            probes.append(
                FormalProbe(
                    world_id=world_id,
                    probe_type=probe_type,  # type: ignore[arg-type]
                    source_text=source_text,
                    formal_obligation=FormalObligationSpec(
                        source_text=source_text,
                        channel_hint="proof",
                        goal_kind="theorem",
                        lean_declaration=lean,
                        requires_proof=True,
                        metadata=metadata,
                    ),
                    notes=(
                        "Coverage-normalization probe; use results as the final decision gate "
                        "for the current hybrid certificate lineage."
                    ),
                )
            )
        return probes

    def _compile_cylinder_pressure_wave_probes(
        self,
        *,
        world_id: str,
        max_probes: int,
    ) -> list[FormalProbe]:
        suffix = _lean_suffix(world_id)
        base_defs = f"""
def cylStep_{suffix} (n : Nat) : Nat :=
  if n % 2 = 0 then n / 2 else 3*n + 1

structure Cylinder_{suffix} where
  k : Nat
  r : Nat

def cylinderMod_{suffix} (c : Cylinder_{suffix}) : Nat :=
  2 ^ c.k

def inCylinder_{suffix} (n : Nat) (c : Cylinder_{suffix}) : Prop :=
  n % cylinderMod_{suffix} c = c.r % cylinderMod_{suffix} c

def firstBitLegal_{suffix} (c : Cylinder_{suffix}) (bit : Nat) : Prop :=
  c.r % 2 = bit

def oddDebt_{suffix} (bits : List Nat) : Nat :=
  bits.foldl (fun acc bit => acc + bit) 0

def pressureSurplus_{suffix} (bits : List Nat) : Nat :=
  bits.length - 2 * oddDebt_{suffix} bits

def positivePressure_{suffix} (bits : List Nat) : Prop :=
  2 * oddDebt_{suffix} bits < bits.length

def cylinderMassDenom_{suffix} (c : Cylinder_{suffix}) : Nat :=
  2 ^ c.k

def childLow_{suffix} (c : Cylinder_{suffix}) : Cylinder_{suffix} :=
  {{ k := c.k + 1, r := c.r }}

def childHigh_{suffix} (c : Cylinder_{suffix}) : Cylinder_{suffix} :=
  {{ k := c.k + 1, r := c.r + 2 ^ c.k }}

def oddCylinder_{suffix} : Cylinder_{suffix} := {{ k := 1, r := 1 }}
def threeModFourCylinder_{suffix} : Cylinder_{suffix} := {{ k := 2, r := 3 }}
def zeroModFourCylinder_{suffix} : Cylinder_{suffix} := {{ k := 2, r := 0 }}

def affineOddEven_{suffix} (n : Nat) : Nat :=
  (3 * n + 1) / 2

def fakeForcedEvenExtension_{suffix} (c : Cylinder_{suffix}) : Prop :=
  firstBitLegal_{suffix} c 0

def BadPressureCylinder_{suffix} (c : Cylinder_{suffix}) (bits : List Nat) : Prop :=
  inCylinder_{suffix} c.r c /\\ ¬ positivePressure_{suffix} bits

def DensityBadBound_{suffix} (level badCount : Nat) : Prop :=
  badCount <= 2 ^ level
""".strip()
        specs: list[tuple[str, str, str, bool, str]] = [
            (
                "definition_probe",
                "Cylinder pressure: 2-adic residue cylinders are definable.",
                f"""{base_defs}

theorem cylinder_mod_three_mod_four_{suffix} :
    cylinderMod_{suffix} threeModFourCylinder_{suffix} = 4 := by
  native_decide
""",
                False,
                "cylinder_definition",
            ),
            (
                "definition_probe",
                "Cylinder pressure: cylinder membership is residue equality, not reachability.",
                f"""{base_defs}

theorem three_in_three_mod_four_cylinder_{suffix} :
    inCylinder_{suffix} 3 threeModFourCylinder_{suffix} := by
  native_decide
""",
                False,
                "cylinder_membership",
            ),
            (
                "bridge_probe",
                "Cylinder pressure: dynamic first-bit admissibility accepts the odd cylinder.",
                f"""{base_defs}

theorem odd_cylinder_legal_first_bit_{suffix} :
    firstBitLegal_{suffix} oddCylinder_{suffix} 1 := by
  native_decide
""",
                False,
                "dynamic_first_bit",
            ),
            (
                "anti_smuggling_probe",
                "Cylinder pressure: forced even extension is rejected on the odd cylinder.",
                f"""{base_defs}

theorem odd_cylinder_rejects_forced_even_extension_{suffix} :
    Not (fakeForcedEvenExtension_{suffix} oddCylinder_{suffix}) := by
  native_decide
""",
                True,
                "reject_forced_extension",
            ),
            (
                "simulation_probe",
                "Cylinder pressure: the odd-even block has concrete affine transport at n = 3.",
                f"""{base_defs}

theorem odd_even_affine_transport_at_three_{suffix} :
    affineOddEven_{suffix} 3 = 5 := by
  native_decide
""",
                False,
                "affine_transport",
            ),
            (
                "closure_probe",
                "Cylinder pressure: a two-even-after-odd block has positive pressure.",
                f"""{base_defs}

theorem positive_pressure_100_{suffix} :
    positivePressure_{suffix} [1, 0, 0] := by
  native_decide
""",
                False,
                "positive_pressure",
            ),
            (
                "anti_smuggling_probe",
                "Cylinder pressure: the short odd-even block is pressure-neutral, not positive.",
                f"""{base_defs}

theorem odd_even_not_positive_pressure_{suffix} :
    Not (positivePressure_{suffix} [1, 0]) := by
  native_decide
""",
                True,
                "neutral_pressure_gate",
            ),
            (
                "anti_smuggling_probe",
                "Cylinder pressure: all-odd blocks are bad-pressure cylinders.",
                f"""{base_defs}

theorem all_odd_bad_pressure_example_{suffix} :
    BadPressureCylinder_{suffix} oddCylinder_{suffix} [1, 1, 1] := by
  constructor
  · native_decide
  · native_decide
""",
                True,
                "bad_pressure_obstruction",
            ),
            (
                "closure_probe",
                "Cylinder pressure: legal cylinder refinement splits mass denominator by two.",
                f"""{base_defs}

theorem child_low_mass_denominator_doubles_{suffix} :
    cylinderMassDenom_{suffix} (childLow_{suffix} threeModFourCylinder_{suffix}) =
      2 * cylinderMassDenom_{suffix} threeModFourCylinder_{suffix} := by
  native_decide
""",
                False,
                "mass_refinement",
            ),
            (
                "closure_probe",
                "Cylinder pressure: high child still refines to a concrete residue cylinder.",
                f"""{base_defs}

theorem child_high_three_mod_four_has_mod_eight_residue_{suffix} :
    cylinderMod_{suffix} (childHigh_{suffix} threeModFourCylinder_{suffix}) = 8 /\\
    (childHigh_{suffix} threeModFourCylinder_{suffix}).r = 7 := by
  native_decide
""",
                False,
                "high_child_refinement",
            ),
            (
                "closure_probe",
                "Cylinder pressure: density-style bad bounds are statable without reachesOne.",
                f"""{base_defs}

theorem density_bad_bound_trivial_level_three_{suffix} :
    DensityBadBound_{suffix} 3 5 := by
  native_decide
""",
                True,
                "density_bad_bound",
            ),
            (
                "anti_smuggling_probe",
                "Decisive cylinder-pressure gate: pressure language has no reachability field.",
                f"""{base_defs}

structure PressureState_{suffix} where
  cylinder : Cylinder_{suffix}
  bits : List Nat
  surplus : Nat

def pressureStateExample_{suffix} : PressureState_{suffix} :=
  {{ cylinder := threeModFourCylinder_{suffix}, bits := [1, 0], surplus := pressureSurplus_{suffix} [1, 0] }}

theorem pressure_state_example_has_neutral_surplus_{suffix} :
    pressureStateExample_{suffix}.surplus = 0 := by
  native_decide
""",
                True,
                "pressure_no_reachability",
            ),
        ]

        probes: list[FormalProbe] = []
        for probe_type, source_text, lean, decisive, role in specs[:max_probes]:
            metadata = {
                "cylinder_pressure_wave": True,
                "cylinder_pressure_role": role,
                "decisive": decisive,
                "world_id": world_id,
            }
            probes.append(
                FormalProbe(
                    world_id=world_id,
                    probe_type=probe_type,  # type: ignore[arg-type]
                    source_text=source_text,
                    formal_obligation=FormalObligationSpec(
                        source_text=source_text,
                        channel_hint="proof",
                        goal_kind="theorem",
                        lean_declaration=lean,
                        requires_proof=True,
                        metadata=metadata,
                    ),
                    notes=(
                        "Cylinder pressure probe; use results to decide whether dynamic 2-adic "
                        "admissibility gives a new world beyond local certificates."
                    ),
                )
            )
        return probes

    def _compile_pressure_globalization_wave_probes(
        self,
        *,
        world_id: str,
        max_probes: int,
    ) -> list[FormalProbe]:
        suffix = _lean_suffix(world_id)
        base_defs = f"""
structure GlobalCylinder_{suffix} where
  k : Nat
  r : Nat

def globalMod_{suffix} (c : GlobalCylinder_{suffix}) : Nat :=
  2 ^ c.k

def globalLow_{suffix} (c : GlobalCylinder_{suffix}) : GlobalCylinder_{suffix} :=
  {{ k := c.k + 1, r := c.r }}

def globalHigh_{suffix} (c : GlobalCylinder_{suffix}) : GlobalCylinder_{suffix} :=
  {{ k := c.k + 1, r := c.r + 2 ^ c.k }}

def globalIn_{suffix} (n : Nat) (c : GlobalCylinder_{suffix}) : Prop :=
  n % globalMod_{suffix} c = c.r % globalMod_{suffix} c

def globalFirstBitLegal_{suffix} (c : GlobalCylinder_{suffix}) (bit : Nat) : Prop :=
  c.r % 2 = bit

def globalOddDebt_{suffix} (bits : List Nat) : Nat :=
  bits.foldl (fun acc bit => acc + bit) 0

def globalPositivePressure_{suffix} (bits : List Nat) : Prop :=
  2 * globalOddDebt_{suffix} bits < bits.length

def globalBadBlock_{suffix} (bits : List Nat) : Prop :=
  ¬ globalPositivePressure_{suffix} bits

def pressureRecovered_{suffix} (prefix suffixBits : List Nat) : Prop :=
  globalPositivePressure_{suffix} (prefix ++ suffixBits)

structure BadFrontier_{suffix} where
  level : Nat
  badCount : Nat

def badMassDenom_{suffix} (f : BadFrontier_{suffix}) : Nat :=
  2 ^ f.level

def StrictMassDecay_{suffix} (parent child : BadFrontier_{suffix}) : Prop :=
  child.level = parent.level + 1 /\\ 2 * child.badCount < parent.badCount

def DensityZeroAt_{suffix} (f : BadFrontier_{suffix}) : Prop :=
  f.badCount = 0

structure PressureGlobalTarget_{suffix} where
  horizon : Nat
  bad : BadFrontier_{suffix}
  recovered : Prop

def threeModFourGlobal_{suffix} : GlobalCylinder_{suffix} := {{ k := 2, r := 3 }}
def oneBadParent_{suffix} : BadFrontier_{suffix} := {{ level := 0, badCount := 1 }}
def oneBadChild_{suffix} : BadFrontier_{suffix} := {{ level := 1, badCount := 1 }}
def zeroBadChild_{suffix} : BadFrontier_{suffix} := {{ level := 1, badCount := 0 }}
def twoLevelZeroBad_{suffix} : BadFrontier_{suffix} := {{ level := 2, badCount := 0 }}
""".strip()
        specs: list[tuple[str, str, str, bool, str]] = [
            (
                "definition_probe",
                "Pressure globalization: legal split-tree cylinders are definable.",
                f"""{base_defs}

theorem split_tree_low_level_advances_{suffix} :
    (globalLow_{suffix} threeModFourGlobal_{suffix}).k = 3 := by
  native_decide
""",
                False,
                "split_tree_definition",
            ),
            (
                "closure_probe",
                "Pressure globalization: high child gives the expected mod-eight residue.",
                f"""{base_defs}

theorem split_tree_high_residue_{suffix} :
    (globalHigh_{suffix} threeModFourGlobal_{suffix}).r = 7 /\\
    globalMod_{suffix} (globalHigh_{suffix} threeModFourGlobal_{suffix}) = 8 := by
  native_decide
""",
                False,
                "split_tree_high_child",
            ),
            (
                "closure_probe",
                "Pressure globalization: split refinement doubles mass denominator.",
                f"""{base_defs}

theorem split_refinement_doubles_mass_denominator_{suffix} :
    badMassDenom_{suffix} oneBadChild_{suffix} =
      2 * badMassDenom_{suffix} oneBadParent_{suffix} := by
  native_decide
""",
                False,
                "mass_denominator",
            ),
            (
                "anti_smuggling_probe",
                "Pressure globalization: bad-frontier state has no reachability field.",
                f"""{base_defs}

def badFrontierExample_{suffix} : BadFrontier_{suffix} :=
  {{ level := 3, badCount := 2 }}

theorem bad_frontier_example_is_pure_counting_data_{suffix} :
    badFrontierExample_{suffix}.level = 3 /\\ badFrontierExample_{suffix}.badCount = 2 := by
  native_decide
""",
                True,
                "frontier_no_reachability",
            ),
            (
                "closure_probe",
                "Pressure globalization: all-odd bad block recovers after four legal even refinements.",
                f"""{base_defs}

theorem all_odd_block_recovers_after_four_evens_{suffix} :
    pressureRecovered_{suffix} [1, 1, 1] [0, 0, 0, 0] := by
  native_decide
""",
                True,
                "pressure_recovery",
            ),
            (
                "anti_smuggling_probe",
                "Pressure globalization: all-odd extension remains a bad-pressure obstruction.",
                f"""{base_defs}

theorem all_odd_extension_still_bad_{suffix} :
    globalBadBlock_{suffix} [1, 1, 1, 1] := by
  native_decide
""",
                True,
                "all_odd_obstruction",
            ),
            (
                "anti_smuggling_probe",
                "Pressure globalization: one bad child is not strict mass decay.",
                f"""{base_defs}

theorem one_bad_child_not_strict_mass_decay_{suffix} :
    Not (StrictMassDecay_{suffix} oneBadParent_{suffix} oneBadChild_{suffix}) := by
  native_decide
""",
                True,
                "one_bad_child_no_decay",
            ),
            (
                "closure_probe",
                "Pressure globalization: zero bad children give strict mass decay.",
                f"""{base_defs}

theorem zero_bad_child_is_strict_mass_decay_{suffix} :
    StrictMassDecay_{suffix} oneBadParent_{suffix} zeroBadChild_{suffix} := by
  native_decide
""",
                True,
                "zero_bad_child_decay",
            ),
            (
                "closure_probe",
                "Pressure globalization: density-zero frontier is a formal target.",
                f"""{base_defs}

theorem zero_bad_child_is_density_zero_target_{suffix} :
    DensityZeroAt_{suffix} zeroBadChild_{suffix} := by
  native_decide
""",
                False,
                "density_zero_target",
            ),
            (
                "closure_probe",
                "Pressure globalization: two-level zero-bad frontier has denominator four.",
                f"""{base_defs}

theorem two_level_zero_bad_denominator_four_{suffix} :
    badMassDenom_{suffix} twoLevelZeroBad_{suffix} = 4 := by
  native_decide
""",
                False,
                "two_level_frontier",
            ),
            (
                "bridge_probe",
                "Pressure globalization: pressure recovery target can package horizon and bad frontier.",
                f"""{base_defs}

def pressureGlobalTargetExample_{suffix} : PressureGlobalTarget_{suffix} :=
  {{ horizon := 7, bad := zeroBadChild_{suffix}, recovered := pressureRecovered_{suffix} [1, 1, 1] [0, 0, 0, 0] }}

theorem pressure_global_target_example_horizon_{suffix} :
    pressureGlobalTargetExample_{suffix}.horizon = 7 := by
  native_decide
""",
                False,
                "global_target_packaging",
            ),
            (
                "anti_smuggling_probe",
                "Decisive pressure-globalization gate: bad-mass decay is stronger than one legal split.",
                f"""{base_defs}

theorem one_legal_split_does_not_imply_decay_{suffix} :
    globalFirstBitLegal_{suffix} threeModFourGlobal_{suffix} 1 /\\
    Not (StrictMassDecay_{suffix} oneBadParent_{suffix} oneBadChild_{suffix}) := by
  constructor
  · native_decide
  · native_decide
""",
                True,
                "decay_stronger_than_split",
            ),
        ]

        probes: list[FormalProbe] = []
        for probe_type, source_text, lean, decisive, role in specs[:max_probes]:
            metadata = {
                "pressure_globalization_wave": True,
                "pressure_globalization_role": role,
                "decisive": decisive,
                "world_id": world_id,
            }
            probes.append(
                FormalProbe(
                    world_id=world_id,
                    probe_type=probe_type,  # type: ignore[arg-type]
                    source_text=source_text,
                    formal_obligation=FormalObligationSpec(
                        source_text=source_text,
                        channel_hint="proof",
                        goal_kind="theorem",
                        lean_declaration=lean,
                        requires_proof=True,
                        metadata=metadata,
                    ),
                    notes=(
                        "Pressure globalization probe; use results to decide whether legal "
                        "2-adic refinement can support bad-cylinder mass decay."
                    ),
                )
            )
        return probes

    def _compile_pivot_portfolio_wave_probes(
        self,
        *,
        world_id: str,
        max_probes: int,
    ) -> list[FormalProbe]:
        suffix = _lean_suffix(world_id)
        base_defs = f"""
structure PortfolioCylinder_{suffix} where
  level : Nat
  residue : Nat

def portfolioMod_{suffix} (c : PortfolioCylinder_{suffix}) : Nat :=
  2 ^ c.level

def portfolioHigh_{suffix} (c : PortfolioCylinder_{suffix}) : PortfolioCylinder_{suffix} :=
  {{ level := c.level + 1, residue := c.residue + 2 ^ c.level }}

def oddDebtPortfolio_{suffix} (bits : List Nat) : Nat :=
  bits.foldl (fun acc bit => acc + bit) 0

def positivePortfolioPressure_{suffix} (bits : List Nat) : Prop :=
  2 * oddDebtPortfolio_{suffix} bits < bits.length

structure BadBranchFrontier_{suffix} where
  level : Nat
  badChildren : Nat
  totalChildren : Nat

def subcriticalBadBranch_{suffix} (f : BadBranchFrontier_{suffix}) : Prop :=
  2 * f.badChildren < f.totalChildren

def pressureRecoveryWindow_{suffix} (bad recovery : List Nat) : Prop :=
  positivePortfolioPressure_{suffix} (bad ++ recovery)

structure InverseTreeNode_{suffix} where
  value : Nat
  parent : Nat
  parityTag : Nat

def inverseOddParentLegal_{suffix} (child parent : Nat) : Prop :=
  child = 3 * parent + 1

def inverseEvenParentLegal_{suffix} (child parent : Nat) : Prop :=
  child = parent / 2

def dynamicInverseAdmissible_{suffix} (node : InverseTreeNode_{suffix}) : Prop :=
  if node.parityTag = 1 then inverseOddParentLegal_{suffix} node.value node.parent
  else inverseEvenParentLegal_{suffix} node.value node.parent

structure MinimalEcology_{suffix} where
  candidate : Nat
  descendant : Nat
  energy : Nat

def ecologyDominates_{suffix} (e : MinimalEcology_{suffix}) : Prop :=
  e.descendant < e.candidate /\\ e.energy < e.candidate

def minimalCounterexampleSurvives_{suffix} (e : MinimalEcology_{suffix}) : Prop :=
  e.candidate <= e.descendant

structure DensityTransport_{suffix} where
  level : Nat
  exceptional : Nat
  total : Nat

def densityImproves_{suffix} (before after : DensityTransport_{suffix}) : Prop :=
  after.level = before.level + 1 /\\ 2 * after.exceptional < before.exceptional

def densityBounded_{suffix} (d : DensityTransport_{suffix}) : Prop :=
  d.exceptional <= d.total

def pressureFrontierGood_{suffix} : BadBranchFrontier_{suffix} :=
  {{ level := 4, badChildren := 1, totalChildren := 4 }}

def pressureFrontierBad_{suffix} : BadBranchFrontier_{suffix} :=
  {{ level := 4, badChildren := 2, totalChildren := 4 }}

def inverseOddExample_{suffix} : InverseTreeNode_{suffix} :=
  {{ value := 10, parent := 3, parityTag := 1 }}

def inverseFakeExample_{suffix} : InverseTreeNode_{suffix} :=
  {{ value := 10, parent := 4, parityTag := 1 }}

def ecologyGoodExample_{suffix} : MinimalEcology_{suffix} :=
  {{ candidate := 9, descendant := 4, energy := 3 }}

def ecologyBadExample_{suffix} : MinimalEcology_{suffix} :=
  {{ candidate := 9, descendant := 10, energy := 8 }}

def densityBefore_{suffix} : DensityTransport_{suffix} :=
  {{ level := 3, exceptional := 3, total := 8 }}

def densityAfterGood_{suffix} : DensityTransport_{suffix} :=
  {{ level := 4, exceptional := 1, total := 16 }}

def densityAfterBad_{suffix} : DensityTransport_{suffix} :=
  {{ level := 4, exceptional := 2, total := 16 }}

def pressureFrontierTinyGood_{suffix} : BadBranchFrontier_{suffix} :=
  {{ level := 5, badChildren := 1, totalChildren := 8 }}

def pressureFrontierNeutral_{suffix} : BadBranchFrontier_{suffix} :=
  {{ level := 5, badChildren := 4, totalChildren := 8 }}

def inverseEvenExample_{suffix} : InverseTreeNode_{suffix} :=
  {{ value := 5, parent := 10, parityTag := 0 }}

def inverseFakeEvenExample_{suffix} : InverseTreeNode_{suffix} :=
  {{ value := 5, parent := 12, parityTag := 0 }}

def ecologyStrongExample_{suffix} : MinimalEcology_{suffix} :=
  {{ candidate := 27, descendant := 13, energy := 5 }}

def ecologyEnergyTrap_{suffix} : MinimalEcology_{suffix} :=
  {{ candidate := 27, descendant := 13, energy := 30 }}

def densityAfterTinyGood_{suffix} : DensityTransport_{suffix} :=
  {{ level := 5, exceptional := 0, total := 32 }}

def densityAfterNeutral_{suffix} : DensityTransport_{suffix} :=
  {{ level := 4, exceptional := 3, total := 16 }}

def pressureToDensity_{suffix} (f : BadBranchFrontier_{suffix}) : DensityTransport_{suffix} :=
  {{ level := f.level, exceptional := f.badChildren, total := f.totalChildren }}

def ecologyToDensity_{suffix} (e : MinimalEcology_{suffix}) : DensityTransport_{suffix} :=
  {{ level := e.energy, exceptional := e.descendant, total := e.candidate }}

def inverseCarriesOddBit_{suffix} (node : InverseTreeNode_{suffix}) : Prop :=
  node.parityTag = 1
""".strip()
        specs: list[tuple[str, str, str, bool, str, str]] = [
            (
                "closure_probe",
                "Pivot portfolio / pressure scarcity: subcritical bad branching is expressible.",
                f"""{base_defs}

theorem pressure_subcritical_branching_example_{suffix} :
    subcriticalBadBranch_{suffix} pressureFrontierGood_{suffix} := by
  native_decide
""",
                True,
                "pressure_scarcity",
                "subcritical_branching",
            ),
            (
                "anti_smuggling_probe",
                "Pivot portfolio / pressure scarcity: half-bad branching is not subcritical.",
                f"""{base_defs}

theorem pressure_half_bad_branching_not_subcritical_{suffix} :
    Not (subcriticalBadBranch_{suffix} pressureFrontierBad_{suffix}) := by
  native_decide
""",
                True,
                "pressure_scarcity",
                "bad_branching_gate",
            ),
            (
                "closure_probe",
                "Pivot portfolio / pressure scarcity: bad all-odd window can recover after four evens.",
                f"""{base_defs}

theorem pressure_recovery_window_example_{suffix} :
    pressureRecoveryWindow_{suffix} [1, 1, 1] [0, 0, 0, 0] := by
  native_decide
""",
                True,
                "pressure_scarcity",
                "recovery_window",
            ),
            (
                "bridge_probe",
                "Pivot portfolio / pressure scarcity: cylinder high child remains concrete.",
                f"""{base_defs}

theorem portfolio_high_child_residue_{suffix} :
    (portfolioHigh_{suffix} {{ level := 2, residue := 3 }}).residue = 7 := by
  native_decide
""",
                False,
                "pressure_scarcity",
                "cylinder_refinement",
            ),
            (
                "definition_probe",
                "Pivot portfolio / inverse tree: dynamic inverse nodes are definable.",
                f"""{base_defs}

theorem inverse_node_example_value_{suffix} :
    inverseOddExample_{suffix}.value = 10 := by
  native_decide
""",
                False,
                "inverse_tree_dynamic_admissibility",
                "inverse_definition",
            ),
            (
                "closure_probe",
                "Pivot portfolio / inverse tree: 10 <- 3 is dynamically admissible.",
                f"""{base_defs}

theorem inverse_odd_example_admissible_{suffix} :
    dynamicInverseAdmissible_{suffix} inverseOddExample_{suffix} := by
  native_decide
""",
                True,
                "inverse_tree_dynamic_admissibility",
                "inverse_admissible",
            ),
            (
                "anti_smuggling_probe",
                "Pivot portfolio / inverse tree: fake odd predecessor is rejected.",
                f"""{base_defs}

theorem inverse_fake_odd_parent_rejected_{suffix} :
    Not (dynamicInverseAdmissible_{suffix} inverseFakeExample_{suffix}) := by
  native_decide
""",
                True,
                "inverse_tree_dynamic_admissibility",
                "inverse_fake_rejected",
            ),
            (
                "anti_smuggling_probe",
                "Pivot portfolio / inverse tree: admissibility is local equality, not reachesOne.",
                f"""{base_defs}

theorem inverse_admissibility_local_equality_{suffix} :
    inverseOddParentLegal_{suffix} 10 3 := by
  native_decide
""",
                True,
                "inverse_tree_dynamic_admissibility",
                "inverse_no_reachability",
            ),
            (
                "definition_probe",
                "Pivot portfolio / minimal ecology: dominance ecology is definable.",
                f"""{base_defs}

theorem ecology_good_candidate_value_{suffix} :
    ecologyGoodExample_{suffix}.candidate = 9 := by
  native_decide
""",
                False,
                "minimal_counterexample_ecology",
                "ecology_definition",
            ),
            (
                "closure_probe",
                "Pivot portfolio / minimal ecology: dominated candidate has lower descendant and energy.",
                f"""{base_defs}

theorem ecology_good_dominates_{suffix} :
    ecologyDominates_{suffix} ecologyGoodExample_{suffix} := by
  native_decide
""",
                True,
                "minimal_counterexample_ecology",
                "ecology_dominance",
            ),
            (
                "anti_smuggling_probe",
                "Pivot portfolio / minimal ecology: survivor condition blocks dominance.",
                f"""{base_defs}

theorem ecology_bad_survives_but_does_not_dominate_{suffix} :
    minimalCounterexampleSurvives_{suffix} ecologyBadExample_{suffix} /\\
    Not (ecologyDominates_{suffix} ecologyBadExample_{suffix}) := by
  native_decide
""",
                True,
                "minimal_counterexample_ecology",
                "ecology_survivor_gate",
            ),
            (
                "anti_smuggling_probe",
                "Pivot portfolio / minimal ecology: dominance target is not termination.",
                f"""{base_defs}

theorem ecology_dominance_is_local_inequality_{suffix} :
    ecologyGoodExample_{suffix}.descendant < ecologyGoodExample_{suffix}.candidate := by
  native_decide
""",
                True,
                "minimal_counterexample_ecology",
                "ecology_no_termination",
            ),
            (
                "definition_probe",
                "Pivot portfolio / density transport: exceptional-density states are definable.",
                f"""{base_defs}

theorem density_before_is_bounded_{suffix} :
    densityBounded_{suffix} densityBefore_{suffix} := by
  native_decide
""",
                False,
                "tao_style_density_transport",
                "density_definition",
            ),
            (
                "closure_probe",
                "Pivot portfolio / density transport: good transport improves exceptional mass.",
                f"""{base_defs}

theorem density_good_transport_improves_{suffix} :
    densityImproves_{suffix} densityBefore_{suffix} densityAfterGood_{suffix} := by
  native_decide
""",
                True,
                "tao_style_density_transport",
                "density_improvement",
            ),
            (
                "anti_smuggling_probe",
                "Pivot portfolio / density transport: weak transport does not improve exceptional mass.",
                f"""{base_defs}

theorem density_bad_transport_not_improving_{suffix} :
    Not (densityImproves_{suffix} densityBefore_{suffix} densityAfterBad_{suffix}) := by
  native_decide
""",
                True,
                "tao_style_density_transport",
                "density_weak_gate",
            ),
            (
                "anti_smuggling_probe",
                "Pivot portfolio / density transport: density bound is counting data, not reachability.",
                f"""{base_defs}

theorem density_after_good_is_bounded_counting_data_{suffix} :
    densityBounded_{suffix} densityAfterGood_{suffix} /\\ densityAfterGood_{suffix}.total = 16 := by
  native_decide
""",
                True,
                "tao_style_density_transport",
                "density_no_reachability",
            ),
            (
                "closure_probe",
                "Pivot portfolio / pressure scarcity: tiny bad frontier is strongly subcritical.",
                f"""{base_defs}

theorem pressure_tiny_frontier_subcritical_{suffix} :
    subcriticalBadBranch_{suffix} pressureFrontierTinyGood_{suffix} := by
  native_decide
""",
                True,
                "pressure_scarcity",
                "strong_subcritical_branching",
            ),
            (
                "anti_smuggling_probe",
                "Pivot portfolio / pressure scarcity: neutral bad frontier is not enough.",
                f"""{base_defs}

theorem pressure_neutral_frontier_not_subcritical_{suffix} :
    Not (subcriticalBadBranch_{suffix} pressureFrontierNeutral_{suffix}) := by
  native_decide
""",
                True,
                "pressure_scarcity",
                "neutral_branching_gate",
            ),
            (
                "anti_smuggling_probe",
                "Pivot portfolio / pressure scarcity: three-even recovery is still insufficient.",
                f"""{base_defs}

theorem pressure_three_even_recovery_insufficient_{suffix} :
    Not (pressureRecoveryWindow_{suffix} [1, 1, 1] [0, 0, 0]) := by
  native_decide
""",
                True,
                "pressure_scarcity",
                "bounded_recovery_lower_gate",
            ),
            (
                "closure_probe",
                "Pivot portfolio / pressure scarcity: five-even recovery has slack.",
                f"""{base_defs}

theorem pressure_five_even_recovery_has_slack_{suffix} :
    pressureRecoveryWindow_{suffix} [1, 1, 1] [0, 0, 0, 0, 0] := by
  native_decide
""",
                True,
                "pressure_scarcity",
                "bounded_recovery_upper_gate",
            ),
            (
                "closure_probe",
                "Pivot portfolio / inverse tree: even inverse node is dynamically admissible.",
                f"""{base_defs}

theorem inverse_even_example_admissible_{suffix} :
    dynamicInverseAdmissible_{suffix} inverseEvenExample_{suffix} := by
  native_decide
""",
                True,
                "inverse_tree_dynamic_admissibility",
                "inverse_even_admissible",
            ),
            (
                "anti_smuggling_probe",
                "Pivot portfolio / inverse tree: fake even predecessor is rejected.",
                f"""{base_defs}

theorem inverse_fake_even_parent_rejected_{suffix} :
    Not (dynamicInverseAdmissible_{suffix} inverseFakeEvenExample_{suffix}) := by
  native_decide
""",
                True,
                "inverse_tree_dynamic_admissibility",
                "inverse_fake_even_rejected",
            ),
            (
                "anti_smuggling_probe",
                "Pivot portfolio / inverse tree: parity tag alone is not admissibility.",
                f"""{base_defs}

theorem inverse_odd_tag_alone_not_enough_{suffix} :
    inverseCarriesOddBit_{suffix} inverseFakeExample_{suffix} /\\
    Not (dynamicInverseAdmissible_{suffix} inverseFakeExample_{suffix}) := by
  native_decide
""",
                True,
                "inverse_tree_dynamic_admissibility",
                "inverse_parity_tag_gate",
            ),
            (
                "bridge_probe",
                "Pivot portfolio / inverse tree: inverse data remains local parent data.",
                f"""{base_defs}

theorem inverse_even_data_is_local_parent_data_{suffix} :
    inverseEvenExample_{suffix}.parent = 10 /\\ inverseEvenExample_{suffix}.value = 5 := by
  native_decide
""",
                False,
                "inverse_tree_dynamic_admissibility",
                "inverse_local_data",
            ),
            (
                "closure_probe",
                "Pivot portfolio / minimal ecology: strong example is dominated.",
                f"""{base_defs}

theorem ecology_strong_example_dominates_{suffix} :
    ecologyDominates_{suffix} ecologyStrongExample_{suffix} := by
  native_decide
""",
                True,
                "minimal_counterexample_ecology",
                "ecology_strong_dominance",
            ),
            (
                "anti_smuggling_probe",
                "Pivot portfolio / minimal ecology: lower descendant alone is not dominance.",
                f"""{base_defs}

theorem ecology_energy_trap_not_dominated_{suffix} :
    ecologyEnergyTrap_{suffix}.descendant < ecologyEnergyTrap_{suffix}.candidate /\\
    Not (ecologyDominates_{suffix} ecologyEnergyTrap_{suffix}) := by
  native_decide
""",
                True,
                "minimal_counterexample_ecology",
                "ecology_energy_gate",
            ),
            (
                "anti_smuggling_probe",
                "Pivot portfolio / minimal ecology: survivor obstruction is explicit.",
                f"""{base_defs}

theorem ecology_survivor_obstruction_explicit_{suffix} :
    minimalCounterexampleSurvives_{suffix} ecologyBadExample_{suffix} := by
  native_decide
""",
                True,
                "minimal_counterexample_ecology",
                "ecology_survivor_obstruction",
            ),
            (
                "bridge_probe",
                "Pivot portfolio / minimal ecology: ecology projects to bounded counting data.",
                f"""{base_defs}

theorem ecology_to_density_is_bounded_counting_data_{suffix} :
    densityBounded_{suffix} (ecologyToDensity_{suffix} ecologyStrongExample_{suffix}) := by
  native_decide
""",
                False,
                "minimal_counterexample_ecology",
                "ecology_density_projection",
            ),
            (
                "closure_probe",
                "Pivot portfolio / density transport: second-stage good transport reaches zero exceptions.",
                f"""{base_defs}

theorem density_second_stage_reaches_zero_exceptions_{suffix} :
    densityImproves_{suffix} densityAfterGood_{suffix} densityAfterTinyGood_{suffix} := by
  native_decide
""",
                True,
                "tao_style_density_transport",
                "density_second_stage_improvement",
            ),
            (
                "anti_smuggling_probe",
                "Pivot portfolio / density transport: boundedness alone is not improvement.",
                f"""{base_defs}

theorem density_bounded_neutral_not_improving_{suffix} :
    densityBounded_{suffix} densityAfterNeutral_{suffix} /\\
    Not (densityImproves_{suffix} densityBefore_{suffix} densityAfterNeutral_{suffix}) := by
  native_decide
""",
                True,
                "tao_style_density_transport",
                "density_boundedness_gate",
            ),
            (
                "bridge_probe",
                "Pivot portfolio / cross-lane: pressure frontier projects to density data.",
                f"""{base_defs}

theorem pressure_frontier_projects_to_density_data_{suffix} :
    densityBounded_{suffix} (pressureToDensity_{suffix} pressureFrontierGood_{suffix}) /\\
    (pressureToDensity_{suffix} pressureFrontierGood_{suffix}).exceptional = 1 := by
  native_decide
""",
                True,
                "cross_lane_bridge_separation",
                "pressure_density_projection",
            ),
            (
                "anti_smuggling_probe",
                "Pivot portfolio / cross-lane: inverse admissibility does not force density improvement.",
                f"""{base_defs}

theorem inverse_admissibility_separate_from_density_improvement_{suffix} :
    dynamicInverseAdmissible_{suffix} inverseOddExample_{suffix} /\\
    Not (densityImproves_{suffix} densityBefore_{suffix} densityAfterBad_{suffix}) := by
  native_decide
""",
                True,
                "cross_lane_bridge_separation",
                "inverse_density_separation",
            ),
        ]

        probes: list[FormalProbe] = []
        for probe_type, source_text, lean, decisive, family, role in specs[:max_probes]:
            metadata = {
                "pivot_portfolio_wave": True,
                "pivot_family": family,
                "pivot_role": role,
                "decisive": decisive,
                "world_id": world_id,
            }
            probes.append(
                FormalProbe(
                    world_id=world_id,
                    probe_type=probe_type,  # type: ignore[arg-type]
                    source_text=source_text,
                    formal_obligation=FormalObligationSpec(
                        source_text=source_text,
                        channel_hint="proof",
                        goal_kind="theorem",
                        lean_declaration=lean,
                        requires_proof=True,
                        metadata=metadata,
                    ),
                    notes=(
                        "Pivot portfolio probe; compare families by verified decision gates "
                        "rather than narrative plausibility."
                    ),
                )
            )
        return probes

    def _compile_composite_scarcity_viability_wave_probes(
        self,
        *,
        world_id: str,
        max_probes: int,
    ) -> list[FormalProbe]:
        suffix = _lean_suffix(world_id)
        base_defs = f"""
import Mathlib

structure ViabilityFrontier_{suffix} where
  level : Nat
  badChildren : Nat
  totalChildren : Nat

structure ViabilityDensity_{suffix} where
  level : Nat
  exceptional : Nat
  total : Nat

structure ViabilitySurvivor_{suffix} where
  candidate : Nat
  obstruction : Nat
  energy : Nat

def legalFrontier_{suffix} (f : ViabilityFrontier_{suffix}) : Prop :=
  f.totalChildren > 0 /\\ f.badChildren <= f.totalChildren

def strongScarcity_{suffix} (f : ViabilityFrontier_{suffix}) : Prop :=
  4 * f.badChildren < f.totalChildren

def weakScarcity_{suffix} (f : ViabilityFrontier_{suffix}) : Prop :=
  2 * f.badChildren <= f.totalChildren

def subcriticalScarcity_{suffix} (f : ViabilityFrontier_{suffix}) : Prop :=
  2 * f.badChildren < f.totalChildren

def pressureToDensityV_{suffix} (f : ViabilityFrontier_{suffix}) : ViabilityDensity_{suffix} :=
  {{ level := f.level, exceptional := f.badChildren, total := f.totalChildren }}

def densityImprovesV_{suffix} (before after : ViabilityDensity_{suffix}) : Prop :=
  after.level = before.level + 1 /\\ 2 * after.exceptional < before.exceptional

def densityZeroTarget_{suffix} (d : ViabilityDensity_{suffix}) : Prop :=
  d.exceptional = 0

def survivorReduces_{suffix} (before after : ViabilitySurvivor_{suffix}) : Prop :=
  after.obstruction < before.obstruction /\\ after.energy <= before.energy

def noPersistentSurvivor_{suffix} (s : ViabilitySurvivor_{suffix}) : Prop :=
  s.obstruction = 0

def finalObstructionRemoved_{suffix} (d : ViabilityDensity_{suffix}) (s : ViabilitySurvivor_{suffix}) : Prop :=
  densityZeroTarget_{suffix} d /\\ noPersistentSurvivor_{suffix} s

def compositeScarcityStep_{suffix}
    (f : ViabilityFrontier_{suffix})
    (before after : ViabilityDensity_{suffix})
    (sBefore sAfter : ViabilitySurvivor_{suffix}) : Prop :=
  legalFrontier_{suffix} f ->
    densityImprovesV_{suffix} before after \\/ survivorReduces_{suffix} sBefore sAfter

def goodFrontierV_{suffix} : ViabilityFrontier_{suffix} :=
  {{ level := 5, badChildren := 1, totalChildren := 8 }}

def neutralFrontierV_{suffix} : ViabilityFrontier_{suffix} :=
  {{ level := 5, badChildren := 4, totalChildren := 8 }}

def densityBeforeV_{suffix} : ViabilityDensity_{suffix} :=
  {{ level := 5, exceptional := 3, total := 8 }}

def densityAfterImprovedV_{suffix} : ViabilityDensity_{suffix} :=
  {{ level := 6, exceptional := 1, total := 16 }}

def densityAfterZeroV_{suffix} : ViabilityDensity_{suffix} :=
  {{ level := 7, exceptional := 0, total := 32 }}

def survivorBeforeV_{suffix} : ViabilitySurvivor_{suffix} :=
  {{ candidate := 27, obstruction := 5, energy := 9 }}

def survivorAfterReducedV_{suffix} : ViabilitySurvivor_{suffix} :=
  {{ candidate := 27, obstruction := 3, energy := 9 }}

def survivorAfterZeroV_{suffix} : ViabilitySurvivor_{suffix} :=
  {{ candidate := 27, obstruction := 0, energy := 9 }}
""".strip()
        specs: list[tuple[str, str, str, bool, str]] = [
            (
                "definition_probe",
                "Composite scarcity viability / exact theorem shape is statable.",
                f"""{base_defs}

theorem composite_scarcity_shape_statable_{suffix} :
    compositeScarcityStep_{suffix}
      goodFrontierV_{suffix}
      densityBeforeV_{suffix}
      densityAfterImprovedV_{suffix}
      survivorBeforeV_{suffix}
      survivorAfterReducedV_{suffix} := by
  intro _legal
  left
  native_decide
""",
                True,
                "exact_composite_statement",
            ),
            (
                "bridge_probe",
                "Composite scarcity viability / density-zero target implies final obstruction removal with no survivor.",
                f"""{base_defs}

theorem density_zero_and_no_survivor_remove_final_obstruction_{suffix}
    (d : ViabilityDensity_{suffix}) (s : ViabilitySurvivor_{suffix})
    (hd : densityZeroTarget_{suffix} d) (hs : noPersistentSurvivor_{suffix} s) :
    finalObstructionRemoved_{suffix} d s := by
  exact And.intro hd hs
""",
                True,
                "pullback_shape",
            ),
            (
                "bridge_probe",
                "Composite scarcity viability / composite step can feed density decay.",
                f"""{base_defs}

theorem composite_step_feeds_density_decay_{suffix} :
    compositeScarcityStep_{suffix}
      goodFrontierV_{suffix}
      densityBeforeV_{suffix}
      densityAfterImprovedV_{suffix}
      survivorBeforeV_{suffix}
      survivorAfterReducedV_{suffix} ->
    legalFrontier_{suffix} goodFrontierV_{suffix} ->
    densityImprovesV_{suffix} densityBeforeV_{suffix} densityAfterImprovedV_{suffix} \\/
      survivorReduces_{suffix} survivorBeforeV_{suffix} survivorAfterReducedV_{suffix} := by
  intro h hlegal
  exact h hlegal
""",
                True,
                "implication_chain",
            ),
            (
                "anti_smuggling_probe",
                "Composite scarcity viability / statement has no reachability or termination field.",
                f"""{base_defs}

theorem composite_statement_uses_only_counting_fields_{suffix} :
    goodFrontierV_{suffix}.badChildren = 1 /\\
    densityBeforeV_{suffix}.exceptional = 3 /\\
    survivorBeforeV_{suffix}.obstruction = 5 := by
  native_decide
""",
                True,
                "anti_smuggling_field_check",
            ),
            (
                "anti_smuggling_probe",
                "Composite scarcity viability / small legal frontier does not refute the composite step.",
                f"""{base_defs}

theorem small_legal_frontier_has_composite_escape_{suffix} :
    legalFrontier_{suffix} goodFrontierV_{suffix} /\\
    (densityImprovesV_{suffix} densityBeforeV_{suffix} densityAfterImprovedV_{suffix} \\/
      survivorReduces_{suffix} survivorBeforeV_{suffix} survivorAfterReducedV_{suffix}) := by
  constructor
  · native_decide
  · left
    native_decide
""",
                True,
                "small_counterexample_gate",
            ),
            (
                "closure_probe",
                "Composite scarcity viability / restricted quantitative scarcity implies subcriticality.",
                f"""{base_defs}

theorem strong_scarcity_implies_subcritical_{suffix}
    (f : ViabilityFrontier_{suffix})
    (h : strongScarcity_{suffix} f) :
    subcriticalScarcity_{suffix} f := by
  unfold strongScarcity_{suffix} subcriticalScarcity_{suffix} at *
  omega
""",
                True,
                "restricted_quantitative_inequality",
            ),
            (
                "closure_probe",
                "Composite scarcity viability / survivor obstruction can strictly decrease.",
                f"""{base_defs}

theorem survivor_obstruction_decreases_example_{suffix} :
    survivorReduces_{suffix} survivorBeforeV_{suffix} survivorAfterReducedV_{suffix} := by
  native_decide
""",
                True,
                "survivor_reduction_gate",
            ),
            (
                "anti_smuggling_probe",
                "Composite scarcity viability / weak scarcity is insufficient for strict decay.",
                f"""{base_defs}

theorem weak_scarcity_not_enough_for_subcritical_{suffix} :
    weakScarcity_{suffix} neutralFrontierV_{suffix} /\\
    Not (subcriticalScarcity_{suffix} neutralFrontierV_{suffix}) := by
  native_decide
""",
                True,
                "weak_scarcity_insufficient",
            ),
        ]

        probes: list[FormalProbe] = []
        for probe_type, source_text, lean, decisive, role in specs[:max_probes]:
            metadata = {
                "composite_scarcity_viability_wave": True,
                "viability_role": role,
                "decisive": decisive,
                "world_id": world_id,
            }
            probes.append(
                FormalProbe(
                    world_id=world_id,
                    probe_type=probe_type,  # type: ignore[arg-type]
                    source_text=source_text,
                    formal_obligation=FormalObligationSpec(
                        source_text=source_text,
                        channel_hint="proof",
                        goal_kind="theorem",
                        lean_declaration=lean,
                        requires_proof=True,
                        metadata=metadata,
                    ),
                    notes=(
                        "Composite scarcity viability probe; kill or promote the "
                        "pressure-density-ecology route before larger investment."
                    ),
                )
            )
        return probes

    def _compile_composite_scarcity_theorem_wave_probes(
        self,
        *,
        world_id: str,
        max_probes: int,
    ) -> list[FormalProbe]:
        suffix = _lean_suffix(world_id)
        base_defs = f"""
import Mathlib

structure TheoremFrontier_{suffix} where
  level : Nat
  badChildren : Nat
  totalChildren : Nat

structure TheoremDensity_{suffix} where
  level : Nat
  exceptional : Nat
  total : Nat

structure SurvivorMeasure_{suffix} where
  obstruction : Nat
  fuel : Nat

def legalTheoremFrontier_{suffix} (f : TheoremFrontier_{suffix}) : Prop :=
  f.totalChildren > 0 /\\ f.badChildren <= f.totalChildren

def strongTheoremScarcity_{suffix} (f : TheoremFrontier_{suffix}) : Prop :=
  4 * f.badChildren < f.totalChildren

def weakTheoremScarcity_{suffix} (f : TheoremFrontier_{suffix}) : Prop :=
  2 * f.badChildren <= f.totalChildren

def subcriticalTheoremScarcity_{suffix} (f : TheoremFrontier_{suffix}) : Prop :=
  2 * f.badChildren < f.totalChildren

def theoremDensityOf_{suffix} (f : TheoremFrontier_{suffix}) : TheoremDensity_{suffix} :=
  {{ level := f.level, exceptional := f.badChildren, total := f.totalChildren }}

def theoremDensityContracts_{suffix} (d : TheoremDensity_{suffix}) : Prop :=
  2 * d.exceptional < d.total

def frontierDensityContracts_{suffix} (f : TheoremFrontier_{suffix}) : Prop :=
  theoremDensityContracts_{suffix} (theoremDensityOf_{suffix} f)

def fullSplitFrontier_{suffix} (level bad : Nat) : TheoremFrontier_{suffix} :=
  {{ level := level, badChildren := bad, totalChildren := 2 ^ level }}

def recoveryBeatsOddDebt_{suffix} (oddDebt badWindow recovery : Nat) : Prop :=
  2 * oddDebt < badWindow + recovery

def survivorDescends_{suffix} (before after : SurvivorMeasure_{suffix}) : Prop :=
  after.obstruction < before.obstruction /\\ after.fuel <= before.fuel

def theoremCompositeStep_{suffix}
    (f : TheoremFrontier_{suffix})
    (after : TheoremDensity_{suffix})
    (sBefore sAfter : SurvivorMeasure_{suffix}) : Prop :=
  legalTheoremFrontier_{suffix} f ->
    theoremDensityContracts_{suffix} after \\/ survivorDescends_{suffix} sBefore sAfter

def finalTheoremObstructionRemoved_{suffix}
    (d : TheoremDensity_{suffix})
    (s : SurvivorMeasure_{suffix}) : Prop :=
  d.exceptional = 0 /\\ s.obstruction = 0

def compositeScarcityNamedTarget_{suffix} (horizon : Nat) : Prop :=
  ∀ f : TheoremFrontier_{suffix},
    legalTheoremFrontier_{suffix} f ->
      strongTheoremScarcity_{suffix} f \\/
        ∃ sAfter : SurvivorMeasure_{suffix},
          survivorDescends_{suffix} {{ obstruction := horizon + f.badChildren, fuel := horizon }}
            sAfter

def strongFrontierT_{suffix} : TheoremFrontier_{suffix} :=
  {{ level := 5, badChildren := 1, totalChildren := 8 }}

def neutralFrontierT_{suffix} : TheoremFrontier_{suffix} :=
  {{ level := 5, badChildren := 4, totalChildren := 8 }}

def zeroDensityT_{suffix} : TheoremDensity_{suffix} :=
  {{ level := 8, exceptional := 0, total := 256 }}

def contractedDensityT_{suffix} : TheoremDensity_{suffix} :=
  {{ level := 8, exceptional := 1, total := 8 }}

def survivorBeforeT_{suffix} : SurvivorMeasure_{suffix} :=
  {{ obstruction := 5, fuel := 9 }}

def survivorMidT_{suffix} : SurvivorMeasure_{suffix} :=
  {{ obstruction := 3, fuel := 8 }}

def survivorAfterT_{suffix} : SurvivorMeasure_{suffix} :=
  {{ obstruction := 1, fuel := 8 }}

def survivorZeroT_{suffix} : SurvivorMeasure_{suffix} :=
  {{ obstruction := 0, fuel := 8 }}
""".strip()
        specs: list[tuple[str, str, str, bool, str]] = [
            (
                "closure_probe",
                "Composite scarcity theorem / parameterized strong scarcity implies subcritical bad mass.",
                f"""{base_defs}

theorem theorem_strong_scarcity_implies_subcritical_{suffix}
    (f : TheoremFrontier_{suffix})
    (h : strongTheoremScarcity_{suffix} f) :
    subcriticalTheoremScarcity_{suffix} f := by
  unfold strongTheoremScarcity_{suffix} subcriticalTheoremScarcity_{suffix} at *
  omega
""",
                True,
                "parameterized_strong_scarcity",
            ),
            (
                "bridge_probe",
                "Composite scarcity theorem / depth-indexed scarcity projects to density contraction.",
                f"""{base_defs}

theorem theorem_depth_scarcity_gives_density_contraction_{suffix}
    (level bad : Nat)
    (h : 4 * bad < 2 ^ level) :
    frontierDensityContracts_{suffix} (fullSplitFrontier_{suffix} level bad) := by
  unfold frontierDensityContracts_{suffix} theoremDensityContracts_{suffix}
    theoremDensityOf_{suffix} fullSplitFrontier_{suffix} at *
  omega
""",
                True,
                "depth_indexed_density_contraction",
            ),
            (
                "closure_probe",
                "Composite scarcity theorem / bounded recovery beats odd debt with a parameterized margin.",
                f"""{base_defs}

theorem theorem_recovery_margin_beats_odd_debt_{suffix}
    (oddDebt badWindow recovery : Nat)
    (hDebt : oddDebt = badWindow)
    (hRecovery : badWindow + 1 <= recovery) :
    recoveryBeatsOddDebt_{suffix} oddDebt badWindow recovery := by
  unfold recoveryBeatsOddDebt_{suffix}
  omega
""",
                True,
                "parameterized_recovery_margin",
            ),
            (
                "anti_smuggling_probe",
                "Composite scarcity theorem / equal recovery is insufficient for all-odd debt.",
                f"""{base_defs}

theorem theorem_equal_recovery_insufficient_{suffix}
    (n : Nat) :
    Not (recoveryBeatsOddDebt_{suffix} n n n) := by
  intro h
  unfold recoveryBeatsOddDebt_{suffix} at h
  omega
""",
                True,
                "weak_recovery_insufficient",
            ),
            (
                "anti_smuggling_probe",
                "Composite scarcity theorem / weak scarcity is not enough for subcritical mass.",
                f"""{base_defs}

theorem theorem_weak_scarcity_insufficient_{suffix} :
    legalTheoremFrontier_{suffix} neutralFrontierT_{suffix} /\\
    weakTheoremScarcity_{suffix} neutralFrontierT_{suffix} /\\
    Not (subcriticalTheoremScarcity_{suffix} neutralFrontierT_{suffix}) := by
  native_decide
""",
                True,
                "weak_scarcity_insufficient",
            ),
            (
                "bridge_probe",
                "Composite scarcity theorem / composite step closes from density contraction or survivor descent.",
                f"""{base_defs}

theorem theorem_composite_step_eliminates_local_obstruction_{suffix}
    (f : TheoremFrontier_{suffix})
    (after : TheoremDensity_{suffix})
    (sBefore sAfter : SurvivorMeasure_{suffix})
    (hStep : theoremCompositeStep_{suffix} f after sBefore sAfter)
    (hLegal : legalTheoremFrontier_{suffix} f) :
    theoremDensityContracts_{suffix} after \\/ survivorDescends_{suffix} sBefore sAfter := by
  exact hStep hLegal
""",
                True,
                "composite_step_elimination",
            ),
            (
                "closure_probe",
                "Composite scarcity theorem / survivor descent forbids persistent self-loop obstruction.",
                f"""{base_defs}

theorem theorem_survivor_descent_not_self_loop_{suffix}
    (s : SurvivorMeasure_{suffix}) :
    Not (survivorDescends_{suffix} s s) := by
  intro h
  exact (Nat.lt_irrefl s.obstruction) h.1
""",
                True,
                "survivor_no_self_loop",
            ),
            (
                "closure_probe",
                "Composite scarcity theorem / survivor descent composes.",
                f"""{base_defs}

theorem theorem_survivor_descent_composes_{suffix}
    (a b c : SurvivorMeasure_{suffix})
    (hab : survivorDescends_{suffix} a b)
    (hbc : survivorDescends_{suffix} b c) :
    survivorDescends_{suffix} a c := by
  exact And.intro (Nat.lt_trans hbc.1 hab.1) (Nat.le_trans hbc.2 hab.2)
""",
                True,
                "survivor_descent_composition",
            ),
            (
                "bridge_probe",
                "Composite scarcity theorem / density zero and zero survivor remove final obstruction.",
                f"""{base_defs}

theorem theorem_density_zero_and_survivor_zero_close_{suffix}
    (d : TheoremDensity_{suffix})
    (s : SurvivorMeasure_{suffix})
    (hd : d.exceptional = 0)
    (hs : s.obstruction = 0) :
    finalTheoremObstructionRemoved_{suffix} d s := by
  exact And.intro hd hs
""",
                True,
                "final_obstruction_closure",
            ),
            (
                "definition_probe",
                "Composite scarcity theorem / named target is a counting theorem, not a reachability field.",
                f"""{base_defs}

theorem theorem_named_target_is_counting_shape_{suffix} :
    compositeScarcityNamedTarget_{suffix} 4 ->
    strongFrontierT_{suffix}.badChildren = 1 /\\
      survivorBeforeT_{suffix}.obstruction = 5 := by
  intro _h
  native_decide
""",
                True,
                "named_theorem_no_reachability",
            ),
        ]

        probes: list[FormalProbe] = []
        for probe_type, source_text, lean, decisive, role in specs[:max_probes]:
            metadata = {
                "composite_scarcity_theorem_wave": True,
                "theorem_role": role,
                "decisive": decisive,
                "world_id": world_id,
            }
            probes.append(
                FormalProbe(
                    world_id=world_id,
                    probe_type=probe_type,  # type: ignore[arg-type]
                    source_text=source_text,
                    formal_obligation=FormalObligationSpec(
                        source_text=source_text,
                        channel_hint="proof",
                        goal_kind="theorem",
                        lean_declaration=lean,
                        requires_proof=True,
                        metadata=metadata,
                    ),
                    notes=(
                        "Composite scarcity theorem probe; prioritize parameterized "
                        "scarcity/recovery lemmas and adversarial insufficiency gates."
                    ),
                )
            )
        return probes

    def _compile_global_forcing_hunt_wave_probes(
        self,
        *,
        world_id: str,
        max_probes: int,
    ) -> list[FormalProbe]:
        suffix = _lean_suffix(world_id)
        base_defs = f"""
import Mathlib

structure ForcingFrontier_{suffix} where
  horizon : Nat
  badChildren : Nat
  totalChildren : Nat
  oddDebt : Nat
  recovery : Nat
  obstruction : Nat
  nextObstruction : Nat

def legalForcingFrontier_{suffix} (f : ForcingFrontier_{suffix}) : Prop :=
  f.totalChildren > 0 /\\ f.badChildren <= f.totalChildren

def strongForcingScarcity_{suffix} (f : ForcingFrontier_{suffix}) : Prop :=
  4 * f.badChildren < f.totalChildren

def weakForcingScarcity_{suffix} (f : ForcingFrontier_{suffix}) : Prop :=
  2 * f.badChildren <= f.totalChildren

def forcingRecoveryWins_{suffix} (f : ForcingFrontier_{suffix}) : Prop :=
  2 * f.oddDebt < f.horizon + f.recovery

def survivorObstructionFalls_{suffix} (f : ForcingFrontier_{suffix}) : Prop :=
  f.nextObstruction < f.obstruction

def localForcingProgress_{suffix} (f : ForcingFrontier_{suffix}) : Prop :=
  strongForcingScarcity_{suffix} f \\/
    forcingRecoveryWins_{suffix} f \\/
    survivorObstructionFalls_{suffix} f

def densityContractsFromFrontier_{suffix} (f : ForcingFrontier_{suffix}) : Prop :=
  2 * f.badChildren < f.totalChildren

def explicitDynamicAlternative_{suffix} (f : ForcingFrontier_{suffix}) : Prop :=
  strongForcingScarcity_{suffix} f \\/
    (f.oddDebt <= f.horizon /\\ f.horizon + 1 <= f.recovery) \\/
    survivorObstructionFalls_{suffix} f

def persistentBadFrontier_{suffix} (f : ForcingFrontier_{suffix}) : Prop :=
  legalForcingFrontier_{suffix} f /\\ Not (localForcingProgress_{suffix} f)

def boundedGlobalForcingTarget_{suffix} (horizon : Nat) : Prop :=
  ∀ f : ForcingFrontier_{suffix},
    legalForcingFrontier_{suffix} f ->
    f.horizon <= horizon ->
    explicitDynamicAlternative_{suffix} f ->
    localForcingProgress_{suffix} f

def strongDepth2Candidate_{suffix} : ForcingFrontier_{suffix} :=
  {{ horizon := 2, badChildren := 1, totalChildren := 8, oddDebt := 2,
    recovery := 0, obstruction := 5, nextObstruction := 5 }}

def recoveredAllOddCandidate_{suffix} : ForcingFrontier_{suffix} :=
  {{ horizon := 3, badChildren := 4, totalChildren := 8, oddDebt := 3,
    recovery := 4, obstruction := 5, nextObstruction := 5 }}

def survivorDropCandidate_{suffix} : ForcingFrontier_{suffix} :=
  {{ horizon := 3, badChildren := 4, totalChildren := 8, oddDebt := 3,
    recovery := 0, obstruction := 5, nextObstruction := 3 }}

def mixedGoodCandidate_{suffix} : ForcingFrontier_{suffix} :=
  {{ horizon := 4, badChildren := 1, totalChildren := 16, oddDebt := 3,
    recovery := 5, obstruction := 7, nextObstruction := 7 }}

def allOddNoRecoveryCandidate_{suffix} : ForcingFrontier_{suffix} :=
  {{ horizon := 3, badChildren := 4, totalChildren := 8, oddDebt := 3,
    recovery := 0, obstruction := 5, nextObstruction := 5 }}

def equalRecoveryCandidate_{suffix} : ForcingFrontier_{suffix} :=
  {{ horizon := 3, badChildren := 4, totalChildren := 8, oddDebt := 3,
    recovery := 3, obstruction := 5, nextObstruction := 5 }}

def weakScarcityCandidate_{suffix} : ForcingFrontier_{suffix} :=
  {{ horizon := 5, badChildren := 4, totalChildren := 8, oddDebt := 3,
    recovery := 3, obstruction := 5, nextObstruction := 5 }}

def repairedDepth2SearchPass_{suffix} : Prop :=
  localForcingProgress_{suffix} strongDepth2Candidate_{suffix} /\\
  localForcingProgress_{suffix} recoveredAllOddCandidate_{suffix} /\\
  localForcingProgress_{suffix} survivorDropCandidate_{suffix} /\\
  localForcingProgress_{suffix} mixedGoodCandidate_{suffix}

def noPersistentBadInRepairedSearch_{suffix} : Prop :=
  Not (persistentBadFrontier_{suffix} strongDepth2Candidate_{suffix}) /\\
  Not (persistentBadFrontier_{suffix} recoveredAllOddCandidate_{suffix}) /\\
  Not (persistentBadFrontier_{suffix} survivorDropCandidate_{suffix}) /\\
  Not (persistentBadFrontier_{suffix} mixedGoodCandidate_{suffix})
""".strip()
        specs: list[tuple[str, str, str, bool, str]] = [
            (
                "closure_probe",
                "Global forcing hunt / explicit dynamic alternatives force local progress.",
                f"""{base_defs}

theorem explicit_dynamic_alternative_forces_local_progress_{suffix}
    (f : ForcingFrontier_{suffix})
    (h : explicitDynamicAlternative_{suffix} f) :
    localForcingProgress_{suffix} f := by
  unfold explicitDynamicAlternative_{suffix} localForcingProgress_{suffix} at *
  rcases h with hStrong | hRecovery | hSurvivor
  · exact Or.inl hStrong
  · right
    left
    rcases hRecovery with ⟨hOdd, hRec⟩
    unfold forcingRecoveryWins_{suffix}
    omega
  · exact Or.inr (Or.inr hSurvivor)
""",
                True,
                "explicit_dynamic_forcing",
            ),
            (
                "bridge_probe",
                "Global forcing hunt / bounded target follows from explicit dynamic alternatives.",
                f"""{base_defs}

theorem bounded_target_from_explicit_dynamic_alternatives_{suffix}
    (horizon : Nat) :
    boundedGlobalForcingTarget_{suffix} horizon := by
  intro f _hLegal _hHorizon hAlt
  unfold explicitDynamicAlternative_{suffix} localForcingProgress_{suffix} at *
  rcases hAlt with hStrong | hRecovery | hSurvivor
  · exact Or.inl hStrong
  · right
    left
    rcases hRecovery with ⟨hOdd, hRec⟩
    unfold forcingRecoveryWins_{suffix}
    omega
  · exact Or.inr (Or.inr hSurvivor)
""",
                True,
                "bounded_target_skeleton",
            ),
            (
                "closure_probe",
                "Global forcing hunt / repaired finite search candidates all force progress.",
                f"""{base_defs}

theorem repaired_finite_search_candidates_force_progress_{suffix} :
    repairedDepth2SearchPass_{suffix} := by
  native_decide
""",
                True,
                "finite_search_pass",
            ),
            (
                "anti_smuggling_probe",
                "Global forcing hunt / all-odd no-recovery candidate is a legal persistent bad frontier.",
                f"""{base_defs}

theorem all_odd_no_recovery_is_persistent_bad_{suffix} :
    persistentBadFrontier_{suffix} allOddNoRecoveryCandidate_{suffix} := by
  native_decide
""",
                True,
                "persistent_bad_counterexample",
            ),
            (
                "anti_smuggling_probe",
                "Global forcing hunt / equal recovery remains a legal persistent bad frontier.",
                f"""{base_defs}

theorem equal_recovery_is_still_persistent_bad_{suffix} :
    persistentBadFrontier_{suffix} equalRecoveryCandidate_{suffix} := by
  native_decide
""",
                True,
                "equal_recovery_counterexample",
            ),
            (
                "anti_smuggling_probe",
                "Global forcing hunt / weak scarcity remains insufficient for local progress.",
                f"""{base_defs}

theorem weak_scarcity_is_not_local_progress_{suffix} :
    weakForcingScarcity_{suffix} weakScarcityCandidate_{suffix} /\\
    persistentBadFrontier_{suffix} weakScarcityCandidate_{suffix} := by
  native_decide
""",
                True,
                "weak_scarcity_counterexample",
            ),
            (
                "bridge_probe",
                "Global forcing hunt / strong scarcity gives density contraction.",
                f"""{base_defs}

theorem strong_scarcity_gives_density_contraction_forcing_{suffix}
    (f : ForcingFrontier_{suffix})
    (h : strongForcingScarcity_{suffix} f) :
    densityContractsFromFrontier_{suffix} f := by
  unfold strongForcingScarcity_{suffix} densityContractsFromFrontier_{suffix} at *
  omega
""",
                True,
                "scarcity_density_contraction",
            ),
            (
                "closure_probe",
                "Global forcing hunt / recovery margin wins for any odd debt bounded by horizon.",
                f"""{base_defs}

theorem recovery_margin_wins_for_bounded_odd_debt_{suffix}
    (f : ForcingFrontier_{suffix})
    (hOdd : f.oddDebt <= f.horizon)
    (hRecovery : f.horizon + 1 <= f.recovery) :
    forcingRecoveryWins_{suffix} f := by
  unfold forcingRecoveryWins_{suffix}
  omega
""",
                True,
                "recovery_margin",
            ),
            (
                "anti_smuggling_probe",
                "Global forcing hunt / persistent bad frontier decomposes into all three failures.",
                f"""{base_defs}

theorem persistent_bad_decomposes_into_missing_forcing_{suffix}
    (f : ForcingFrontier_{suffix})
    (h : persistentBadFrontier_{suffix} f) :
    Not (strongForcingScarcity_{suffix} f) /\\
      Not (forcingRecoveryWins_{suffix} f) /\\
      Not (survivorObstructionFalls_{suffix} f) := by
  rcases h with ⟨_hLegal, hNoProgress⟩
  constructor
  · intro hStrong
    exact hNoProgress (Or.inl hStrong)
  constructor
  · intro hRecovery
    exact hNoProgress (Or.inr (Or.inl hRecovery))
  · intro hSurvivor
    exact hNoProgress (Or.inr (Or.inr hSurvivor))
""",
                True,
                "persistent_bad_decomposition",
            ),
            (
                "closure_probe",
                "Global forcing hunt / repaired finite search has no persistent bad frontier.",
                f"""{base_defs}

theorem repaired_search_has_no_persistent_bad_{suffix} :
    noPersistentBadInRepairedSearch_{suffix} := by
  native_decide
""",
                True,
                "finite_search_no_persistent_bad",
            ),
            (
                "anti_smuggling_probe",
                "Global forcing hunt / named target is counting-only and has no reachability field.",
                f"""{base_defs}

theorem bounded_global_target_is_counting_shape_{suffix} :
    boundedGlobalForcingTarget_{suffix} 4 ->
    strongDepth2Candidate_{suffix}.badChildren = 1 /\\
      recoveredAllOddCandidate_{suffix}.recovery = 4 /\\
      survivorDropCandidate_{suffix}.nextObstruction = 3 := by
  intro _h
  native_decide
""",
                True,
                "counting_only_target",
            ),
            (
                "bridge_probe",
                "Global forcing hunt / survivor obstruction drop is a local forcing alternative.",
                f"""{base_defs}

theorem survivor_drop_is_local_forcing_alternative_{suffix}
    (f : ForcingFrontier_{suffix})
    (h : survivorObstructionFalls_{suffix} f) :
    localForcingProgress_{suffix} f := by
  exact Or.inr (Or.inr h)
""",
                True,
                "survivor_forcing_alternative",
            ),
        ]

        probes: list[FormalProbe] = []
        for probe_type, source_text, lean, decisive, role in specs[:max_probes]:
            metadata = {
                "global_forcing_hunt_wave": True,
                "forcing_role": role,
                "decisive": decisive,
                "world_id": world_id,
            }
            probes.append(
                FormalProbe(
                    world_id=world_id,
                    probe_type=probe_type,  # type: ignore[arg-type]
                    source_text=source_text,
                    formal_obligation=FormalObligationSpec(
                        source_text=source_text,
                        channel_hint="proof",
                        goal_kind="theorem",
                        lean_declaration=lean,
                        requires_proof=True,
                        metadata=metadata,
                    ),
                    notes=(
                        "Global forcing hunt probe; adversarially test whether bounded "
                        "Composite Scarcity needs stronger dynamic admissibility."
                    ),
                )
            )
        return probes

    def _compile_dynamic_admissibility_compass_wave_probes(
        self,
        *,
        world_id: str,
        max_probes: int,
    ) -> list[FormalProbe]:
        suffix = _lean_suffix(world_id)
        base_defs = f"""
import Mathlib

def compassStep_{suffix} (n : Nat) : Nat :=
  if n % 2 = 0 then n / 2 else 3 * n + 1

structure CompassTransition_{suffix} where
  input : Nat
  output : Nat
  tag : Nat

def compassTransitionAdmissible_{suffix} (t : CompassTransition_{suffix}) : Prop :=
  if t.tag = 0 then t.input % 2 = 0 /\\ t.output = t.input / 2
  else t.input % 2 = 1 /\\ t.output = 3 * t.input + 1

structure CompassBlock_{suffix} where
  start : Nat
  finish : Nat
  horizon : Nat
  oddDebt : Nat
  recovery : Nat
  badChildren : Nat
  totalChildren : Nat
  obstruction : Nat
  nextObstruction : Nat

def compassLegalBlock_{suffix} (b : CompassBlock_{suffix}) : Prop :=
  b.totalChildren > 0 /\\ b.badChildren <= b.totalChildren /\\ b.finish > 0

def compassStrongScarcity_{suffix} (b : CompassBlock_{suffix}) : Prop :=
  4 * b.badChildren < b.totalChildren

def compassRecoveryWins_{suffix} (b : CompassBlock_{suffix}) : Prop :=
  2 * b.oddDebt < b.horizon + b.recovery

def compassSurvivorDrops_{suffix} (b : CompassBlock_{suffix}) : Prop :=
  b.nextObstruction < b.obstruction

def compassProgress_{suffix} (b : CompassBlock_{suffix}) : Prop :=
  compassStrongScarcity_{suffix} b \\/
    compassRecoveryWins_{suffix} b \\/
    compassSurvivorDrops_{suffix} b

def compassPersistentBad_{suffix} (b : CompassBlock_{suffix}) : Prop :=
  compassLegalBlock_{suffix} b /\\ Not (compassProgress_{suffix} b)

def compassDensityContracts_{suffix} (b : CompassBlock_{suffix}) : Prop :=
  2 * b.badChildren < b.totalChildren

def compassFinalClosure_{suffix} (b : CompassBlock_{suffix}) : Prop :=
  b.badChildren = 0 /\\ b.obstruction = 0

def compassDynamicBridgeTarget_{suffix} (horizon : Nat) : Prop :=
  ∀ b : CompassBlock_{suffix},
    compassLegalBlock_{suffix} b ->
    b.horizon <= horizon ->
    compassProgress_{suffix} b

def step3to10_{suffix} : CompassTransition_{suffix} :=
  {{ input := 3, output := 10, tag := 1 }}

def step10to5_{suffix} : CompassTransition_{suffix} :=
  {{ input := 10, output := 5, tag := 0 }}

def step5to16_{suffix} : CompassTransition_{suffix} :=
  {{ input := 5, output := 16, tag := 1 }}

def step16to8_{suffix} : CompassTransition_{suffix} :=
  {{ input := 16, output := 8, tag := 0 }}

def fakeOddAfterOdd_{suffix} : CompassTransition_{suffix} :=
  {{ input := 10, output := 31, tag := 1 }}

def fakeParityTagOnly_{suffix} : CompassTransition_{suffix} :=
  {{ input := 10, output := 31, tag := 1 }}

def realOddEvenBlock3_{suffix} : CompassBlock_{suffix} :=
  {{ start := 3, finish := 5, horizon := 2, oddDebt := 1, recovery := 1,
    badChildren := 1, totalChildren := 8, obstruction := 5, nextObstruction := 5 }}

def realOddEvenBlock5_{suffix} : CompassBlock_{suffix} :=
  {{ start := 5, finish := 8, horizon := 2, oddDebt := 1, recovery := 1,
    badChildren := 1, totalChildren := 8, obstruction := 5, nextObstruction := 5 }}

def realMixedBlock7_{suffix} : CompassBlock_{suffix} :=
  {{ start := 7, finish := 11, horizon := 2, oddDebt := 1, recovery := 1,
    badChildren := 1, totalChildren := 8, obstruction := 7, nextObstruction := 7 }}

def staticAllOddNoRecoveryBlock_{suffix} : CompassBlock_{suffix} :=
  {{ start := 3, finish := 31, horizon := 3, oddDebt := 3, recovery := 0,
    badChildren := 4, totalChildren := 8, obstruction := 5, nextObstruction := 5 }}

def equalRecoveryStaticBlock_{suffix} : CompassBlock_{suffix} :=
  {{ start := 3, finish := 5, horizon := 3, oddDebt := 3, recovery := 3,
    badChildren := 4, totalChildren := 8, obstruction := 5, nextObstruction := 5 }}

def weakScarcityStaticBlock_{suffix} : CompassBlock_{suffix} :=
  {{ start := 9, finish := 9, horizon := 5, oddDebt := 3, recovery := 3,
    badChildren := 4, totalChildren := 8, obstruction := 5, nextObstruction := 5 }}

def densityOnlyBlock_{suffix} : CompassBlock_{suffix} :=
  {{ start := 1, finish := 1, horizon := 1, oddDebt := 0, recovery := 1,
    badChildren := 0, totalChildren := 8, obstruction := 5, nextObstruction := 5 }}

def survivorDropBlock_{suffix} : CompassBlock_{suffix} :=
  {{ start := 27, finish := 82, horizon := 1, oddDebt := 1, recovery := 0,
    badChildren := 4, totalChildren := 8, obstruction := 7, nextObstruction := 3 }}

def realSmallSearchPass_{suffix} : Prop :=
  compassProgress_{suffix} realOddEvenBlock3_{suffix} /\\
  compassProgress_{suffix} realOddEvenBlock5_{suffix} /\\
  compassProgress_{suffix} realMixedBlock7_{suffix}

def noPersistentBadInRealSmallSearch_{suffix} : Prop :=
  Not (compassPersistentBad_{suffix} realOddEvenBlock3_{suffix}) /\\
  Not (compassPersistentBad_{suffix} realOddEvenBlock5_{suffix}) /\\
  Not (compassPersistentBad_{suffix} realMixedBlock7_{suffix})
""".strip()
        specs: list[tuple[str, str, str, bool, str, str]] = [
            (
                "closure_probe",
                "Dynamic admissibility compass / real odd-even Collatz block at 3 is admissible.",
                f"""{base_defs}

theorem compass_real_3_10_5_admissible_{suffix} :
    compassTransitionAdmissible_{suffix} step3to10_{suffix} /\\
    compassTransitionAdmissible_{suffix} step10to5_{suffix} := by
  native_decide
""",
                True,
                "dynamic_bridge",
                "real_odd_even_block",
            ),
            (
                "bridge_probe",
                "Dynamic admissibility compass / real odd-even block projects to forcing progress.",
                f"""{base_defs}

theorem compass_real_odd_even_block_projects_to_progress_{suffix} :
    compassProgress_{suffix} realOddEvenBlock3_{suffix} := by
  native_decide
""",
                True,
                "dynamic_bridge",
                "real_block_progress",
            ),
            (
                "anti_smuggling_probe",
                "Dynamic admissibility compass / fake all-odd no-recovery step is rejected.",
                f"""{base_defs}

theorem compass_fake_all_odd_step_rejected_{suffix} :
    Not (compassTransitionAdmissible_{suffix} fakeOddAfterOdd_{suffix}) := by
  native_decide
""",
                True,
                "dynamic_bridge",
                "fake_all_odd_rejected",
            ),
            (
                "anti_smuggling_probe",
                "Dynamic admissibility compass / parity tag alone is not dynamic admissibility.",
                f"""{base_defs}

theorem compass_parity_tag_alone_not_enough_{suffix} :
    fakeParityTagOnly_{suffix}.tag = 1 /\\
    Not (compassTransitionAdmissible_{suffix} fakeParityTagOnly_{suffix}) := by
  native_decide
""",
                True,
                "pivot_sentinel",
                "parity_tag_insufficient",
            ),
            (
                "closure_probe",
                "Dynamic admissibility compass / real small Collatz block search forces progress.",
                f"""{base_defs}

theorem compass_real_small_search_forces_progress_{suffix} :
    realSmallSearchPass_{suffix} := by
  native_decide
""",
                True,
                "dynamic_bridge",
                "finite_real_search",
            ),
            (
                "closure_probe",
                "Dynamic admissibility compass / real small search has no persistent bad block.",
                f"""{base_defs}

theorem compass_real_small_search_has_no_persistent_bad_{suffix} :
    noPersistentBadInRealSmallSearch_{suffix} := by
  native_decide
""",
                True,
                "dynamic_bridge",
                "finite_real_no_persistent_bad",
            ),
            (
                "anti_smuggling_probe",
                "Dynamic admissibility compass / static all-odd no-recovery block remains persistent bad.",
                f"""{base_defs}

theorem compass_static_all_odd_no_recovery_persistent_bad_{suffix} :
    compassPersistentBad_{suffix} staticAllOddNoRecoveryBlock_{suffix} := by
  native_decide
""",
                True,
                "pivot_sentinel",
                "static_all_odd_persistent",
            ),
            (
                "anti_smuggling_probe",
                "Dynamic admissibility compass / equal-recovery static block remains persistent bad.",
                f"""{base_defs}

theorem compass_equal_recovery_static_persistent_bad_{suffix} :
    compassPersistentBad_{suffix} equalRecoveryStaticBlock_{suffix} := by
  native_decide
""",
                True,
                "pivot_sentinel",
                "equal_recovery_persistent",
            ),
            (
                "anti_smuggling_probe",
                "Dynamic admissibility compass / weak-scarcity static block remains persistent bad.",
                f"""{base_defs}

theorem compass_weak_scarcity_static_persistent_bad_{suffix} :
    compassPersistentBad_{suffix} weakScarcityStaticBlock_{suffix} := by
  native_decide
""",
                True,
                "pivot_sentinel",
                "weak_scarcity_persistent",
            ),
            (
                "bridge_probe",
                "Dynamic admissibility compass / strong scarcity still gives density contraction.",
                f"""{base_defs}

theorem compass_strong_scarcity_gives_density_contraction_{suffix}
    (b : CompassBlock_{suffix})
    (h : compassStrongScarcity_{suffix} b) :
    compassDensityContracts_{suffix} b := by
  unfold compassStrongScarcity_{suffix} compassDensityContracts_{suffix} at *
  omega
""",
                True,
                "dynamic_bridge",
                "density_projection",
            ),
            (
                "closure_probe",
                "Dynamic admissibility compass / recovery margin wins for actual odd-even block.",
                f"""{base_defs}

theorem compass_recovery_margin_wins_for_real_odd_even_block_{suffix} :
    compassRecoveryWins_{suffix} realOddEvenBlock3_{suffix} := by
  native_decide
""",
                True,
                "dynamic_bridge",
                "recovery_margin",
            ),
            (
                "anti_smuggling_probe",
                "Dynamic admissibility compass / density-only closure does not remove survivor obstruction.",
                f"""{base_defs}

theorem compass_density_only_does_not_close_survivor_{suffix} :
    densityOnlyBlock_{suffix}.badChildren = 0 /\\
    Not (compassFinalClosure_{suffix} densityOnlyBlock_{suffix}) := by
  native_decide
""",
                True,
                "pivot_sentinel",
                "density_only_insufficient",
            ),
            (
                "bridge_probe",
                "Dynamic admissibility compass / survivor drop is a separate forcing exit.",
                f"""{base_defs}

theorem compass_survivor_drop_is_forcing_exit_{suffix} :
    compassProgress_{suffix} survivorDropBlock_{suffix} := by
  native_decide
""",
                True,
                "pivot_sentinel",
                "survivor_exit",
            ),
            (
                "definition_probe",
                "Dynamic admissibility compass / bridge target is counting-only and has no reachability field.",
                f"""{base_defs}

theorem compass_bridge_target_is_counting_shape_{suffix} :
    compassDynamicBridgeTarget_{suffix} 4 ->
    realOddEvenBlock3_{suffix}.oddDebt = 1 /\\
      realOddEvenBlock3_{suffix}.recovery = 1 /\\
      staticAllOddNoRecoveryBlock_{suffix}.badChildren = 4 := by
  intro _h
  native_decide
""",
                True,
                "anti_smuggling",
                "counting_only_target",
            ),
            (
                "anti_smuggling_probe",
                "Dynamic admissibility compass / fake static obstruction has no dynamic transition witness.",
                f"""{base_defs}

theorem compass_static_obstruction_has_no_dynamic_witness_{suffix} :
    compassPersistentBad_{suffix} staticAllOddNoRecoveryBlock_{suffix} /\\
    Not (compassTransitionAdmissible_{suffix} fakeOddAfterOdd_{suffix}) := by
  native_decide
""",
                True,
                "dynamic_bridge",
                "static_obstruction_no_witness",
            ),
        ]

        probes: list[FormalProbe] = []
        for probe_type, source_text, lean, decisive, family, role in specs[:max_probes]:
            metadata = {
                "dynamic_admissibility_compass_wave": True,
                "compass_family": family,
                "compass_role": role,
                "decisive": decisive,
                "world_id": world_id,
            }
            probes.append(
                FormalProbe(
                    world_id=world_id,
                    probe_type=probe_type,  # type: ignore[arg-type]
                    source_text=source_text,
                    formal_obligation=FormalObligationSpec(
                        source_text=source_text,
                        channel_hint="proof",
                        goal_kind="theorem",
                        lean_declaration=lean,
                        requires_proof=True,
                        metadata=metadata,
                    ),
                    notes=(
                        "Dynamic admissibility compass probe; use verification as discovery "
                        "for both the bridge path and pivot sentinels."
                    ),
                )
            )
        return probes

    def _compile_dynamic_pressure_automaton_wave_probes(
        self,
        *,
        world_id: str,
        reports: list[dict[str, Any]],
        height_reports: list[dict[str, Any]],
        max_probes: int,
    ) -> list[FormalProbe]:
        suffix = uuid4().hex[:8]
        cycle_report = next((report for report in reports if report["cycle_found"]), None)
        acyclic_report = next((report for report in reports if not report["cycle_found"]), reports[0])
        expanding_report = next(
            (
                report
                for report in height_reports
                if report["decision"] == "all_checked_bad_cycles_height_expanding"
            ),
            None,
        )
        expanding_component = (
            expanding_report["components"][0]
            if expanding_report and expanding_report.get("components")
            else None
        )
        expanding_drift = (
            expanding_component.get("witness_height_drift", {})
            if expanding_component
            else {}
        )
        expanding_odd = int(expanding_drift.get("cycle_odd_count", 1))
        expanding_even = int(expanding_drift.get("cycle_even_count", 1))
        modulus = int((cycle_report or reports[0])["modulus"])
        window = int((cycle_report or reports[0])["window"])
        base_defs = f"""
def dpaM_{suffix} : Nat := {modulus}

def dpaSuccs_{suffix} (r : Nat) : List Nat :=
  if r % 2 = 0 then [r / 2, r / 2 + dpaM_{suffix} / 2]
  else [((3 * r + 1) % dpaM_{suffix})]

def dpaPositivePressure_{suffix} (evenCount oddCount : Nat) : Prop :=
  8 * oddCount < 5 * evenCount

def dpaHeightExpands_{suffix} (evenCount oddCount : Nat) : Prop :=
  2 ^ evenCount < 3 ^ oddCount

def dpaGhostEven_{suffix} : Nat := dpaM_{suffix} - 2

def dpaGhostOdd_{suffix} : Nat := dpaM_{suffix} - 1

def dpaWindow_{suffix} : Nat := {window}

def dpaExpandingOddWitness_{suffix} : Nat := {expanding_odd}

def dpaExpandingEvenWitness_{suffix} : Nat := {expanding_even}

def dpaAcyclicRankWitness_{suffix} : Nat :=
  {int(acyclic_report.get("certificate", {}).get("max_rank", 0))}
""".strip()
        specs: list[tuple[str, str, str, bool, str, str]] = [
            (
                "definition_probe",
                "Dynamic pressure automaton / pressure rule separates one-even from two-even recovery.",
                f"""{base_defs}

theorem dpa_pressure_rule_separates_recovery_{suffix} :
    dpaPositivePressure_{suffix} 2 1 /\\
    Not (dpaPositivePressure_{suffix} 1 1) := by
  native_decide
""",
                True,
                "pressure_rule",
                "two_even_recovery",
            ),
            (
                "simulation_probe",
                "Dynamic pressure automaton / even residue step must split on the hidden high bit.",
                f"""{base_defs}

theorem dpa_even_step_has_two_residue_successors_{suffix} :
    0 ∈ dpaSuccs_{suffix} 0 /\\
    dpaM_{suffix} / 2 ∈ dpaSuccs_{suffix} 0 := by
  native_decide
""",
                True,
                "residue_relation",
                "even_high_bit_split",
            ),
            (
                "closure_probe",
                "Dynamic pressure automaton / acyclic reports carry a finite bad-rank witness.",
                f"""{base_defs}

theorem dpa_acyclic_report_has_rank_witness_{suffix} :
    dpaAcyclicRankWitness_{suffix} = {int(acyclic_report.get("certificate", {}).get("max_rank", 0))} := by
  native_decide
""",
                False,
                "certificate_shape",
                "acyclic_rank_witness",
            ),
        ]
        if cycle_report:
            specs.extend(
                [
                    (
                        "anti_smuggling_probe",
                        "Dynamic pressure automaton / sound residue relation exposes the 2-adic ghost cycle.",
                        f"""{base_defs}

theorem dpa_two_adic_ghost_cycle_edges_{suffix} :
    dpaGhostOdd_{suffix} ∈ dpaSuccs_{suffix} dpaGhostEven_{suffix} /\\
    dpaGhostEven_{suffix} ∈ dpaSuccs_{suffix} dpaGhostOdd_{suffix} := by
  native_decide
""",
                        True,
                        "ghost_obstruction",
                        "negative_two_negative_one_cycle",
                    ),
                    (
                        "anti_smuggling_probe",
                        "Dynamic pressure automaton / the ghost cycle is bad for the pressure rule.",
                        f"""{base_defs}

theorem dpa_two_adic_ghost_cycle_is_pressure_bad_{suffix} :
    Not (dpaPositivePressure_{suffix} 1 1) := by
  native_decide
""",
                        True,
                        "ghost_obstruction",
                        "pressure_bad_cycle",
                    ),
                    (
                        "bridge_probe",
                        "Dynamic pressure automaton / ghost obstruction is a negative residue-class phenomenon.",
                        f"""{base_defs}

theorem dpa_ghost_is_modulus_boundary_pair_{suffix} :
    dpaGhostEven_{suffix} + 2 = dpaM_{suffix} /\\
    dpaGhostOdd_{suffix} + 1 = dpaM_{suffix} := by
  native_decide
""",
                        True,
                        "positive_integer_side_condition",
                        "archimedean_gap",
                    ),
                ]
            )
        else:
            specs.extend(
                [
                    (
                        "closure_probe",
                        "Dynamic pressure automaton / one-step even windows exit through positive pressure.",
                        f"""{base_defs}

theorem dpa_one_step_even_window_positive_{suffix} :
    dpaPositivePressure_{suffix} 1 0 := by
  native_decide
""",
                        True,
                        "certificate_shape",
                        "one_step_exit",
                    ),
                    (
                        "anti_smuggling_probe",
                        "Dynamic pressure automaton / one-step odd windows do not fake pressure progress.",
                        f"""{base_defs}

theorem dpa_one_step_odd_window_not_positive_{suffix} :
    Not (dpaPositivePressure_{suffix} 0 1) := by
  native_decide
""",
                        True,
                        "pressure_rule",
                        "odd_debt_gate",
                    ),
                ]
            )
        if expanding_report:
            specs.extend(
                [
                    (
                        "bridge_probe",
                        "Dynamic pressure automaton / height lift removes the first recurrent bad ghost.",
                        f"""{base_defs}

theorem dpa_height_lift_removes_recurrent_bad_ghost_{suffix} :
    dpaHeightExpands_{suffix}
      dpaExpandingEvenWitness_{suffix}
      dpaExpandingOddWitness_{suffix} := by
  native_decide
""",
                        True,
                        "height_lift",
                        "expanding_bad_component",
                    ),
                    (
                        "bridge_probe",
                        "Dynamic pressure automaton / pressure-bad and height-expanding are separate exits.",
                        f"""{base_defs}

theorem dpa_pressure_bad_can_still_height_escape_{suffix} :
    Not (dpaPositivePressure_{suffix}
      dpaExpandingEvenWitness_{suffix}
      dpaExpandingOddWitness_{suffix}) /\\
    dpaHeightExpands_{suffix}
      dpaExpandingEvenWitness_{suffix}
      dpaExpandingOddWitness_{suffix} := by
  native_decide
""",
                        True,
                        "height_lift",
                        "pressure_bad_height_escape",
                    ),
                ]
            )

        probes: list[FormalProbe] = []
        for probe_type, source_text, lean, decisive, family, role in specs[:max_probes]:
            metadata = {
                "dynamic_pressure_automaton_wave": True,
                "automaton_family": family,
                "automaton_role": role,
                "decisive": decisive,
                "world_id": world_id,
                "cycle_found": bool(cycle_report),
                "window": window,
                "modulus": modulus,
            }
            probes.append(
                FormalProbe(
                    world_id=world_id,
                    probe_type=probe_type,  # type: ignore[arg-type]
                    source_text=source_text,
                    formal_obligation=FormalObligationSpec(
                        source_text=source_text,
                        channel_hint="proof",
                        goal_kind="theorem",
                        lean_declaration=lean,
                        requires_proof=True,
                        metadata=metadata,
                    ),
                    notes=(
                        "Dynamic pressure automaton probe; generated from finite residue "
                        "search rather than hand-picked narrative examples."
                    ),
                )
            )
        return probes

    def _compile_pressure_height_survivor_closure_wave_probes(
        self,
        *,
        world_id: str,
        height_reports: list[dict[str, Any]],
        max_probes: int,
    ) -> list[FormalProbe]:
        suffix = uuid4().hex[:8]
        expanding_report = next(
            (
                report
                for report in height_reports
                if report["decision"] == "all_checked_bad_cycles_height_expanding"
            ),
            None,
        )
        expanding_component = (
            expanding_report["components"][0]
            if expanding_report and expanding_report.get("components")
            else None
        )
        drift = expanding_component.get("witness_height_drift", {}) if expanding_component else {}
        recurrent_bad = int(expanding_report.get("recurrent_component_count", 1)) if expanding_report else 1
        height_escaping = int(expanding_report.get("height_expanding_component_count", 1)) if expanding_report else 1
        dangerous = int(expanding_report.get("dangerous_component_count", 0)) if expanding_report else 0
        odd_witness = int(drift.get("cycle_odd_count", 1))
        even_witness = int(drift.get("cycle_even_count", 1))
        height_before = max(1, 2**min(even_witness, 8))
        height_after = height_before + max(1, odd_witness)
        base_defs = f"""
structure SurvivorClosureBlock_{suffix} where
  oddEdges : Nat
  evenEdges : Nat
  heightBefore : Nat
  heightAfter : Nat
  badMass : Nat
  nextBadMass : Nat
  obstruction : Nat
  nextObstruction : Nat

def scPressureRecovers_{suffix} (b : SurvivorClosureBlock_{suffix}) : Prop :=
  8 * b.oddEdges < 5 * b.evenEdges

def scPressureBad_{suffix} (b : SurvivorClosureBlock_{suffix}) : Prop :=
  Not (scPressureRecovers_{suffix} b)

def scHeightEscapes_{suffix} (b : SurvivorClosureBlock_{suffix}) : Prop :=
  b.heightBefore < b.heightAfter

def scMinimalPersists_{suffix} (b : SurvivorClosureBlock_{suffix}) : Prop :=
  b.heightAfter <= b.heightBefore

def scSurvivorDrops_{suffix} (b : SurvivorClosureBlock_{suffix}) : Prop :=
  b.nextObstruction < b.obstruction

def scCompositeExit_{suffix} (b : SurvivorClosureBlock_{suffix}) : Prop :=
  scPressureRecovers_{suffix} b \\/
    scHeightEscapes_{suffix} b \\/
    scSurvivorDrops_{suffix} b

def scMinimalBadObstruction_{suffix} (b : SurvivorClosureBlock_{suffix}) : Prop :=
  scPressureBad_{suffix} b /\\
    scMinimalPersists_{suffix} b /\\
    Not (scPressureRecovers_{suffix} b) /\\
    Not (scSurvivorDrops_{suffix} b)

def scGhostEscapeBlock_{suffix} : SurvivorClosureBlock_{suffix} :=
  {{ oddEdges := {odd_witness}, evenEdges := {even_witness},
    heightBefore := {height_before}, heightAfter := {height_after},
    badMass := 1, nextBadMass := 1, obstruction := 5, nextObstruction := 5 }}

def scPressureBadPersistentBlock_{suffix} : SurvivorClosureBlock_{suffix} :=
  {{ oddEdges := 1, evenEdges := 1,
    heightBefore := 2, heightAfter := 2,
    badMass := 1, nextBadMass := 1, obstruction := 5, nextObstruction := 5 }}

def scRecoveryBlock_{suffix} : SurvivorClosureBlock_{suffix} :=
  {{ oddEdges := 1, evenEdges := 2,
    heightBefore := 2, heightAfter := 2,
    badMass := 1, nextBadMass := 0, obstruction := 5, nextObstruction := 5 }}

def scDropBlock_{suffix} : SurvivorClosureBlock_{suffix} :=
  {{ oddEdges := 1, evenEdges := 1,
    heightBefore := 2, heightAfter := 2,
    badMass := 1, nextBadMass := 1, obstruction := 5, nextObstruction := 3 }}

structure SurvivorClosureFrontier_{suffix} where
  horizon : Nat
  recurrentBad : Nat
  heightEscaping : Nat
  dangerous : Nat

def scCheckedFrontier_{suffix} : SurvivorClosureFrontier_{suffix} :=
  {{ horizon := {int(expanding_report.get("window", 2)) if expanding_report else 2},
    recurrentBad := {recurrent_bad}, heightEscaping := {height_escaping}, dangerous := {dangerous} }}

def scAllCheckedHeightEscaping_{suffix} (f : SurvivorClosureFrontier_{suffix}) : Prop :=
  f.recurrentBad = f.heightEscaping /\\ f.dangerous = 0

def scNoDangerousSurvivor_{suffix} (f : SurvivorClosureFrontier_{suffix}) : Prop :=
  f.dangerous = 0

structure SurvivorClosureTarget_{suffix} where
  horizon : Nat
  recurrentBad : Nat
  heightEscaping : Nat
  dangerous : Nat

def scTargetExample_{suffix} : SurvivorClosureTarget_{suffix} :=
  {{ horizon := scCheckedFrontier_{suffix}.horizon,
    recurrentBad := scCheckedFrontier_{suffix}.recurrentBad,
    heightEscaping := scCheckedFrontier_{suffix}.heightEscaping,
    dangerous := scCheckedFrontier_{suffix}.dangerous }}
""".strip()
        height_escape_contradiction = f"""
theorem sc_height_escape_contradicts_minimal_persistence_{suffix}
    (b : SurvivorClosureBlock_{suffix})
    (hEscape : scHeightEscapes_{suffix} b)
    (hPersist : scMinimalPersists_{suffix} b) :
    False := by
  unfold scHeightEscapes_{suffix} scMinimalPersists_{suffix} at *
  omega
""".strip()
        specs: list[tuple[str, str, str, bool, str, str]] = [
            (
                "anti_smuggling_probe",
                "Pressure-height survivor closure / pressure-bad alone can still persist.",
                f"""{base_defs}

theorem sc_pressure_bad_alone_can_still_persist_{suffix} :
    scPressureBad_{suffix} scPressureBadPersistentBlock_{suffix} /\\
    scMinimalPersists_{suffix} scPressureBadPersistentBlock_{suffix} /\\
    Not (scCompositeExit_{suffix} scPressureBadPersistentBlock_{suffix}) := by
  native_decide
""",
                True,
                "adversarial_gate",
                "pressure_bad_alone_insufficient",
            ),
            (
                "bridge_probe",
                "Pressure-height survivor closure / height escape contradicts minimal persistence.",
                f"""{base_defs}

{height_escape_contradiction}
""",
                True,
                "survivor_closure",
                "height_escape_not_minimal",
            ),
            (
                "bridge_probe",
                "Pressure-height survivor closure / checked ghost block is pressure-bad but not persistent.",
                f"""{base_defs}

theorem sc_checked_ghost_is_pressure_bad_but_not_persistent_{suffix} :
    scPressureBad_{suffix} scGhostEscapeBlock_{suffix} /\\
    scHeightEscapes_{suffix} scGhostEscapeBlock_{suffix} /\\
    Not (scMinimalPersists_{suffix} scGhostEscapeBlock_{suffix}) := by
  native_decide
""",
                True,
                "survivor_closure",
                "ghost_height_escape",
            ),
            (
                "closure_probe",
                "Pressure-height survivor closure / composite exit kills minimal bad obstruction.",
                f"""{base_defs}

{height_escape_contradiction}

theorem sc_composite_exit_kills_minimal_bad_{suffix}
    (b : SurvivorClosureBlock_{suffix})
    (hExit : scCompositeExit_{suffix} b)
    (hBad : scMinimalBadObstruction_{suffix} b) :
    False := by
  cases hExit with
  | inl hRecover =>
      exact hBad.2.2.1 hRecover
  | inr hRest =>
      cases hRest with
      | inl hHeight =>
          exact sc_height_escape_contradicts_minimal_persistence_{suffix} b hHeight hBad.2.1
      | inr hDrop =>
          exact hBad.2.2.2 hDrop
""",
                True,
                "survivor_closure",
                "composite_exit",
            ),
            (
                "anti_smuggling_probe",
                "Pressure-height survivor closure / nonexpanding pressure-bad block remains obstruction.",
                f"""{base_defs}

theorem sc_nonexpanding_pressure_bad_remains_obstruction_{suffix} :
    scMinimalBadObstruction_{suffix} scPressureBadPersistentBlock_{suffix} := by
  native_decide
""",
                True,
                "adversarial_gate",
                "strict_height_needed",
            ),
            (
                "closure_probe",
                "Pressure-height survivor closure / checked frontier has no dangerous survivor component.",
                f"""{base_defs}

theorem sc_checked_frontier_has_no_dangerous_survivor_{suffix} :
    scAllCheckedHeightEscaping_{suffix} scCheckedFrontier_{suffix} /\\
    scNoDangerousSurvivor_{suffix} scCheckedFrontier_{suffix} := by
  native_decide
""",
                True,
                "survivor_closure",
                "checked_frontier_no_dangerous",
            ),
            (
                "bridge_probe",
                "Pressure-height survivor closure / pressure recovery is an independent closure exit.",
                f"""{base_defs}

theorem sc_pressure_recovery_is_independent_exit_{suffix} :
    scPressureRecovers_{suffix} scRecoveryBlock_{suffix} /\\
    scCompositeExit_{suffix} scRecoveryBlock_{suffix} := by
  native_decide
""",
                False,
                "survivor_closure",
                "pressure_recovery_exit",
            ),
            (
                "bridge_probe",
                "Pressure-height survivor closure / survivor drop is an independent closure exit.",
                f"""{base_defs}

theorem sc_survivor_drop_is_independent_exit_{suffix} :
    scSurvivorDrops_{suffix} scDropBlock_{suffix} /\\
    scCompositeExit_{suffix} scDropBlock_{suffix} := by
  native_decide
""",
                False,
                "survivor_closure",
                "survivor_drop_exit",
            ),
            (
                "definition_probe",
                "Pressure-height survivor closure / target is counting-height only.",
                f"""{base_defs}

theorem sc_target_is_counting_height_only_{suffix} :
    scTargetExample_{suffix}.horizon = scCheckedFrontier_{suffix}.horizon /\\
    scTargetExample_{suffix}.dangerous = 0 := by
  native_decide
""",
                True,
                "anti_smuggling",
                "counting_height_only",
            ),
            (
                "closure_probe",
                "Pressure-height survivor closure / all-checked height escape implies no dangerous survivor.",
                f"""{base_defs}

theorem sc_all_checked_height_escape_implies_no_dangerous_survivor_{suffix}
    (f : SurvivorClosureFrontier_{suffix})
    (h : scAllCheckedHeightEscaping_{suffix} f) :
    scNoDangerousSurvivor_{suffix} f := by
  exact h.2
""",
                True,
                "survivor_closure",
                "frontier_closure_schema",
            ),
        ]

        probes: list[FormalProbe] = []
        for probe_type, source_text, lean, decisive, family, role in specs[:max_probes]:
            metadata = {
                "pressure_height_survivor_closure_wave": True,
                "closure_family": family,
                "closure_role": role,
                "decisive": decisive,
                "world_id": world_id,
                "height_escape_witness": {
                    "odd_edges": odd_witness,
                    "even_edges": even_witness,
                    "height_before": height_before,
                    "height_after": height_after,
                },
            }
            probes.append(
                FormalProbe(
                    world_id=world_id,
                    probe_type=probe_type,  # type: ignore[arg-type]
                    source_text=source_text,
                    formal_obligation=FormalObligationSpec(
                        source_text=source_text,
                        channel_hint="proof",
                        goal_kind="theorem",
                        lean_declaration=lean,
                        requires_proof=True,
                        metadata=metadata,
                    ),
                    notes=(
                        "Pressure-height survivor closure probe; this is the gate after "
                        "the height-lifted automaton signal, with adversarial insufficiency checks."
                    ),
                )
            )
        return probes

    def _compile_pressure_height_frontier_certificate_wave_probes(
        self,
        *,
        world_id: str,
        height_reports: list[dict[str, Any]],
        max_probes: int,
    ) -> list[FormalProbe]:
        suffix = uuid4().hex[:8]
        expanding_report = next(
            (
                report
                for report in height_reports
                if report["decision"] == "all_checked_bad_cycles_height_expanding"
            ),
            None,
        )
        expanding_component = (
            expanding_report["components"][0]
            if expanding_report and expanding_report.get("components")
            else None
        )
        drift = expanding_component.get("witness_height_drift", {}) if expanding_component else {}
        recurrent_bad = int(expanding_report.get("recurrent_component_count", 1)) if expanding_report else 1
        height_escaping = int(expanding_report.get("height_expanding_component_count", 1)) if expanding_report else 1
        dangerous = int(expanding_report.get("dangerous_component_count", 0)) if expanding_report else 0
        odd_witness = int(drift.get("cycle_odd_count", 1))
        even_witness = int(drift.get("cycle_even_count", 1))
        base_defs = f"""
structure FrontierComponent_{suffix} where
  oddEdges : Nat
  evenEdges : Nat
  heightBefore : Nat
  heightAfter : Nat
  obstruction : Nat
  nextObstruction : Nat

def fcPressureRecovers_{suffix} (c : FrontierComponent_{suffix}) : Prop :=
  8 * c.oddEdges < 5 * c.evenEdges

def fcPressureBad_{suffix} (c : FrontierComponent_{suffix}) : Prop :=
  Not (fcPressureRecovers_{suffix} c)

def fcHeightEscapes_{suffix} (c : FrontierComponent_{suffix}) : Prop :=
  c.heightBefore < c.heightAfter

def fcSurvivorDrops_{suffix} (c : FrontierComponent_{suffix}) : Prop :=
  c.nextObstruction < c.obstruction

def fcCertified_{suffix} (c : FrontierComponent_{suffix}) : Prop :=
  fcPressureRecovers_{suffix} c \\/
    fcHeightEscapes_{suffix} c \\/
    fcSurvivorDrops_{suffix} c

def fcDangerous_{suffix} (c : FrontierComponent_{suffix}) : Prop :=
  fcPressureBad_{suffix} c /\\
    Not (fcHeightEscapes_{suffix} c) /\\
    Not (fcSurvivorDrops_{suffix} c)

def fcAllCertified_{suffix} (xs : List FrontierComponent_{suffix}) : Prop :=
  ∀ c, c ∈ xs -> fcCertified_{suffix} c

def fcHasDangerous_{suffix} (xs : List FrontierComponent_{suffix}) : Prop :=
  ∃ c, c ∈ xs /\\ fcDangerous_{suffix} c

def fcHeightComponent_{suffix} : FrontierComponent_{suffix} :=
  {{ oddEdges := {odd_witness}, evenEdges := {even_witness},
    heightBefore := 2, heightAfter := 3, obstruction := 5, nextObstruction := 5 }}

def fcRecoveryComponent_{suffix} : FrontierComponent_{suffix} :=
  {{ oddEdges := 1, evenEdges := 2,
    heightBefore := 2, heightAfter := 2, obstruction := 5, nextObstruction := 5 }}

def fcDropComponent_{suffix} : FrontierComponent_{suffix} :=
  {{ oddEdges := 1, evenEdges := 1,
    heightBefore := 2, heightAfter := 2, obstruction := 5, nextObstruction := 3 }}

def fcDangerousComponent_{suffix} : FrontierComponent_{suffix} :=
  {{ oddEdges := 1, evenEdges := 1,
    heightBefore := 2, heightAfter := 2, obstruction := 5, nextObstruction := 5 }}

def fcCheckedFrontier_{suffix} : List FrontierComponent_{suffix} :=
  [fcHeightComponent_{suffix}, fcRecoveryComponent_{suffix}, fcDropComponent_{suffix}]

def fcAdversarialFrontier_{suffix} : List FrontierComponent_{suffix} :=
  [fcDangerousComponent_{suffix}]

def fcMixedFrontier_{suffix} : List FrontierComponent_{suffix} :=
  [fcHeightComponent_{suffix}, fcDangerousComponent_{suffix}]

structure FrontierCertificate_{suffix} where
  components : List FrontierComponent_{suffix}
  recurrentBad : Nat
  certified : Nat
  dangerous : Nat

def fcCheckedCertificate_{suffix} : FrontierCertificate_{suffix} :=
  {{ components := fcCheckedFrontier_{suffix},
    recurrentBad := {recurrent_bad}, certified := {height_escaping}, dangerous := {dangerous} }}

def fcSoundCertificate_{suffix} (cert : FrontierCertificate_{suffix}) : Prop :=
  fcAllCertified_{suffix} cert.components /\\ cert.dangerous = 0

def fcNoDangerousFrontier_{suffix} (cert : FrontierCertificate_{suffix}) : Prop :=
  cert.dangerous = 0 /\\ Not (fcHasDangerous_{suffix} cert.components)

def fcDensityClosed_{suffix} (cert : FrontierCertificate_{suffix}) : Prop :=
  cert.dangerous = 0

structure FrontierCertificateTarget_{suffix} where
  recurrentBad : Nat
  certified : Nat
  dangerous : Nat

def fcTargetExample_{suffix} : FrontierCertificateTarget_{suffix} :=
  {{ recurrentBad := fcCheckedCertificate_{suffix}.recurrentBad,
    certified := fcCheckedCertificate_{suffix}.certified,
    dangerous := fcCheckedCertificate_{suffix}.dangerous }}
""".strip()
        component_soundness = f"""
theorem fc_component_certificate_not_dangerous_{suffix}
    (c : FrontierComponent_{suffix})
    (hCert : fcCertified_{suffix} c) :
    Not (fcDangerous_{suffix} c) := by
  intro hDanger
  cases hCert with
  | inl hRecover =>
      exact hDanger.1 hRecover
  | inr hRest =>
      cases hRest with
      | inl hHeight =>
          exact hDanger.2.1 hHeight
      | inr hDrop =>
          exact hDanger.2.2 hDrop
""".strip()
        frontier_soundness = f"""
{component_soundness}

theorem fc_all_certified_frontier_has_no_dangerous_{suffix}
    (xs : List FrontierComponent_{suffix})
    (hAll : fcAllCertified_{suffix} xs) :
    Not (fcHasDangerous_{suffix} xs) := by
  intro hDanger
  cases hDanger with
  | intro c hRest =>
      exact fc_component_certificate_not_dangerous_{suffix} c (hAll c hRest.1) hRest.2
""".strip()
        specs: list[tuple[str, str, str, bool, str, str]] = [
            (
                "definition_probe",
                "Pressure-height frontier certificate / component certificate format has three exits.",
                f"""{base_defs}

theorem fc_component_certificate_format_has_three_exits_{suffix} :
    fcCertified_{suffix} fcRecoveryComponent_{suffix} /\\
    fcCertified_{suffix} fcHeightComponent_{suffix} /\\
    fcCertified_{suffix} fcDropComponent_{suffix} := by
  native_decide
""",
                True,
                "certificate_format",
                "three_exits",
            ),
            (
                "closure_probe",
                "Pressure-height frontier certificate / component certificate excludes danger.",
                f"""{base_defs}

{component_soundness}
""",
                True,
                "certificate_soundness",
                "component_soundness",
            ),
            (
                "closure_probe",
                "Pressure-height frontier certificate / all-certified frontier has no dangerous component.",
                f"""{base_defs}

{frontier_soundness}
""",
                True,
                "certificate_soundness",
                "frontier_soundness",
            ),
            (
                "closure_probe",
                "Pressure-height frontier certificate / checked frontier packages as all-certified.",
                f"""{base_defs}

theorem fc_checked_frontier_is_all_certified_{suffix} :
    fcAllCertified_{suffix} fcCheckedFrontier_{suffix} := by
  native_decide
""",
                True,
                "bounded_certificate",
                "checked_all_certified",
            ),
            (
                "closure_probe",
                "Pressure-height frontier certificate / checked certificate has no dangerous survivor.",
                f"""{base_defs}

{frontier_soundness}

theorem fc_checked_certificate_has_no_dangerous_survivor_{suffix} :
    fcNoDangerousFrontier_{suffix} fcCheckedCertificate_{suffix} := by
  constructor
  · native_decide
  · exact fc_all_certified_frontier_has_no_dangerous_{suffix}
      fcCheckedCertificate_{suffix}.components
      (by native_decide)
""",
                True,
                "bounded_certificate",
                "checked_no_dangerous",
            ),
            (
                "anti_smuggling_probe",
                "Pressure-height frontier certificate / uncertified frontier can contain danger.",
                f"""{base_defs}

theorem fc_uncertified_frontier_can_contain_danger_{suffix} :
    fcHasDangerous_{suffix} fcAdversarialFrontier_{suffix} := by
  native_decide
""",
                True,
                "adversarial_gate",
                "uncertified_danger",
            ),
            (
                "anti_smuggling_probe",
                "Pressure-height frontier certificate / pressure-bad alone is not a certificate.",
                f"""{base_defs}

theorem fc_pressure_bad_alone_is_not_certificate_{suffix} :
    fcPressureBad_{suffix} fcDangerousComponent_{suffix} /\\
    Not (fcCertified_{suffix} fcDangerousComponent_{suffix}) := by
  native_decide
""",
                True,
                "adversarial_gate",
                "pressure_bad_not_certificate",
            ),
            (
                "anti_smuggling_probe",
                "Pressure-height frontier certificate / one height escape without coverage is insufficient.",
                f"""{base_defs}

theorem fc_one_height_escape_without_coverage_insufficient_{suffix} :
    (∃ c, c ∈ fcMixedFrontier_{suffix} /\\ fcHeightEscapes_{suffix} c) /\\
    fcHasDangerous_{suffix} fcMixedFrontier_{suffix} := by
  native_decide
""",
                True,
                "adversarial_gate",
                "coverage_required",
            ),
            (
                "closure_probe",
                "Pressure-height frontier certificate / sound certificate gives density closure.",
                f"""{base_defs}

theorem fc_sound_certificate_gives_density_closure_{suffix}
    (cert : FrontierCertificate_{suffix})
    (hSound : fcSoundCertificate_{suffix} cert) :
    fcDensityClosed_{suffix} cert := by
  exact hSound.2
""",
                True,
                "density_bridge",
                "certificate_to_density",
            ),
            (
                "definition_probe",
                "Pressure-height frontier certificate / target is counting-height only.",
                f"""{base_defs}

theorem fc_target_is_counting_height_only_{suffix} :
    fcTargetExample_{suffix}.recurrentBad = {recurrent_bad} /\\
    fcTargetExample_{suffix}.certified = {height_escaping} /\\
    fcTargetExample_{suffix}.dangerous = 0 := by
  native_decide
""",
                True,
                "anti_smuggling",
                "counting_height_only",
            ),
            (
                "closure_probe",
                "Pressure-height frontier certificate / checked certificate is sound.",
                f"""{base_defs}

theorem fc_checked_certificate_is_sound_{suffix} :
    fcSoundCertificate_{suffix} fcCheckedCertificate_{suffix} := by
  constructor
  · native_decide
  · native_decide
""",
                True,
                "bounded_certificate",
                "checked_certificate_sound",
            ),
            (
                "closure_probe",
                "Pressure-height frontier certificate / certificate theorem is uniform over frontiers.",
                f"""{base_defs}

{frontier_soundness}

theorem fc_uniform_certificate_theorem_{suffix}
    (cert : FrontierCertificate_{suffix})
    (hSound : fcSoundCertificate_{suffix} cert) :
    fcNoDangerousFrontier_{suffix} cert := by
  constructor
  · exact hSound.2
  · exact fc_all_certified_frontier_has_no_dangerous_{suffix}
      cert.components hSound.1
""",
                True,
                "certificate_soundness",
                "uniform_frontier_theorem",
            ),
        ]

        probes: list[FormalProbe] = []
        for probe_type, source_text, lean, decisive, family, role in specs[:max_probes]:
            metadata = {
                "pressure_height_frontier_certificate_wave": True,
                "certificate_family": family,
                "certificate_role": role,
                "decisive": decisive,
                "world_id": world_id,
                "frontier_counts": {
                    "recurrent_bad": recurrent_bad,
                    "height_escaping": height_escaping,
                    "dangerous": dangerous,
                },
            }
            probes.append(
                FormalProbe(
                    world_id=world_id,
                    probe_type=probe_type,  # type: ignore[arg-type]
                    source_text=source_text,
                    formal_obligation=FormalObligationSpec(
                        source_text=source_text,
                        channel_hint="proof",
                        goal_kind="theorem",
                        lean_declaration=lean,
                        requires_proof=True,
                        metadata=metadata,
                    ),
                    notes=(
                        "Pressure-height frontier certificate probe; this packages the "
                        "local survivor-closure result into a uniform certificate theorem."
                    ),
                )
            )
        return probes

    def _compile_pressure_height_frontier_completeness_wave_probes(
        self,
        *,
        world_id: str,
        generated_reports: list[dict[str, Any]],
        max_probes: int,
    ) -> list[FormalProbe]:
        suffix = uuid4().hex[:8]
        max_window = max((int(report["window"]) for report in generated_reports), default=0)
        acyclic_report = next(
            (
                report
                for report in generated_reports
                if int(report["recurrent_bad_components"]) == 0
            ),
            generated_reports[0],
        )
        recurrent_report = next(
            (
                report
                for report in generated_reports
                if int(report["recurrent_bad_components"]) > 0
            ),
            generated_reports[-1],
        )
        max_window_report = generated_reports[-1]

        def lean_report(report: dict[str, Any]) -> str:
            return (
                "{ "
                f"window := {int(report['window'])}, "
                f"modulusBits := {int(report['modulus_bits'])}, "
                f"stateCount := {int(report['state_count'])}, "
                f"edgeCount := {int(report['edge_count'])}, "
                f"recurrentBad := {int(report['recurrent_bad_components'])}, "
                f"pressureRecovery := {int(report['pressure_recovery_components'])}, "
                f"heightEscape := {int(report['height_escape_components'])}, "
                f"survivorDrop := {int(report['survivor_drop_components'])}, "
                f"dangerous := {int(report['dangerous_components'])}, "
                f"unchecked := {int(report['unchecked_components'])} "
                "}"
            )

        report_entries = ",\n  ".join(lean_report(report) for report in generated_reports)
        acyclic_entry = lean_report(acyclic_report)
        recurrent_entry = lean_report(recurrent_report)
        max_window_entry = lean_report(max_window_report)
        generated_count = len(generated_reports)
        total_recurrent = sum(int(report["recurrent_bad_components"]) for report in generated_reports)
        total_height_escape = sum(int(report["height_escape_components"]) for report in generated_reports)
        total_dangerous = sum(int(report["dangerous_components"]) for report in generated_reports)
        total_unchecked = sum(int(report["unchecked_components"]) for report in generated_reports)

        base_defs = f"""
structure PHKFrontierReport_{suffix} where
  window : Nat
  modulusBits : Nat
  stateCount : Nat
  edgeCount : Nat
  recurrentBad : Nat
  pressureRecovery : Nat
  heightEscape : Nat
  survivorDrop : Nat
  dangerous : Nat
  unchecked : Nat
  deriving DecidableEq, Repr

def phkCertifiedCount_{suffix} (r : PHKFrontierReport_{suffix}) : Nat :=
  r.pressureRecovery + r.heightEscape + r.survivorDrop

def phkReportComplete_{suffix} (r : PHKFrontierReport_{suffix}) : Prop :=
  r.unchecked = 0 /\\
    r.dangerous = 0 /\\
    r.recurrentBad <= phkCertifiedCount_{suffix} r

def phkReportNoDangerous_{suffix} (r : PHKFrontierReport_{suffix}) : Prop :=
  r.dangerous = 0

def phkReportNoUnchecked_{suffix} (r : PHKFrontierReport_{suffix}) : Prop :=
  r.unchecked = 0

def phkGeneratedReports_{suffix} : List PHKFrontierReport_{suffix} := [
  {report_entries}
]

def phkAcyclicGeneratedReport_{suffix} : PHKFrontierReport_{suffix} :=
  {acyclic_entry}

def phkRecurrentGeneratedReport_{suffix} : PHKFrontierReport_{suffix} :=
  {recurrent_entry}

def phkMaxWindowGeneratedReport_{suffix} : PHKFrontierReport_{suffix} :=
  {max_window_entry}

def phkGeneratedComplete_{suffix} : Prop :=
  ∀ r, r ∈ phkGeneratedReports_{suffix} -> phkReportComplete_{suffix} r

def phkGeneratedNoDangerous_{suffix} : Prop :=
  ∀ r, r ∈ phkGeneratedReports_{suffix} -> phkReportNoDangerous_{suffix} r

def phkGeneratedNoUnchecked_{suffix} : Prop :=
  ∀ r, r ∈ phkGeneratedReports_{suffix} -> phkReportNoUnchecked_{suffix} r

structure PHKBoundedCompletenessCertificate_{suffix} where
  maxWindow : Nat
  generatedReportCount : Nat
  totalRecurrentBad : Nat
  totalHeightEscape : Nat
  totalDangerous : Nat
  totalUnchecked : Nat
  deriving DecidableEq, Repr

def phkBoundedCertificate_{suffix} : PHKBoundedCompletenessCertificate_{suffix} :=
  {{ maxWindow := {max_window},
    generatedReportCount := {generated_count},
    totalRecurrentBad := {total_recurrent},
    totalHeightEscape := {total_height_escape},
    totalDangerous := {total_dangerous},
    totalUnchecked := {total_unchecked} }}

def phkDangerousReport_{suffix} : PHKFrontierReport_{suffix} :=
  {{ window := {max_window + 1}, modulusBits := 1, stateCount := 1, edgeCount := 1,
    recurrentBad := 1, pressureRecovery := 0, heightEscape := 0,
    survivorDrop := 0, dangerous := 1, unchecked := 0 }}

def phkUncheckedReport_{suffix} : PHKFrontierReport_{suffix} :=
  {{ window := {max_window + 2}, modulusBits := 1, stateCount := 1, edgeCount := 1,
    recurrentBad := 1, pressureRecovery := 0, heightEscape := 0,
    survivorDrop := 0, dangerous := 0, unchecked := 1 }}

def phkAdversarialFrontier_{suffix} : List PHKFrontierReport_{suffix} :=
  [phkDangerousReport_{suffix}]

def phkParameterizedCompleteness_{suffix}
    (gen : Nat -> PHKFrontierReport_{suffix}) : Prop :=
  ∀ depth, phkReportComplete_{suffix} (gen depth)

def phkNoDangerousAtEveryDepth_{suffix}
    (gen : Nat -> PHKFrontierReport_{suffix}) : Prop :=
  ∀ depth, phkReportNoDangerous_{suffix} (gen depth)

def phkCountingTarget_{suffix} : PHKBoundedCompletenessCertificate_{suffix} :=
  phkBoundedCertificate_{suffix}
""".strip()

        generated_complete = f"""
theorem phk_generated_frontiers_complete_{suffix} :
    phkGeneratedComplete_{suffix} := by
  unfold phkGeneratedComplete_{suffix} phkGeneratedReports_{suffix}
  unfold phkReportComplete_{suffix} phkCertifiedCount_{suffix}
  native_decide
""".strip()

        specs: list[tuple[str, str, str, bool, str, str]] = [
            (
                "definition_probe",
                "Pressure-height frontier completeness / generated report count matches bounded horizon.",
                f"""{base_defs}

theorem phk_generated_report_count_matches_horizon_{suffix} :
    phkGeneratedReports_{suffix}.length = {generated_count} /\\
    phkBoundedCertificate_{suffix}.maxWindow = {max_window} := by
  unfold phkGeneratedReports_{suffix} phkBoundedCertificate_{suffix}
  native_decide
""",
                True,
                "bounded_generated_frontier",
                "report_count",
            ),
            (
                "closure_probe",
                "Pressure-height frontier completeness / generated frontiers are all certified through bounded horizon.",
                f"""{base_defs}

{generated_complete}
""",
                True,
                "bounded_generated_frontier",
                "bounded_completeness",
            ),
            (
                "closure_probe",
                "Pressure-height frontier completeness / generated frontiers have no dangerous component.",
                f"""{base_defs}

{generated_complete}

theorem phk_generated_frontiers_have_no_dangerous_{suffix} :
    phkGeneratedNoDangerous_{suffix} := by
  intro r hMem
  exact (phk_generated_frontiers_complete_{suffix} r hMem).2.1
""",
                True,
                "bounded_generated_frontier",
                "no_dangerous",
            ),
            (
                "closure_probe",
                "Pressure-height frontier completeness / generated frontiers have no unchecked component.",
                f"""{base_defs}

{generated_complete}

theorem phk_generated_frontiers_have_no_unchecked_{suffix} :
    phkGeneratedNoUnchecked_{suffix} := by
  intro r hMem
  exact (phk_generated_frontiers_complete_{suffix} r hMem).1
""",
                True,
                "bounded_generated_frontier",
                "no_unchecked",
            ),
            (
                "closure_probe",
                "Pressure-height frontier completeness / generated recurrent bad components are covered by exits.",
                f"""{base_defs}

{generated_complete}

theorem phk_generated_recurrent_bad_covered_by_exits_{suffix} :
    ∀ r, r ∈ phkGeneratedReports_{suffix} ->
      r.recurrentBad <= r.pressureRecovery + r.heightEscape + r.survivorDrop := by
  intro r hMem
  exact (phk_generated_frontiers_complete_{suffix} r hMem).2.2
""",
                True,
                "bounded_generated_frontier",
                "exit_coverage",
            ),
            (
                "definition_probe",
                "Pressure-height frontier completeness / max-window generated frontier is complete.",
                f"""{base_defs}

theorem phk_max_window_generated_frontier_complete_{suffix} :
    phkMaxWindowGeneratedReport_{suffix} ∈ phkGeneratedReports_{suffix} /\\
    phkReportComplete_{suffix} phkMaxWindowGeneratedReport_{suffix} := by
  unfold phkMaxWindowGeneratedReport_{suffix} phkGeneratedReports_{suffix}
  unfold phkReportComplete_{suffix} phkCertifiedCount_{suffix}
  native_decide
""",
                True,
                "bounded_generated_frontier",
                "max_window_complete",
            ),
            (
                "definition_probe",
                "Pressure-height frontier completeness / acyclic generated frontier is vacuously complete.",
                f"""{base_defs}

theorem phk_acyclic_generated_frontier_vacuously_complete_{suffix} :
    phkAcyclicGeneratedReport_{suffix}.recurrentBad = 0 /\\
    phkReportComplete_{suffix} phkAcyclicGeneratedReport_{suffix} := by
  unfold phkAcyclicGeneratedReport_{suffix}
  unfold phkReportComplete_{suffix} phkCertifiedCount_{suffix}
  native_decide
""",
                True,
                "bounded_generated_frontier",
                "acyclic_vacuous",
            ),
            (
                "closure_probe",
                "Pressure-height frontier completeness / recurrent generated frontier is height-certified.",
                f"""{base_defs}

theorem phk_recurrent_generated_frontier_height_certified_{suffix} :
    phkRecurrentGeneratedReport_{suffix}.recurrentBad <=
      phkRecurrentGeneratedReport_{suffix}.heightEscape /\\
    phkReportComplete_{suffix} phkRecurrentGeneratedReport_{suffix} := by
  unfold phkRecurrentGeneratedReport_{suffix}
  unfold phkReportComplete_{suffix} phkCertifiedCount_{suffix}
  native_decide
""",
                True,
                "bounded_generated_frontier",
                "height_certified",
            ),
            (
                "anti_smuggling_probe",
                "Pressure-height frontier completeness / bounded certificate declares finite horizon only.",
                f"""{base_defs}

theorem phk_bounded_certificate_is_finite_only_{suffix} :
    phkBoundedCertificate_{suffix}.maxWindow = {max_window} /\\
    phkBoundedCertificate_{suffix}.generatedReportCount = {generated_count} := by
  unfold phkBoundedCertificate_{suffix}
  native_decide
""",
                True,
                "bounded_not_global",
                "finite_horizon_only",
            ),
            (
                "closure_probe",
                "Pressure-height frontier completeness / generated completeness feeds no-dangerous frontier theorem.",
                f"""{base_defs}

{generated_complete}

theorem phk_generated_completeness_feeds_no_dangerous_theorem_{suffix} :
    ∀ r, r ∈ phkGeneratedReports_{suffix} -> r.dangerous = 0 := by
  intro r hMem
  exact (phk_generated_frontiers_complete_{suffix} r hMem).2.1
""",
                True,
                "certificate_bridge",
                "feeds_no_dangerous",
            ),
            (
                "closure_probe",
                "Pressure-height frontier completeness / parameterized completeness would close danger at every depth.",
                f"""{base_defs}

theorem phk_parameterized_completeness_closes_danger_{suffix}
    (gen : Nat -> PHKFrontierReport_{suffix})
    (hComplete : phkParameterizedCompleteness_{suffix} gen) :
    phkNoDangerousAtEveryDepth_{suffix} gen := by
  intro depth
  exact (hComplete depth).2.1
""",
                True,
                "parameterized_bridge",
                "global_shape",
            ),
            (
                "anti_smuggling_probe",
                "Pressure-height frontier completeness / counting target has no reachability field.",
                f"""{base_defs}

theorem phk_counting_target_has_only_frontier_counts_{suffix} :
    phkCountingTarget_{suffix}.totalDangerous = 0 /\\
    phkCountingTarget_{suffix}.totalUnchecked = 0 /\\
    phkCountingTarget_{suffix}.totalRecurrentBad = {total_recurrent} := by
  unfold phkCountingTarget_{suffix} phkBoundedCertificate_{suffix}
  native_decide
""",
                True,
                "anti_smuggling",
                "counting_only",
            ),
            (
                "anti_smuggling_probe",
                "Pressure-height frontier completeness / adversarial dangerous report is not complete.",
                f"""{base_defs}

theorem phk_adversarial_dangerous_report_not_complete_{suffix} :
    Not (phkReportComplete_{suffix} phkDangerousReport_{suffix}) := by
  unfold phkReportComplete_{suffix} phkDangerousReport_{suffix}
  unfold phkCertifiedCount_{suffix}
  native_decide
""",
                True,
                "kill_gate",
                "dangerous_refutes_completeness",
            ),
            (
                "anti_smuggling_probe",
                "Pressure-height frontier completeness / adversarial unchecked report is not complete.",
                f"""{base_defs}

theorem phk_adversarial_unchecked_report_not_complete_{suffix} :
    Not (phkReportComplete_{suffix} phkUncheckedReport_{suffix}) := by
  unfold phkReportComplete_{suffix} phkUncheckedReport_{suffix}
  unfold phkCertifiedCount_{suffix}
  native_decide
""",
                True,
                "kill_gate",
                "unchecked_refutes_completeness",
            ),
            (
                "anti_smuggling_probe",
                "Pressure-height frontier completeness / dangerous member refutes any completeness proof.",
                f"""{base_defs}

theorem phk_dangerous_member_refutes_completeness_{suffix}
    (xs : List PHKFrontierReport_{suffix})
    (r : PHKFrontierReport_{suffix})
    (hMem : r ∈ xs)
    (hDanger : r.dangerous ≠ 0)
    (hComplete : ∀ x, x ∈ xs -> phkReportComplete_{suffix} x) :
    False := by
  exact hDanger ((hComplete r hMem).2.1)
""",
                True,
                "kill_gate",
                "dangerous_member_refutes",
            ),
        ]

        probes: list[FormalProbe] = []
        for probe_type, source_text, lean, decisive, family, role in specs[:max_probes]:
            metadata = {
                "pressure_height_frontier_completeness_wave": True,
                "completeness_family": family,
                "completeness_role": role,
                "decisive": decisive,
                "world_id": world_id,
                "bounded_horizon": max_window,
                "generated_frontier_totals": {
                    "report_count": generated_count,
                    "recurrent_bad": total_recurrent,
                    "height_escape": total_height_escape,
                    "dangerous": total_dangerous,
                    "unchecked": total_unchecked,
                },
            }
            probes.append(
                FormalProbe(
                    world_id=world_id,
                    probe_type=probe_type,  # type: ignore[arg-type]
                    source_text=source_text,
                    formal_obligation=FormalObligationSpec(
                        source_text=source_text,
                        channel_hint="proof",
                        goal_kind="theorem",
                        lean_declaration=lean,
                        requires_proof=True,
                        metadata=metadata,
                    ),
                    notes=(
                        "Pressure-height frontier completeness kill-test; bounded generated "
                        "frontiers must satisfy the R20 certificate precondition while adversarial "
                        "dangerous/unchecked reports must refute completeness."
                    ),
                )
            )
        return probes

    def _decision_for_formal_probe(
        self,
        campaign: CampaignRecord,
        probe: FormalProbe,
        world: WorldProgram | None,
    ) -> ManagerDecision:
        return ManagerDecision(
            candidate_answer=CandidateAnswer(
                stance="undecided",
                summary="Baking compiled formal probes; not solving from narrative confidence.",
                confidence=0.1,
            ),
            alternatives=[],
            target_frontier_node=f"probe:{probe.id}",
            world_family="bridge",
            bounded_claim=probe.source_text,
            formal_obligations=[probe.formal_obligation],
            expected_information_gain=(
                "Determine whether the promoted world has Lean-clean formal contact."
            ),
            why_this_next=(
                "World evolution compiled this as a tiny probe; bake probes before grand proof debt."
            ),
            update_rules=UpdateRules(
                if_proved="Increase world formal-probe success and keep the survivor.",
                if_refuted="Treat this probe shape as invalid and mutate the world.",
                if_blocked="Record the missing formalization/proof gap and mutate the probe.",
                if_inconclusive="Retry only after reducing the probe or budget shape.",
            ),
            self_improvement_note=SelfImprovementNote(
                proposal="None",
                reason="Probe baking is an execution step, not a policy update.",
            ),
            obligation_hints={"formal_probe_id": probe.id, "probe_type": probe.probe_type},
            manager_backend="probe_baker",
            global_thesis=(
                "A promoted invented world must survive tiny formal probes before closure debt."
            ),
            primary_world=world,
            proof_debt=[],
            critical_next_debt_id=probe.id,
        )

    def _mark_formal_probe_submitted(
        self,
        campaign_id: str,
        probe: FormalProbe,
        job: PendingAristotleJob,
    ) -> None:
        updated = probe.model_copy(
            update={
                "status": "submitted",
                "result_status": job.status,
                "artifact_paths": list(dict.fromkeys([
                    *probe.artifact_paths,
                    f"aristotle_project_id:{job.project_id}",
                ])),
                "notes": f"{probe.notes} Submitted to Aristotle project {job.project_id}.",
            }
        )
        self.memory.upsert_research_node(
            campaign_id=campaign_id,
            node_id=probe.id,
            node_type="FormalProbe",
            title=f"{probe.probe_type}:{probe.world_id}",
            summary=probe.source_text,
            status=updated.status,
            payload=updated.model_dump(mode="json"),
        )

    def _update_formal_probe_result(
        self,
        campaign_id: str,
        probe_id: str,
        job: PendingAristotleJob,
        result: ExecutionResult,
    ) -> None:
        node = self.memory.get_research_node(campaign_id, probe_id)
        if not node:
            return
        try:
            probe = FormalProbe.model_validate(node.payload)
        except Exception:
            logger.warning("Could not update invalid FormalProbe node=%s", probe_id)
            return
        if result.status == "proved":
            status = "proved"
        elif result.status == "blocked":
            status = "blocked"
        else:
            status = "inconclusive"
        updated = probe.model_copy(
            update={
                "status": status,
                "result_status": result.status,
                "failure_type": result.failure_type,
                "artifact_paths": [
                    artifact for artifact in result.artifacts if _looks_like_aristotle_tar_path(artifact)
                ],
                "notes": (
                    f"{probe.notes} Aristotle project {job.project_id} finished with "
                    f"{result.status}/{result.failure_type or 'ok'}."
                ),
            }
        )
        self.memory.upsert_research_node(
            campaign_id=campaign_id,
            node_id=probe_id,
            node_type="FormalProbe",
            title=f"{probe.probe_type}:{probe.world_id}",
            summary=probe.source_text,
            status=updated.status,
            payload=updated.model_dump(mode="json"),
        )

    def _record_probe_bake_run(self, bake_run: FormalProbeBakeRun) -> None:
        self.memory.upsert_research_node(
            campaign_id=bake_run.campaign_id,
            node_id=bake_run.id,
            node_type="FormalProbeBakeRun",
            title=f"formal-probe-bake:{bake_run.submitted_probe_count}",
            summary=", ".join(bake_run.notes),
            status=bake_run.status,
            payload=bake_run.model_dump(mode="json"),
        )

    def _latest_probe_digest_summary(self, campaign_id: str) -> dict[str, Any]:
        nodes = self.memory.list_research_nodes(
            campaign_id,
            node_type="FormalProbeDigestRun",
            limit=1,
        )
        if not nodes:
            return {
                "latest_digest_id": None,
                "artifact_count": 0,
                "probe_count": 0,
                "top_failure_modes": [],
                "repair_instructions": [],
            }
        payload = nodes[0].payload or {}
        return {
            "latest_digest_id": payload.get("id") or nodes[0].id,
            "artifact_count": payload.get("artifact_count", 0),
            "probe_count": payload.get("probe_count", 0),
            "proved_count": payload.get("proved_count", 0),
            "blocked_count": payload.get("blocked_count", 0),
            "inconclusive_count": payload.get("inconclusive_count", 0),
            "top_failure_modes": payload.get("top_failure_modes", []),
            "repair_instructions": payload.get("repair_instructions", [])[:5],
        }

    def _latest_final_collatz_experiment_summary(self, campaign_id: str) -> dict[str, Any]:
        nodes = self.memory.list_research_nodes(
            campaign_id,
            node_type="FinalCollatzExperimentRun",
            limit=1,
        )
        if not nodes:
            return {
                "latest_run_id": None,
                "compiled_probe_count": 0,
                "hard_probe_count": 0,
                "decisive_probe_count": 0,
                "decision_status": None,
                "summary": None,
            }
        payload = nodes[0].payload or {}
        return {
            "latest_run_id": payload.get("id") or nodes[0].id,
            "world_id": payload.get("world_id"),
            "world_label": payload.get("world_label"),
            "compiled_probe_count": payload.get("compiled_probe_count", 0),
            "control_probe_count": payload.get("control_probe_count", 0),
            "hard_probe_count": payload.get("hard_probe_count", 0),
            "decisive_probe_count": len(payload.get("decisive_probe_ids", [])),
            "submitted_probe_count": payload.get("submitted_probe_count", 0),
            "decision_status": payload.get("decision_status"),
            "kill_criteria": payload.get("kill_criteria", [])[:4],
            "pursue_criteria": payload.get("pursue_criteria", [])[:4],
            "expected_learning": payload.get("expected_learning", [])[:4],
            "summary": payload.get("summary"),
        }

    def _artifacts_by_probe(
        self,
        campaign_id: str,
        probes: list[FormalProbe],
        *,
        campaign: CampaignRecord | None = None,
        include_project_refs: bool = False,
    ) -> dict[str, list[str]]:
        probe_ids = {probe.id for probe in probes}
        artifacts_by_probe: dict[str, list[str]] = {probe_id: [] for probe_id in probe_ids}
        for event in self.memory.list_events(campaign_id, limit=1000):
            if event.event_type != "aristotle_job_completed":
                continue
            probe_id = event.payload.get("debt_id")
            if probe_id not in probe_ids:
                continue
            for artifact in event.payload.get("artifacts") or []:
                if _looks_like_aristotle_artifact(artifact):
                    artifacts_by_probe[probe_id].append(artifact)
            if include_project_refs and event.payload.get("project_id"):
                artifacts_by_probe[probe_id].append(
                    f"aristotle_project_id:{event.payload['project_id']}"
                )
        if include_project_refs:
            try:
                campaign = campaign or self.get_campaign(campaign_id)
                pending_jobs = self._pending_jobs(campaign)
            except Exception:
                logger.exception("Unable to include pending Aristotle project refs for digest.")
                pending_jobs = []
            for job in pending_jobs:
                if job.debt_id in probe_ids:
                    artifacts_by_probe[job.debt_id].append(
                        f"aristotle_project_id:{job.project_id}"
                    )
        return artifacts_by_probe

    def _reconcile_pending_jobs_from_probe_diagnostics(
        self,
        campaign: CampaignRecord,
        diagnostics: list[dict[str, Any]],
    ) -> int:
        """Clear pending proof jobs when digest recovered a terminal probe artifact."""
        pending_jobs = self._pending_jobs(campaign)
        if not pending_jobs:
            return 0

        terminal_by_probe: dict[str, dict[str, Any]] = {}
        for diagnostic in diagnostics:
            probe_id = diagnostic.get("probe_id")
            probe_status = diagnostic.get("probe_status")
            if not probe_id or probe_status == "inconclusive":
                continue
            terminal_by_probe[probe_id] = diagnostic

        if not terminal_by_probe:
            return 0

        completed_project_ids = {
            event.payload.get("project_id")
            for event in self.memory.list_events(campaign.id, limit=1000)
            if event.event_type == "aristotle_job_completed"
        }
        updated = campaign.model_copy(deep=True)
        still_pending: list[PendingAristotleJob] = []
        reconciled_count = 0

        for job in pending_jobs:
            diagnostic = terminal_by_probe.get(job.debt_id or "")
            if not diagnostic:
                still_pending.append(job)
                continue

            reconciled_count += 1
            result_status = diagnostic.get("result_status") or diagnostic.get("probe_status")
            failure_type = diagnostic.get("failure_type")
            artifact_paths = diagnostic.get("artifact_paths") or []
            tar_paths = [
                path for path in artifact_paths if isinstance(path, str) and _looks_like_aristotle_tar_path(path)
            ]

            if job.project_id not in completed_project_ids:
                self.memory.add_event(
                    campaign_id=campaign.id,
                    tick=campaign.tick_count,
                    event_type="aristotle_job_completed",
                    payload={
                        "project_id": job.project_id,
                        "poll_count": job.poll_count,
                        "status": result_status,
                        "debt_id": job.debt_id,
                        "result_status": result_status,
                        "failure_type": failure_type,
                        "artifacts": artifact_paths,
                        "source": "formal_probe_digest_reconciliation",
                    },
                )

            for debt in updated.proof_debt_ledger:
                if debt.get("id") != job.debt_id:
                    continue
                debt["status"] = diagnostic.get("probe_status")
                debt["failure_type"] = failure_type
                debt["result_status"] = result_status
                debt["artifact_paths"] = artifact_paths

            if updated.last_execution_result is None:
                updated.last_execution_result = {
                    "status": result_status,
                    "failure_type": failure_type,
                    "notes": (
                        f"Formal probe digest reconciled Aristotle project {job.project_id} "
                        f"for {job.debt_id}."
                    ),
                    "artifacts": artifact_paths,
                    "executor_backend": "aristotle",
                }
            if tar_paths:
                job.result_tar_path = tar_paths[0]
            job.status = result_status
            job.notes.append(
                f"Reconciled by formal probe digest as {result_status}/{failure_type or 'ok'}."
            )

        if reconciled_count:
            self._set_pending_jobs(updated, still_pending)
            self._recompute_resolved_debt_ids(updated)
            self._persist_campaign(updated)
        return reconciled_count

    def _unmapped_aristotle_artifacts(
        self,
        campaign_id: str,
        limit: int,
    ) -> list[str]:
        try:
            artifacts = self.memory.store.list_artifacts(
                campaign_id,
                artifact_type="execution_result",
                limit=limit,
            )
        except Exception:
            logger.exception("Unable to list execution_result artifacts for digest.")
            return []
        paths: list[str] = []
        for artifact in artifacts:
            text = artifact.content_text or ""
            if _looks_like_aristotle_artifact(text):
                paths.append(text)
        return list(dict.fromkeys(paths))

    def _diagnose_probe_artifacts(
        self,
        probe: FormalProbe,
        artifact_paths: list[str],
        *,
        redownload_missing_artifacts: bool = False,
    ) -> dict[str, Any]:
        base = self._diagnose_artifact_paths(
            artifact_paths,
            redownload_missing_artifacts=redownload_missing_artifacts,
        )
        probe_status = base["probe_status"]
        if probe.status == "proved" and base["failure_type"] == "no_error_detected":
            probe_status = "proved"
        result_status = base["result_status"]
        if probe_status != "proved" and probe.result_status:
            result_status = probe.result_status
        return {
            **base,
            "probe_id": probe.id,
            "world_id": probe.world_id,
            "probe_type": probe.probe_type,
            "source_text": probe.source_text,
            "result_status": result_status,
        }

    def _diagnose_unmapped_artifact(
        self,
        artifact_path: str,
        *,
        redownload_missing_artifacts: bool = False,
    ) -> dict[str, Any]:
        return {
            **self._diagnose_artifact_paths(
                [artifact_path],
                redownload_missing_artifacts=redownload_missing_artifacts,
            ),
            "probe_id": None,
            "world_id": None,
            "probe_type": "unmapped",
            "source_text": "Unmapped Aristotle result artifact.",
        }

    def _diagnose_artifact_paths(
        self,
        artifact_paths: list[str],
        *,
        redownload_missing_artifacts: bool = False,
    ) -> dict[str, Any]:
        snippets: list[str] = []
        tar_members: list[str] = []
        missing_paths: list[str] = []
        for artifact_path in artifact_paths:
            if artifact_path.startswith("aristotle_project_id:"):
                project_id = artifact_path.split(":", 1)[1]
                if project_id.startswith("submission-failed"):
                    missing_paths.append(artifact_path)
                    continue
                if redownload_missing_artifacts:
                    recovered = self.executor.download_aristotle_result_artifacts(project_id)
                    if recovered:
                        recovered_base = self._diagnose_artifact_paths(
                            recovered,
                            redownload_missing_artifacts=False,
                        )
                        snippets.append(recovered_base.get("lean_error_excerpt") or recovered_base.get("summary") or "")
                        tar_members.extend(recovered_base.get("tar_members", []))
                        missing_paths.extend(recovered_base.get("missing_artifact_paths", []))
                    else:
                        missing_paths.append(artifact_path)
                continue
            if not _looks_like_aristotle_tar_path(artifact_path):
                if artifact_path.strip():
                    snippets.append(artifact_path[:12000])
                continue
            path = Path(artifact_path)
            if not path.exists():
                missing_paths.append(artifact_path)
                continue
            extracted = _extract_texts_from_tar(path)
            tar_members.extend(extracted.keys())
            snippets.extend(extracted.values())

        combined = "\n\n".join(snippets)
        failure_type = _classify_aristotle_text(combined, missing_paths)
        repair = _repair_instruction_for_failure(failure_type, combined)
        probe_status = "proved" if failure_type == "no_error_detected" else "blocked"
        if failure_type in {"artifact_missing", "artifact_empty", "unknown_complete_with_errors"}:
            probe_status = "inconclusive"
        return {
            "artifact_paths": artifact_paths,
            "missing_artifact_paths": missing_paths,
            "tar_members": tar_members[:50],
            "failure_type": failure_type,
            "probe_status": probe_status,
            "result_status": "proved" if probe_status == "proved" else "blocked",
            "summary": _summarize_diagnostic(failure_type, combined, missing_paths),
            "lean_error_excerpt": _first_error_excerpt(combined),
            "remaining_sorry_count": len(re.findall(r"\bsorry\b", combined, re.IGNORECASE)),
            "repair_instruction": repair,
        }

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


def _looks_like_aristotle_tar_path(value: str) -> bool:
    return value.endswith(".tar.gz") and "aristotle_results" in value


def _lean_suffix(value: str) -> str:
    suffix = re.sub(r"[^A-Za-z0-9_]", "_", value)
    if not suffix or suffix[0].isdigit():
        suffix = f"W_{suffix}"
    return suffix


def _looks_like_aristotle_artifact(value: str) -> bool:
    if _looks_like_aristotle_tar_path(value):
        return True
    lower = value.lower()
    return any(
        marker in lower
        for marker in (
            "error:",
            "unsolved goals",
            "unknown module",
            "unknown package",
            "complete_with_errors",
            "with errors",
            "--- ",
            ".lean",
        )
    )


def _extract_texts_from_tar(path: Path) -> dict[str, str]:
    texts: dict[str, str] = {}
    try:
        with tarfile.open(path, "r:*") as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                if not member.name.endswith((".lean", ".log", ".txt", ".json", ".stderr", ".stdout")):
                    continue
                extracted = tar.extractfile(member)
                if extracted is None:
                    continue
                content = extracted.read().decode("utf-8", errors="ignore")
                if content.strip():
                    texts[member.name] = content[:12000]
    except (tarfile.TarError, OSError):
        return {}
    return texts


def _classify_aristotle_text(text: str, missing_paths: list[str]) -> str:
    lower = text.lower()
    if "aristotle_project_status:" in lower and ":failed" in lower:
        return "artifact_missing"
    if not text.strip():
        return "artifact_missing" if missing_paths else "artifact_empty"
    if "unknown package" in lower or "unknown module" in lower or "no such file or directory" in lower:
        return "missing_import_or_dependency"
    if "invalid" in lower and ("field notation" in lower or "declaration" in lower):
        return "lean_declaration_error"
    if "unsolved goals" in lower:
        return "unsolved_goals"
    if re.search(r"\berror:", lower):
        return "lean_compile_error"
    if re.search(r"\bsorry\b", lower):
        return "partial_proof"
    if "complete_with_errors" in lower or "with errors" in lower:
        return "unknown_complete_with_errors"
    return "no_error_detected"


def _repair_instruction_for_failure(failure_type: str, text: str) -> str:
    if failure_type == "missing_import_or_dependency":
        return "Add the missing Lean/Mathlib imports or remove dependency-specific syntax from the probe."
    if failure_type == "lean_declaration_error":
        return "Repair the generated Lean declaration before asking Aristotle to fill proofs."
    if failure_type == "unsolved_goals":
        return "Keep the statement but add a smaller lemma or stronger tactic hint for the unresolved goal."
    if failure_type == "lean_compile_error":
        return "Parse the Lean compiler error, fix the statement or tactic syntax, and resubmit a single canonical probe."
    if failure_type == "partial_proof":
        return "Replace remaining sorry with a narrower theorem or expose the missing lemma as a new probe."
    if failure_type in {"artifact_missing", "artifact_empty"}:
        return "Ensure Aristotle result archives are downloaded and persisted before judging the probe."
    if failure_type == "unknown_complete_with_errors":
        return "Inspect full Aristotle logs; the archive did not expose a recognizable Lean error pattern."
    return "Mark this probe shape as Lean-clean and prefer it in the next repaired probe batch."


def _first_error_excerpt(text: str) -> str | None:
    if not text.strip():
        return None
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        lower = line.lower()
        if "error:" in lower or "unsolved goals" in lower or "unknown module" in lower:
            start = max(0, idx - 2)
            end = min(len(lines), idx + 8)
            return "\n".join(lines[start:end])[:2000]
    if "sorry" in text.lower():
        for idx, line in enumerate(lines):
            if "sorry" in line.lower():
                start = max(0, idx - 3)
                end = min(len(lines), idx + 6)
                return "\n".join(lines[start:end])[:2000]
    return text[:1000]


def _summarize_diagnostic(
    failure_type: str,
    text: str,
    missing_paths: list[str],
) -> str:
    if missing_paths and not text.strip():
        return f"Missing Aristotle artifact archive(s): {', '.join(missing_paths[:3])}."
    if failure_type == "no_error_detected":
        return "No Lean error or remaining sorry detected in Aristotle artifact text."
    excerpt = _first_error_excerpt(text)
    if excerpt:
        return f"{failure_type}: {excerpt[:300]}"
    return failure_type
