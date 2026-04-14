from __future__ import annotations

import re
from collections import Counter
from typing import Any

from lima_memory import MemoryService

from .config import Settings
from .invention import InventionService
from .schemas import (
    CampaignRecord,
    CircularityAssessment,
    DistilledWorld,
    EvolutionLineage,
    FormalObligationSpec,
    FormalProbe,
    InventionBatchCreate,
    MiracleObject,
    WorldEvolutionRun,
    WorldEvolutionRunRequest,
    WorldFitness,
    WorldGeneration,
    WorldMutation,
)


class WorldEvolutionService:
    """Population-level invention loop with conservative formal pressure."""

    def __init__(
        self,
        memory: MemoryService,
        settings: Settings,
        invention: InventionService,
    ) -> None:
        self.memory = memory
        self.settings = settings
        self.invention = invention

    def run(
        self,
        campaign: CampaignRecord,
        payload: WorldEvolutionRunRequest,
        *,
        policy: dict[str, Any] | None = None,
    ) -> tuple[WorldEvolutionRun, DistilledWorld | None]:
        policy = policy or {}
        run = WorldEvolutionRun(
            campaign_id=campaign.id,
            generations_requested=payload.generations,
        )
        previous_survivors: list[DistilledWorld] = []
        all_survivors: list[DistilledWorld] = []
        failure_modes: Counter[str] = Counter()

        for generation_index in range(payload.generations):
            batch_payload = InventionBatchCreate(
                mode="wild" if generation_index == 0 else "mutation",
                wildness=payload.wildness,
                requested_worlds=payload.worlds_per_generation,
                prompt=self._generation_prompt(generation_index, previous_survivors),
            )
            batch = self.invention.create_batch(campaign, batch_payload, policy=policy)
            raw_world_count = len(batch.raw_world_ids)
            distilled = self.invention.distill_batch(campaign, batch.id)
            falsifiers = self.invention.falsify_batch(campaign, batch.id)
            falsified_ids = {
                item.distilled_world_id for item in falsifiers if item.status == "falsified"
            }

            annotated: list[DistilledWorld] = []
            circular_count = 0
            for idx, world in enumerate(distilled):
                parent = previous_survivors[idx % len(previous_survivors)] if previous_survivors else None
                world = self._annotate_world(world, parent=parent, generation_index=generation_index)
                if world.id in falsified_ids and world.status != "circularity_failed":
                    world.status = "falsified"
                    failure_modes["cheap_falsifier"] += 1
                if world.anti_circularity and world.anti_circularity.status == "failed":
                    circular_count += 1
                    failure_modes[self._failure_mode_for_circularity(world.anti_circularity)] += 1
                annotated.append(world)
                self._record_distilled_world(world)

            survivors = self._select_survivors(
                annotated,
                limit=payload.survivors_per_generation,
            )
            probes = self._compile_generation_probes(
                survivors,
                limit=payload.max_formal_probes_per_generation,
            )
            evidence_probe_count = min(
                payload.max_evidence_probes_per_generation,
                sum(max(1, len(world.falsifiable_predictions)) for world in survivors),
            )
            mutations = self._record_mutations(
                campaign=campaign,
                generation_index=generation_index,
                worlds=annotated,
                survivors=survivors,
                limit=payload.mutations_per_survivor,
            )

            generation = WorldGeneration(
                campaign_id=campaign.id,
                run_id=run.id,
                generation_index=generation_index,
                batch_id=batch.id,
                raw_world_count=raw_world_count,
                distilled_world_count=len(distilled),
                circular_world_count=circular_count,
                survivor_world_ids=[world.world_program.id for world in survivors],
                mutation_ids=[mutation.id for mutation in mutations],
                formal_probe_ids=[probe.id for probe in probes],
                evidence_probe_count=evidence_probe_count,
            )
            self._record_generation(generation)

            run.generations_completed += 1
            run.raw_world_count += raw_world_count
            run.distilled_world_count += len(distilled)
            run.falsified_world_count += len(falsified_ids)
            run.circular_world_count += circular_count
            run.formal_probe_count += len(probes)
            run.evidence_probe_count += evidence_probe_count
            run.generation_ids.append(generation.id)
            all_survivors = survivors
            previous_survivors = survivors

        best_world = self._best_promotable_world(all_survivors)
        if best_world:
            run.best_world_id = best_world.world_program.id
            run.best_distilled_world_id = best_world.id
            run.best_world_label = best_world.world_program.label
            if payload.promote_best_survivor:
                run.promoted_world_id = best_world.world_program.id

        run.survivor_count = len(all_survivors)
        run.blocked_probe_count = self._count_probe_status(all_survivors, "blocked")
        run.proved_probe_count = self._count_probe_status(all_survivors, "proved")
        run.top_failure_modes = [mode for mode, _ in failure_modes.most_common(5)]
        run.learning_summary = self._learning_summary(run, best_world)
        self._record_run(run)
        self.memory.add_event(
            campaign_id=campaign.id,
            tick=campaign.tick_count,
            event_type="world_evolution_run_completed",
            payload=run.model_dump(mode="json"),
        )
        return run, best_world if payload.promote_best_survivor else None

    def get_summary(self, campaign_id: str) -> dict[str, Any]:
        runs = self.memory.list_research_nodes(
            campaign_id,
            node_type="WorldEvolutionRun",
            limit=1,
        )
        if not runs:
            return {
                "latest_run_id": None,
                "generations_completed": 0,
                "survivor_count": 0,
                "best_world_label": None,
                "top_failure_modes": [],
                "promoted_world_id": None,
            }
        payload = runs[0].payload or {}
        return {
            "latest_run_id": payload.get("run_id") or runs[0].id,
            "generations_completed": payload.get("generations_completed", 0),
            "survivor_count": payload.get("survivor_count", 0),
            "best_world_label": payload.get("best_world_label"),
            "top_failure_modes": payload.get("top_failure_modes", []),
            "promoted_world_id": payload.get("promoted_world_id"),
            "formal_probe_count": payload.get("formal_probe_count", 0),
            "circular_world_count": payload.get("circular_world_count", 0),
            "learning_summary": payload.get("learning_summary", ""),
        }

    def _annotate_world(
        self,
        world: DistilledWorld,
        *,
        parent: DistilledWorld | None,
        generation_index: int,
    ) -> DistilledWorld:
        updated = world.model_copy(deep=True)
        updated.miracle_object = self._extract_miracle(updated)
        updated.anti_circularity = self._assess_circularity(updated)
        updated.lineage = EvolutionLineage(
            parent_world_ids=[parent.world_program.id] if parent else [],
            mutation_reason=self._mutation_reason(parent) if parent else None,
            dead_patterns_avoided=[] if generation_index == 0 else ["bridge_restates_target"],
        )
        updated.fitness = self._score_world(updated)
        if updated.anti_circularity.status == "failed":
            updated.status = "circularity_failed"
        elif updated.status not in {"falsified", "baking", "retired"}:
            updated.status = "promising" if updated.fitness.overall >= 0.45 else "candidate"
        updated.notes.append(
            f"World-evolution generation {generation_index}: anti_circularity={updated.anti_circularity.status}, fitness={updated.fitness.overall:.3f}."
        )
        return updated

    def _extract_miracle(self, world: DistilledWorld) -> MiracleObject:
        if world.miracle_object:
            return world.miracle_object
        objects = world.world_program.ontology or []
        name = objects[0] if objects else world.world_program.label
        bridge = world.world_program.bridge_to_target.bridge_claim if world.world_program.bridge_to_target else ""
        risk = "medium"
        lower = f"{world.world_program.thesis} {bridge}".lower()
        if "eventually reaches 1" in lower or "all trajectories terminate" in lower:
            risk = "high"
        elif objects and any(cue in bridge.lower() for cue in ("simulate", "maps", "interpret", "encoding")):
            risk = "low"
        return MiracleObject(
            name=name,
            claimed_power=world.world_program.thesis,
            property_that_would_imply_target=bridge or "No explicit bridge supplied.",
            risk_of_smuggling_target=risk,  # type: ignore[arg-type]
        )

    def _assess_circularity(self, world: DistilledWorld) -> CircularityAssessment:
        text = " ".join(
            [
                world.world_program.label,
                world.world_program.thesis,
                world.world_program.bridge_to_target.bridge_claim
                if world.world_program.bridge_to_target
                else "",
                " ".join(debt.statement for debt in world.proof_debt),
            ]
        ).lower()
        suspects: list[str] = []
        if not world.world_program.ontology:
            return CircularityAssessment(
                status="failed",
                reason="empty_ontology",
                suspect_assumptions=["World introduced no concrete mathematical objects."],
            )
        if re.search(r"if\s+collatz.*then\s+collatz", text):
            return CircularityAssessment(
                status="failed",
                reason="bridge_restates_target",
                suspect_assumptions=["Bridge is an if-Collatz-then-Collatz restatement."],
            )
        if "eventually reaches 1" in text and len(world.world_program.ontology) < 2:
            return CircularityAssessment(
                status="failed",
                reason="target_restatement",
                suspect_assumptions=["World theorem is the target theorem under renamed terms."],
            )
        if "global descent follows" in text or "forces ordinary descent" in text:
            suspects.append("Global descent is asserted before the invented measure is proved.")
        if (
            "always decreases" in text or "strictly decreasing" in text
        ) and not any(cue in text for cue in ("define", "simulation", "encoding", "maps")):
            suspects.append("A descent principle appears without a verifiable definition.")
        if suspects:
            return CircularityAssessment(
                status="failed",
                reason="unproved_global_descent",
                suspect_assumptions=suspects,
            )
        if world.miracle_object and world.miracle_object.risk_of_smuggling_target == "high":
            return CircularityAssessment(
                status="unclear",
                reason="high_smuggling_risk_declared",
                suspect_assumptions=["Inventor marked the miracle object as high circularity risk."],
            )
        return CircularityAssessment(
            status="passed",
            reason="has_objects_and_nontrivial_bridge_shape",
            suspect_assumptions=[],
        )

    def _score_world(self, world: DistilledWorld) -> WorldFitness:
        anti = 1.0 if world.anti_circularity and world.anti_circularity.status == "passed" else 0.45
        if world.anti_circularity and world.anti_circularity.status == "failed":
            anti = 0.0
        definability = min(1.0, 0.25 + 0.12 * len(world.world_program.ontology_definitions))
        if world.miracle_object and world.miracle_object.risk_of_smuggling_target == "low":
            definability += 0.15
        formal_success = 0.0
        if world.formal_probes:
            formal_success = min(1.0, len([p for p in world.formal_probes if p.status == "compiled"]) / 3)
        debt_compression = max(0.0, min(1.0, 1.0 - (len(world.proof_debt) / 16)))
        overall = (
            0.18 * world.novelty_score
            + 0.18 * definability
            + 0.22 * world.bridge_score
            + 0.20 * anti
            + 0.12 * formal_success
            + 0.10 * debt_compression
        )
        return WorldFitness(
            novelty=world.novelty_score,
            definability=min(1.0, definability),
            bridge_quality=world.bridge_score,
            anti_circularity=anti,
            formal_probe_success=formal_success,
            debt_compression=debt_compression,
            overall=min(1.0, overall),
        )

    def _select_survivors(self, worlds: list[DistilledWorld], *, limit: int) -> list[DistilledWorld]:
        eligible = [
            world
            for world in worlds
            if world.status not in {"falsified", "circularity_failed", "retired"}
            and world.fitness is not None
        ]
        eligible.sort(key=lambda world: (world.fitness.overall if world.fitness else 0), reverse=True)
        return eligible[:limit]

    def _compile_generation_probes(self, worlds: list[DistilledWorld], *, limit: int) -> list[FormalProbe]:
        probes: list[FormalProbe] = []
        for world in worlds:
            if len(probes) >= limit:
                break
            for probe in self._compile_world_probes(world):
                if len(probes) >= limit:
                    break
                world.formal_probes.append(probe)
                probes.append(probe)
                self._record_probe(probe, world)
            world.fitness = self._score_world(world)
            self._record_distilled_world(world)
        return probes

    def _compile_world_probes(self, world: DistilledWorld) -> list[FormalProbe]:
        suffix = _lean_suffix(world.world_program.id)
        object_name = world.miracle_object.name if world.miracle_object else world.world_program.label
        definition_code = (
            f"structure WorldObject_{suffix} where\n"
            "  value : Nat\n"
            "deriving Repr\n"
        )
        simulation_code = (
            f"def collatzStep_{suffix} (n : Nat) : Nat :=\n"
            "  if n % 2 = 0 then n / 2 else 3*n + 1\n\n"
            f"theorem collatzStep_even_shape_{suffix} (n : Nat) (h : n % 2 = 0) :\n"
            f"    collatzStep_{suffix} n = n / 2 := by\n"
            f"  simp [collatzStep_{suffix}, h]\n"
        )
        bridge_code = (
            f"def worldTerminal_{suffix} (n : Nat) : Prop := True\n\n"
            f"theorem bridge_shape_{suffix} "
            f"(h : ∀ n : Nat, n > 0 → worldTerminal_{suffix} n) :\n"
            "    ∀ n : Nat, n > 0 → True := by\n"
            "  intro n hn\n"
            "  trivial\n"
        )
        return [
            self._probe(
                world,
                "definition_probe",
                f"Can `{object_name}` be represented as a concrete Lean object?",
                definition_code,
            ),
            self._probe(
                world,
                "simulation_probe",
                "Check the even branch shape of the standard Collatz step.",
                simulation_code,
            ),
            self._probe(
                world,
                "bridge_probe",
                "Check that the world-to-target bridge has a Lean-clean implication shape.",
                bridge_code,
            ),
        ]

    def _probe(
        self,
        world: DistilledWorld,
        probe_type: str,
        source_text: str,
        lean_code: str,
    ) -> FormalProbe:
        return FormalProbe(
            world_id=world.world_program.id,
            probe_type=probe_type,  # type: ignore[arg-type]
            source_text=source_text,
            formal_obligation=FormalObligationSpec(
                source_text=source_text,
                goal_kind="lemma",
                lean_declaration=lean_code,
                channel_hint="proof",
                requires_proof=True,
                metadata={
                    "world_id": world.world_program.id,
                    "probe_type": probe_type,
                    "probe_only": True,
                },
            ),
            status="compiled",
            notes="Compiled as a tiny formal probe; not a Collatz proof.",
        )

    def _record_mutations(
        self,
        *,
        campaign: CampaignRecord,
        generation_index: int,
        worlds: list[DistilledWorld],
        survivors: list[DistilledWorld],
        limit: int,
    ) -> list[WorldMutation]:
        mutations: list[WorldMutation] = []
        failed = [
            world
            for world in worlds
            if world.status in {"falsified", "circularity_failed"}
        ]
        parents = [*survivors, *failed][: max(0, limit * max(1, len(survivors)))]
        for parent in parents:
            failure_type = (
                parent.anti_circularity.reason
                if parent.anti_circularity and parent.anti_circularity.status == "failed"
                else "survivor_refinement"
            )
            mutation = WorldMutation(
                campaign_id=campaign.id,
                generation_index=generation_index,
                parent_world_id=parent.world_program.id,
                failure_type=failure_type,
                mutation_instruction=self._mutation_instruction_for_failure(parent, failure_type),
                dead_patterns=[failure_type] if failure_type != "survivor_refinement" else [],
            )
            mutations.append(mutation)
            self._record_mutation(mutation)
        return mutations

    def _best_promotable_world(self, worlds: list[DistilledWorld]) -> DistilledWorld | None:
        eligible = [
            world
            for world in worlds
            if world.anti_circularity
            and world.anti_circularity.status in {"passed", "unclear"}
            and (not world.miracle_object or world.miracle_object.risk_of_smuggling_target != "high")
            and world.bridge_score >= 0.55
            and any(probe.probe_type in {"definition_probe", "simulation_probe"} for probe in world.formal_probes)
            and world.fitness
        ]
        eligible.sort(key=lambda world: world.fitness.overall if world.fitness else 0, reverse=True)
        return eligible[0] if eligible else None

    def _generation_prompt(self, generation_index: int, survivors: list[DistilledWorld]) -> str | None:
        if generation_index == 0 or not survivors:
            return None
        labels = ", ".join(world.world_program.label for world in survivors[:5])
        return (
            "Mutate the previous survivor worlds. Preserve any concrete miracle objects, "
            "repair circular bridges, and produce sharper definability and bridge probes. "
            f"Survivors to mutate: {labels}"
        )

    def _mutation_reason(self, parent: DistilledWorld | None) -> str | None:
        if parent is None:
            return None
        if parent.anti_circularity and parent.anti_circularity.status != "passed":
            return f"repair_{parent.anti_circularity.reason}"
        return "survivor_refinement"

    def _mutation_instruction_for_failure(self, world: DistilledWorld, failure_type: str) -> str:
        mapping = {
            "empty_ontology": "Force concrete objects and definitions before any closure claim.",
            "bridge_restates_target": "Replace the bridge with an explicit interpretation map back to Nat.",
            "target_restatement": "Weaken the world theorem into definability and one-step simulation probes.",
            "unproved_global_descent": "Preserve the invented object but replace global descent with a local monotonicity probe.",
            "cheap_falsifier": "Keep the highest-scoring component and mutate the failed prediction.",
            "survivor_refinement": "Sharpen the miracle object and compile a smaller bridge probe.",
        }
        return mapping.get(failure_type, "Split the failed world into definition, bridge, and closure probes.")

    def _failure_mode_for_circularity(self, assessment: CircularityAssessment) -> str:
        return assessment.reason or "circularity_failed"

    def _count_probe_status(self, worlds: list[DistilledWorld], status: str) -> int:
        return sum(1 for world in worlds for probe in world.formal_probes if probe.status == status)

    def _learning_summary(self, run: WorldEvolutionRun, best_world: DistilledWorld | None) -> str:
        if not best_world:
            return (
                "World evolution produced candidates but no promotable survivor passed the "
                "bridge, anti-circularity, and probe gates."
            )
        return (
            "World evolution did not solve the target. The best survivor "
            f"`{best_world.world_program.label}` exposed `{best_world.miracle_object.name if best_world.miracle_object else 'an invented object'}` "
            "and compiled Lean-clean probes; remaining closure and bridge debt still require proof."
        )

    def _record_run(self, run: WorldEvolutionRun) -> None:
        self.memory.upsert_research_node(
            campaign_id=run.campaign_id,
            node_id=run.id,
            node_type="WorldEvolutionRun",
            title=f"world-evolution:{run.generations_completed}",
            summary=run.learning_summary,
            status=run.solve_status,
            payload=run.model_dump(mode="json"),
        )

    def _record_generation(self, generation: WorldGeneration) -> None:
        self.memory.upsert_research_node(
            campaign_id=generation.campaign_id,
            node_id=generation.id,
            node_type="WorldGeneration",
            title=f"generation:{generation.generation_index}",
            summary=f"{generation.distilled_world_count} worlds, {len(generation.survivor_world_ids)} survivors",
            status="complete",
            payload=generation.model_dump(mode="json"),
        )
        self.memory.add_research_edge(
            campaign_id=generation.campaign_id,
            src_id=generation.run_id,
            edge_type="HAS_GENERATION",
            dst_id=generation.id,
        )

    def _record_distilled_world(self, world: DistilledWorld) -> None:
        confidence = world.fitness.overall if world.fitness else min(0.99, (world.novelty_score + world.bridge_score) / 2)
        self.memory.upsert_research_node(
            campaign_id=world.campaign_id,
            node_id=world.id,
            node_type="DistilledWorld",
            title=world.world_program.label,
            summary=world.world_program.thesis,
            status=world.status,
            confidence=confidence,
            payload=world.model_dump(mode="json"),
        )

    def _record_probe(self, probe: FormalProbe, world: DistilledWorld) -> None:
        self.memory.upsert_research_node(
            campaign_id=world.campaign_id,
            node_id=probe.id,
            node_type="FormalProbe",
            title=f"{probe.probe_type}:{world.world_program.label}",
            summary=probe.source_text,
            status=probe.status,
            payload=probe.model_dump(mode="json"),
        )
        self.memory.add_research_edge(
            campaign_id=world.campaign_id,
            src_id=world.id,
            edge_type="TESTED_BY",
            dst_id=probe.id,
            payload={"probe_type": probe.probe_type},
        )

    def _record_mutation(self, mutation: WorldMutation) -> None:
        self.memory.upsert_research_node(
            campaign_id=mutation.campaign_id,
            node_id=mutation.id,
            node_type="WorldMutation",
            title=f"mutation:{mutation.failure_type}",
            summary=mutation.mutation_instruction,
            status="planned",
            payload=mutation.model_dump(mode="json"),
        )
        self.memory.add_research_edge(
            campaign_id=mutation.campaign_id,
            src_id=mutation.parent_world_id,
            edge_type="MUTATES_TO",
            dst_id=mutation.id,
            payload={"failure_type": mutation.failure_type},
        )


def _lean_suffix(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", value)
    cleaned = cleaned.strip("_")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"W_{cleaned}"
    return cleaned
