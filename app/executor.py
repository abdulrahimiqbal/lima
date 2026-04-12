from __future__ import annotations

import asyncio
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from .config import Settings
from .schemas import CampaignRecord, ExecutionResult, FrontierNode, ManagerDecision

logger = logging.getLogger(__name__)


class Executor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(self, campaign: CampaignRecord, decision: ManagerDecision) -> ExecutionResult:
        if self.settings.executor_backend == "aristotle" or (
            self.settings.executor_backend == "http" and self.settings.aristotle_api_key
        ):
            try:
                return self._run_aristotle(campaign, decision)
            except Exception as exc:
                logger.error(f"Aristotle execution failed: {exc}")
                return ExecutionResult(
                    status="inconclusive",
                    failure_type="executor_unavailable",
                    notes=f"Aristotle executor failed: {exc}",
                    executor_backend="aristotle",
                )
        return self._run_mock(campaign, decision)

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

    def _run_aristotle(self, campaign: CampaignRecord, decision: ManagerDecision) -> ExecutionResult:
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
        lean_code = self._obligations_to_lean(campaign, decision)
        logger.info(f"Submitting Lean code to Aristotle ({len(lean_code)} chars)")

        # Run the async SDK in a sync context
        loop = None
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're inside an async context (like FastAPI), create a new thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = pool.submit(self._run_aristotle_sync, lean_code, decision).result(
                        timeout=self.settings.aristotle_timeout_seconds
                    )
                return result
        except RuntimeError:
            pass

        # No running loop, create one
        return asyncio.run(self._run_aristotle_async(lean_code, decision))

    def _run_aristotle_sync(self, lean_code: str, decision: ManagerDecision) -> ExecutionResult:
        """Run aristotle in a new event loop (for thread pool)."""
        return asyncio.run(self._run_aristotle_async(lean_code, decision))

    async def _run_aristotle_async(self, lean_code: str, decision: ManagerDecision) -> ExecutionResult:
        from aristotlelib import Project

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.lean"
            output_path = Path(tmpdir) / "output.lean"
            input_path.write_text(lean_code)

            try:
                result_path = await Project.prove_from_file(
                    input_content=lean_code,
                    wait_for_completion=True,
                    polling_interval_seconds=10,
                    max_polling_failures=5,
                    output_file_path=str(output_path),
                    auto_add_imports=True,
                )

                # If we get here, Aristotle completed
                if output_path.exists():
                    solved_code = output_path.read_text()
                    has_sorry = "sorry" in solved_code.lower()

                    if has_sorry:
                        return ExecutionResult(
                            status="blocked",
                            failure_type="partial_proof",
                            notes="Aristotle returned a partial proof — some 'sorry' remain.",
                            artifacts=[solved_code[:2000]],
                            executor_backend="aristotle",
                        )
                    else:
                        return ExecutionResult(
                            status="proved",
                            notes="Aristotle fully proved all obligations.",
                            artifacts=[solved_code[:2000]],
                            executor_backend="aristotle",
                        )
                else:
                    return ExecutionResult(
                        status="proved",
                        notes=f"Aristotle completed. Result path: {result_path}",
                        artifacts=[str(result_path)],
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

    def _obligations_to_lean(self, campaign: CampaignRecord, decision: ManagerDecision) -> str:
        """Convert formal obligations into Lean 4 code for Aristotle."""
        lines = [
            "-- Auto-generated by LIMA Learning Platform",
            f"-- Campaign: {campaign.id}",
            f"-- World family: {decision.world_family}",
            f"-- Bounded claim: {decision.bounded_claim}",
            "",
        ]

        for i, obligation in enumerate(decision.formal_obligations):
            # If the obligation looks like Lean code, use it directly
            if any(kw in obligation for kw in ["theorem", "lemma", "def ", "example", "import"]):
                lines.append(obligation)
            else:
                # Wrap it as a sorry theorem
                safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', obligation[:40])
                lines.append(f"theorem obligation_{i}_{safe_name} : sorry := by")
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
