from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import requests
from pydantic import ValidationError

from .config import Settings
from .frontier import choose_frontier_node
from .schemas import (
    Alternative,
    CandidateAnswer,
    FrontierNode,
    InterfaceDescription,
    ManagerContext,
    ManagerDecision,
    SelfImprovementNote,
    UpdateRules,
)

logger = logging.getLogger(__name__)


@lru_cache(maxsize=4)
def load_root_file(filename: str) -> str:
    return _resolve_root_file(filename).read_text()


def _resolve_root_file(filename: str) -> Path:
    # Try current directory first, then one level up
    search_paths = [Path(filename), Path("..") / filename]
    for path in search_paths:
        if path.exists():
            return path
    raise FileNotFoundError(f"Required root file missing: {filename}")


def get_constitution() -> str:
    return load_root_file("MANAGER_CONSTITUTION.md")


def get_policy() -> dict[str, Any]:
    # Read policy fresh each call so on-disk updates are visible without restart.
    return json.loads(_resolve_root_file("MANAGER_POLICY.json").read_text())


def get_decision_schema() -> dict[str, Any]:
    return json.loads(load_root_file("MANAGER_DECISION_SCHEMA.json"))


def get_self_improvement_prompt() -> str:
    return load_root_file("SELF_IMPROVEMENT_PROMPT.md")


