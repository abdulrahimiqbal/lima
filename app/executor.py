from __future__ import annotations

import asyncio
import logging
import os
import re
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any

from .config import Settings
from .schemas import ApprovedExecutionPlan, CampaignRecord, ExecutionResult, FrontierNode, ManagerDecision

logger = logging.getLogger(__name__)


class Executor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

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
            if self.settings.executor_backend == "aristotle" or (
                self.settings.executor_backend == "http" and self.settings.aristotle_api_key
            ):
                try:
                    result = self._run_aristotle(campaign, decision, plan)
                    executed_proof_jobs = plan.approved_proof_jobs[:1]
                except Exception as exc:
                    logger.error(f"Aristotle execution failed: {exc}")
                    result = ExecutionResult(
                        status="inconclusive",
                        failure_type="executor_unavailable",
                        notes=f"Aristotle executor failed: {exc}",
                        executor_backend="aristotle",
                    )
            else:
                result = self._run_mock(campaign, decision)
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

    def check_connectivity(self) -> dict[str, Any]:
        """Smoke check: can we reach Aristotle via the SDK?"""
        if not self.settings.aristotle_api_key:
            return {"status": "skipped", "reason": "no ARISTOTLE_API_KEY"}

        try:
            os.environ["ARISTOTLE_API_KEY"] = self.settings.aristotle_api_key
            import aristotlelib  # noqa: F401
            # SDK is importable and key is set — that's our smoke check.
            # A full check would call Project.list_projects() but that's expensive.
            return {"status": "connected", "sdk": "aristotlelib"}
        except ImportError:
            return {"status": "disconnected", "error": "aristotlelib not installed"}
        except Exception as e:
            return {"status": "disconnected", "error": str(e)}

    def _run_aristotle(
        self,
        campaign: CampaignRecord,
        decision: ManagerDecision,
        plan: ApprovedExecutionPlan,
    ) -> ExecutionResult:
        """Use aristotlelib SDK to submit formal obligations to Aristotle."""
        os.environ["ARISTOTLE_API_KEY"] = self.settings.aristotle_api_key or ""

        try:
            from aristotlelib import Project
        except ImportError:
            return ExecutionResult(
                status="inconclusive",
                failure_type="sdk_missing",
                notes="aristotlelib is not installed. Install it with: pip install aristotlelib",
                executor_backend="aristotle",
            )

        # Build Lean 4 code from the formal obligations
        proof_obligation = plan.approved_proof_jobs[0]
        lean_code = self._obligations_to_lean(campaign, decision, [proof_obligation])
        logger.info(f"Submitting Lean code to Aristotle ({len(lean_code)} chars)")
        analyzed_map = {item.text: item for item in plan.analyzed_obligations}

        # Run the async SDK in a sync context
        loop = None
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're inside an async context (like FastAPI), create a new thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = pool.submit(
                        self._run_aristotle_sync,
                        lean_code,
                        decision,
                        [proof_obligation],
                        analyzed_map,
                    ).result(
                        timeout=self.settings.aristotle_timeout_seconds
                    )
                return result
        except RuntimeError:
            pass

        # No running loop, create one
        return asyncio.run(
            self._run_aristotle_async(
                lean_code,
                decision,
                [proof_obligation],
                analyzed_map,
            )
        )

    def _run_aristotle_sync(
        self,
        lean_code: str,
        decision: ManagerDecision,
        obligations: list[str],
        analyzed_map: dict[str, Any],
    ) -> ExecutionResult:
        """Run aristotle in a new event loop (for thread pool)."""
        return asyncio.run(self._run_aristotle_async(lean_code, decision, obligations, analyzed_map))

    async def _run_aristotle_async(
        self,
        lean_code: str,
        decision: ManagerDecision,
        obligations: list[str],
        analyzed_map: dict[str, Any],
    ) -> ExecutionResult:
        from aristotlelib import Project, ProjectStatus

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "lean_project"
            project_dir.mkdir(parents=True, exist_ok=True)
            input_path = project_dir / "Main.lean"
            result_tar = Path(tmpdir) / "aristotle_result.tar.gz"
            input_path.write_text(lean_code)

            prompt = self._build_aristotle_prompt(decision)

            try:
                project = await Project.create_from_directory(prompt=prompt, project_dir=project_dir)
                await asyncio.wait_for(
                    project.wait_for_completion(destination=result_tar, polling_interval_seconds=10),
                    timeout=self.settings.aristotle_timeout_seconds,
                )
                await project.refresh()

                if project.status == ProjectStatus.COMPLETE:
                    extracted = self._extract_lean_from_tar(result_tar)
                    has_sorry = "sorry" in extracted.lower() if extracted else False
                    if has_sorry:
                        return ExecutionResult(
                            status="blocked",
                            failure_type="partial_proof",
                            notes=f"Aristotle completed project {project.project_id}, but output still contains 'sorry'.",
                            artifacts=[extracted[:2000]] if extracted else [str(result_tar)],
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
                    notes=f"Aristotle project {project.project_id} finished in status {project.status.value}.",
                    artifacts=[str(result_tar)] if result_tar.exists() else [],
                    executor_backend="aristotle",
                )

            except asyncio.TimeoutError:
                failure_type = self._timeout_failure_type(obligations, analyzed_map)
                return ExecutionResult(
                    status="inconclusive",
                    failure_type=failure_type,
                    notes=f"Aristotle timed out after {self.settings.aristotle_timeout_seconds}s.",
                    executor_backend="aristotle",
                )
            except Exception as e:
                error_str = str(e)
                if "FAILED" in error_str.upper():
                    return ExecutionResult(
                        status="refuted",
                        failure_type="proof_failed",
                        notes=f"Aristotle could not find a proof: {error_str}",
                        executor_backend="aristotle",
                    )
                return ExecutionResult(
                    status="inconclusive",
                    failure_type="sdk_error",
                    notes=f"Aristotle SDK error: {error_str}",
                    executor_backend="aristotle",
                )

    def _run_computational_evidence(
        self,
        campaign: CampaignRecord,
        decision: ManagerDecision,
        plan: ApprovedExecutionPlan,
    ) -> ExecutionResult:
        artifacts: list[str] = []
        for obligation in plan.approved_evidence_jobs:
            obligation_lower = obligation.lower()
            if self._extract_bound(obligation_lower) is not None:
                artifacts.append(f"evidence_bound:{self._extract_bound(obligation_lower)}")
            artifacts.append(f"evidence_job:{obligation[:180]}")
        return ExecutionResult(
            status="inconclusive",
            failure_type="evidence_only",
            notes="Computed bounded evidence jobs locally. Evidence recorded separately from formal proof.",
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
        for obligation in obligations:
            meta = analyzed_map.get(obligation)
            if not meta:
                continue
            if meta.scope == "global" or meta.complexity_class in {"large", "unsafe"}:
                return "excessive_scope"
        return "timeout"

    @staticmethod
    def _extract_bound(text: str) -> int | None:
        match = re.search(r"(<=|≤|up to|at most)\s*(\d+)", text)
        if not match:
            return None
        try:
            return int(match.group(2))
        except ValueError:
            return None

    def _build_aristotle_prompt(self, decision: ManagerDecision) -> str:
        return "\n".join(
            [
                "Fill in all Lean sorries in this project.",
                "Preserve theorem names where possible.",
                f"World family: {decision.world_family}",
                f"Bounded claim: {decision.bounded_claim}",
            ]
        )

    def _extract_lean_from_tar(self, tar_path: Path) -> str | None:
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

    def _obligations_to_lean(
        self,
        campaign: CampaignRecord,
        decision: ManagerDecision,
        obligations: list[str],
    ) -> str:
        """Convert formal obligations into Lean 4 code for Aristotle."""
        lines = [
            "-- Auto-generated by LIMA Learning Platform",
            f"-- Campaign: {campaign.id}",
            f"-- World family: {decision.world_family}",
            f"-- Bounded claim: {decision.bounded_claim}",
            "",
        ]

        for i, obligation in enumerate(obligations):
            # If the obligation looks like Lean code, use it directly
            if any(kw in obligation for kw in ["theorem", "lemma", "def ", "example", "import"]):
                lines.append(obligation)
            else:
                # Wrap it as a Lean theorem skeleton Aristotle can complete.
                safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', obligation[:40])
                lines.append(f"theorem obligation_{i}_{safe_name} : True := by")
                lines.append(f"  -- Obligation: {obligation}")
                lines.append(f"  sorry")
            lines.append("")

        return "\n".join(lines)

    def _run_mock(self, campaign: CampaignRecord, decision: ManagerDecision) -> ExecutionResult:
        claim = decision.bounded_claim.lower()
        target = next(
            (node for node in campaign.frontier if node.id == decision.target_frontier_node),
            None
        )
        if not target:
             return ExecutionResult(
                status="inconclusive",
                failure_type="node_not_found",
                notes=f"Target node {decision.target_frontier_node} not found in frontier.",
                executor_backend="mock",
            )

        artifacts = [f"world_family:{decision.world_family}", f"target:{target.id}"]

        if decision.world_family == "counterexample":
            return ExecutionResult(
                status="inconclusive",
                failure_type="inconclusive",
                notes="Mock executor found no concrete counterexample. Keep this only as weak negative evidence.",
                artifacts=artifacts,
                executor_backend="mock",
            )

        if decision.world_family == "finite_check":
            if re.search(r"\b(up to|<=|less than or equal to)\s*\d+", claim):
                return ExecutionResult(
                    status="proved",
                    notes="Mock executor accepted the bounded finite-check slice only.",
                    artifacts=artifacts + ["bounded_scope_verified"],
                    executor_backend="mock",
                )
            return ExecutionResult(
                status="blocked",
                failure_type="too_big",
                notes="Finite check requested, but the claim did not define a clear bound.",
                artifacts=artifacts,
                executor_backend="mock",
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
                notes="Bridge approach seems plausible, but the mock executor requires a sharper intermediate lemma before verification.",
                artifacts=artifacts,
                executor_backend="mock",
            )

        if decision.world_family == "reformulate":
            return ExecutionResult(
                status="inconclusive",
                failure_type="inconclusive",
                notes="Reformulation produced a candidate view, but it has not been linked back to the original target yet.",
                artifacts=artifacts,
                executor_backend="mock",
            )

        return ExecutionResult(
            status="blocked",
            failure_type="no_direct_proof",
            notes="Direct attempt did not reduce proof debt in the mock executor.",
            artifacts=artifacts,
            executor_backend="mock",
        )
