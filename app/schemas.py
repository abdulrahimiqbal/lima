from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


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
ObligationType = Literal[
    "proof",
    "finite_check",
    "reduction_check",
    "counterexample_search",
    "sanity_check",
]
ObligationScope = Literal["local", "semi_global", "global"]
QuantifierProfile = Literal["bounded", "unbounded", "mixed"]
ComplexityClass = Literal["micro", "small", "medium", "large", "unsafe"]
RuntimeClass = Literal["fast", "moderate", "slow", "unknown"]
SubmissionChannel = Literal["aristotle_proof", "computational_evidence", "reject"]
GoalKind = Literal[
    "lemma",
    "theorem",
    "sanity_check",
    "finite_check",
    "counterexample_search",
    "reduction_check",
]


class FormalObligationSpec(BaseModel):
    """Structured formal obligation model for theorem-search work."""

    id: str | None = None
    source_text: str
    channel_hint: Literal["proof", "evidence", "auto"] = "auto"
    goal_kind: GoalKind = "theorem"
    theorem_name: str | None = None
    imports: list[str] = Field(default_factory=list)
    variables: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    statement: str | None = None
    lean_declaration: str | None = None
    bounded_domain_description: str | None = None
    evidence_plan: dict[str, Any] = Field(default_factory=dict)
    tactic_hints: list[str] = Field(default_factory=list)
    requires_proof: bool = False
    requires_evidence: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_string(cls, text: str) -> "FormalObligationSpec":
        """Coerce old string obligations into structured form."""
        return cls(
            source_text=text,
            channel_hint="auto",
            goal_kind=_infer_goal_kind(text),
            statement=None,
            requires_proof=False,
            requires_evidence=False,
        )


def _infer_goal_kind(text: str) -> GoalKind:
    """Infer goal kind from text for backward compatibility."""
    lowered = text.lower()
    if "counterexample" in lowered or "cycle" in lowered:
        return "counterexample_search"
    if "finite" in lowered and "check" in lowered:
        return "finite_check"
    if "reduction" in lowered or "reduces" in lowered:
        return "reduction_check"
    if "sanity" in lowered or "base case" in lowered:
        return "sanity_check"
    if "lemma" in lowered:
        return "lemma"
    return "theorem"


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


class ManagerReadReceipt(BaseModel):
    problem_summary: str
    candidate_answer_seen: str | None = None
    target_node_id_confirmed: str
    target_node_text_confirmed: str
    operator_notes_seen: list[str] = Field(default_factory=list)
    relevant_memory_seen: dict[str, list[str]] = Field(default_factory=dict)
    constraints_seen: list[str] = Field(default_factory=list)
    open_uncertainties: list[str] = Field(default_factory=list)
    why_not_other_frontier_nodes: str


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
    # Evidence-to-proof escalation tracking
    evidence_streaks: dict[str, int] = Field(default_factory=dict)
    formalization_streaks: dict[str, int] = Field(default_factory=dict)
    timeout_streaks: dict[str, int] = Field(default_factory=dict)


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
    formal_obligations: list[str | FormalObligationSpec] = Field(default_factory=list)
    expected_information_gain: str
    why_this_next: str
    update_rules: UpdateRules
    self_improvement_note: SelfImprovementNote
    manager_read_receipt: ManagerReadReceipt | None = None
    obligation_hints: dict[str, Any] = Field(default_factory=dict)
    manager_backend: str = "rules"

    @field_validator("formal_obligations", mode="before")
    @classmethod
    def coerce_obligations(cls, v: Any) -> list[str | FormalObligationSpec]:
        """Coerce old string obligations to structured form for backward compatibility."""
        if not isinstance(v, list):
            return v
        result = []
        for item in v:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                result.append(FormalObligationSpec.model_validate(item))
            else:
                result.append(item)
        return result

    def get_normalized_obligations(self) -> list[FormalObligationSpec]:
        """Get all obligations as structured specs."""
        result = []
        for ob in self.formal_obligations:
            if isinstance(ob, str):
                result.append(FormalObligationSpec.from_string(ob))
            else:
                result.append(ob)
        return result


class AnalyzedObligation(BaseModel):
    text: str
    obligation_type: ObligationType
    scope: ObligationScope
    quantifier_profile: QuantifierProfile
    complexity_class: ComplexityClass
    expected_runtime_class: RuntimeClass
    submission_channel: SubmissionChannel
    allowed_in_default_loop: bool
    rejection_reason: str | None = None


class ApprovedExecutionPlan(BaseModel):
    original_obligations: list[str] = Field(default_factory=list)
    analyzed_obligations: list[AnalyzedObligation] = Field(default_factory=list)
    approved_proof_jobs: list[str] = Field(default_factory=list)
    approved_evidence_jobs: list[str] = Field(default_factory=list)
    rejected_obligations: list[str] = Field(default_factory=list)
    rejected_reasons: dict[str, str] = Field(default_factory=dict)
    channel_used: Literal["aristotle_proof", "computational_evidence", "none"] = "none"
    max_proof_jobs_per_step: int = 1
    budget_metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionResult(BaseModel):
    status: VerdictStatus
    failure_type: str | None = None
    notes: str
    artifacts: list[str] = Field(default_factory=list)
    spawned_nodes: list[FrontierNode] = Field(default_factory=list)
    executor_backend: str
    original_obligations: list[str] = Field(default_factory=list)
    analyzed_obligations: list[dict[str, Any]] = Field(default_factory=list)
    approved_proof_jobs: list[str] = Field(default_factory=list)
    approved_evidence_jobs: list[str] = Field(default_factory=list)
    rejected_obligations: list[str] = Field(default_factory=list)
    approved_jobs_count: int = 0
    rejected_jobs_count: int = 0
    channel_used: str = "none"
    timing_ms: int | None = None
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


class PendingAristotleJob(BaseModel):
    """Represents a long-running Aristotle proof job that survives restarts."""
    project_id: str
    target_frontier_node: str
    world_family: WorldFamily
    bounded_claim: str
    submitted_at: datetime
    last_polled_at: datetime | None = None
    poll_count: int = 0
    status: Literal["submitted", "running", "complete", "complete_with_errors", "out_of_budget", "failed", "canceled"] = "submitted"
    decision_snapshot: dict[str, Any]
    plan_snapshot: dict[str, Any]
    lean_code: str
    result_tar_path: str | None = None
    notes: list[str] = Field(default_factory=list)


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
    pending_aristotle_job: PendingAristotleJob | None = None


class CampaignEventRecord(BaseModel):
    id: int
    campaign_id: str
    tick: int
    kind: str
    payload: dict[str, Any]
    created_at: datetime


# Backward compatibility alias; prefer CampaignEventRecord in app code.
EventRecord = CampaignEventRecord


class InterfaceDescription(BaseModel):
    constitution: str
    manager_context_schema: dict[str, Any]
    manager_decision_schema: dict[str, Any]
    execution_result_schema: dict[str, Any]
