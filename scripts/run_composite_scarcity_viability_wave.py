from __future__ import annotations

import json
import os
import time
from pathlib import Path

from app.config import Settings
from app.schemas import (
    CampaignCreate,
    CompositeScarcityViabilityWaveRequest,
    FormalProbeBakeRequest,
    FormalProbeDigestRequest,
)
from app.service import CampaignService


WORLD_ID = "W-0273193499"
POLL_SECONDS = 20


def emit(label: str, payload: object) -> None:
    print(json.dumps({label: payload}, indent=2, default=str), flush=True)


def main() -> None:
    api_key = os.environ.get("ARISTOTLE_API_KEY")
    if not api_key:
        raise SystemExit("ARISTOTLE_API_KEY is required")

    memory_path = Path("/tmp/lima_composite_scarcity_viability/lima_memory.db")
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    if memory_path.exists():
        memory_path.unlink()

    service = CampaignService(
        Settings(
            executor_backend="aristotle",
            aristotle_api_key=api_key,
            aristotle_timeout_seconds=180,
            memory_db_path=str(memory_path),
            worker_poll_seconds=5,
        )
    )
    campaign = service.create_campaign(
        CampaignCreate(
            title="Local composite scarcity viability Aristotle run",
            problem_statement="Collatz composite scarcity kill-or-promote probe run.",
            operator_notes=[
                "Disposable local run created because Railway deployment upload timed out.",
                f"World id carried over from production campaign: {WORLD_ID}.",
            ],
            auto_run=False,
        )
    )
    run = service.run_composite_scarcity_viability_wave(
        campaign.id,
        CompositeScarcityViabilityWaveRequest(
            world_id=WORLD_ID,
            max_probes=8,
            submit_after_compile=False,
        ),
    )
    emit(
        "compiled",
        {
            "campaign_id": campaign.id,
            "run_id": run.id,
            "world_id": run.world_id,
            "compiled_probe_count": run.compiled_probe_count,
            "decisive_probe_ids": run.decisive_probe_ids,
            "viability_gates": run.viability_gates,
        },
    )

    bake = service.bake_formal_probes(
        campaign.id,
        FormalProbeBakeRequest(
            world_id=WORLD_ID,
            max_probes=8,
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

    poll_to_empty(service, campaign.id)

    digest = service.digest_formal_probe_results(
        campaign.id,
        FormalProbeDigestRequest(
            world_id=WORLD_ID,
            max_artifacts=120,
            attach_unmapped_artifacts=True,
            redownload_missing_artifacts=True,
        ),
    )
    emit(
        "digest",
        {
            "digest_id": digest.id,
            "artifact_count": digest.artifact_count,
            "probe_count": digest.probe_count,
            "proved_count": digest.proved_count,
            "blocked_count": digest.blocked_count,
            "inconclusive_count": digest.inconclusive_count,
            "reconciled_pending_job_count": digest.reconciled_pending_job_count,
            "diagnostics": [
                {
                    "probe_id": item.get("probe_id"),
                    "probe_status": item.get("probe_status"),
                    "result_status": item.get("result_status"),
                    "failure_type": item.get("failure_type"),
                    "source_text": item.get("source_text"),
                    "remaining_sorry_count": item.get("remaining_sorry_count"),
                }
                for item in digest.diagnostics
                if isinstance(item, dict)
                and str(item.get("source_text", "")).startswith(
                    "Composite scarcity viability"
                )
            ],
        },
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


if __name__ == "__main__":
    main()
