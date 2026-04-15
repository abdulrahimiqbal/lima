from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.collatz_automaton import (
    analyze_dynamic_pressure_automaton,
    analyze_height_lifted_pressure_automaton,
)
from app.config import Settings
from app.schemas import (
    CampaignCreate,
    DynamicPressureAutomatonWaveRequest,
    FormalProbeBakeRequest,
    FormalProbeDigestRequest,
)
from app.service import CampaignService


WORLD_ID = "W-0273193499"
DEFAULT_MEMORY_PATH = "/tmp/lima_dynamic_pressure_automaton/lima_memory.db"
POLL_SECONDS = 20


def emit(label: str, payload: object) -> None:
    print(json.dumps({label: payload}, indent=2, default=str), flush=True)


def build_service() -> CampaignService:
    api_key = os.environ.get("ARISTOTLE_API_KEY")
    if not api_key:
        raise SystemExit("ARISTOTLE_API_KEY is required for submit/poll mode")
    memory_path = Path(os.environ.get("DYNAMIC_PRESSURE_MEMORY_PATH", DEFAULT_MEMORY_PATH))
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    return CampaignService(
        Settings(
            executor_backend="aristotle",
            aristotle_api_key=api_key,
            aristotle_timeout_seconds=180,
            memory_db_path=str(memory_path),
            worker_poll_seconds=5,
        )
    )


def main() -> None:
    mode = os.environ.get("DYNAMIC_PRESSURE_MODE", "local")
    max_window = int(os.environ.get("DYNAMIC_PRESSURE_MAX_WINDOW", "6"))
    extra_bits = int(os.environ.get("DYNAMIC_PRESSURE_EXTRA_BITS", "4"))
    max_probes = int(os.environ.get("DYNAMIC_PRESSURE_MAX_PROBES", "8"))

    if mode == "local":
        run_local(max_window=max_window, extra_bits=extra_bits)
        return

    service = build_service()
    campaign_id = os.environ.get("DYNAMIC_PRESSURE_CAMPAIGN_ID")
    if mode == "submit":
        submit(service, campaign_id, max_window=max_window, extra_bits=extra_bits, max_probes=max_probes)
        return
    if mode == "poll":
        if not campaign_id:
            raise SystemExit("DYNAMIC_PRESSURE_CAMPAIGN_ID is required for poll mode")
        poll_to_empty(service, campaign_id)
        digest(service, campaign_id)
        return
    raise SystemExit(f"Unsupported DYNAMIC_PRESSURE_MODE={mode!r}; use local, submit, or poll")


def run_local(*, max_window: int, extra_bits: int) -> None:
    reports = [
        analyze_dynamic_pressure_automaton(
            window=window,
            modulus_bits=max(2, window + extra_bits),
        )
        for window in range(1, max_window + 1)
    ]
    height_reports = [
        analyze_height_lifted_pressure_automaton(
            window=window,
            modulus_bits=max(2, window + extra_bits),
        )
        for window in range(1, max_window + 1)
    ]
    emit(
        "local_reports",
        [
            {
                "window": report["window"],
                "modulus_bits": report["modulus_bits"],
                "state_count": report["state_count"],
                "edge_count": report["edge_count"],
                "cycle_found": report["cycle_found"],
                "ghost_family": report["ghost_family"],
                "certificate": report["certificate"],
                "interpretation": report["interpretation"],
            }
            for report in reports
        ],
    )
    emit(
        "height_lift_reports",
        [
            {
                "window": report["window"],
                "modulus_bits": report["modulus_bits"],
                "state_count": report["state_count"],
                "edge_count": report["edge_count"],
                "recurrent_component_count": report["recurrent_component_count"],
                "height_expanding_component_count": report["height_expanding_component_count"],
                "dangerous_component_count": report["dangerous_component_count"],
                "unchecked_component_count": report["unchecked_component_count"],
                "decision": report["decision"],
                "components": report["components"],
                "interpretation": report["interpretation"],
            }
            for report in height_reports
        ],
    )


