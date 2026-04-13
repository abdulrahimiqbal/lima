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
    ManagerReadReceipt,
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
        
        # Build deterministic read receipt for rules mode
        read_receipt = self._build_read_receipt_from_context(context, target)
        
        # Try to reuse existing world program for continuity
        existing_world = self._load_existing_world_from_context(context)
        existing_debt = self._load_existing_open_debt_from_context(context)
        
        if existing_world and existing_debt:
            # Reuse existing world and debt for continuity
            primary_world = existing_world
            proof_debt = existing_debt
            
            # Choose critical_next_debt_id from highest-priority open critical debt
            critical_open = [d for d in proof_debt if d.critical and d.status == "open"]
            if critical_open:
                next_debt = max(critical_open, key=lambda d: d.priority)
                critical_next_debt_id = next_debt.id
                bounded_claim = next_debt.statement
            else:
                open_debt = [d for d in proof_debt if d.status == "open"]
                if open_debt:
                    next_debt = max(open_debt, key=lambda d: d.priority)
                    critical_next_debt_id = next_debt.id
                    bounded_claim = next_debt.statement
                else:
                    critical_next_debt_id = None
                    bounded_claim = f"Continue work on: {target.text[:80]}"
        else:
            # Synthesize a default world program for rules mode
            primary_world = self._synthesize_default_world(target, world_family, context)
            proof_debt = self._synthesize_default_debt(primary_world, target)
            critical_next_debt_id = proof_debt[0].id if proof_debt else None
            bounded_claim = f"Local reduction check for node {target.id}: isolate one lemma that shrinks proof debt."
        
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
            bounded_claim=bounded_claim,
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
            manager_read_receipt=read_receipt,
            manager_backend=manager_backend,
            global_thesis=f"Seek local reduction for {target.text[:60]}",
            primary_world=primary_world,
            proof_debt=proof_debt,
            critical_next_debt_id=critical_next_debt_id,
        )
    
    def _load_existing_world_from_context(self, context: ManagerContext) -> "WorldProgram | None":
        """Load existing world program from context for continuity."""
        world_dict = context.problem.get("current_world_program")
        if not world_dict:
            return None
        
        try:
            from .schemas import WorldProgram
            return WorldProgram.model_validate(world_dict)
        except Exception:
            return None
    
    def _load_existing_open_debt_from_context(self, context: ManagerContext) -> "list[ProofDebtItem]":
        """Load existing open debt items from context for continuity."""
        ledger = context.problem.get("proof_debt_ledger", [])
        if not ledger:
            return []
        
        try:
            from .schemas import ProofDebtItem
            debt_items = []
            for debt_dict in ledger:
                if debt_dict.get("status") in {"open", "active"}:
                    debt_items.append(ProofDebtItem.model_validate(debt_dict))
            return debt_items
        except Exception:
            return []
    
    def _synthesize_default_world(
        self, target: FrontierNode, world_family: str, context: ManagerContext
    ) -> "WorldProgram":
        """Synthesize a minimal default world program for rules mode."""
        from .schemas import WorldProgram, BridgePlan, ReductionCertificate, CompressionPrinciple
        
        return WorldProgram(
            label=f"Default {world_family} world for {target.id}",
            family_tags=[world_family],  # type: ignore[list-item]
            mode="micro",
            thesis=f"Seek one local lemma that reduces proof debt for: {target.text[:100]}",
            ontology=[],
            compression_principles=[
                CompressionPrinciple(
                    name="local_reduction",
                    description="Reduce the target to a smaller sub-claim"
                )
            ],
            bridge_to_target=BridgePlan(
                bridge_claim="If enough local reductions close, the parent claim closes.",
                bridge_obligations=[],
                estimated_cost=0.3,
            ),
            reduction_certificate=ReductionCertificate(
                closure_items=[],
                bridge_items=[],
                support_items=[target.text],
                total_debt_count=1,
            ),
            theorem_deltas=[],
            falsifiers=[],
        )
    
    def _synthesize_default_debt(
        self, world: "WorldProgram", target: FrontierNode
    ) -> list["ProofDebtItem"]:
        """Synthesize default proof debt from target."""
        from .schemas import ProofDebtItem
        
        return [
            ProofDebtItem(
                world_id=world.id,
                role="support",
                statement=f"Prove one local lemma for: {target.text[:100]}",
                depends_on=[],
                critical=True,
                status="open",
                priority=1.0,
                notes=["Synthesized from target in rules mode"],
            )
        ]

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
                    "IMPORTANT: You MUST include a 'manager_read_receipt' field that proves you read and understood the context.\n"
                    "The read receipt must include:\n"
                    "- problem_summary: Brief summary of the problem statement\n"
                    "- candidate_answer_seen: Current candidate answer if present\n"
                    "- target_node_id_confirmed: The frontier node ID you selected\n"
                    "- target_node_text_confirmed: The text of that node\n"
                    "- operator_notes_seen: List of operator notes you considered\n"
                    "- relevant_memory_seen: Dict with blocked_patterns, useful_lemmas, recent_failures\n"
                    "- constraints_seen: Runtime constraints you're following\n"
                    "- open_uncertainties: Any uncertainties you have\n"
                    "- why_not_other_frontier_nodes: Why you chose this node over others\n\n"
                    "WORLD-ORIENTED DECISION REQUIREMENTS:\n"
                    "You should think top-down and construct a world-oriented plan:\n"
                    "1. Form a global_thesis about the problem\n"
                    "2. Propose a primary_world (macro or micro) that makes the problem easier\n"
                    "3. For the world, explain the bridge_to_target\n"
                    "4. Compile the world into explicit proof_debt items\n"
                    "5. Choose the critical_next_debt_id from that debt\n"
                    "6. Derive bounded_claim and formal_obligations from that debt item\n\n"
                    "WORLD CONTINUITY:\n"
                    "If current_world_program is present and not structurally broken, continue it rather than inventing a fresh world.\n"
                    "Reuse the existing world ID, update proof debt based on progress, and choose the next critical debt item.\n\n"
                    "World modes:\n"
                    "- macro: new ontology/invariant/local-to-global view\n"
                    "- micro: small theorem perturbation near the target\n\n"
                    "Proof debt roles:\n"
                    "- closure: items that close the world's reduction\n"
                    "- bridge: items that connect world back to target\n"
                    "- support: supporting lemmas\n"
                    "- boundary: boundary checks\n"
                    "- falsifier: ways the world could fail\n\n"
                    f"Decision Schema:\n{json.dumps(get_decision_schema(), indent=2)}\n\n"
                    f"Runtime and channel guardrails:\n{guardrails}\n\n"
                    f"Context:\n{context.model_dump_json(indent=2)}"
                ),
            },
        ]

        try:
            decision = self._call_llm_and_parse(messages)
            return self._normalize_decision(decision, policy, context)
        except (ValidationError, json.JSONDecodeError) as e:
            logger.warning(f"Initial LLM response failed validation: {e}. Attempting repair pass.")
            repair_messages = messages + [
                {"role": "assistant", "content": "Checking and fixing schema errors..."},
                {"role": "user", "content": f"The previous response failed validation with error: {e}. Please fix the JSON and return it strictly according to the schema."}
            ]
            try:
                decision = self._call_llm_and_parse(repair_messages)
                return self._normalize_decision(decision, policy, context)
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
            f"- After timeout/scope failures, shrink scope instead of rebundling.\n"
            f"- When repeated bounded evidence has not improved the frontier, convert evidence patterns into formal lemmas.\n"
            f"- After formalization failures, state claims in clean Lean-compatible form.\n"
            f"- After proof failures, identify missing lemmas or split theorems into smaller pieces."
        )

    @staticmethod
    def _normalize_decision(decision: ManagerDecision, policy: dict[str, Any], context: ManagerContext | None = None) -> ManagerDecision:
        max_formal = int(policy.get("complexity_limits", {}).get("max_formal_obligations_per_cycle", 4))
        if len(decision.formal_obligations) > max_formal:
            decision.formal_obligations = decision.formal_obligations[:max_formal]
        if not decision.formal_obligations:
            decision.formal_obligations = [f"Prove a local lemma for: {decision.bounded_claim[:100]}"]
        
        # Normalize world program - prefer existing world from context if available
        if decision.primary_world is None:
            existing_world_dict = context.problem.get("current_world_program") if context else None
            if existing_world_dict:
                # Reuse existing world for continuity
                try:
                    from .schemas import WorldProgram
                    decision.primary_world = WorldProgram.model_validate(existing_world_dict)
                except Exception:
                    pass
            
            # If still no world, synthesize default
            if decision.primary_world is None:
                from .schemas import WorldProgram, BridgePlan, ReductionCertificate, CompressionPrinciple
                decision.primary_world = WorldProgram(
                    label=f"Default world for {decision.target_frontier_node}",
                    family_tags=[decision.world_family],  # type: ignore[list-item]
                    mode="micro",
                    thesis=decision.bounded_claim,
                    ontology=[],
                    compression_principles=[
                        CompressionPrinciple(
                            name="local_reduction",
                            description="Reduce target to smaller sub-claim"
                        )
                    ],
                    bridge_to_target=BridgePlan(
                        bridge_claim="If local obligations close, parent claim closes.",
                        bridge_obligations=[],
                        estimated_cost=0.3,
                    ),
                    reduction_certificate=ReductionCertificate(
                        closure_items=[],
                        bridge_items=[],
                        support_items=[decision.bounded_claim],
                        total_debt_count=1,
                    ),
                )
        
        # Apply theorem delta scoring if present
        if decision.primary_world and decision.primary_world.theorem_deltas:
            theorem_delta_priors = policy.get("theorem_delta_priors", {})
            bridge_cost_penalty = policy.get("bridge_cost_penalty", 0.15)
            proximity_bonus = policy.get("proximity_bonus", 0.20)
            
            scored_deltas = []
            for delta in decision.primary_world.theorem_deltas:
                score = (
                    theorem_delta_priors.get(delta.delta_type, 0.5)
                    + proximity_bonus * (1 - delta.distance_from_target)
                    + delta.estimated_proof_gain
                    - bridge_cost_penalty * delta.estimated_bridge_cost
                )
                scored_deltas.append((score, delta))
            
            # Sort by score descending
            scored_deltas.sort(key=lambda x: x[0], reverse=True)
            decision.primary_world.theorem_deltas = [delta for score, delta in scored_deltas]
        
        # Normalize proof debt
        if not decision.proof_debt and decision.primary_world:
            from .schemas import ProofDebtItem
            decision.proof_debt = [
                ProofDebtItem(
                    world_id=decision.primary_world.id,
                    role="support",
                    statement=decision.bounded_claim,
                    depends_on=[],
                    critical=True,
                    status="open",
                    priority=1.0,
                    notes=["Synthesized from bounded_claim"],
                )
            ]
        
        # Cap proof debt length
        if len(decision.proof_debt) > 8:
            decision.proof_debt = decision.proof_debt[:8]
        
        # Normalize critical_next_debt_id
        if decision.critical_next_debt_id is None and decision.proof_debt:
            # Choose highest-priority open critical item, else highest-priority open item
            critical_open = [d for d in decision.proof_debt if d.critical and d.status == "open"]
            if critical_open:
                decision.critical_next_debt_id = max(critical_open, key=lambda d: d.priority).id
            else:
                open_items = [d for d in decision.proof_debt if d.status == "open"]
                if open_items:
                    decision.critical_next_debt_id = max(open_items, key=lambda d: d.priority).id
        
        return decision

    def _build_read_receipt_from_context(
        self, context: ManagerContext, target: FrontierNode
    ) -> ManagerReadReceipt:
        """Build a read receipt from context and selected target for rules mode."""
        problem = context.problem or {}
        candidate_answer = problem.get("current_candidate_answer")
        candidate_seen = None
        if candidate_answer:
            stance = candidate_answer.get("stance", "undecided")
            summary = candidate_answer.get("summary", "")
            candidate_seen = f"{stance}: {summary[:100]}"
        
        # Extract relevant memory
        relevant_memory = {}
        if context.memory.blocked_patterns:
            relevant_memory["blocked_patterns"] = context.memory.blocked_patterns[:5]
        if context.memory.useful_lemmas:
            relevant_memory["useful_lemmas"] = context.memory.useful_lemmas[:5]
        if context.memory.recent_failures:
            relevant_memory["recent_failures"] = [
                f"{f.get('pattern', 'unknown')}: {f.get('reason', '')[:60]}"
                for f in context.memory.recent_failures[:3]
            ]
        
        # Extract constraints
        constraints = []
        if context.operator_notes:
            constraints.extend([f"Operator: {note[:80]}" for note in context.operator_notes[:3]])
        constraints.append("Prefer bounded local work")
        constraints.append("Avoid repeated blocked worlds")
        constraints.append("Max 1 proof job per step")
        
        # Count other frontier nodes
        other_nodes = [n for n in context.frontier if n.id != target.id and n.status == "open"]
        why_not_others = f"Selected {target.id} over {len(other_nodes)} other open nodes based on priority and status."
        
        return ManagerReadReceipt(
            problem_summary=problem.get("statement", "")[:200],
            candidate_answer_seen=candidate_seen,
            target_node_id_confirmed=target.id,
            target_node_text_confirmed=target.text[:200],
            operator_notes_seen=context.operator_notes[:5],
            relevant_memory_seen=relevant_memory,
            constraints_seen=constraints,
            open_uncertainties=[],
            why_not_other_frontier_nodes=why_not_others,
        )


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
