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
        self._active_llm_context: ManagerContext | None = None
        self._active_llm_policy: dict[str, Any] | None = None
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
        decision = ManagerDecision(
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
        return self._normalize_decision(decision, policy, context)
    
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
            audit_status="fallback",
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
        formalization_guide = self._formalization_requirements()
        
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
                    "3. Define the world's ontology with ontology_definitions, not only prose labels\n"
                    "4. For the world, explain bridge_to_target and link it to bridge proof debt where possible\n"
                    "5. Compile the world into explicit proof_debt items and reduction_certificate debt IDs\n"
                    "6. Choose the critical_next_debt_id from that debt\n"
                    "7. Derive bounded_claim and formal_obligations from that debt item\n\n"
                    "WORLD CONTINUITY:\n"
                    "If current_world_program is present, continue it by default. Set world_transition='continue' or 'repair'.\n"
                    "Only set world_transition='retire' or 'replace' with a concrete world_transition_reason when falsifiers, repeated bridge/scaffold failure, or operator override justify changing worlds.\n"
                    "Reuse the existing world ID for ordinary repair work, update proof debt based on progress, and choose the next critical debt item.\n\n"
                    "World modes:\n"
                    "- macro: new ontology/invariant/local-to-global view; include ontology_definitions\n"
                    "- micro: small theorem perturbation near the target; include theorem_deltas\n\n"
                    "Proof debt roles:\n"
                    "- closure: items that close the world's reduction\n"
                    "- bridge: items that connect world back to target\n"
                    "- support: supporting lemmas\n"
                    "- boundary: boundary checks\n"
                    "- falsifier: ways the world could fail\n\n"
                    f"{formalization_guide}\n\n"
                    f"Decision Schema:\n{json.dumps(get_decision_schema(), indent=2)}\n\n"
                    f"Runtime and channel guardrails:\n{guardrails}\n\n"
                    f"Context:\n{context.model_dump_json(indent=2)}"
                ),
            },
        ]

        try:
            self._active_llm_context = context
            self._active_llm_policy = policy
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
        finally:
            self._active_llm_context = None
            self._active_llm_policy = None

    def _call_llm_and_parse(self, messages: list[dict[str, str]]) -> ManagerDecision:
        payload = {
            "model": self.settings.llm_model,
            "temperature": self.settings.llm_temperature,
            "messages": messages,
            "response_format": {"type": "json_object"},
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
        if self._active_llm_context is None or self._active_llm_policy is None:
            raise RuntimeError("LLM parsing called without active context")
        decision = self._coerce_llm_payload(parsed, self._active_llm_context, self._active_llm_policy)
        decision.manager_backend = "llm"
        return decision

    def _coerce_llm_payload(
        self,
        payload: dict[str, Any],
        context: ManagerContext,
        policy: dict[str, Any],
    ) -> ManagerDecision:
        if not isinstance(payload, dict):
            raise ValidationError.from_exception_data(
                "ManagerDecision",
                [{"type": "model_type", "loc": (), "msg": "LLM payload must be an object", "input": payload}],
            )

        target = choose_frontier_node(context.frontier)
        if target is None:
            raise ValueError("No frontier node available")

        target_id = payload.get("target_frontier_node") or target.id
        target_node = next((node for node in context.frontier if node.id == target_id), target)
        world_family = payload.get("world_family")
        if world_family not in context.allowed_world_families:
            world_family = self._pick_world(context, target_node, policy)

        candidate_answer = payload.get("candidate_answer")
        if not isinstance(candidate_answer, dict):
            candidate_answer = {
                "stance": "undecided",
                "summary": payload.get("global_thesis") or "Heuristically proceeding with formal exploration.",
                "confidence": 0.1,
            }

        update_rules = payload.get("update_rules")
        if not isinstance(update_rules, dict):
            update_rules = {
                "if_proved": "Close node.",
                "if_refuted": "Refute branch.",
                "if_blocked": "Split or clarify.",
                "if_inconclusive": "Try different world family or broaden search.",
            }

        self_improvement_note = payload.get("self_improvement_note")
        if not isinstance(self_improvement_note, dict):
            self_improvement_note = {
                "proposal": "None",
                "reason": "LLM response omitted a self-improvement note.",
            }

        read_receipt_payload = payload.get("manager_read_receipt")
        if isinstance(read_receipt_payload, dict):
            read_receipt_payload = {
                **self._build_read_receipt_from_context(context, target_node).model_dump(),
                **read_receipt_payload,
                "target_node_id_confirmed": read_receipt_payload.get("target_node_id_confirmed") or target_node.id,
                "target_node_text_confirmed": read_receipt_payload.get("target_node_text_confirmed") or target_node.text,
            }
        else:
            read_receipt_payload = self._build_read_receipt_from_context(context, target_node).model_dump()

        bounded_claim = payload.get("bounded_claim")
        if not isinstance(bounded_claim, str) or not bounded_claim.strip():
            bounded_claim = (
                f"Local reduction check for node {target_node.id}: "
                "isolate one lemma that shrinks proof debt."
            )

        formal_obligations = payload.get("formal_obligations")
        if not isinstance(formal_obligations, list) or not formal_obligations:
            formal_obligations = [f"Prove a local lemma for: {bounded_claim[:100]}"]

        normalized_payload = {
            "candidate_answer": candidate_answer,
            "alternatives": payload.get("alternatives", []),
            "target_frontier_node": target_node.id,
            "world_family": world_family,
            "bounded_claim": bounded_claim,
            "formal_obligations": formal_obligations,
            "expected_information_gain": payload.get("expected_information_gain")
            or "Fast signal from one bounded lemma with low verification cost.",
            "why_this_next": payload.get("why_this_next")
            or f"Selected {world_family} for node {target_node.id}.",
            "update_rules": update_rules,
            "self_improvement_note": self_improvement_note,
            "manager_read_receipt": read_receipt_payload,
            "obligation_hints": payload.get("obligation_hints", {}),
            "manager_backend": "llm",
            "global_thesis": payload.get("global_thesis"),
            "primary_world": payload.get("primary_world"),
            "alternative_worlds": payload.get("alternative_worlds", []),
            "proof_debt": payload.get("proof_debt", []),
            "critical_next_debt_id": payload.get("critical_next_debt_id"),
        }
        return ManagerDecision.model_validate(normalized_payload)

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
    def _formalization_requirements() -> str:
        """Return critical formalization requirements for the Manager."""
        return (
            "FORMALIZATION REQUIREMENTS (CRITICAL):\n"
            "Aristotle requires structured formal obligations. Natural language alone will FAIL.\n\n"
            "For PROOF obligations, you MUST provide:\n"
            "- 'statement': Valid Lean syntax with explicit types and quantifiers\n"
            "  Example: \"∀ n : ℕ, n > 2 → n^2 > 2*n\"\n"
            "- OR 'lean_declaration': Complete Lean code\n\n"
            "Highly recommended fields:\n"
            "- 'goal_kind': \"theorem\", \"lemma\", \"sanity_check\", etc.\n"
            "- 'theorem_name': Valid Lean identifier (e.g., \"n_squared_gt_2n\")\n"
            "- 'channel_hint': \"proof\" for Aristotle, \"evidence\" for computation\n"
            "- 'requires_proof': true for proof obligations\n\n"
            "Valuable context fields:\n"
            "- 'imports': Lean imports needed (e.g., [\"Mathlib.Data.Nat.Basic\"])\n"
            "- 'variables': Variable declarations (e.g., [\"(n : ℕ)\"])\n"
            "- 'assumptions': Hypotheses (e.g., [\"n > 2\"])\n"
            "- 'tactic_hints': Specific tactics that might help\n"
            "- 'bounded_domain_description': Domain constraints\n"
            "- 'metadata': Link to proof debt, world program\n\n"
            "Example well-formed obligation:\n"
            "{\n"
            "  \"source_text\": \"Prove n^2 > 2n for n > 2\",\n"
            "  \"goal_kind\": \"theorem\",\n"
            "  \"theorem_name\": \"n_squared_gt_2n\",\n"
            "  \"statement\": \"∀ n : ℕ, n > 2 → n^2 > 2*n\",\n"
            "  \"tactic_hints\": [\"Use induction on n\"],\n"
            "  \"channel_hint\": \"proof\",\n"
            "  \"requires_proof\": true\n"
            "}\n\n"
            "See docs/notes/MANAGER_FORMALIZATION_GUIDE.md for complete examples."
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
                    audit_status="fallback",
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
        
        # Cap proof debt length before hardening; hardening may add mandatory
        # bridge/soundness debt that should not be truncated away.
        if len(decision.proof_debt) > 8:
            decision.proof_debt = decision.proof_debt[:8]

        if decision.primary_world:
            decision.primary_world = Manager._harden_world_program(decision)
        
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

    @staticmethod
    def _harden_world_program(decision: ManagerDecision):
        """Link world structure to proof debt so worlds remain auditable."""
        from .schemas import (
            BridgePlan,
            FormalObligationSpec,
            ProofDebtItem,
            ReductionCertificate,
            SoundnessCertificate,
            WorldObjectDefinition,
            WorldProgram,
        )

        world = decision.primary_world
        if world is None:
            return world

        if world.ontology and not world.ontology_definitions:
            world.ontology_definitions = [
                WorldObjectDefinition(
                    name=name,
                    natural_language=f"Define `{name}` precisely inside world `{world.label}`.",
                )
                for name in world.ontology
            ]

        if world.bridge_to_target is None:
            world.bridge_to_target = BridgePlan(
                bridge_claim="Prove that discharged world proof debt implies the target claim.",
                estimated_cost=0.5,
            )

        bridge_debt = [d for d in decision.proof_debt if d.role == "bridge"]
        closure_debt = [d for d in decision.proof_debt if d.role == "closure"]
        support_debt = [d for d in decision.proof_debt if d.role == "support"]
        boundary_debt = [d for d in decision.proof_debt if d.role == "boundary"]
        falsifier_debt = [d for d in decision.proof_debt if d.role == "falsifier"]
        soundness_debt = [
            d
            for d in decision.proof_debt
            if d.role == "bridge" and d.debt_class == "pullback_to_original"
        ]

        if world.soundness_certificate is None:
            target_claim = world.bridge_to_target.bridge_claim if world.bridge_to_target else decision.bounded_claim
            world.soundness_certificate = SoundnessCertificate(
                source_world_statement=world.thesis,
                target_statement=target_claim,
                interpretation_claim=(
                    "Interpret every invented world object and theorem statement back "
                    "in the original target domain."
                ),
            )

        if not soundness_debt:
            depends_on = [d.id for d in bridge_debt if d.status != "proved"]
            transfer_debt = ProofDebtItem(
                world_id=world.id,
                role="bridge",
                debt_class="pullback_to_original",
                statement=(
                    f"Prove soundness transfer for `{world.label}`: the world thesis "
                    f"and bridge obligations imply the original target claim."
                ),
                assigned_channel="aristotle",
                expected_difficulty=0.85,
                depends_on=depends_on,
                critical=True,
                status="open",
                priority=0.98,
                notes=["Mandatory soundness debt; internal world closure is not enough."],
            )
            decision.proof_debt.append(transfer_debt)
            soundness_debt = [transfer_debt]
            bridge_debt = [*bridge_debt, transfer_debt]

        if bridge_debt and not world.bridge_to_target.bridge_debt_ids:
            world.bridge_to_target.bridge_debt_ids = [d.id for d in bridge_debt]
        if bridge_debt and not world.bridge_to_target.bridge_obligations:
            world.bridge_to_target.bridge_obligations = [d.statement for d in bridge_debt]
        if bridge_debt and not world.bridge_to_target.bridge_formal_obligations:
            world.bridge_to_target.bridge_formal_obligations = [
                FormalObligationSpec.from_debt_item(d)
                for d in bridge_debt
                if d.formal_statement or d.lean_declaration
            ]

        if world.reduction_certificate is None:
            world.reduction_certificate = ReductionCertificate(total_debt_count=len(decision.proof_debt))

        rc = world.reduction_certificate
        if closure_debt and not rc.closure_debt_ids:
            rc.closure_debt_ids = [d.id for d in closure_debt]
        if bridge_debt and not rc.bridge_debt_ids:
            rc.bridge_debt_ids = [d.id for d in bridge_debt]
        if support_debt and not rc.support_debt_ids:
            rc.support_debt_ids = [d.id for d in support_debt]
        if boundary_debt and not rc.boundary_debt_ids:
            rc.boundary_debt_ids = [d.id for d in boundary_debt]
        if falsifier_debt and not rc.falsifier_debt_ids:
            rc.falsifier_debt_ids = [d.id for d in falsifier_debt]
        if rc.total_debt_count < len(decision.proof_debt):
            rc.total_debt_count = len(decision.proof_debt)

        sc = world.soundness_certificate
        if sc:
            existing_ids = set(sc.soundness_debt_ids)
            for debt in soundness_debt:
                if debt.id not in existing_ids:
                    sc.soundness_debt_ids.append(debt.id)
                    existing_ids.add(debt.id)
                if debt.statement not in sc.soundness_obligations:
                    sc.soundness_obligations.append(debt.statement)
            if not sc.soundness_formal_obligations:
                sc.soundness_formal_obligations = [
                    FormalObligationSpec.from_debt_item(d)
                    for d in soundness_debt
                    if d.formal_statement or d.lean_declaration
                ]
            soundness_statuses = [d.status for d in soundness_debt]
            if soundness_statuses and all(status == "proved" for status in soundness_statuses):
                sc.status = "proved"
            elif any(status == "blocked" for status in soundness_statuses):
                sc.status = "blocked"
            elif any(status == "proved" for status in soundness_statuses):
                sc.status = "partially_proved"

        if not world.falsifiers:
            falsifier_text = [d.statement for d in [*boundary_debt, *falsifier_debt]]
            if falsifier_text:
                world.falsifiers = falsifier_text

        return WorldProgram.model_validate(world.model_dump())

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
    if content.startswith("```"):
        fence_match = re.search(r"```(?:json)?\s*(.*?)```", content, re.DOTALL)
        if fence_match:
            content = fence_match.group(1).strip()

    decoder = json.JSONDecoder()
    candidate_offsets = [idx for idx, char in enumerate(content) if char == "{"] or [0]
    last_error: json.JSONDecodeError | None = None

    for offset in candidate_offsets:
        snippet = content[offset:].lstrip()
        if not snippet.startswith("{"):
            continue
        try:
            parsed, _end = decoder.raw_decode(snippet)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if isinstance(parsed, dict):
            return parsed

    if last_error is not None:
        raise last_error
    return json.loads(content)
