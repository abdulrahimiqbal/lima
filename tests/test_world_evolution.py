from datetime import datetime, timezone
from pathlib import Path
import tarfile

from fastapi.testclient import TestClient

from app.executor import AristotleSdkProofAdapter
from app.config import Settings
from app.main import create_app
from app.schemas import (
    ApprovedExecutionPlan,
    BridgePlan,
    CampaignCreate,
    DistilledWorld,
    FormalProbeDigestRequest,
    FormalObligationSpec,
    FormalProbe,
    InventionBatchCreate,
    PendingAristotleJob,
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


def test_final_collatz_experiment_compiles_decisive_hard_probes(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    client = TestClient(app)
    campaign_id = _create_campaign(client)
    run_response = client.post(
        f"/api/campaigns/{campaign_id}/world-evolution/run",
        json={
            "generations": 1,
            "worlds_per_generation": 10,
            "survivors_per_generation": 4,
            "mutations_per_survivor": 2,
            "wildness": "extreme",
            "max_formal_probes_per_generation": 4,
            "max_evidence_probes_per_generation": 4,
            "promote_best_survivor": True,
        },
    )
    assert run_response.status_code == 200

    response = client.post(
        f"/api/campaigns/{campaign_id}/world-evolution/final-collatz-experiment",
        json={
            "max_hard_probes": 6,
            "include_control_probes": True,
            "submit_after_compile": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision_status"] == "ready_to_run"
    assert payload["compiled_probe_count"] >= 8
    assert payload["hard_probe_count"] >= 6
    assert payload["decisive_probe_ids"]
    assert any("Pivot if" in item for item in payload["kill_criteria"])
    assert any("Pursue if" in item for item in payload["pursue_criteria"])

    brief = client.get(f"/api/campaigns/{campaign_id}/operator-brief").json()
    assert brief["final_experiment"]["latest_run_id"] == payload["id"]
    assert brief["final_experiment"]["decisive_probe_count"] >= 1

    bake = client.post(
        f"/api/campaigns/{campaign_id}/world-evolution/bake-probes",
        json={
            "world_id": payload["world_id"],
            "max_probes": payload["compiled_probe_count"],
            "submit_all_at_once": True,
        },
    ).json()
    assert bake["submitted_probe_count"] == payload["compiled_probe_count"]
    brief_after_bake = client.get(f"/api/campaigns/{campaign_id}/operator-brief").json()
    assert brief_after_bake["final_experiment"]["submitted_probe_count"] == payload["compiled_probe_count"]


def test_rank_certificate_hunt_compiles_decisive_probes(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    client = TestClient(app)
    campaign_id = _create_campaign(client)
    run_response = client.post(
        f"/api/campaigns/{campaign_id}/world-evolution/run",
        json={
            "generations": 1,
            "worlds_per_generation": 10,
            "survivors_per_generation": 4,
            "mutations_per_survivor": 2,
            "wildness": "extreme",
            "max_formal_probes_per_generation": 4,
            "max_evidence_probes_per_generation": 4,
            "promote_best_survivor": True,
        },
    )
    assert run_response.status_code == 200

    response = client.post(
        f"/api/campaigns/{campaign_id}/world-evolution/rank-certificate-hunt",
        json={
            "max_probes": 8,
            "include_naive_rank_falsifiers": True,
            "submit_after_compile": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["compiled_probe_count"] >= 6
    assert payload["decisive_probe_ids"]
    assert any("non-circular" in item for item in payload["expected_learning"])


def test_candidate_rank_family_hunt_compiles_concrete_falsifiers(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    client = TestClient(app)
    campaign_id = _create_campaign(client)
    run_response = client.post(
        f"/api/campaigns/{campaign_id}/world-evolution/run",
        json={
            "generations": 1,
            "worlds_per_generation": 10,
            "survivors_per_generation": 4,
            "mutations_per_survivor": 2,
            "wildness": "extreme",
            "max_formal_probes_per_generation": 4,
            "max_evidence_probes_per_generation": 4,
            "promote_best_survivor": True,
        },
    )
    assert run_response.status_code == 200

    response = client.post(
        f"/api/campaigns/{campaign_id}/world-evolution/candidate-rank-families",
        json={
            "max_probes": 8,
            "submit_after_compile": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["compiled_probe_count"] >= 6
    assert "identity rank" in payload["candidate_families"]
    assert any("small witnesses" in item for item in payload["expected_learning"])


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


def test_bake_formal_probes_submits_compiled_probe_jobs(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    client = TestClient(app)
    campaign_id = _create_campaign(client)

    run_response = client.post(
        f"/api/campaigns/{campaign_id}/world-evolution/run",
        json={
            "generations": 1,
            "worlds_per_generation": 8,
            "survivors_per_generation": 3,
            "mutations_per_survivor": 1,
            "wildness": "high",
            "max_formal_probes_per_generation": 6,
            "max_evidence_probes_per_generation": 4,
            "promote_best_survivor": True,
        },
    )
    assert run_response.status_code == 200

    bake_response = client.post(
        f"/api/campaigns/{campaign_id}/world-evolution/bake-probes",
        json={
            "max_probes": 6,
            "submit_all_at_once": True,
        },
    )

    assert bake_response.status_code == 200
    bake = bake_response.json()
    assert bake["submitted_probe_count"] == 6
    assert bake["pending_job_count"] == 6
    assert len(bake["probe_ids"]) == 6

    campaign = client.get(f"/api/campaigns/{campaign_id}").json()
    assert len(campaign["pending_aristotle_jobs"]) == 6
    assert all(job["debt_id"].startswith("FP-") for job in campaign["pending_aristotle_jobs"])

    service = app.state.service
    submitted_probes = service.memory.list_research_nodes(
        campaign_id,
        node_type="FormalProbe",
        limit=20,
    )
    assert len([node for node in submitted_probes if node.status == "submitted"]) == 6


def test_digest_formal_probe_results_extracts_repair_instruction(tmp_path: Path) -> None:
    service = CampaignService(_settings(tmp_path))
    campaign = service.create_campaign(
        CampaignCreate(
            title="Digest",
            problem_statement="Digest Aristotle errors.",
            auto_run=False,
        )
    )
    result_dir = tmp_path / "data" / "aristotle_results"
    result_dir.mkdir(parents=True)
    lean_file = tmp_path / "Main.lean"
    lean_file.write_text(
        "theorem bad_probe : True := by\n"
        "  exact False.elim\n"
        "-- error: application type mismatch\n"
    )
    tar_path = result_dir / "probe.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(lean_file, arcname="Main.lean")

    probe = FormalProbe(
        world_id="W-digest",
        probe_type="definition_probe",
        source_text="Can a probe be represented?",
        formal_obligation=FormalObligationSpec(
            source_text="Can a probe be represented?",
            lean_declaration="theorem digest_probe : True := by\n  trivial\n",
        ),
        status="blocked",
        result_status="blocked",
        failure_type="partial_proof",
        artifact_paths=[str(tar_path)],
    )
    service.memory.upsert_research_node(
        campaign_id=campaign.id,
        node_id=probe.id,
        node_type="FormalProbe",
        title="probe",
        summary=probe.source_text,
        status=probe.status,
        payload=probe.model_dump(mode="json"),
    )

    digest = service.digest_formal_probe_results(
        campaign.id,
        payload=FormalProbeDigestRequest(max_artifacts=10),
    )

    assert digest.artifact_count == 1
    assert digest.probe_count == 1
    assert "lean_compile_error" in digest.top_failure_modes
    assert digest.repair_instructions
    updated = service.memory.get_research_node(campaign.id, probe.id)
    assert updated is not None
    assert updated.payload["diagnostics"]["failure_type"] == "lean_compile_error"


def test_digest_formal_probe_results_accepts_inline_aristotle_text(tmp_path: Path) -> None:
    service = CampaignService(_settings(tmp_path))
    campaign = service.create_campaign(
        CampaignCreate(
            title="Inline digest",
            problem_statement="Digest inline Aristotle diagnostics.",
            auto_run=False,
        )
    )
    probe = FormalProbe(
        world_id="W-inline",
        probe_type="definition_probe",
        source_text="Can inline diagnostics be represented?",
        formal_obligation=FormalObligationSpec(
            source_text="Can inline diagnostics be represented?",
            lean_declaration="theorem inline_probe : True := by\n  trivial\n",
        ),
        status="blocked",
        result_status="blocked",
        failure_type="partial_proof",
        artifact_paths=["--- Main.lean ---\n-- error: unknown identifier 'stateGlyph'\n"],
    )
    service.memory.upsert_research_node(
        campaign_id=campaign.id,
        node_id=probe.id,
        node_type="FormalProbe",
        title="probe",
        summary=probe.source_text,
        status=probe.status,
        payload=probe.model_dump(mode="json"),
    )

    digest = service.digest_formal_probe_results(
        campaign.id,
        payload=FormalProbeDigestRequest(max_artifacts=10),
    )

    assert digest.artifact_count == 1
    assert digest.probe_count == 1
    assert "lean_compile_error" in digest.top_failure_modes
    assert digest.diagnostics[0]["lean_error_excerpt"]


def test_digest_formal_probe_results_can_recover_by_project_id(tmp_path: Path) -> None:
    service = CampaignService(_settings(tmp_path))
    campaign = service.create_campaign(
        CampaignCreate(
            title="Recover digest",
            problem_statement="Recover old Aristotle artifact by project id.",
            auto_run=False,
        )
    )
    probe = FormalProbe(
        world_id="W-recover",
        probe_type="definition_probe",
        source_text="Can missing artifacts be recovered?",
        formal_obligation=FormalObligationSpec(
            source_text="Can missing artifacts be recovered?",
            lean_declaration="theorem recover_probe : True := by\n  trivial\n",
        ),
        status="blocked",
        result_status="blocked",
        failure_type="partial_proof",
    )
    service.memory.upsert_research_node(
        campaign_id=campaign.id,
        node_id=probe.id,
        node_type="FormalProbe",
        title="probe",
        summary=probe.source_text,
        status=probe.status,
        payload=probe.model_dump(mode="json"),
    )
    service.memory.add_event(
        campaign_id=campaign.id,
        tick=0,
        event_type="aristotle_job_completed",
        payload={
            "project_id": "project-recover",
            "debt_id": probe.id,
            "artifacts": [],
        },
    )

    service.executor.download_aristotle_result_artifacts = lambda project_id: [
        "--- Main.lean ---\n-- error: unknown module prefix 'Mathlib.Experimental'\n"
    ]

    digest = service.digest_formal_probe_results(
        campaign.id,
        payload=FormalProbeDigestRequest(
            max_artifacts=10,
            redownload_missing_artifacts=True,
        ),
    )

    assert digest.probe_count == 1
    assert "missing_import_or_dependency" in digest.top_failure_modes
    assert "imports" in " ".join(digest.repair_instructions).lower()
    assert digest.diagnostics[0]["result_status"] == "blocked"


def test_digest_reconciles_pending_probe_jobs_by_project_id(tmp_path: Path) -> None:
    service = CampaignService(_settings(tmp_path))
    campaign = service.create_campaign(
        CampaignCreate(
            title="Pending digest",
            problem_statement="Recover pending Aristotle artifact by project id.",
            auto_run=False,
        )
    )
    probe = FormalProbe(
        world_id="W-pending",
        probe_type="definition_probe",
        source_text="Can pending project refs be digested?",
        formal_obligation=FormalObligationSpec(
            source_text="Can pending project refs be digested?",
            lean_declaration="theorem pending_probe : True := by\n  trivial\n",
        ),
        status="submitted",
        result_status="running",
    )
    service.memory.upsert_research_node(
        campaign_id=campaign.id,
        node_id=probe.id,
        node_type="FormalProbe",
        title="probe",
        summary=probe.source_text,
        status=probe.status,
        payload=probe.model_dump(mode="json"),
    )
    pending = PendingAristotleJob(
        project_id="project-pending",
        target_frontier_node=f"probe:{probe.id}",
        world_family="bridge",
        bounded_claim=probe.source_text,
        debt_id=probe.id,
        obligation_text=probe.source_text,
        submitted_at=datetime.now(timezone.utc),
        status="running",
        decision_snapshot={},
        plan_snapshot=ApprovedExecutionPlan(
            approved_proof_jobs=[probe.source_text],
        ).model_dump(mode="json"),
        lean_code=probe.formal_obligation.lean_declaration,
    )
    service._set_pending_jobs(campaign, [pending])
    service._persist_campaign(campaign)
    service.executor.download_aristotle_result_artifacts = lambda project_id: [
        "--- Main.lean ---\ntheorem pending_probe : True := by\n  trivial\n"
    ]

    digest = service.digest_formal_probe_results(
        campaign.id,
        payload=FormalProbeDigestRequest(
            max_artifacts=10,
            redownload_missing_artifacts=True,
        ),
    )

    assert digest.proved_count == 1
    assert digest.reconciled_pending_job_count == 1
    updated_campaign = service.get_campaign(campaign.id)
    assert updated_campaign.pending_aristotle_jobs == []
    updated_probe = service.memory.get_research_node(campaign.id, probe.id)
    assert updated_probe is not None
    assert updated_probe.status == "proved"


def test_digest_does_not_mark_submission_failed_project_as_proved(tmp_path: Path) -> None:
    service = CampaignService(_settings(tmp_path))
    campaign = service.create_campaign(
        CampaignCreate(
            title="Submission failed digest",
            problem_statement="Do not recover fake submission ids as proof.",
            auto_run=False,
        )
    )
    probe = FormalProbe(
        world_id="W-failed-submit",
        probe_type="definition_probe",
        source_text="Submission never reached Aristotle.",
        formal_obligation=FormalObligationSpec(
            source_text="Submission never reached Aristotle.",
            lean_declaration="theorem failed_submit_probe : True := by\n  trivial\n",
        ),
        status="inconclusive",
        result_status="inconclusive",
        failure_type="sdk_error",
    )
    service.memory.upsert_research_node(
        campaign_id=campaign.id,
        node_id=probe.id,
        node_type="FormalProbe",
        title="probe",
        summary=probe.source_text,
        status=probe.status,
        payload=probe.model_dump(mode="json"),
    )
    service.memory.add_event(
        campaign_id=campaign.id,
        tick=0,
        event_type="aristotle_job_completed",
        payload={
            "project_id": "submission-failed-C-test-0",
            "debt_id": probe.id,
            "artifacts": [],
        },
    )

    digest = service.digest_formal_probe_results(
        campaign.id,
        payload=FormalProbeDigestRequest(
            max_artifacts=10,
            redownload_missing_artifacts=True,
        ),
    )

    assert digest.proved_count == 0
    assert digest.inconclusive_count == 1
    assert "artifact_missing" in digest.top_failure_modes


def test_aristotle_status_conversion_normalizes_uppercase_complete_with_errors() -> None:
    result = AristotleSdkProofAdapter(
        Settings(executor_backend="aristotle", aristotle_api_key="fake")
    )._convert_terminal_status_to_result(
        "COMPLETE_WITH_ERRORS",
        "project-1",
        None,
        plan=ApprovedExecutionPlan(),
    )

    assert result.status == "blocked"
    assert result.failure_type == "partial_proof"


def test_aristotle_complete_with_errors_persists_diagnostic_text(tmp_path: Path) -> None:
    lean_file = tmp_path / "Main.lean"
    lean_file.write_text("-- error: application type mismatch\n", encoding="utf-8")
    tar_path = tmp_path / "result.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(lean_file, arcname="Main.lean")

    result = AristotleSdkProofAdapter(
        Settings(executor_backend="aristotle", aristotle_api_key="fake")
    )._convert_terminal_status_to_result(
        "COMPLETE_WITH_ERRORS",
        "project-1",
        str(tar_path),
        plan=ApprovedExecutionPlan(),
    )

    assert result.status == "blocked"
    assert str(tar_path) in result.artifacts
    assert any("application type mismatch" in artifact for artifact in result.artifacts)
