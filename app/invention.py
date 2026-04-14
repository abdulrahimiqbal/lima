from __future__ import annotations

import json
import logging
from typing import Any

import requests

from lima_memory import MemoryService

from .config import Settings
from .manager import _extract_json
from .schemas import (
    BakeAttempt,
    BridgePlan,
    CampaignRecord,
    CompressionPrinciple,
    DistilledWorld,
    FormalDefinition,
    InventionBatch,
    InventionBatchCreate,
    MiracleObject,
    ProofDebtItem,
    RawWorldInvention,
    ReductionCertificate,
    SoundnessCertificate,
    WorldFalsifierResult,
    WorldObjectDefinition,
    WorldProgram,
)

logger = logging.getLogger(__name__)


DEFAULT_STRATEGY_SLOTS = [
    "alien_state_space_encoding",
    "parity_word_grammar",
    "residue_flow_conservation",
    "minimal_counterexample_world",
    "compressed_trajectory_dynamics",
    "inverse_tree_normal_form",
    "rewrite_system_termination",
    "two_adic_shadow_dynamics",
    "automaton_boundary_world",
    "bridge_from_unrelated_field",
]


class InventionService:
    """Wild mathematical world invention with conservative memory boundaries."""

    def __init__(self, memory: MemoryService, settings: Settings) -> None:
        self.memory = memory
        self.settings = settings

    def create_batch(
        self,
        campaign: CampaignRecord,
        payload: InventionBatchCreate,
        *,
        policy: dict[str, Any] | None = None,
    ) -> InventionBatch:
        policy = policy or {}
        invention_policy = policy.get("invention_policy", {})
        slots = (
            payload.strategy_slots
            or invention_policy.get("strategy_slots")
            or DEFAULT_STRATEGY_SLOTS
        )
        requested_worlds = payload.requested_worlds or int(
            invention_policy.get("default_batch_size", 30)
        )
        batch = InventionBatch(
            campaign_id=campaign.id,
            problem_statement=campaign.problem_statement,
            mode=payload.mode,
            wildness=payload.wildness,
            requested_worlds=requested_worlds,
            prompt=payload.prompt,
            strategy_slots=list(slots),
        )

        raw_worlds = self._generate_raw_worlds(campaign, batch)
        source_models = {world.source_model for world in raw_worlds}
        source = "deterministic"
        if any(model != "deterministic" for model in source_models):
            source = "mixed" if "deterministic" in source_models else "llm"
        batch.raw_world_ids = [world.id for world in raw_worlds]
        batch.metrics = {
            "raw_world_count": len(raw_worlds),
            "strategy_slot_count": len(batch.strategy_slots),
            "wildness": batch.wildness,
            "source": source,
        }

        self._record_batch(batch)
        self.memory.add_research_edge(
            campaign_id=campaign.id,
            src_id=campaign.id,
            edge_type="INVENTED",
            dst_id=batch.id,
        )
        for raw_world in raw_worlds:
            self._record_raw_world(raw_world)
            self.memory.add_research_edge(
                campaign_id=campaign.id,
                src_id=batch.id,
                edge_type="INVENTED",
                dst_id=raw_world.id,
            )

        self.memory.add_event(
            campaign_id=campaign.id,
            tick=campaign.tick_count,
            event_type="invention_batch_created",
            payload=batch.model_dump(mode="json"),
        )
        return batch

    def distill_batch(self, campaign: CampaignRecord, batch_id: str) -> list[DistilledWorld]:
        batch = self._load_batch(campaign.id, batch_id)
        raw_worlds = self._list_raw_worlds(campaign.id, batch_id)
        existing = {
            world.raw_world_id
            for world in self._list_distilled_worlds(campaign.id, batch_id)
        }

        distilled: list[DistilledWorld] = []
        for raw_world in raw_worlds:
            if raw_world.id in existing:
                continue
            distilled_world = self._distill_raw_world(raw_world)
            distilled.append(distilled_world)
            self._record_distilled_world(distilled_world)
            self.memory.add_research_edge(
                campaign_id=campaign.id,
                src_id=raw_world.id,
                edge_type="DISTILLED_TO",
                dst_id=distilled_world.id,
            )
            for definition in distilled_world.definitions:
                self._record_definition(definition, distilled_world)
            for debt in distilled_world.proof_debt:
                self._record_proof_debt(debt, distilled_world)

        all_distilled = self._list_distilled_worlds(campaign.id, batch_id)
        batch.status = "distilled"
        batch.distilled_world_ids = [world.id for world in all_distilled]
        batch.metrics = {
            **batch.metrics,
            "distilled_world_count": len(all_distilled),
            "average_novelty_score": _avg([world.novelty_score for world in all_distilled]),
            "average_bridge_score": _avg([world.bridge_score for world in all_distilled]),
        }
        self._record_batch(batch)
        self.memory.add_event(
            campaign_id=campaign.id,
            tick=campaign.tick_count,
            event_type="invention_batch_distilled",
            payload=batch.model_dump(mode="json"),
        )
        return all_distilled

    def falsify_batch(self, campaign: CampaignRecord, batch_id: str) -> list[WorldFalsifierResult]:
        batch = self._load_batch(campaign.id, batch_id)
        distilled_worlds = self._list_distilled_worlds(campaign.id, batch_id)
        existing_worlds = {
            result.distilled_world_id
            for result in self._list_falsifier_results(campaign.id, batch_id)
        }
        results: list[WorldFalsifierResult] = []

        for world in distilled_worlds:
            if world.id in existing_worlds:
                continue
            result = self._cheap_falsify(campaign, world)
            results.append(result)
            if result.status == "falsified":
                world.status = "falsified"
            elif result.status == "survived":
                world.status = "promising"
            else:
                world.status = "candidate"
            world.notes.append(result.summary)
            self._record_distilled_world(world)
            self._record_falsifier_result(result)

        all_results = self._list_falsifier_results(campaign.id, batch_id)
        all_distilled = self._list_distilled_worlds(campaign.id, batch_id)
        batch.status = "falsified"
        batch.selected_world_ids = [
            world.id for world in all_distilled if world.status in {"promising", "baking"}
        ]
        batch.metrics = {
            **batch.metrics,
            "falsifier_result_count": len(all_results),
            "promising_world_count": len(batch.selected_world_ids),
            "falsified_world_count": len(
                [result for result in all_results if result.status == "falsified"]
            ),
        }
        self._record_batch(batch)
        self.memory.add_event(
            campaign_id=campaign.id,
            tick=campaign.tick_count,
            event_type="invention_batch_falsified",
            payload=batch.model_dump(mode="json"),
        )
        return all_results

    def load_distilled_world(self, campaign_id: str, distilled_world_id: str) -> DistilledWorld:
        node = self.memory.get_research_node(campaign_id, distilled_world_id)
        if not node or node.node_type != "DistilledWorld":
            raise KeyError(f"Distilled world not found: {distilled_world_id}")
        return DistilledWorld.model_validate(node.payload)

    def promote_world(self, campaign: CampaignRecord, distilled_world_id: str) -> DistilledWorld:
        world = self.load_distilled_world(campaign.id, distilled_world_id)
        world.status = "baking"
        world.notes.append("Promoted into active campaign world for proof-debt baking.")
        self._record_distilled_world(world)
        self.memory.add_event(
            campaign_id=campaign.id,
            tick=campaign.tick_count,
            event_type="distilled_world_promoted",
            payload={
                "distilled_world_id": world.id,
                "world_id": world.world_program.id,
                "label": world.world_program.label,
                "proof_debt_count": len(world.proof_debt),
            },
        )
        return world

    def record_bake_attempt(self, attempt: BakeAttempt) -> BakeAttempt:
        self.memory.upsert_research_node(
            campaign_id=attempt.campaign_id,
            node_id=attempt.id,
            node_type="BakeAttempt",
            title=f"{attempt.status}:{attempt.debt_id}",
            summary=attempt.notes,
            status=attempt.status,
            payload=attempt.model_dump(mode="json"),
        )
        self.memory.add_research_edge(
            campaign_id=attempt.campaign_id,
            src_id=attempt.id,
            edge_type="TESTED_BY",
            dst_id=attempt.debt_id,
        )
        self.memory.add_event(
            campaign_id=attempt.campaign_id,
            tick=0,
            event_type="bake_attempt_recorded",
            payload=attempt.model_dump(mode="json"),
        )
        return attempt

    def get_lab(self, campaign_id: str) -> dict[str, Any]:
        batches = self.memory.list_research_nodes(
            campaign_id, node_type="InventionBatch", limit=50
        )
        raw_worlds = self.memory.list_research_nodes(
            campaign_id, node_type="RawWorldInvention", limit=200
        )
        distilled_worlds = self.memory.list_research_nodes(
            campaign_id, node_type="DistilledWorld", limit=200
        )
        falsifiers = self.memory.list_research_nodes(
            campaign_id, node_type="Falsifier", limit=200
        )
        proof_debt = self.memory.list_research_nodes(
            campaign_id, node_type="ProofDebtItem", limit=300
        )
        bake_attempts = self.memory.list_research_nodes(
            campaign_id, node_type="BakeAttempt", limit=200
        )
        promising = [
            node for node in distilled_worlds
            if (node.payload or {}).get("status") in {"promising", "baking"}
        ]
        dead_patterns = [
            (node.payload or {}).get("pattern")
            for node in falsifiers
            if (node.payload or {}).get("status") == "falsified"
        ]
        return {
            "summary": {
                "batch_count": len(batches),
                "raw_world_count": len(raw_worlds),
                "distilled_world_count": len(distilled_worlds),
                "promising_world_count": len(promising),
                "falsifier_count": len(falsifiers),
                "proof_debt_count": len(proof_debt),
                "bake_attempt_count": len(bake_attempts),
                "dead_pattern_count": len([p for p in dead_patterns if p]),
            },
            "batches": [node.asdict() for node in batches],
            "raw_worlds": [node.asdict() for node in raw_worlds],
            "distilled_worlds": [node.asdict() for node in distilled_worlds],
            "falsifiers": [node.asdict() for node in falsifiers],
            "proof_debt": [node.asdict() for node in proof_debt],
            "bake_attempts": [node.asdict() for node in bake_attempts],
            "dead_patterns": [pattern for pattern in dead_patterns if pattern],
        }

    def _generate_raw_worlds(
        self,
        campaign: CampaignRecord,
        batch: InventionBatch,
    ) -> list[RawWorldInvention]:
        if self.settings.llm_api_key and self.settings.manager_backend_resolved == "llm":
            try:
                llm_worlds = self._generate_raw_worlds_with_llm(campaign, batch)
                if llm_worlds:
                    llm_worlds = llm_worlds[: batch.requested_worlds]
                    if len(llm_worlds) >= batch.requested_worlds:
                        return llm_worlds
                    needed = batch.requested_worlds - len(llm_worlds)
                    fallback_worlds = self._generate_raw_worlds_deterministic(campaign, batch)
                    return [*llm_worlds, *fallback_worlds[:needed]]
            except Exception:
                logger.exception("Wild inventor LLM call failed; using deterministic fallback.")
        return self._generate_raw_worlds_deterministic(campaign, batch)

    def _generate_raw_worlds_with_llm(
        self,
        campaign: CampaignRecord,
        batch: InventionBatch,
    ) -> list[RawWorldInvention]:
        prompt = _inventor_prompt(campaign, batch)
        response = requests.post(
            self.settings.llm_base_url.rstrip("/") + "/chat/completions",
            headers={
                "Authorization": f"Bearer {self.settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.settings.llm_model,
                "temperature": 0.95 if batch.wildness == "extreme" else 0.75,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are Lima's wild mathematical inventor. "
                            "Invent unfamiliar mathematical worlds. Do not claim truth."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
            },
            timeout=self.settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = _extract_json(content)
        worlds_payload = parsed.get("worlds", [])
        worlds: list[RawWorldInvention] = []
        for item in worlds_payload:
            if not isinstance(item, dict):
                continue
            miracle_object = item.get("miracle_object")
            if not isinstance(miracle_object, dict):
                miracle_object = None
            parsed_miracle_object = None
            if miracle_object:
                try:
                    parsed_miracle_object = MiracleObject.model_validate(miracle_object)
                except Exception:
                    parsed_miracle_object = None
            worlds.append(
                RawWorldInvention(
                    batch_id=batch.id,
                    campaign_id=campaign.id,
                    label=str(item.get("label") or "Unnamed invented world"),
                    raw_text=str(item.get("raw_text") or item.get("thesis") or ""),
                    new_objects=list(item.get("new_objects") or []),
                    thesis=str(item.get("thesis") or ""),
                    bridge_to_target=str(item.get("bridge_to_target") or ""),
                    cheap_predictions=list(item.get("cheap_predictions") or []),
                    likely_falsifiers=list(item.get("likely_falsifiers") or []),
                    proof_debt_sketch=list(item.get("proof_debt_sketch") or []),
                    novelty_rationale=str(item.get("novelty_rationale") or ""),
                    miracle_object=parsed_miracle_object,
                    hidden_circularity_risk=(
                        str(item.get("hidden_circularity_risk"))
                        if item.get("hidden_circularity_risk") is not None
                        else None
                    ),
                    definability_probe=(
                        str(item.get("definability_probe"))
                        if item.get("definability_probe") is not None
                        else None
                    ),
                    bridge_probe=(
                        str(item.get("bridge_probe"))
                        if item.get("bridge_probe") is not None
                        else None
                    ),
                    closure_probe=(
                        str(item.get("closure_probe"))
                        if item.get("closure_probe") is not None
                        else None
                    ),
                    source_model=self.settings.llm_model,
                    temperature=0.95 if batch.wildness == "extreme" else 0.75,
                    wildness=batch.wildness,
                )
            )
        return worlds

    def _generate_raw_worlds_deterministic(
        self,
        campaign: CampaignRecord,
        batch: InventionBatch,
    ) -> list[RawWorldInvention]:
        worlds: list[RawWorldInvention] = []
        slots = batch.strategy_slots or DEFAULT_STRATEGY_SLOTS
        for idx in range(batch.requested_worlds):
            slot = slots[idx % len(slots)]
            worlds.append(_template_world(campaign, batch, slot, idx))
        return worlds

    def _distill_raw_world(self, raw_world: RawWorldInvention) -> DistilledWorld:
        family = _family_for_label(raw_world.label)
        world_program = WorldProgram(
            label=raw_world.label,
            family_tags=[family],
            mode="macro" if raw_world.wildness in {"high", "extreme"} else "micro",
            thesis=raw_world.thesis,
            ontology=raw_world.new_objects,
            ontology_definitions=[
                WorldObjectDefinition(
                    name=obj,
                    natural_language=f"Define {obj} for world {raw_world.label}.",
                )
                for obj in raw_world.new_objects[:4]
            ],
            compression_principles=[
                CompressionPrinciple(
                    name="invented_compression",
                    description=raw_world.novelty_rationale,
                )
            ],
            bridge_to_target=BridgePlan(
                bridge_claim=raw_world.bridge_to_target,
                bridge_obligations=[
                    "Prove the invented world simulates the original target.",
                    "Prove the invented compression has a well-founded decreasing certificate.",
                ],
                estimated_cost=0.7,
            ),
            soundness_certificate=SoundnessCertificate(
                source_world_statement=raw_world.thesis,
                target_statement=raw_world.bridge_to_target,
                interpretation_claim=(
                    "Interpret the invented objects and closure theorem as a "
                    "statement over the original target domain."
                ),
                soundness_obligations=[
                    "Prove the interpretation preserves the original theorem statement.",
                    "Prove world closure transfers to the original target.",
                ],
            ),
            reduction_certificate=ReductionCertificate(
                closure_items=raw_world.proof_debt_sketch[:2],
                bridge_items=[raw_world.bridge_to_target],
                support_items=raw_world.new_objects[:3],
                total_debt_count=max(3, len(raw_world.proof_debt_sketch) + 2),
            ),
            falsifiers=raw_world.likely_falsifiers,
        )
        definitions = [
            FormalDefinition(
                world_id=world_program.id,
                name=_definition_name(obj),
                natural_language=f"Define {obj} for world {raw_world.label}.",
            )
            for obj in raw_world.new_objects[:4]
        ]
        proof_debt = _compile_debt(world_program, raw_world)
        soundness_debt = [d for d in proof_debt if d.debt_class == "pullback_to_original"]
        if world_program.soundness_certificate:
            world_program.soundness_certificate.soundness_debt_ids = [d.id for d in soundness_debt]
            world_program.soundness_certificate.soundness_obligations.extend(
                d.statement
                for d in soundness_debt
                if d.statement not in world_program.soundness_certificate.soundness_obligations
            )
        return DistilledWorld(
            batch_id=raw_world.batch_id,
            raw_world_id=raw_world.id,
            campaign_id=raw_world.campaign_id,
            world_program=world_program,
            definitions=definitions,
            falsifiable_predictions=raw_world.cheap_predictions,
            proof_debt=proof_debt,
            novelty_score=_score_novelty(raw_world),
            plausibility_score=_score_plausibility(raw_world),
            bridge_score=_score_bridge(raw_world),
            miracle_object=raw_world.miracle_object
            or MiracleObject(
                name=raw_world.new_objects[0] if raw_world.new_objects else raw_world.label,
                claimed_power=raw_world.thesis,
                property_that_would_imply_target=raw_world.bridge_to_target,
                risk_of_smuggling_target="medium",
            ),
            notes=["Distilled from raw wild invention; truth is not assumed."],
        )

    def _cheap_falsify(
        self,
        campaign: CampaignRecord,
        world: DistilledWorld,
    ) -> WorldFalsifierResult:
        bridge_plan = world.world_program.bridge_to_target
        raw_bridge = bridge_plan.bridge_claim.lower() if bridge_plan else ""
        thesis = world.world_program.thesis.lower()
        objects = world.world_program.ontology

        if not objects:
            return WorldFalsifierResult(
                batch_id=world.batch_id,
                distilled_world_id=world.id,
                campaign_id=campaign.id,
                status="falsified",
                falsifier_type="empty_ontology",
                summary="World introduced no usable mathematical objects.",
                pattern="empty_invented_ontology",
            )

        if "collatz" in thesis and "collatz" in raw_bridge and len(objects) < 2:
            return WorldFalsifierResult(
                batch_id=world.batch_id,
                distilled_world_id=world.id,
                campaign_id=campaign.id,
                status="falsified",
                falsifier_type="circular_bridge",
                summary="Bridge appears to restate the target without a new compression object.",
                pattern="bridge_restates_target",
            )

        artifacts = []
        if "collatz" in campaign.problem_statement.lower():
            artifacts = _collatz_probe_artifacts()

        if world.novelty_score >= 0.65 and world.bridge_score >= 0.45:
            return WorldFalsifierResult(
                batch_id=world.batch_id,
                distilled_world_id=world.id,
                campaign_id=campaign.id,
                status="survived",
                falsifier_type="cheap_static_probe",
                summary="No cheap structural falsifier found; promote only after debt compilation review.",
                artifacts=artifacts,
            )

        return WorldFalsifierResult(
            batch_id=world.batch_id,
            distilled_world_id=world.id,
            campaign_id=campaign.id,
            status="inconclusive",
            falsifier_type="cheap_static_probe",
            summary="World is coherent enough to keep, but the bridge is not yet compelling.",
            artifacts=artifacts,
        )

    def _load_batch(self, campaign_id: str, batch_id: str) -> InventionBatch:
        node = self.memory.get_research_node(campaign_id, batch_id)
        if not node or node.node_type != "InventionBatch":
            raise KeyError(f"Invention batch not found: {batch_id}")
        return InventionBatch.model_validate(node.payload)

    def _list_raw_worlds(self, campaign_id: str, batch_id: str) -> list[RawWorldInvention]:
        nodes = self.memory.list_research_nodes(
            campaign_id, node_type="RawWorldInvention", limit=500
        )
        worlds = [RawWorldInvention.model_validate(node.payload) for node in nodes]
        return [world for world in worlds if world.batch_id == batch_id]

    def _list_distilled_worlds(self, campaign_id: str, batch_id: str) -> list[DistilledWorld]:
        nodes = self.memory.list_research_nodes(
            campaign_id, node_type="DistilledWorld", limit=500
        )
        worlds = [DistilledWorld.model_validate(node.payload) for node in nodes]
        return [world for world in worlds if world.batch_id == batch_id]

    def _list_falsifier_results(
        self,
        campaign_id: str,
        batch_id: str,
    ) -> list[WorldFalsifierResult]:
        nodes = self.memory.list_research_nodes(campaign_id, node_type="Falsifier", limit=500)
        results = [WorldFalsifierResult.model_validate(node.payload) for node in nodes]
        return [result for result in results if result.batch_id == batch_id]

    def _record_batch(self, batch: InventionBatch) -> None:
        self.memory.upsert_research_node(
            campaign_id=batch.campaign_id,
            node_id=batch.id,
            node_type="InventionBatch",
            title=f"{batch.mode}:{batch.wildness}:{batch.requested_worlds}",
            summary=f"{batch.mode} invention batch for {batch.problem_statement[:120]}",
            status=batch.status,
            payload=batch.model_dump(mode="json"),
        )

    def _record_raw_world(self, raw_world: RawWorldInvention) -> None:
        self.memory.upsert_research_node(
            campaign_id=raw_world.campaign_id,
            node_id=raw_world.id,
            node_type="RawWorldInvention",
            title=raw_world.label,
            summary=raw_world.thesis,
            status="speculative",
            payload=raw_world.model_dump(mode="json"),
        )

    def _record_distilled_world(self, world: DistilledWorld) -> None:
        self.memory.upsert_research_node(
            campaign_id=world.campaign_id,
            node_id=world.id,
            node_type="DistilledWorld",
            title=world.world_program.label,
            summary=world.world_program.thesis,
            status=world.status,
            confidence=min(0.99, (world.novelty_score + world.bridge_score) / 2),
            payload=world.model_dump(mode="json"),
        )

    def _record_definition(self, definition: FormalDefinition, world: DistilledWorld) -> None:
        self.memory.upsert_research_node(
            campaign_id=world.campaign_id,
            node_id=definition.id,
            node_type="FormalDefinition",
            title=definition.name,
            summary=definition.natural_language,
            status=definition.status,
            payload=definition.model_dump(mode="json"),
        )
        self.memory.add_research_edge(
            campaign_id=world.campaign_id,
            src_id=world.id,
            edge_type="REUSES_DEFINITION",
            dst_id=definition.id,
        )

    def _record_proof_debt(self, debt: ProofDebtItem, world: DistilledWorld) -> None:
        self.memory.upsert_research_node(
            campaign_id=world.campaign_id,
            node_id=debt.id,
            node_type="ProofDebtItem",
            title=debt.statement,
            summary=debt.statement,
            status=debt.status,
            payload=debt.model_dump(mode="json"),
        )
        self.memory.add_research_edge(
            campaign_id=world.campaign_id,
            src_id=world.id,
            edge_type="HAS_PROOF_DEBT",
            dst_id=debt.id,
            weight=debt.priority,
            payload={"role": debt.role, "critical": debt.critical},
        )

    def _record_falsifier_result(self, result: WorldFalsifierResult) -> None:
        self.memory.upsert_research_node(
            campaign_id=result.campaign_id,
            node_id=result.id,
            node_type="Falsifier",
            title=f"{result.status}:{result.falsifier_type}",
            summary=result.summary,
            status=result.status,
            payload=result.model_dump(mode="json"),
        )
        edge_type = "FALSIFIED_BY" if result.status == "falsified" else "TESTED_BY"
        self.memory.add_research_edge(
            campaign_id=result.campaign_id,
            src_id=result.distilled_world_id,
            edge_type=edge_type,
            dst_id=result.id,
        )


def _inventor_prompt(campaign: CampaignRecord, batch: InventionBatch) -> str:
    return (
        "Invent a batch of wild mathematical worlds for this problem.\n"
        "This is the hallucination zone: be structurally strange, not safe.\n"
        "Do not claim truth. Every world must define new objects and falsifiers.\n\n"
        f"Problem:\n{campaign.problem_statement}\n\n"
        f"Requested worlds: {batch.requested_worlds}\n"
        f"Wildness: {batch.wildness}\n"
        f"Strategy slots: {batch.strategy_slots}\n\n"
        "Return JSON: {\"worlds\": [...]} where each world has label, raw_text, "
        "new_objects, thesis, bridge_to_target, cheap_predictions, "
        "likely_falsifiers, proof_debt_sketch, novelty_rationale, "
        "miracle_object {name, claimed_power, property_that_would_imply_target, "
        "risk_of_smuggling_target}, hidden_circularity_risk, definability_probe, "
        "bridge_probe, and closure_probe."
    )


def _template_world(
    campaign: CampaignRecord,
    batch: InventionBatch,
    slot: str,
    idx: int,
) -> RawWorldInvention:
    label, objects, thesis, bridge, predictions, falsifiers, debt, novelty = _slot_template(
        slot,
        campaign.problem_statement,
        idx,
    )
    return RawWorldInvention(
        batch_id=batch.id,
        campaign_id=campaign.id,
        label=label,
        raw_text=f"{label}: {thesis} Bridge: {bridge}",
        new_objects=objects,
        thesis=thesis,
        bridge_to_target=bridge,
        cheap_predictions=predictions,
        likely_falsifiers=falsifiers,
        proof_debt_sketch=debt,
        novelty_rationale=novelty,
        source_model="deterministic",
        wildness=batch.wildness,
    )


def _slot_template(
    slot: str,
    problem: str,
    idx: int,
) -> tuple[list[str] | str, ...]:
    target = problem[:140]
    templates: dict[str, tuple[str, list[str], str, str, list[str], list[str], list[str], str]] = {
        "alien_state_space_encoding": (
            f"Alien State-Space Encoding {idx + 1}",
            ["state glyph", "transition shadow", "certificate fiber"],
            f"Re-encode states of `{target}` as certificate fibers where difficult moves become local fiber transitions.",
            "If every original state maps into a well-founded certificate fiber and each transition lowers the fiber rank, the target follows.",
            ["Small trajectories admit unique certificate fibers.", "Fiber rank does not increase on sampled transitions."],
            ["Find a state with no certificate fiber.", "Find a transition that increases fiber rank."],
            ["Define certificate fibers.", "Prove original transitions lift into fibers.", "Prove fiber rank is well-founded and decreasing."],
            "Changes the proof object from integer motion to typed certificate motion.",
        ),
        "parity_word_grammar": (
            f"Parity Word Grammar {idx + 1}",
            ["parity word", "grammar production", "normal word"],
            f"Treat trajectories for `{target}` as words in a grammar and search for a terminating normal-form rewrite system.",
            "If grammar productions simulate trajectories and every word rewrites to the terminal normal word, the target follows.",
            ["Initial samples rewrite to a short normal word.", "No sampled production increases grammar height."],
            ["A sampled trajectory word has no rewrite.", "A rewrite loop appears."],
            ["Define trajectory words.", "Prove grammar simulation.", "Prove rewrite termination.", "Bridge terminal word to target conclusion."],
            "Replaces arithmetic iteration with formal-language termination.",
        ),
        "residue_flow_conservation": (
            f"Residue Flow Conservation {idx + 1}",
            ["residue chamber", "flow leak", "mass ledger"],
            f"Partition `{target}` into residue chambers with a mass ledger that must leak from nonterminal chambers.",
            "If every chamber either leaks mass to a lower chamber or reaches the target chamber, global descent follows.",
            ["Sampled chambers have positive leak.", "Exceptional chambers are finite and classifiable."],
            ["A chamber has zero leak and no escape.", "Leak accounting is not invariant under transition."],
            ["Define chambers.", "Prove transition accounting.", "Prove finite exception closure.", "Bridge chamber leak to descent."],
            "Invents a conservation-law view rather than a direct descent measure.",
        ),
        "minimal_counterexample_world": (
            f"Minimal Counterexample Ecology {idx + 1}",
            ["counterexample organism", "mutation edge", "dominance relation"],
            f"Assume a minimal counterexample to `{target}` and model its descendants as an ecology with dominance pressure.",
            "If every organism mutates into a dominated organism, minimal counterexamples cannot exist.",
            ["No sampled organism is dominance-minimal after expansion.", "Dominance is transitive on generated samples."],
            ["A sampled organism reproduces without dominated descendants.", "Dominance is not well-founded."],
            ["Define organism encoding.", "Prove mutation simulation.", "Prove dominance well-founded.", "Derive contradiction for minimal counterexample."],
            "Turns the problem into elimination of a structured counterexample ecology.",
        ),
        "compressed_trajectory_dynamics": (
            f"Compressed Trajectory Dynamics {idx + 1}",
            ["macro step", "compression window", "energy leak"],
            f"Bundle many primitive moves in `{target}` into macro steps whose compression windows expose a hidden energy leak.",
            "If every trajectory reaches a macro step with negative energy leak, iterated compression gives descent.",
            ["Macro windows exist for sampled states.", "Energy leak is negative on most sampled windows."],
            ["A state has only nonnegative leak windows.", "Macro simulation skips a primitive transition."],
            ["Define macro step.", "Prove macro step simulates primitive dynamics.", "Prove leak negativity under coverage.", "Bridge leak to target."],
            "Searches for proof at the scale of transition blocks rather than individual steps.",
        ),
        "inverse_tree_normal_form": (
            f"Inverse Tree Normal Form {idx + 1}",
            ["inverse branch", "normal ancestor", "pruning certificate"],
            f"Study the inverse tree of `{target}` and invent a normal form where every branch has a pruning certificate.",
            "If all inverse branches are generated by prunable normal ancestors, no nonterminal component remains.",
            ["Generated inverse branches normalize in bounded depth.", "Pruning certificates compose."],
            ["A branch has no normal ancestor.", "Certificates fail to compose."],
            ["Define inverse branches.", "Define normal ancestors.", "Prove pruning certificate soundness.", "Bridge inverse coverage to target."],
            "Attacks the target backwards through generated structure.",
        ),
        "rewrite_system_termination": (
            f"Rewrite System Termination {idx + 1}",
            ["rewrite token", "critical pair", "termination order"],
            f"Present `{target}` as a rewrite system and search for a termination order over critical pairs.",
            "If the rewrite system simulates the original dynamics and terminates, every path reaches normal form.",
            ["Critical pairs close on small generated systems.", "Termination order orients sampled rules."],
            ["A critical pair is unjoinable.", "A sampled rule cannot be oriented."],
            ["Define rewrite tokens.", "Prove simulation.", "Prove local confluence or controlled critical pairs.", "Prove termination order."],
            "Moves the problem into rewriting theory and termination certificates.",
        ),
        "two_adic_shadow_dynamics": (
            f"2-Adic Shadow Dynamics {idx + 1}",
            ["2-adic shadow", "valuation surplus", "shadow descent"],
            f"Project `{target}` into a 2-adic shadow where valuation surplus predicts eventual descent.",
            "If every shadow orbit accumulates surplus that forces an ordinary descent, the target follows.",
            ["Sampled shadows accumulate surplus.", "Surplus predicts observed descent windows."],
            ["A shadow orbit loses surplus forever.", "Surplus does not imply ordinary descent."],
            ["Define shadow projection.", "Prove projection simulates dynamics.", "Prove surplus accumulation.", "Bridge surplus to descent."],
            "Uses valuation geometry as the primary invented world.",
        ),
        "automaton_boundary_world": (
            f"Automaton Boundary World {idx + 1}",
            ["boundary automaton", "escape state", "absorbing proof cell"],
            f"Build a finite boundary automaton for `{target}` where escape states correspond to reduced proof debt.",
            "If every automaton path reaches an absorbing proof cell and simulation is sound, the target reduces to finite closure.",
            ["Bounded samples enter absorbing cells.", "No sampled path cycles outside escape states."],
            ["A nonabsorbing automaton cycle appears.", "Simulation misses a transition."],
            ["Define automaton states.", "Prove simulation.", "Prove all cycles escape.", "Bridge absorbing cells to target."],
            "Compresses infinite behavior into automaton boundary closure.",
        ),
        "bridge_from_unrelated_field": (
            f"Unrelated-Field Bridge {idx + 1}",
            ["flow category", "ranking functor", "terminal object"],
            f"Treat `{target}` as a category of flows and invent a ranking functor into a well-founded category.",
            "If every nonterminal morphism maps to a strictly decreasing ranking morphism, terminal reachability follows.",
            ["Sample transitions map functorially.", "Ranking morphisms compose decreasingly."],
            ["Functor is not well-defined.", "A nonterminal morphism maps to an identity ranking."],
            ["Define flow category.", "Define ranking functor.", "Prove functorial simulation.", "Prove well-founded descent."],
            "Imports categorical language as a strange bridge, then demands formal debt.",
        ),
    }
    return templates.get(slot, templates["alien_state_space_encoding"])


def _compile_debt(world: WorldProgram, raw_world: RawWorldInvention) -> list[ProofDebtItem]:
    first_object = raw_world.new_objects[0] if raw_world.new_objects else world.label
    debts = [
        ProofDebtItem(
            world_id=world.id,
            role="support",
            debt_class="world_definitions",
            statement=f"Define the invented object `{first_object}` precisely for world `{world.label}`.",
            assigned_channel="human",
            expected_difficulty=0.35,
            critical=True,
            priority=0.95,
            notes=["Definition debt generated by invention distiller."],
        ),
        ProofDebtItem(
            world_id=world.id,
            role="boundary",
            debt_class="falsifier",
            statement=f"Search cheap falsifiers for world `{world.label}`: {', '.join(raw_world.likely_falsifiers[:2])}.",
            assigned_channel="evidence",
            expected_difficulty=0.25,
            critical=True,
            priority=0.9,
            notes=["Boundary/falsifier debt should run before expensive proof work."],
        ),
        ProofDebtItem(
            world_id=world.id,
            role="bridge",
            debt_class="bridge_to_nat",
            statement=f"Prove the bridge from `{world.label}` back to the target: {raw_world.bridge_to_target}",
            assigned_channel="aristotle",
            expected_difficulty=0.85,
            critical=True,
            priority=0.85,
            notes=["Bridge debt; do not claim solved until this closes."],
        ),
        ProofDebtItem(
            world_id=world.id,
            role="bridge",
            debt_class="pullback_to_original",
            statement=(
                f"Prove soundness transfer for `{world.label}`: the invented "
                "world theorem implies the original target statement over the "
                "standard domain."
            ),
            assigned_channel="aristotle",
            expected_difficulty=0.85,
            critical=True,
            priority=0.84,
            notes=["Soundness debt; internal world closure is not enough."],
        ),
        ProofDebtItem(
            world_id=world.id,
            role="closure",
            debt_class="in_world_theorem",
            statement=f"Prove the main closure claim inside world `{world.label}`: {raw_world.thesis}",
            assigned_channel="aristotle",
            expected_difficulty=0.9,
            critical=True,
            priority=0.8,
            notes=["Closure debt generated by invention distiller."],
        ),
    ]
    for sketch in raw_world.proof_debt_sketch[:3]:
        debts.append(
            ProofDebtItem(
                world_id=world.id,
                role="support",
                debt_class="supporting_lemma",
                statement=sketch,
                assigned_channel="auto",
                expected_difficulty=0.6,
                critical=False,
                priority=0.5,
                notes=["Support debt from raw invention sketch."],
            )
        )
    return debts


def _collatz_probe_artifacts() -> list[str]:
    samples = [3, 7, 27, 31, 63, 127]
    artifacts = []
    for n in samples:
        steps = 0
        value = n
        max_value = n
        while value != 1 and steps < 300:
            value = value // 2 if value % 2 == 0 else 3 * value + 1
            max_value = max(max_value, value)
            steps += 1
        artifacts.append(f"collatz_sample:n={n}:steps={steps}:max={max_value}:ended={value == 1}")
    return artifacts


def _family_for_label(label: str) -> str:
    lowered = label.lower()
    if "counterexample" in lowered:
        return "counterexample"
    if "automaton" in lowered or "grammar" in lowered or "rewrite" in lowered:
        return "reformulate"
    if "bridge" in lowered or "category" in lowered:
        return "bridge"
    if "residue" in lowered:
        return "structural_case_split"
    if "shadow" in lowered or "trajectory" in lowered:
        return "invariant_lift"
    return "local_to_global"


def _definition_name(text: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in text.lower()).strip("_")
    return cleaned or "invented_definition"


def _score_novelty(raw_world: RawWorldInvention) -> float:
    object_bonus = min(0.25, 0.06 * len(raw_world.new_objects))
    weird_words = ["grammar", "shadow", "category", "ecology", "fiber", "automaton", "ledger"]
    weird_bonus = 0.08 * sum(1 for word in weird_words if word in raw_world.raw_text.lower())
    return min(1.0, 0.45 + object_bonus + min(0.25, weird_bonus))


def _score_plausibility(raw_world: RawWorldInvention) -> float:
    prediction_bonus = min(0.2, 0.05 * len(raw_world.cheap_predictions))
    debt_bonus = min(0.2, 0.04 * len(raw_world.proof_debt_sketch))
    falsifier_bonus = 0.1 if raw_world.likely_falsifiers else 0.0
    return min(1.0, 0.35 + prediction_bonus + debt_bonus + falsifier_bonus)


def _score_bridge(raw_world: RawWorldInvention) -> float:
    bridge = raw_world.bridge_to_target.lower()
    if not bridge:
        return 0.0
    score = 0.35
    for cue in ("if", "then", "simulate", "well-founded", "bridge", "target", "follows"):
        if cue in bridge:
            score += 0.08
    return min(1.0, score)


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0
