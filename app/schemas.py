from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


CampaignStatus = Literal["running", "paused", "solved", "failed"]
FrontierStatus = Literal["open", "active", "blocked", "proved", "refuted"]
WorldFamily = Literal[
    "direct",
    "bridge",
    "reformulate",
    "finite_check",
    "counterexample",
    "local_to_global",
    "invariant_lift",
    "structural_case_split",
]
DecisionMode = Literal["bootstrap", "explore", "unblock", "repair"]
VerdictStatus = Literal["proved", "refuted", "blocked", "inconclusive"]


class CandidateAnswer(BaseModel):
    stance: Literal["likely_true", "likely_false", "undecided"]
    summary: str
    confidence: float


class Alternative(BaseModel):
    summary: str
    confidence: float


class UpdateRules(BaseModel):
    if_proved: str
    if_refuted: str
    if_blocked: str
    if_inconclusive: str


class SelfImprovementNote(BaseModel):
    proposal: str
    reason: str


class FrontierNode(BaseModel):
    id: str = Field(default_factory=lambda: f"F-{uuid4().hex[:10]}")
    text: str
    status: FrontierStatus = "open"
    priority: float = 1.0
    parent_id: str | None = None
    kind: Literal["claim", "lemma", "obstruction", "finite_check", "exploration"] = (
        "claim"
    )
    failure_count: int = 0
    evidence: list[str] = Field(default_factory=list)


class MemoryState(BaseModel):
    world_scores: dict[str, float] = Field(
        default_factory=lambda: {
            "direct": 0.0,
            "bridge": 0.2,
            "reformulate": 0.1,
            "finite_check": 0.0,
            "counterexample": 0.0,
        }
    )
    blocked_patterns: list[str] = Field(default_factory=list)
    useful_lemmas: list[str] = Field(default_factory=list)
    recent_failures: list[dict[str, str]] = Field(default_factory=list)
    retry_penalties: dict[str, int] = Field(default_factory=dict)
    policy_notes: list[str] = Field(default_factory=list)


class DecisionBounds(BaseModel):
    max_jobs: int = 3
    max_new_nodes: int = 2


class ManagerContext(BaseModel):
    problem: dict[str, Any]
    frontier: list[FrontierNode]
    memory: MemoryState
    operator_notes: list[str] = Field(default_factory=list)
    allowed_world_families: list[WorldFamily]
    tick: int


class ManagerDecision(BaseModel):
    candidate_answer: CandidateAnswer
    alternatives: list[Alternative] = Field(default_factory=list)
    target_frontier_node: str
    world_family: WorldFamily
    bounded_claim: str
    formal_obligations: list[str] = Field(default_factory=list)
    expected_information_gain: str
    why_this_next: str
    update_rules: UpdateRules
    self_improvement_note: SelfImprovementNote
    manager_backend: str = "rules"


class ExecutionResult(BaseModel):
    status: VerdictStatus
    failure_type: str | None = None
    notes: str
    artifacts: list[str] = Field(default_factory=list)
    spawned_nodes: list[FrontierNode] = Field(default_factory=list)
    executor_backend: str
    raw: dict[str, Any] = Field(default_factory=dict)


class CampaignCreate(BaseModel):
    title: str
    problem_statement: str
    operator_notes: list[str] = Field(default_factory=list)
    auto_run: bool = True


class CampaignUpdateNotes(BaseModel):
    operator_notes: list[str]


class CampaignControl(BaseModel):
    action: Literal["pause", "resume"]


class CampaignRecord(BaseModel):
    id: str
    title: str
    problem_statement: str
    status: CampaignStatus
    auto_run: bool
    operator_notes: list[str]
    frontier: list[FrontierNode]
    memory: MemoryState
    current_candidate_answer: CandidateAnswer | None = None
    tick_count: int = 0
    created_at: datetime
    updated_at: datetime
    last_manager_context: dict[str, Any] | None = None
    last_manager_decision: dict[str, Any] | None = None
    last_execution_result: dict[str, Any] | None = None
    manager_backend: str
    executor_backend: str


class EventRecord(BaseModel):
    id: int
    campaign_id: str
    tick: int
    kind: str
    payload: dict[str, Any]
    created_at: datetime


class InterfaceDescription(BaseModel):
    constitution: str
    manager_context_schema: dict[str, Any]
    manager_decision_schema: dict[str, Any]
    execution_result_schema: dict[str, Any]
