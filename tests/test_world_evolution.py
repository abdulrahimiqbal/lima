from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.schemas import (
    BridgePlan,
    CampaignCreate,
    DistilledWorld,
    InventionBatchCreate,
    ProofDebtItem,
    RawWorldInvention,
    WorldObjectDefinition,
    WorldProgram,
)
from app.service import CampaignService
from app.world_evolution import WorldEvolutionService


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        memory_db_path=str(tmp_path / "memory.db"),
        worker_poll_seconds=999,
        manager_backend="rules",
        executor_backend="mock",
    )


def _create_campaign(client: TestClient) -> str:
    response = client.post(
        "/api/campaigns",
        json={
            "title": "Collatz World Evolution Test 001",
            "problem_statement": (
                "Let T(n) be the Collatz map on positive integers: if n is even, "
                "T(n) = n / 2; if n is odd, T(n) = 3n + 1. Conjecture: every "
                "positive integer eventually reaches 1 under repeated iteration of T. "
                "Use world evolution, not direct proof search."
            ),
            "operator_notes": [
                "Run world evolution mode only.",
                "Do not declare solved from narrative confidence.",
                "Require anti-circularity screening before promotion.",
            ],
            "auto_run": False,
        },
    )
    assert response.status_code == 200
    return response.json()["id"]


