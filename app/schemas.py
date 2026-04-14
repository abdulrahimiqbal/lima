from __future__ import annotations

from datetime import datetime, timezone
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
InventionMode = Literal["wild", "repair", "mutation", "combination"]
InventionWildness = Literal["medium", "high", "extreme"]
InventionBatchStatus = Literal[
    "generated",
    "distilled",
    "falsified",
    "compiled",
    "baking",
    "complete",
]
DistilledWorldStatus = Literal[
    "candidate",
    "promising",
    "falsified",
    "baking",
    "retired",
]
FalsifierStatus = Literal["survived", "falsified", "inconclusive"]
BakeAttemptStatus = Literal[
    "formalization_failed",
    "submitted",
    "proved",
    "blocked",
    "inconclusive",
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
    
    @classmethod
    def from_debt_item(cls, debt: "ProofDebtItem") -> "FormalObligationSpec":
        """Convert a ProofDebtItem to a FormalObligationSpec."""
        # Map debt role to channel hint and goal kind
        inferred_goal_kind = _infer_goal_kind(debt.statement)
        if debt.role == "support" and inferred_goal_kind in {"finite_check", "counterexample_search", "sanity_check"}:
            channel_hint = "evidence"
            goal_kind = inferred_goal_kind
        elif debt.role in {"closure", "bridge", "support"}:
            channel_hint = "proof"
            goal_kind = "lemma" if debt.role == "support" else "theorem"
        elif debt.role in {"boundary", "falsifier"}:
            channel_hint = "evidence"
            goal_kind = "finite_check" if debt.role == "boundary" else "counterexample_search"
        else:
            channel_hint = "auto"
            goal_kind = inferred_goal_kind
        
        return cls(
            id=debt.id,
            source_text=debt.statement,
            channel_hint=channel_hint,
            goal_kind=goal_kind,
            statement=debt.formal_statement,
            lean_declaration=debt.lean_declaration,
            requires_proof=(channel_hint == "proof"),
            requires_evidence=(channel_hint == "evidence"),
            metadata={
                "debt_id": debt.id,
                "debt_role": debt.role,
                "debt_world_id": debt.world_id,
                "debt_critical": debt.critical,
                "debt_priority": debt.priority,
                "assigned_channel": debt.assigned_channel,
                "expected_difficulty": debt.expected_difficulty,
            },
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
    # World diagnostics
    world_diagnostics: dict[str, dict[str, Any]] = Field(default_factory=dict)


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


class TheoremDelta(BaseModel):
    """A small shift relative to the target theorem."""
    id: str = Field(default_factory=lambda: f"TD-{uuid4().hex[:8]}")
    delta_type: Literal[
        "strengthen_hypothesis",
        "weaken_conclusion",
        "change_measure",
        "introduce_normal_form",
        "factor_through_intermediate",
        "minimal_counterexample",
        "residue_refinement",
        "classify_then_transfer",
        "bounded_to_schema",
        "shortcut_dynamics",
        "other",
    ]
    source_claim: str
    transformed_claim: str
    distance_from_target: float = Field(ge=0.0, le=1.0)
    bridge_back_claim: str
    estimated_proof_gain: float = Field(ge=0.0, le=1.0)
    estimated_bridge_cost: float = Field(ge=0.0, le=1.0)


class CompressionPrinciple(BaseModel):
    """A compression principle like descent, partition, transfer, etc."""
    name: str
    description: str


class BridgePlan(BaseModel):
    """Structured bridge back to the original theorem."""
    bridge_claim: str
    bridge_obligations: list[str] = Field(default_factory=list)
    estimated_cost: float = Field(ge=0.0, le=1.0, default=0.5)


class ReductionCertificate(BaseModel):
    """Finite closure summary for a world."""
    closure_items: list[str] = Field(default_factory=list)
    bridge_items: list[str] = Field(default_factory=list)
    support_items: list[str] = Field(default_factory=list)
    total_debt_count: int = 0


class WorldProgram(BaseModel):
    """A structured mathematical world that contains a thesis and reduction strategy."""
    id: str = Field(default_factory=lambda: f"W-{uuid4().hex[:10]}")
    label: str
    family_tags: list[WorldFamily] = Field(default_factory=list)
    mode: Literal["macro", "micro"] = "macro"
    thesis: str
    ontology: list[str] = Field(default_factory=list)
    compression_principles: list[CompressionPrinciple] = Field(default_factory=list)
    bridge_to_target: BridgePlan | None = None
    reduction_certificate: ReductionCertificate | None = None
    theorem_deltas: list[TheoremDelta] = Field(default_factory=list)
    falsifiers: list[str] = Field(default_factory=list)


class ProofDebtItem(BaseModel):
    """Explicit proof debt item."""
    id: str = Field(default_factory=lambda: f"D-{uuid4().hex[:8]}")
    world_id: str
    role: Literal["closure", "bridge", "support", "boundary", "falsifier"]
    statement: str
    formal_statement: str | None = None
    lean_declaration: str | None = None
    assigned_channel: Literal["aristotle", "evidence", "human", "auto"] = "auto"
    expected_difficulty: float = Field(default=0.5, ge=0.0, le=1.0)
    depends_on: list[str] = Field(default_factory=list)
    critical: bool = False
    status: Literal["open", "active", "proved", "refuted", "blocked"] = "open"
    priority: float = 1.0
    notes: list[str] = Field(default_factory=list)
    last_failure_type: str | None = None


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
    # New world-oriented fields
    global_thesis: str | None = None
    primary_world: WorldProgram | None = None
    alternative_worlds: list[WorldProgram] = Field(default_factory=list)
    proof_debt: list[ProofDebtItem] = Field(default_factory=list)
    critical_next_debt_id: str | None = None

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


class InventionBatchCreate(BaseModel):
    mode: InventionMode = "wild"
    wildness: InventionWildness = "high"
    requested_worlds: int = Field(default=30, ge=1, le=80)
    prompt: str | None = None
    strategy_slots: list[str] = Field(default_factory=list)


class InventionBatch(BaseModel):
    id: str = Field(default_factory=lambda: f"IB-{uuid4().hex[:10]}")
    campaign_id: str
    problem_statement: str
    mode: InventionMode = "wild"
    wildness: InventionWildness = "high"
    requested_worlds: int = 30
    prompt: str | None = None
    strategy_slots: list[str] = Field(default_factory=list)
    status: InventionBatchStatus = "generated"
    raw_world_ids: list[str] = Field(default_factory=list)
    distilled_world_ids: list[str] = Field(default_factory=list)
    selected_world_ids: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utc_now)


class RawWorldInvention(BaseModel):
    id: str = Field(default_factory=lambda: f"RW-{uuid4().hex[:10]}")
    batch_id: str
    campaign_id: str
    label: str
    raw_text: str
    new_objects: list[str] = Field(default_factory=list)
    thesis: str
    bridge_to_target: str
    cheap_predictions: list[str] = Field(default_factory=list)
    likely_falsifiers: list[str] = Field(default_factory=list)
    proof_debt_sketch: list[str] = Field(default_factory=list)
    novelty_rationale: str
    source_model: str = "deterministic"
    temperature: float | None = None
    wildness: InventionWildness = "high"
    created_at: datetime = Field(default_factory=_utc_now)


class FormalDefinition(BaseModel):
    id: str = Field(default_factory=lambda: f"DEF-{uuid4().hex[:8]}")
    world_id: str
    name: str
    natural_language: str
    lean_stub: str | None = None
    status: Literal["draft", "formalized", "blocked"] = "draft"


class DistilledWorld(BaseModel):
    id: str = Field(default_factory=lambda: f"DW-{uuid4().hex[:10]}")
    batch_id: str
    raw_world_id: str
    campaign_id: str
    world_program: WorldProgram
    definitions: list[FormalDefinition] = Field(default_factory=list)
    falsifiable_predictions: list[str] = Field(default_factory=list)
    proof_debt: list[ProofDebtItem] = Field(default_factory=list)
    novelty_score: float = Field(default=0.5, ge=0.0, le=1.0)
    plausibility_score: float = Field(default=0.5, ge=0.0, le=1.0)
    bridge_score: float = Field(default=0.5, ge=0.0, le=1.0)
    status: DistilledWorldStatus = "candidate"
    notes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utc_now)