class Manager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.policy_provider = None
        # Warm the cache and fail early if missing
        try:
            get_constitution()
            get_policy()
            get_decision_schema()
            get_self_improvement_prompt()
        except FileNotFoundError as e:
            logger.error(f"Startup error: {e}")
            raise RuntimeError(f"Manager bootstrap failed: {e}") from e

    def describe_interfaces(self) -> InterfaceDescription:
        return InterfaceDescription(
            constitution=get_constitution(),
            manager_context_schema=ManagerContext.model_json_schema(),
            manager_decision_schema=get_decision_schema(),
            execution_result_schema={
                "$ref": "ExecutionResult",
                "schema": {
                    "status": "proved|refuted|blocked|inconclusive",
                    "failure_type": "optional string",
                    "notes": "string",
                    "artifacts": ["string"],
                    "spawned_nodes": ["FrontierNode"],
                    "channel_used": "aristotle_proof|computational_evidence|none",
                    "approved_jobs_count": "int",
                    "rejected_jobs_count": "int",
                },
            },
        )

    def decide(self, context: ManagerContext) -> ManagerDecision:
        active_policy = None
        if callable(self.policy_provider):
            active_policy = self.policy_provider()
        active_policy = active_policy or get_policy()

        if self.settings.manager_backend_resolved == "llm":
            try:
                return self._decide_with_llm(context, active_policy)
            except Exception as e:
                logger.error(f"LLM decision failed, falling back to rules: {e}")
                return self._decide_with_rules(context, active_policy, manager_backend="rules_fallback")
        return self._decide_with_rules(context, active_policy, manager_backend="rules")

    def _decide_with_rules(
        self,
        context: ManagerContext,
        policy: dict[str, Any],
        manager_backend: str,
    ) -> ManagerDecision:
        target = choose_frontier_node(context.frontier)
        if target is None:
            raise ValueError("No frontier node available")

        world_family = self._pick_world(context, target, policy)
        
        # Simple deterministic fallback matching the updated schema
        return ManagerDecision(
            candidate_answer=CandidateAnswer(
                stance="undecided",
                summary="Heuristically proceeding with formal exploration.",
                confidence=0.1,
            ),
            alternatives=[],
            target_frontier_node=target.id,
            world_family=world_family,
            bounded_claim=f"Local reduction check for node {target.id}: isolate one lemma that shrinks proof debt.",
            formal_obligations=[f"Prove one local lemma that reduces `{target.text[:80]}` to a narrower sub-claim."],
            expected_information_gain="Fast signal from one bounded lemma with low verification cost.",
            why_this_next=f"Deterministic low-cost selection of {world_family} for node {target.id}.",
            update_rules=UpdateRules(
                if_proved="Close node.",
                if_refuted="Refute branch.",
                if_blocked="Split or clarify.",
                if_inconclusive="Try different world family or broaden search."
            ),
            self_improvement_note=SelfImprovementNote(
                proposal="None",
                reason="Rule-based fallback used."
            ),
            manager_backend=manager_backend,
        )

    def _pick_world(self, context: ManagerContext, target: FrontierNode, policy: dict[str, Any]) -> str:
        ranked = []
        priors = policy.get("world_family_priors", {})
        for world in context.allowed_world_families:
            penalty_key = f"{target.id}:{world}"
            penalty = context.memory.retry_penalties.get(penalty_key, 0) * 0.3
            score = priors.get(world, context.memory.world_scores.get(world, 0.0)) - penalty
            if target.status == "blocked" and world in {"bridge", "reformulate"}:
                score += 0.2
            ranked.append((score, world))
        ranked.sort(reverse=True)
        return ranked[0][1] if ranked else "direct"

    def _decide_with_llm(self, context: ManagerContext, policy: dict[str, Any]) -> ManagerDecision:
        system_prompt = f"{get_constitution()}\n\nCURRENT POLICY:\n{json.dumps(policy, indent=2)}"
        guardrails = self._runtime_guardrails(policy)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Return a JSON object matching the ManagerDecision schema.\n\n"
                    f"Decision Schema:\n{json.dumps(get_decision_schema(), indent=2)}\n\n"
                    f"Runtime and channel guardrails:\n{guardrails}\n\n"
                    f"Context:\n{context.model_dump_json(indent=2)}"
                ),
            },
        ]

        try:
            decision = self._call_llm_and_parse(messages)
            return self._normalize_decision(decision, policy)
        except (ValidationError, json.JSONDecodeError) as e:
            logger.warning(f"Initial LLM response failed validation: {e}. Attempting repair pass.")
            repair_messages = messages + [
                {"role": "assistant", "content": "Checking and fixing schema errors..."},
                {"role": "user", "content": f"The previous response failed validation with error: {e}. Please fix the JSON and return it strictly according to the schema."}
            ]
            try:
                decision = self._call_llm_and_parse(repair_messages)
                return self._normalize_decision(decision, policy)
            except Exception as fatal_e:
                logger.error(f"Repair pass failed: {fatal_e}")
                raise

    def _call_llm_and_parse(self, messages: list[dict[str, str]]) -> ManagerDecision:
        payload = {
            "model": self.settings.llm_model,
            "temperature": self.settings.llm_temperature,
            "messages": messages,
        }
        response = requests.post(
            self.settings.llm_base_url.rstrip("/") + "/chat/completions",
            headers={
                "Authorization": f"Bearer {self.settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        parsed = _extract_json(content)
        decision = ManagerDecision.model_validate(parsed)
        decision.manager_backend = "llm"
        return decision

    @staticmethod
    def _runtime_guardrails(policy: dict[str, Any]) -> str:
        limits = policy.get("complexity_limits", {})
        max_formal = limits.get("max_formal_obligations_per_cycle", 4)
        max_proof = limits.get("max_proof_obligations_per_step", 1)
        return (
            f"- Optimize for information gain per expected verification cost.\n"
            f"- Prefer local lemmas, reduction checks, and bounded sanity checks.\n"
            f"- Do not mix broad finite computation jobs with proof jobs in one obligation.\n"
            f"- Avoid global unbounded 'for all integers' obligations as default moves.\n"
            f"- Emit <= {max_formal} total obligations and assume only {max_proof} proof obligation can run this step.\n"
            f"- After timeout/scope failures, shrink scope instead of rebundling."
        )

    @staticmethod
    def _normalize_decision(decision: ManagerDecision, policy: dict[str, Any]) -> ManagerDecision:
        max_formal = int(policy.get("complexity_limits", {}).get("max_formal_obligations_per_cycle", 4))
        if len(decision.formal_obligations) > max_formal:
            decision.formal_obligations = decision.formal_obligations[:max_formal]
        if not decision.formal_obligations:
            decision.formal_obligations = [f"Prove a local lemma for: {decision.bounded_claim[:100]}"]
        return decision


def _extract_json(content: str) -> dict[str, Any]:
    content = content.strip()
    # Find the outermost { }
    match = re.search(r"(\{.*\})", content, re.DOTALL)
    if match:
        content = match.group(1)
    else:
        # Fallback if no clean JSON object is found
        return json.loads(content)
    
    return json.loads(content)
