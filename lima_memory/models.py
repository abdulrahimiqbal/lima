from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

NodeType = Literal[
    "Campaign",
    "Problem",
    "CandidateAnswer",
    "FrontierNode",
    "WorldModel",
    "Claim",
    "FormalObligation",
    "ExecutionResult",
    "InventionBatch",
    "RawWorldInvention",
    "DistilledWorld",
    "WorldMutation",
    "Falsifier",
    "ProofDebtItem",
    "BakeAttempt",
    "FormalDefinition",
    "ReusableLemma",
    "DeadPattern",
    "ScoringRubric",
    "SelfImprovementPatch",
    "Blocker",
    "Pattern",
    "Paper",
    "PaperUnit",
    "Technique",
    "Artifact",
    "PolicyPatch",
]

EdgeType = Literal[
    "HAS_PROBLEM",
    "HAS_FRONTIER",
    "CURRENT_ANSWER",
    "TARGETS_FRONTIER",
    "PROPOSES_WORLD",
    "PROPOSES_CLAIM",
    "GENERATES_OBLIGATION",
    "EXECUTED_AS",
    "RETURNS_VERDICT",
    "SUPPORTS",
    "REFUTES",
    "BLOCKS",
    "SPAWNS",
    "INSPIRED_BY",
    "USES_TECHNIQUE",
    "DERIVED_FROM_PAPER",
    "DEPENDS_ON",
    "SIMILAR_TO",
    "INVENTED",
    "DISTILLED_TO",
    "MUTATED_FROM",
    "COMBINES_WITH",
    "HAS_PROOF_DEBT",
    "TESTED_BY",
    "FALSIFIED_BY",
    "PROVED_BY",
    "REPAIRS",
    "REUSES_DEFINITION",
    "GENERALIZES",
    "SPECIALIZES",
]

ArtifactType = Literal[
    "aristotle_request",
    "aristotle_response",
    "lean_input",
    "lean_output",
    "paper_pdf",
    "paper_unit",
    "manager_context",
    "manager_decision",
    "execution_result",
    "note",
]

StatusType = Literal[
    "speculative",
    "supported",
    "verified_local",
    "blocked",
    "refuted",
    "deprecated",
    "open",
    "active",
    "proved",
    "failed",
]

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def make_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"

@dataclass(slots=True)
class NodeRecord:
    id: str
    campaign_id: str
    node_type: str
    title: str
    summary: str = ""
    status: str = "speculative"
    confidence: float | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def asdict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(slots=True)
class EdgeRecord:
    id: str
    campaign_id: str
    src_id: str
    edge_type: str
    dst_id: str
    weight: float = 1.0
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)

    def asdict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(slots=True)
class EventRecord:
    id: str
    campaign_id: str
    tick: int
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)

    def asdict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(slots=True)
class ArtifactRecord:
    id: str
    campaign_id: str
    artifact_type: str
    title: str
    uri: str | None = None
    content_text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)

    def asdict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PolicySnapshotRecord:
    id: str
    version: str
    policy_json: str
    patch_json: str
    reason: str | None = None
    created_at: str = field(default_factory=now_iso)

    def asdict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(slots=True)
class ManagerPacket:
    campaign: dict[str, Any]
    problem: dict[str, Any]
    current_candidate_answer: dict[str, Any] | None
    active_frontier: list[dict[str, Any]]
    relevant_worlds: list[dict[str, Any]]
    recent_claims: list[dict[str, Any]]
    recent_results: list[dict[str, Any]]
    blockers: list[dict[str, Any]]
    paper_units: list[dict[str, Any]]
    patterns: list[dict[str, Any]]
    operator_notes: list[str] = field(default_factory=list)

    def asdict(self) -> dict[str, Any]:
        return asdict(self)