class WorldFalsifierResult(BaseModel):
    id: str = Field(default_factory=lambda: f"FR-{uuid4().hex[:10]}")
    batch_id: str
    distilled_world_id: str
    campaign_id: str
    status: FalsifierStatus
    falsifier_type: str
    summary: str
    counterexamples: list[str] = Field(default_factory=list)
    pattern: str | None = None
    artifacts: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utc_now)


class BakeAttempt(BaseModel):
    id: str = Field(default_factory=lambda: f"BA-{uuid4().hex[:10]}")
    campaign_id: str
    distilled_world_id: str
    debt_id: str
    channel: Literal["aristotle", "evidence", "human"] = "aristotle"
    status: BakeAttemptStatus
    failure_type: str | None = None
    lean_code: str | None = None
    aristotle_project_id: str | None = None
    notes: str
    artifacts: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utc_now)


class PromoteWorldRequest(BaseModel):
    distilled_world_id: str


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
    # New world-oriented fields
    current_world_program: dict[str, Any] | None = None
    alternative_world_programs: list[dict[str, Any]] = Field(default_factory=list)
    proof_debt_ledger: list[dict[str, Any]] = Field(default_factory=list)
    resolved_debt_ids: list[str] = Field(default_factory=list)
    active_world_id: str | None = None


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
