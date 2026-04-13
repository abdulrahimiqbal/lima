from __future__ import annotations

import asyncio
import logging
import os
import re
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any, Protocol

import requests

from .config import Settings
from .schemas import (
    ApprovedExecutionPlan,
    CampaignRecord,
    ExecutionResult,
    FrontierNode,
    ManagerDecision,
)

logger = logging.getLogger(__name__)


class ProofAdapter(Protocol):
    name: str

    def run_proof(
        self,
        campaign: CampaignRecord,
        decision: ManagerDecision,
        plan: ApprovedExecutionPlan,
        timeout_seconds: int,
    ) -> ExecutionResult: ...

    def check_connectivity(self, *, strict_live_probe: bool) -> dict[str, Any]: ...


class MockProofAdapter:
    name = "mock"

    def run_proof(
        self,
        campaign: CampaignRecord,
        decision: ManagerDecision,
        plan: ApprovedExecutionPlan,
        timeout_seconds: int,
    ) -> ExecutionResult:
        target = next(
            (node for node in campaign.frontier if node.id == decision.target_frontier_node),
            None,
        )
        if not target:
            return ExecutionResult(
                status="inconclusive",
                failure_type="node_not_found",
                notes=f"Target node {decision.target_frontier_node} not found in frontier.",
                executor_backend=self.name,
            )

        artifacts = [f"world_family:{decision.world_family}", f"target:{target.id}"]
        if decision.world_family == "finite_check":
            bound = _extract_bound(decision.bounded_claim.lower())
            if bound is not None:
                return ExecutionResult(
                    status="inconclusive",
                    failure_type="evidence_only",
                    notes="Mock mode recorded bounded evidence only; no formal proof verdict is produced.",
                    artifacts=artifacts + [f"bounded_scope:{bound}"],
                    executor_backend=self.name,
                )
            return ExecutionResult(
                status="blocked",
                failure_type="too_big",
                notes="Finite check requested without a clear bound.",
                artifacts=artifacts,
                executor_backend=self.name,
                spawned_nodes=[
                    FrontierNode(
                        text=f"Define an explicit bounded finite check for: {target.text}",
                        status="open",
                        priority=max(0.2, target.priority - 0.1),
                        parent_id=target.id,
                        kind="finite_check",
                    )
                ],
            )

        if decision.world_family == "bridge":
            return ExecutionResult(
                status="blocked",
                failure_type="missing_lemma",
                notes="Bridge approach requires a sharper intermediate lemma in mock mode.",
                artifacts=artifacts,
                executor_backend=self.name,
            )

        return ExecutionResult(
            status="inconclusive",
            failure_type="mock_no_formal_verdict",
            notes="Mock mode does not produce proved/refuted outcomes.",
            artifacts=artifacts,
            executor_backend=self.name,
        )

    def check_connectivity(self, *, strict_live_probe: bool) -> dict[str, Any]:
        return {
            "status": "skipped",
            "reason": "mock_executor_selected",
            "limitations": "No live Aristotle connectivity in mock mode.",
        }