def test_world_evolution_endpoint_runs_and_promotes_scoped_debt(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    client = TestClient(app)
    campaign_id = _create_campaign(client)

    response = client.post(
        f"/api/campaigns/{campaign_id}/world-evolution/run",
        json={
            "generations": 2,
            "worlds_per_generation": 12,
            "survivors_per_generation": 4,
            "mutations_per_survivor": 2,
            "wildness": "extreme",
            "max_formal_probes_per_generation": 6,
            "max_evidence_probes_per_generation": 8,
            "promote_best_survivor": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["solve_status"] == "not_solved"
    assert payload["generations_completed"] == 2
    assert payload["raw_world_count"] == 24
    assert payload["distilled_world_count"] == 24
    assert payload["survivor_count"] >= 4
    assert payload["formal_probe_count"] >= 6
    assert payload["circular_world_count"] >= 1
    assert payload["promoted_world_id"]

    campaign = client.get(f"/api/campaigns/{campaign_id}").json()
    assert campaign["status"] != "solved"
    assert campaign["active_world_id"] == payload["promoted_world_id"]
    assert len(campaign["proof_debt_ledger"]) <= 12

    brief = client.get(f"/api/campaigns/{campaign_id}/operator-brief").json()
    assert brief["world_evolution"]["latest_run_id"] == payload["run_id"]
    assert brief["world_evolution"]["survivor_count"] == payload["survivor_count"]


def test_anti_circularity_rejects_restatement(tmp_path: Path) -> None:
    service = CampaignService(_settings(tmp_path))
    world_evolution = WorldEvolutionService(service.memory, service.settings, service.invention)
    world = DistilledWorld(
        batch_id="IB-test",
        raw_world_id="RW-test",
        campaign_id="C-test",
        world_program=WorldProgram(
            label="Circular Collatz World",
            family_tags=["bridge"],
            mode="macro",
            thesis="Collatz eventually reaches 1 because all Collatz trajectories terminate.",
            ontology=["trajectory"],
            ontology_definitions=[
                WorldObjectDefinition(
                    name="trajectory",
                    natural_language="A renamed Collatz trajectory.",
                )
            ],
            bridge_to_target=BridgePlan(
                bridge_claim="If Collatz is true in this world, then Collatz is true.",
                estimated_cost=0.9,
            ),
        ),
        proof_debt=[
            ProofDebtItem(
                world_id="W-test",
                role="closure",
                statement="Prove all Collatz trajectories terminate.",
                critical=True,
            )
        ],
    )

    assessment = world_evolution._assess_circularity(world)

    assert assessment.status == "failed"
    assert assessment.reason == "bridge_restates_target"


def test_formal_probe_compiler_emits_lean_clean_probes(tmp_path: Path) -> None:
    service = CampaignService(_settings(tmp_path))
    world_evolution = WorldEvolutionService(service.memory, service.settings, service.invention)
    campaign = service.create_campaign(
        payload=CampaignCreate(
            title="Probe",
            problem_statement="Explore Collatz.",
            auto_run=False,
        )
    )
    batch = service.invention.create_batch(
        campaign,
        InventionBatchCreate(
            requested_worlds=1,
            wildness="high",
        ),
    )
    world = service.invention.distill_batch(campaign, batch.id)[0]
    annotated = world_evolution._annotate_world(world, parent=None, generation_index=0)

    probes = world_evolution._compile_world_probes(annotated)

    assert {probe.probe_type for probe in probes} >= {
        "definition_probe",
        "simulation_probe",
        "bridge_probe",
    }
    assert all(probe.formal_obligation.lean_declaration for probe in probes)
    assert any("collatzStep" in probe.formal_obligation.lean_declaration for probe in probes)


def test_world_evolution_run_records_mutations_and_lineage(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    client = TestClient(app)
    campaign_id = _create_campaign(client)

    response = client.post(
        f"/api/campaigns/{campaign_id}/world-evolution/run",
        json={
            "generations": 2,
            "worlds_per_generation": 8,
            "survivors_per_generation": 3,
            "mutations_per_survivor": 2,
            "wildness": "high",
            "max_formal_probes_per_generation": 4,
            "max_evidence_probes_per_generation": 4,
            "promote_best_survivor": True,
        },
    )
    assert response.status_code == 200

    lab = client.get(f"/api/campaigns/{campaign_id}/invention/lab").json()
    worlds_with_lineage = [
        node for node in lab["distilled_worlds"]
        if node["payload"].get("lineage", {}).get("parent_world_ids")
    ]
    assert worlds_with_lineage

    service = app.state.service
    mutations = service.memory.list_research_nodes(
        campaign_id,
        node_type="WorldMutation",
        limit=20,
    )
    assert mutations


def test_llm_invention_batch_tops_up_underproduced_worlds(tmp_path: Path, monkeypatch) -> None:
    settings = Settings(
        memory_db_path=str(tmp_path / "memory.db"),
        worker_poll_seconds=999,
        manager_backend="llm",
        executor_backend="mock",
        llm_api_key="test-key",
    )
    service = CampaignService(settings)
    campaign = service.create_campaign(
        payload=CampaignCreate(
            title="Underproduced LLM batch",
            problem_statement="Explore Collatz worlds.",
            auto_run=False,
        )
    )

    def fake_llm_worlds(campaign, batch):
        return [
            RawWorldInvention(
                batch_id=batch.id,
                campaign_id=campaign.id,
                label="LLM short world",
                raw_text="A single LLM world.",
                new_objects=["llm object"],
                thesis="One generated world is not enough.",
                bridge_to_target="Bridge by an explicit interpretation map.",
                cheap_predictions=["Probe one sample."],
                likely_falsifiers=["Missing interpretation map."],
                proof_debt_sketch=["Define the interpretation map."],
                novelty_rationale="Short LLM response.",
                source_model="llm-test",
            )
        ]

    monkeypatch.setattr(service.invention, "_generate_raw_worlds_with_llm", fake_llm_worlds)

    batch = service.invention.create_batch(
        campaign,
        InventionBatchCreate(
            requested_worlds=5,
            wildness="extreme",
        ),
    )
    raw_worlds = service.invention._list_raw_worlds(campaign.id, batch.id)

    assert len(batch.raw_world_ids) == 5
    assert len(raw_worlds) == 5
    assert batch.metrics["source"] == "mixed"
    assert any(world.source_model == "llm-test" for world in raw_worlds)
    assert any(world.source_model == "deterministic" for world in raw_worlds)
