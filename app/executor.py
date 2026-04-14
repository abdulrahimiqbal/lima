from __future__ import annotations

import asyncio
import logging
import os
import re
import tarfile
import tempfile
import time
from datetime import datetime, timezone
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
    PendingAristotleJob,
)

logger = logging.getLogger(__name__)


LEAN_DECLARATION_RE = re.compile(
    r"^\s*(?:import|open|namespace|section|variable|variables|theorem|lemma|def|example)\b",
    re.MULTILINE,
)


class ProofAdapter(Protocol):
    name: str

    def submit_proof(
        self,
        campaign: CampaignRecord,
        decision: ManagerDecision,
        plan: ApprovedExecutionPlan,
    ) -> PendingAristotleJob: ...

    def poll_proof(
        self,
        pending_job: PendingAristotleJob,
    ) -> tuple[PendingAristotleJob, ExecutionResult | None]: ...

    def check_connectivity(self, *, strict_live_probe: bool) -> dict[str, Any]: ...


class MockProofAdapter:
    name = "mock"

    def submit_proof(
        self,
        campaign: CampaignRecord,
        decision: ManagerDecision,
        plan: ApprovedExecutionPlan,
    ) -> PendingAristotleJob:
        """Mock submission - immediately returns a pending job that will complete on first poll."""
        return PendingAristotleJob(
            project_id=f"mock-{campaign.id}-{campaign.tick_count}",
            target_frontier_node=decision.target_frontier_node,
            world_family=decision.world_family,
            bounded_claim=decision.bounded_claim,
            submitted_at=datetime.now(timezone.utc),
            decision_snapshot=decision.model_dump(),
            plan_snapshot=plan.model_dump(),
            lean_code="-- mock lean code",
            status="submitted",
        )

    def poll_proof(
        self,
        pending_job: PendingAristotleJob,
    ) -> tuple[PendingAristotleJob, ExecutionResult | None]:
        """Mock polling - completes immediately with inconclusive result."""
        updated_job = pending_job.model_copy(deep=True)
        updated_job.poll_count += 1
        updated_job.last_polled_at = datetime.now(timezone.utc)
        updated_job.status = "complete"
        
        # Reconstruct decision and plan from snapshots
        from .schemas import ManagerDecision, ApprovedExecutionPlan
        decision = ManagerDecision.model_validate(pending_job.decision_snapshot)
        plan = ApprovedExecutionPlan.model_validate(pending_job.plan_snapshot)
        
        # Use the original mock logic
        artifacts = [f"world_family:{decision.world_family}", f"target:{decision.target_frontier_node}"]
        
        if decision.world_family == "finite_check":
            bound = _extract_bound(decision.bounded_claim.lower())
            if bound is not None:
                result = ExecutionResult(
                    status="inconclusive",
                    failure_type="evidence_only",
                    notes="Mock mode recorded bounded evidence only; no formal proof verdict is produced.",
                    artifacts=artifacts + [f"bounded_scope:{bound}"],
                    executor_backend=self.name,
                )
            else:
                result = ExecutionResult(
                    status="blocked",
                    failure_type="too_big",
                    notes="Finite check requested without a clear bound.",
                    artifacts=artifacts,
                    executor_backend=self.name,
                    spawned_nodes=[
                        FrontierNode(
                            text=f"Define an explicit bounded finite check for: {decision.target_frontier_node}",
                            status="open",
                            priority=0.2,
                            parent_id=decision.target_frontier_node,
                            kind="finite_check",
                        )
                    ],
                )
        elif decision.world_family == "bridge":
            result = ExecutionResult(
                status="blocked",
                failure_type="missing_lemma",
                notes="Bridge approach requires a sharper intermediate lemma in mock mode.",
                artifacts=artifacts,
                executor_backend=self.name,
            )
        else:
            result = ExecutionResult(
                status="inconclusive",
                failure_type="mock_no_formal_verdict",
                notes="Mock mode does not produce proved/refuted outcomes.",
                artifacts=artifacts,
                executor_backend=self.name,
            )
        
        return updated_job, result

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

    def submit_proof(
        self,
        campaign: CampaignRecord,
        decision: ManagerDecision,
        plan: ApprovedExecutionPlan,
    ) -> PendingAristotleJob:
        """Submit a proof job to Aristotle without waiting for completion."""
        if not self.settings.aristotle_api_key:
            raise RuntimeError("ARISTOTLE_API_KEY is missing")

        proof_obligation = plan.approved_proof_jobs[0]
        
        # Get structured obligation if available
        normalized_obligations = decision.get_normalized_obligations()
        obligation_spec = None
        for spec in normalized_obligations:
            if spec.source_text == proof_obligation or proof_obligation in spec.source_text:
                obligation_spec = spec
                break
        if obligation_spec is None:
            for debt in decision.proof_debt:
                if debt.statement == proof_obligation:
                    from .schemas import FormalObligationSpec

                    obligation_spec = FormalObligationSpec.from_debt_item(debt)
                    break

        lean_result = self._obligation_to_lean(obligation_spec or proof_obligation)
        
        # Check if formalization failed
        if lean_result["status"] == "formalization_failed":
            # Return a pending job that's already marked as failed
            pending_job = PendingAristotleJob(
                project_id=f"formalization-failed-{campaign.id}-{campaign.tick_count}",
                target_frontier_node=decision.target_frontier_node,
                world_family=decision.world_family,
                bounded_claim=decision.bounded_claim,
                submitted_at=datetime.now(timezone.utc),
                decision_snapshot=decision.model_dump(),
                plan_snapshot=plan.model_dump(),
                lean_code="",
                status="failed",
                notes=[lean_result["notes"]],
            )
            return pending_job
        
        lean_code = lean_result["lean_code"]
        
        # Submit to Aristotle
        try:
            project_id = self._submit_to_aristotle_sync(lean_code, decision)
            
            return PendingAristotleJob(
                project_id=project_id,
                target_frontier_node=decision.target_frontier_node,
                world_family=decision.world_family,
                bounded_claim=decision.bounded_claim,
                submitted_at=datetime.now(timezone.utc),
                decision_snapshot=decision.model_dump(),
                plan_snapshot=plan.model_dump(),
                lean_code=lean_code,
                status="submitted",
            )
        except Exception as exc:
            # If submission fails, return a failed pending job
            logger.exception("Failed to submit proof to Aristotle")
            return PendingAristotleJob(
                project_id=f"submission-failed-{campaign.id}-{campaign.tick_count}",
                target_frontier_node=decision.target_frontier_node,
                world_family=decision.world_family,
                bounded_claim=decision.bounded_claim,
                submitted_at=datetime.now(timezone.utc),
                decision_snapshot=decision.model_dump(),
                plan_snapshot=plan.model_dump(),
                lean_code=lean_code,
                status="failed",
                notes=[f"Submission error: {str(exc)}"],
            )

    def poll_proof(
        self,
        pending_job: PendingAristotleJob,
    ) -> tuple[PendingAristotleJob, ExecutionResult | None]:
        """Poll an existing Aristotle proof job. Returns updated job and optional result if terminal."""
        updated_job = pending_job.model_copy(deep=True)
        updated_job.poll_count += 1
        updated_job.last_polled_at = datetime.now(timezone.utc)
        
        # If job already failed during submission, return terminal result
        if pending_job.status == "failed" and pending_job.project_id.startswith("formalization-failed"):
            result = ExecutionResult(
                status="blocked",
                failure_type="formalization_failed",
                notes=pending_job.notes[0] if pending_job.notes else "Formalization failed",
                artifacts=[],
                executor_backend="aristotle",
            )
            return updated_job, result
        
        if pending_job.status == "failed" and pending_job.project_id.startswith("submission-failed"):
            result = ExecutionResult(
                status="inconclusive",
                failure_type="sdk_error",
                notes=pending_job.notes[0] if pending_job.notes else "Submission failed",
                executor_backend="aristotle",
            )
            return updated_job, result
        
        # Poll Aristotle for status
        try:
            project_status, result_tar_path = self._poll_aristotle_sync(
                pending_job.project_id,
                pending_job.lean_code,
            )
            
            updated_job.status = project_status
            if result_tar_path:
                updated_job.result_tar_path = result_tar_path
            
            # Check if terminal (status strings are uppercase from enum)
            if project_status.upper() in {"COMPLETE", "COMPLETE_WITH_ERRORS", "OUT_OF_BUDGET", "FAILED", "CANCELED"}:
                # Reconstruct decision and plan from snapshots
                from .schemas import ManagerDecision, ApprovedExecutionPlan
                decision = ManagerDecision.model_validate(pending_job.decision_snapshot)
                plan = ApprovedExecutionPlan.model_validate(pending_job.plan_snapshot)
                
                # Convert to ExecutionResult
                result = self._convert_terminal_status_to_result(
                    project_status,
                    pending_job.project_id,
                    result_tar_path,
                    plan,
                )
                return updated_job, result
            else:
                # Still running
                updated_job.status = "running"
                updated_job.notes.append(f"Poll {updated_job.poll_count}: still running")
                return updated_job, None
                
        except Exception as exc:
            logger.exception("Failed to poll Aristotle project")
            updated_job.notes.append(f"Poll error: {str(exc)}")
            # Don't mark as failed yet - might be transient network issue
            return updated_job, None

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

    def _submit_to_aristotle_sync(
        self,
        lean_code: str,
        decision: ManagerDecision,
    ) -> str:
        """Submit proof to Aristotle and return project_id."""
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(
                        self._submit_to_aristotle_async_wrapper,
                        lean_code,
                        decision,
                    ).result(timeout=self.settings.aristotle_timeout_seconds)
        except RuntimeError:
            pass
        
        return asyncio.run(self._submit_to_aristotle_async(lean_code, decision))

    async def _submit_to_aristotle_async(
        self,
        lean_code: str,
        decision: ManagerDecision,
    ) -> str:
        """Async submission to Aristotle."""
        os.environ["ARISTOTLE_API_KEY"] = self.settings.aristotle_api_key or ""
        try:
            from aristotlelib import Project
        except ImportError:
            raise RuntimeError("aristotlelib is not installed")

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "lean_project"
            project_dir.mkdir(parents=True, exist_ok=True)
            input_path = project_dir / "Main.lean"
            input_path.write_text(lean_code)
            
            # Build rich context prompt for Aristotle
            prompt_parts = [
                "Fill in all Lean sorries in this project.",
                "Preserve theorem names where possible.",
                "",
                "=== PROBLEM CONTEXT ===",
                f"Bounded claim: {decision.bounded_claim}",
                f"World family: {decision.world_family}",
            ]
            
            # Add global thesis if available
            if hasattr(decision, 'global_thesis') and decision.global_thesis:
                prompt_parts.extend([
                    "",
                    "=== OVERALL STRATEGY ===",
                    decision.global_thesis,
                ])
            
            # Add world program context if available
            if hasattr(decision, 'primary_world') and decision.primary_world:
                world = decision.primary_world
                prompt_parts.extend([
                    "",
                    "=== WORLD PROGRAM ===",
                    f"World ID: {world.id}",
                    f"Mode: {world.mode}",
                    f"Thesis: {world.thesis}",
                ])
                if world.bridge_to_target:
                    prompt_parts.append(f"Bridge to target: {world.bridge_to_target}")
            
            # Add proof debt context from decision obligations
            normalized_obligations = decision.get_normalized_obligations()
            for spec in normalized_obligations:
                # Add context from any obligation with debt metadata
                if spec.metadata.get("debt_role"):
                    prompt_parts.extend([
                        "",
                        "=== PROOF DEBT CONTEXT ===",
                        f"Role: {spec.metadata.get('debt_role')}",
                        f"Critical: {spec.metadata.get('debt_critical', False)}",
                    ])
                # Add tactic hints if available
                if spec.tactic_hints:
                    prompt_parts.extend([
                        "",
                        "=== TACTIC HINTS ===",
                    ] + [f"- {hint}" for hint in spec.tactic_hints])
                # Add assumptions if available
                if spec.assumptions:
                    prompt_parts.extend([
                        "",
                        "=== ASSUMPTIONS ===",
                    ] + [f"- {assumption}" for assumption in spec.assumptions])
                # Only use first obligation with metadata
                if spec.metadata.get("debt_role") or spec.tactic_hints or spec.assumptions:
                    break
            
            prompt = "\n".join(prompt_parts)
            
            project = await Project.create_from_directory(
                prompt=prompt, project_dir=project_dir
            )
            return project.project_id

    def _submit_to_aristotle_async_wrapper(
        self,
        lean_code: str,
        decision: ManagerDecision,
    ) -> str:
        """Wrapper for running async submission in thread pool."""
        return asyncio.run(self._submit_to_aristotle_async(lean_code, decision))

    def _poll_aristotle_sync(
        self,
        project_id: str,
        lean_code: str,
    ) -> tuple[str, str | None]:
        """Poll Aristotle project status. Returns (status, result_tar_path)."""
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(
                        self._poll_aristotle_async_wrapper,
                        project_id,
                        lean_code,
                    ).result(timeout=self.settings.aristotle_timeout_seconds)
        except RuntimeError:
            pass
        
        return asyncio.run(self._poll_aristotle_async(project_id, lean_code))

    async def _poll_aristotle_async(
        self,
        project_id: str,
        lean_code: str,
    ) -> tuple[str, str | None]:
        """Async poll of Aristotle project."""
        os.environ["ARISTOTLE_API_KEY"] = self.settings.aristotle_api_key or ""
        try:
            from aristotlelib import Project, ProjectStatus
        except ImportError:
            raise RuntimeError("aristotlelib is not installed")

        # Reconstruct project from project_id using from_id() method
        try:
            project = await Project.from_id(project_id)
        except Exception as exc:
            # Log the actual error for debugging
            logger.error(f"Failed to poll project {project_id}: {exc}", exc_info=True)
            # Return failed status instead of silently returning "running"
            return "failed", None
        
        status_str = project.status.value if hasattr(project.status, 'value') else str(project.status)
        
        # Log the actual status for debugging
        logger.info(f"Aristotle project {project_id} status: {status_str} (type: {type(project.status)}, raw: {project.status})")
        
        # If terminal, try to download results
        result_tar_path = None
        if project.status in {ProjectStatus.COMPLETE, ProjectStatus.COMPLETE_WITH_ERRORS, ProjectStatus.OUT_OF_BUDGET, ProjectStatus.FAILED, ProjectStatus.CANCELED}:
            with tempfile.TemporaryDirectory() as tmpdir:
                result_tar = Path(tmpdir) / f"aristotle_result_{project_id}.tar.gz"
                try:
                    # Download results with short timeout
                    await asyncio.wait_for(
                        project.wait_for_completion(
                            destination=result_tar,
                            polling_interval_seconds=1,
                        ),
                        timeout=10,  # Short timeout just for download
                    )
                    if result_tar.exists():
                        # Copy to persistent location
                        persistent_path = Path(f"./data/aristotle_results/{project_id}.tar.gz")
                        persistent_path.parent.mkdir(parents=True, exist_ok=True)
                        import shutil
                        shutil.copy(result_tar, persistent_path)
                        result_tar_path = str(persistent_path)
                except Exception as exc:
                    logger.warning(f"Failed to download results for {project_id}: {exc}")
        
        return status_str, result_tar_path

    def _poll_aristotle_async_wrapper(
        self,
        project_id: str,
        lean_code: str,
    ) -> tuple[str, str | None]:
        """Wrapper for running async poll in thread pool."""
        return asyncio.run(self._poll_aristotle_async(project_id, lean_code))

    def _convert_terminal_status_to_result(
        self,
        status: str,
        project_id: str,
        result_tar_path: str | None,
        plan: ApprovedExecutionPlan,
    ) -> ExecutionResult:
        """Convert terminal Aristotle status to ExecutionResult."""
        if status == "complete":
            extracted = None
            if result_tar_path:
                extracted = self._extract_lean_from_tar(Path(result_tar_path))
            
            if extracted and "sorry" in extracted.lower():
                return ExecutionResult(
                    status="blocked",
                    failure_type="partial_proof",
                    notes=f"Aristotle completed {project_id}, but output still contains sorry.",
                    artifacts=[extracted[:2000]],
                    executor_backend="aristotle",
                )
            return ExecutionResult(
                status="proved",
                notes=f"Aristotle completed project {project_id}.",
                artifacts=[extracted[:2000]] if extracted else [str(result_tar_path) if result_tar_path else ""],
                executor_backend="aristotle",
            )
        
        if status == "complete_with_errors":
            return ExecutionResult(
                status="blocked",
                failure_type="partial_proof",
                notes=f"Aristotle completed project {project_id} with errors.",
                artifacts=[str(result_tar_path)] if result_tar_path else [],
                executor_backend="aristotle",
            )
        
        if status == "out_of_budget":
            return ExecutionResult(
                status="inconclusive",
                failure_type="budget_exhausted",
                notes=f"Aristotle project {project_id} ran out of budget.",
                artifacts=[str(result_tar_path)] if result_tar_path else [],
                executor_backend="aristotle",
            )
        
        if status == "failed":
            return ExecutionResult(
                status="blocked",
                failure_type="proof_failed",
                notes=f"Aristotle project {project_id} failed to find a proof. This does not mean the theorem is false.",
                artifacts=[str(result_tar_path)] if result_tar_path else [],
                executor_backend="aristotle",
            )
        
        if status == "canceled":
            return ExecutionResult(
                status="inconclusive",
                failure_type="canceled",
                notes=f"Aristotle project {project_id} was canceled.",
                artifacts=[str(result_tar_path)] if result_tar_path else [],
                executor_backend="aristotle",
            )
        
        return ExecutionResult(
            status="inconclusive",
            failure_type="inconclusive",
            notes=f"Aristotle finished with status {status}.",
            artifacts=[str(result_tar_path)] if result_tar_path else [],
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
    def _obligation_to_lean(obligation: Any) -> dict[str, Any]:
        """
        Convert obligation to Lean code honestly.
        Returns dict with status, lean_code, notes, and artifacts.
        """
        from .schemas import FormalObligationSpec
        
        # Handle structured obligation
        if isinstance(obligation, FormalObligationSpec):
            spec = obligation
            
            # If lean_declaration is present, use it directly
            if spec.lean_declaration:
                return {
                    "status": "ok",
                    "lean_code": spec.lean_declaration,
                    "notes": "Using provided lean_declaration",
                }
            
            # If statement is present, build real theorem
            if spec.statement:
                lines = []
                
                # Add imports
                if spec.imports:
                    for imp in spec.imports:
                        lines.append(f"import {imp}")
                    lines.append("")
                
                # Add context header
                lines.append("/-")
                lines.append(f"Source: {spec.source_text[:200]}")
                if spec.metadata.get("debt_role"):
                    lines.append(f"Proof debt role: {spec.metadata.get('debt_role')}")
                if spec.bounded_domain_description:
                    lines.append(f"Bounded domain: {spec.bounded_domain_description}")
                lines.append("-/")
                lines.append("")
                
                # Add variables
                if spec.variables:
                    for var in spec.variables:
                        lines.append(f"variable {var}")
                    lines.append("")
                
                # Build theorem name
                theorem_name = spec.theorem_name or _sanitize_theorem_name(spec.source_text[:40])
                
                # Add assumptions as hypotheses if present
                if spec.assumptions:
                    lines.append(f"-- Assumptions:")
                    for assumption in spec.assumptions:
                        lines.append(f"-- {assumption}")
                    lines.append("")
                
                # Build theorem declaration
                goal_keyword = "lemma" if spec.goal_kind == "lemma" else "theorem"
                lines.append(f"{goal_keyword} {theorem_name} : {spec.statement} := by")
                
                # Add tactic hints as comments
                if spec.tactic_hints:
                    for hint in spec.tactic_hints:
                        lines.append(f"  -- Hint: {hint}")
                
                lines.append("  sorry")
                lines.append("")
                
                return {
                    "status": "ok",
                    "lean_code": "\n".join(lines),
                    "notes": "Generated from structured statement",
                }
            
            # No formal statement available - fail honestly
            return {
                "status": "formalization_failed",
                "lean_code": "",
                "notes": f"Obligation lacks formal statement. Cannot generate Lean code from natural language alone. Source: {spec.source_text[:200]}",
                "artifacts": [
                    f"source_text:{spec.source_text}",
                    f"goal_kind:{spec.goal_kind}",
                    "formalization_gap:no_statement_provided",
                ],
            }
        
        # Handle string obligation (backward compatibility)
        if isinstance(obligation, str):
            text = obligation.strip()
            
            # Accept only strings that actually start like Lean code.
            if _looks_like_lean_code(text):
                return {
                    "status": "ok",
                    "lean_code": text,
                    "notes": "Using obligation as-is (appears to be Lean code)",
                }
            
            # Otherwise, fail honestly - don't create fake theorems
            return {
                "status": "formalization_failed",
                "lean_code": "",
                "notes": f"Cannot formalize natural language obligation without structured statement. Text: {text[:200]}",
                "artifacts": [
                    f"source_text:{text}",
                    "formalization_gap:unstructured_natural_language",
                ],
            }
        
        return {
            "status": "formalization_failed",
            "lean_code": "",
            "notes": f"Unknown obligation type: {type(obligation)}",
            "artifacts": [],
        }


def _sanitize_theorem_name(text: str) -> str:
    """Sanitize text into a valid Lean theorem name."""
    # Remove non-alphanumeric characters, replace with underscore
    name = re.sub(r"[^a-zA-Z0-9_]", "_", text)
    # Remove leading/trailing underscores
    name = name.strip("_")
    # Ensure it starts with a letter
    if name and not name[0].isalpha():
        name = "theorem_" + name
    # Ensure it's not empty
    if not name:
        name = "obligation"
    return name


def _looks_like_lean_code(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if not LEAN_DECLARATION_RE.match(stripped):
        return False
    return any(token in stripped for token in (":=", " by", "\nby", "import ", "example "))


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

    def submit_proof(
        self,
        campaign: CampaignRecord,
        decision: ManagerDecision,
        plan: ApprovedExecutionPlan,
    ) -> PendingAristotleJob:
        """Submit a proof job without waiting for completion."""
        return self._proof_adapter.submit_proof(campaign, decision, plan)

    def poll_proof(
        self,
        pending_job: PendingAristotleJob,
    ) -> tuple[PendingAristotleJob, ExecutionResult | None]:
        """Poll an existing proof job. Returns updated job and optional result if terminal."""
        return self._proof_adapter.poll_proof(pending_job)

    def run_evidence(
        self,
        campaign: CampaignRecord,
        decision: ManagerDecision,
        plan: ApprovedExecutionPlan,
    ) -> ExecutionResult:
        """Run computational evidence jobs (synchronous, fast)."""
        started = time.perf_counter()
        result = self._run_computational_evidence(campaign, decision, plan)
        elapsed = int((time.perf_counter() - started) * 1000)
        return self._attach_plan_metadata(
            result,
            plan,
            elapsed,
            executed_proof_jobs=[],
            executed_evidence_jobs=plan.approved_evidence_jobs,
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


def _extract_bound(text: str) -> int | None:
    match = re.search(r"(<=|≤|up to|at most)\s*(\d+)", text)
    if not match:
        return None
    try:
        return int(match.group(2))
    except ValueError:
        return None