class AristotleSdkProofAdapter:
    name = "aristotle_sdk"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run_proof(
        self,
        campaign: CampaignRecord,
        decision: ManagerDecision,
        plan: ApprovedExecutionPlan,
        timeout_seconds: int,
    ) -> ExecutionResult:
        if not self.settings.aristotle_api_key:
            return ExecutionResult(
                status="inconclusive",
                failure_type="executor_unavailable",
                notes="ARISTOTLE_API_KEY is missing.",
                executor_backend="aristotle",
            )

        proof_obligation = plan.approved_proof_jobs[0]
        lean_code = self._obligations_to_lean(campaign, decision, [proof_obligation])
        analyzed_map = {item.text: item for item in plan.analyzed_obligations}

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(
                        self._run_aristotle_sync,
                        lean_code,
                        decision,
                        [proof_obligation],
                        analyzed_map,
                        timeout_seconds,
                    ).result(timeout=timeout_seconds)
        except RuntimeError:
            pass

        return asyncio.run(
            self._run_aristotle_async(
                lean_code,
                decision,
                [proof_obligation],
                analyzed_map,
                timeout_seconds,
            )
        )

    def check_connectivity(self, *, strict_live_probe: bool) -> dict[str, Any]:
        if not self.settings.aristotle_api_key:
            return {"status": "disconnected", "reason": "no ARISTOTLE_API_KEY"}
        try:
            os.environ["ARISTOTLE_API_KEY"] = self.settings.aristotle_api_key
            import aristotlelib  # noqa: F401
        except ImportError:
            return {"status": "disconnected", "error": "aristotlelib not installed"}
        except Exception as exc:
            return {"status": "disconnected", "error": str(exc)}

        if not strict_live_probe:
            return {
                "status": "connected",
                "adapter": self.name,
                "probe": "sdk_import",
                "limitations": "No remote verification round-trip performed.",
            }

        if not self.settings.aristotle_base_url:
            return {
                "status": "disconnected",
                "error": "strict_live_probe_requires_aristotle_base_url",
            }
        probe_url = self.settings.aristotle_base_url.rstrip("/") + "/healthz"
        try:
            response = requests.get(
                probe_url,
                headers={"Authorization": f"Bearer {self.settings.aristotle_api_key}"},
                timeout=min(10, self.settings.aristotle_timeout_seconds),
            )
        except requests.RequestException as exc:
            return {"status": "disconnected", "error": f"probe_failed:{exc}"}

        if response.status_code >= 500:
            return {
                "status": "disconnected",
                "error": f"probe_server_error:{response.status_code}",
            }
        return {
            "status": "connected",
            "adapter": self.name,
            "probe": "http_healthz",
            "probe_status_code": response.status_code,
            "limitations": "Probe checks reachability/auth path, not a full theorem verification run.",
        }

    def _run_aristotle_sync(
        self,
        lean_code: str,
        decision: ManagerDecision,
        obligations: list[str],
        analyzed_map: dict[str, Any],
        timeout_seconds: int,
    ) -> ExecutionResult:
        return asyncio.run(
            self._run_aristotle_async(
                lean_code, decision, obligations, analyzed_map, timeout_seconds
            )
        )

    async def _run_aristotle_async(
        self,
        lean_code: str,
        decision: ManagerDecision,
        obligations: list[str],
        analyzed_map: dict[str, Any],
        timeout_seconds: int,
    ) -> ExecutionResult:
        os.environ["ARISTOTLE_API_KEY"] = self.settings.aristotle_api_key or ""
        try:
            from aristotlelib import Project, ProjectStatus
        except ImportError:
            return ExecutionResult(
                status="inconclusive",
                failure_type="sdk_missing",
                notes="aristotlelib is not installed.",
                executor_backend="aristotle",
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "lean_project"
            project_dir.mkdir(parents=True, exist_ok=True)
            input_path = project_dir / "Main.lean"
            result_tar = Path(tmpdir) / "aristotle_result.tar.gz"
            input_path.write_text(lean_code)
            prompt = "\n".join(
                [
                    "Fill in all Lean sorries in this project.",
                    "Preserve theorem names where possible.",
                    f"World family: {decision.world_family}",
                    f"Bounded claim: {decision.bounded_claim}",
                ]
            )
            try:
                project = await Project.create_from_directory(
                    prompt=prompt, project_dir=project_dir
                )
                await asyncio.wait_for(
                    project.wait_for_completion(
                        destination=result_tar, polling_interval_seconds=10
                    ),
                    timeout=timeout_seconds,
                )
                await project.refresh()
                if project.status == ProjectStatus.COMPLETE:
                    extracted = self._extract_lean_from_tar(result_tar)
                    if extracted and "sorry" in extracted.lower():
                        return ExecutionResult(
                            status="blocked",
                            failure_type="partial_proof",
                            notes=f"Aristotle completed {project.project_id}, but output still contains sorry.",
                            artifacts=[extracted[:2000]],
                            executor_backend="aristotle",
                        )
                    return ExecutionResult(
                        status="proved",
                        notes=f"Aristotle completed project {project.project_id}.",
                        artifacts=[extracted[:2000]] if extracted else [str(result_tar)],
                        executor_backend="aristotle",
                    )
                if project.status == ProjectStatus.COMPLETE_WITH_ERRORS:
                    return ExecutionResult(
                        status="blocked",
                        failure_type="partial_proof",
                        notes=f"Aristotle completed project {project.project_id} with errors.",
                        artifacts=[str(result_tar)] if result_tar.exists() else [],
                        executor_backend="aristotle",
                    )
                if project.status == ProjectStatus.OUT_OF_BUDGET:
                    return ExecutionResult(
                        status="inconclusive",
                        failure_type="budget_exhausted",
                        notes=f"Aristotle project {project.project_id} ran out of budget.",
                        artifacts=[str(result_tar)] if result_tar.exists() else [],
                        executor_backend="aristotle",
                    )
                if project.status == ProjectStatus.FAILED:
                    return ExecutionResult(
                        status="refuted",
                        failure_type="proof_failed",
                        notes=f"Aristotle project {project.project_id} failed.",
                        artifacts=[str(result_tar)] if result_tar.exists() else [],
                        executor_backend="aristotle",
                    )
                if project.status == ProjectStatus.CANCELED:
                    return ExecutionResult(
                        status="inconclusive",
                        failure_type="canceled",
                        notes=f"Aristotle project {project.project_id} was canceled.",
                        artifacts=[str(result_tar)] if result_tar.exists() else [],
                        executor_backend="aristotle",
                    )
                return ExecutionResult(
                    status="inconclusive",
                    failure_type="inconclusive",
                    notes=f"Aristotle finished with status {project.status.value}.",
                    artifacts=[str(result_tar)] if result_tar.exists() else [],
                    executor_backend="aristotle",
                )
            except asyncio.TimeoutError:
                return ExecutionResult(
                    status="inconclusive",
                    failure_type=self._timeout_failure_type(obligations, analyzed_map),
                    notes=f"Aristotle timed out after {timeout_seconds}s.",
                    executor_backend="aristotle",
                )
            except Exception as exc:
                error = str(exc)
                if "FAILED" in error.upper():
                    return ExecutionResult(
                        status="refuted",
                        failure_type="proof_failed",
                        notes=f"Aristotle could not find a proof: {error}",
                        executor_backend="aristotle",
                    )
                return ExecutionResult(
                    status="inconclusive",
                    failure_type="sdk_error",
                    notes=f"Aristotle SDK error: {error}",
                    executor_backend="aristotle",
                )

    @staticmethod
    def _extract_lean_from_tar(tar_path: Path) -> str | None:
        if not tar_path.exists():
            return None
        try:
            with tarfile.open(tar_path, "r:*") as tar:
                for member in tar.getmembers():
                    if member.isfile() and member.name.endswith(".lean"):
                        extracted = tar.extractfile(member)
                        if extracted is None:
                            continue
                        content = extracted.read().decode("utf-8", errors="ignore")
                        if content.strip():
                            return content
        except (tarfile.TarError, OSError):
            return None
        return None

    @staticmethod
    def _timeout_failure_type(obligations: list[str], analyzed_map: dict[str, Any]) -> str:
        for obligation in obligations:
            meta = analyzed_map.get(obligation)
            if not meta:
                continue
            if meta.scope == "global" or meta.complexity_class in {"large", "unsafe"}:
                return "excessive_scope"
        return "timeout"

    @staticmethod
    def _obligations_to_lean(
        campaign: CampaignRecord,
        decision: ManagerDecision,
        obligations: list[str],
    ) -> str:
        lines = [
            "-- Auto-generated by LIMA Learning Platform",
            f"-- Campaign: {campaign.id}",
            f"-- World family: {decision.world_family}",
            f"-- Bounded claim: {decision.bounded_claim}",
            "",
        ]
        for i, obligation in enumerate(obligations):
            if any(
                kw in obligation
                for kw in ["theorem", "lemma", "def ", "example", "import"]
            ):
                lines.append(obligation)
            else:
                safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", obligation[:40])
                lines.append(f"theorem obligation_{i}_{safe_name} : True := by")
                lines.append(f"  -- Obligation: {obligation}")
                lines.append("  sorry")
            lines.append("")
        return "\n".join(lines)


class Executor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._proof_adapter = self._build_adapter(settings)
        logger.info("Executor using proof adapter=%s", self._proof_adapter.name)

    def _build_adapter(self, settings: Settings) -> ProofAdapter:
        if settings.executor_backend == "mock":
            return MockProofAdapter()
        if settings.executor_backend in {"aristotle", "http"}:
            # "http" is retained as a compatibility alias; execution path is SDK-backed.
            return AristotleSdkProofAdapter(settings)
        logger.warning(
            "Unknown executor_backend=%s, defaulting to mock adapter",
            settings.executor_backend,
        )
        return MockProofAdapter()

    def run(
        self,
        campaign: CampaignRecord,
        decision: ManagerDecision,
        plan: ApprovedExecutionPlan,
    ) -> ExecutionResult:
        started = time.perf_counter()
        executed_proof_jobs: list[str] = []
        executed_evidence_jobs: list[str] = []

        if plan.approved_proof_jobs:
            result = self._proof_adapter.run_proof(
                campaign,
                decision,
                plan,
                timeout_seconds=self.settings.aristotle_timeout_seconds,
            )
            executed_proof_jobs = plan.approved_proof_jobs[:1]
        elif plan.approved_evidence_jobs:
            result = self._run_computational_evidence(campaign, decision, plan)
            executed_evidence_jobs = plan.approved_evidence_jobs
        else:
            result = ExecutionResult(
                status="blocked",
                failure_type="excessive_scope",
                notes="No approved jobs in execution plan.",
                executor_backend="gate",
            )

        elapsed = int((time.perf_counter() - started) * 1000)
        return self._attach_plan_metadata(
            result,
            plan,
            elapsed,
            executed_proof_jobs=executed_proof_jobs,
            executed_evidence_jobs=executed_evidence_jobs,
        )

    def check_connectivity(self, *, strict_live_probe: bool = False) -> dict[str, Any]:
        return self._proof_adapter.check_connectivity(strict_live_probe=strict_live_probe)

    def _run_computational_evidence(
        self,
        campaign: CampaignRecord,
        decision: ManagerDecision,
        plan: ApprovedExecutionPlan,
    ) -> ExecutionResult:
        artifacts: list[str] = []
        for obligation in plan.approved_evidence_jobs:
            obligation_lower = obligation.lower()
            bound = _extract_bound(obligation_lower)
            if bound is not None:
                artifacts.append(f"evidence_bound:{bound}")
            artifacts.append(f"evidence_job:{obligation[:180]}")
        return ExecutionResult(
            status="inconclusive",
            failure_type="evidence_only",
            notes="Computed bounded evidence jobs locally. Evidence is not a formal proof verdict.",
            artifacts=artifacts,
            executor_backend="evidence",
        )

    def _attach_plan_metadata(
        self,
        result: ExecutionResult,
        plan: ApprovedExecutionPlan,
        elapsed_ms: int,
        *,
        executed_proof_jobs: list[str],
        executed_evidence_jobs: list[str],
    ) -> ExecutionResult:
        result.original_obligations = plan.original_obligations
        result.analyzed_obligations = [item.model_dump() for item in plan.analyzed_obligations]
        result.approved_proof_jobs = executed_proof_jobs
        result.approved_evidence_jobs = executed_evidence_jobs
        result.rejected_obligations = plan.rejected_obligations
        result.approved_jobs_count = len(executed_proof_jobs) + len(executed_evidence_jobs)
        result.rejected_jobs_count = len(plan.rejected_obligations)
        if executed_proof_jobs:
            result.channel_used = "aristotle_proof"
        elif executed_evidence_jobs:
            result.channel_used = "computational_evidence"
        else:
            result.channel_used = "none"
        result.timing_ms = elapsed_ms
        if plan.rejected_reasons and "rejected_reasons" not in result.raw:
            result.raw["rejected_reasons"] = plan.rejected_reasons
        return result

    def _timeout_failure_type(self, obligations: list[str], analyzed_map: dict[str, Any]) -> str:
        return AristotleSdkProofAdapter._timeout_failure_type(obligations, analyzed_map)


def _extract_bound(text: str) -> int | None:
    match = re.search(r"(<=|≤|up to|at most)\s*(\d+)", text)
    if not match:
        return None
    try:
        return int(match.group(2))
    except ValueError:
        return None
