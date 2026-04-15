from __future__ import annotations

import json
import os
from pathlib import Path

from app.config import Settings
from app.schemas import FormalProbe, FormalProbeBakeRequest
from app.service import CampaignService


WORLD_ID = "W-0273193499"
DEFAULT_CAMPAIGN_ID = "C-c99c9a92c421"
DEFAULT_MEMORY_PATH = "/tmp/lima_pivot_portfolio/lima_memory.db"


def emit(label: str, payload: object) -> None:
    print(json.dumps({label: payload}, indent=2, default=str), flush=True)


def main() -> None:
    api_key = os.environ.get("ARISTOTLE_API_KEY")
    if not api_key:
        raise SystemExit("ARISTOTLE_API_KEY is required")
    campaign_id = os.environ.get("PIVOT_CAMPAIGN_ID", DEFAULT_CAMPAIGN_ID)
    memory_path = os.environ.get("PIVOT_MEMORY_PATH", DEFAULT_MEMORY_PATH)
    submit_count = int(os.environ.get("PIVOT_SUBMIT_COUNT", "15"))
    if not Path(memory_path).exists():
        raise SystemExit(f"Memory db not found: {memory_path}")

    service = CampaignService(
        Settings(
            executor_backend="aristotle",
            aristotle_api_key=api_key,
            aristotle_timeout_seconds=180,
            memory_db_path=memory_path,
            worker_poll_seconds=5,
        )
    )

    nodes = service.memory.list_research_nodes(
        campaign_id,
        node_type="FormalProbe",
        limit=500,
    )
    missing: list[FormalProbe] = []
    for node in nodes:
        probe = FormalProbe.model_validate(node.payload)
        if not probe.formal_obligation.metadata.get("pivot_portfolio_wave"):
            continue
        if probe.status == "proved":
            continue
        missing.append(probe)

    selected = missing[:submit_count]
    for probe in selected:
        reset_probe = probe.model_copy(
            update={
                "status": "compiled",
                "result_status": None,
                "failure_type": None,
                "artifact_paths": [],
                "diagnostics": {},
                "repair_instruction": None,
            },
            deep=True,
        )
        service.memory.upsert_research_node(
            campaign_id=campaign_id,
            node_id=reset_probe.id,
            node_type="FormalProbe",
            title=f"pivot-portfolio:{reset_probe.probe_type}:{WORLD_ID}",
            summary=reset_probe.source_text,
            status=reset_probe.status,
            payload=reset_probe.model_dump(mode="json"),
        )

    emit(
        "requeued",
        {
            "campaign_id": campaign_id,
            "missing_count": len(missing),
            "selected_count": len(selected),
            "selected_probe_ids": [probe.id for probe in selected],
            "selected_source_text": [probe.source_text for probe in selected],
        },
    )

    bake = service.bake_formal_probes(
        campaign_id,
        FormalProbeBakeRequest(
            world_id=WORLD_ID,
            max_probes=submit_count,
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


if __name__ == "__main__":
    main()
