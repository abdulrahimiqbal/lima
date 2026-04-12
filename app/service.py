from __future__ import annotations

from .config import Settings
from .db import Database
from .executor import Executor
from .frontier import apply_execution_result, seed_frontier
from .learner import update_memory
from .manager import Manager, get_policy
from .schemas import CampaignCreate, CampaignRecord, CampaignUpdateNotes, ManagerContext, MemoryState
from .self_improvement import SelfImprovementService


class CampaignService:
    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.manager = Manager(settings)
        self.executor = Executor(settings)
        self.self_improvement = SelfImprovementService(db, settings)

    def create_campaign(self, payload: CampaignCreate) -> CampaignRecord:
        return self.db.create_campaign(
            title=payload.title,
            problem_statement=payload.problem_statement,
            operator_notes=payload.operator_notes,
            auto_run=payload.auto_run,
            frontier=seed_frontier(payload.problem_statement),
            memory=MemoryState(),
            manager_backend=self.settings.manager_backend_resolved,
            executor_backend=self.settings.executor_backend,
        )

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
        return self._build_context(campaign)

    def step_campaign(self, campaign_id: str) -> CampaignRecord:
        campaign = self.db.get_campaign(campaign_id)
        if campaign.status in {"solved", "failed", "paused"}:
            return campaign

        context = self._build_context(campaign)
        decision = self.manager.decide(context)
        result = self.executor.run(campaign, decision)

        # Get latest policy for learning
        active_policy = self.db.get_latest_policy() or get_policy()

        updated = campaign.model_copy(deep=True)
        updated.tick_count += 1
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