def submit(
    service: CampaignService,
    campaign_id: str | None,
    *,
    max_window: int,
    extra_bits: int,
    max_probes: int,
) -> None:
    if campaign_id:
        try:
            campaign = service.get_campaign(campaign_id)
        except KeyError:
            campaign = create_campaign(service)
    else:
        campaign = create_campaign(service)
    campaign_id = campaign.id

    run = service.run_dynamic_pressure_automaton_wave(
        campaign_id,
        DynamicPressureAutomatonWaveRequest(
            world_id=WORLD_ID,
            max_window=max_window,
            modulus_extra_bits=extra_bits,
            max_probes=max_probes,
            submit_after_compile=False,
        ),
    )
    emit(
        "compiled",
        {
            "campaign_id": campaign_id,
            "run_id": run.id,
            "world_id": run.world_id,
            "compiled_probe_count": run.compiled_probe_count,
            "decisive_probe_ids": run.decisive_probe_ids,
            "obstruction_summary": run.obstruction_summary,
            "height_gate_summary": run.height_gate_summary,
            "reports": run.automaton_reports,
            "height_lift_reports": run.height_lift_reports,
        },
    )

    bake = service.bake_formal_probes(
        campaign_id,
        FormalProbeBakeRequest(
            world_id=WORLD_ID,
            max_probes=max_probes,
            submit_all_at_once=True,
            retry_failed_submissions=False,
        ),
    )
    emit(
        "submitted",
        {
            "bake_run_id": bake.id,
            "status": bake.status,
            "submitted_probe_count": bake.submitted_probe_count,
            "pending_job_count": bake.pending_job_count,
            "probe_ids": bake.probe_ids,
            "project_ids": bake.project_ids,
        },
    )


def create_campaign(service: CampaignService):
    return service.create_campaign(
        CampaignCreate(
            title="Local dynamic pressure automaton Aristotle run",
            problem_statement="Collatz dynamic-pressure automaton certificate and obstruction probe run.",
            operator_notes=[
                "Search-backed run; generated after the dynamic admissibility compass.",
                f"World id carried over from production campaign: {WORLD_ID}.",
            ],
            auto_run=False,
        )
    )


def poll_to_empty(service: CampaignService, campaign_id: str, max_polls: int = 50) -> None:
    last_pending = None
    for poll_index in range(max_polls):
        campaign = service.step_campaign(campaign_id)
        pending = [
            {
                "project_id": job.project_id,
                "status": job.status,
                "poll_count": job.poll_count,
                "debt_id": job.debt_id,
                "obligation_text": job.obligation_text,
            }
            for job in campaign.pending_aristotle_jobs
        ]
        pending_count = len(pending)
        if pending_count != last_pending or poll_index % 5 == 0:
            emit(
                "poll",
                {
                    "poll_index": poll_index,
                    "pending_count": pending_count,
                    "pending_jobs": pending,
                    "last_execution_result": campaign.last_execution_result,
                },
            )
            last_pending = pending_count
        if pending_count == 0:
            break
        time.sleep(POLL_SECONDS)


def digest(service: CampaignService, campaign_id: str) -> None:
    result = service.digest_formal_probe_results(
        campaign_id,
        FormalProbeDigestRequest(
            world_id=WORLD_ID,
            max_artifacts=220,
            attach_unmapped_artifacts=True,
            redownload_missing_artifacts=True,
        ),
    )
    emit(
        "digest",
        {
            "digest_id": result.id,
            "artifact_count": result.artifact_count,
            "probe_count": result.probe_count,
            "proved_count": result.proved_count,
            "blocked_count": result.blocked_count,
            "inconclusive_count": result.inconclusive_count,
            "reconciled_pending_job_count": result.reconciled_pending_job_count,
            "diagnostics": [
                {
                    "probe_id": diagnostic.probe_id,
                    "source_text": diagnostic.source_text,
                    "verdict": diagnostic.verdict,
                    "failure_type": diagnostic.failure_type,
                    "suggested_repair": diagnostic.suggested_repair,
                    "artifact_path": diagnostic.artifact_path,
                }
                for diagnostic in result.diagnostics
            ],
        },
    )


if __name__ == "__main__":
    main()
