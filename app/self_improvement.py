from __future__ import annotations

import json
import logging
from typing import Any

import requests

from .config import Settings
from .manager import get_self_improvement_prompt, get_policy
from lima_memory import MemoryService

logger = logging.getLogger(__name__)


class SelfImprovementService:
    def __init__(self, memory: MemoryService, settings: Settings) -> None:
        self.memory = memory
        self.settings = settings
        self._last_event_count = 0
        self._last_run_policy_version = None
        self._consecutive_rejections = 0
        self._max_consecutive_rejections = 3

    def run_cycle(self) -> dict[str, Any] | None:
        if not self.settings.enable_self_improvement:
            return None

        # Check if there's new data worth analyzing
        if not self._has_new_data():
            return {"status": "skipped", "reason": "no_new_data"}
        
        # Check if we've had too many consecutive rejections
        if self._consecutive_rejections >= self._max_consecutive_rejections:
            return {"status": "skipped", "reason": "too_many_rejections", "count": self._consecutive_rejections}

        logger.info("Starting self-improvement cycle.")
        
        # 1. Load history - only from campaigns with recent activity
        all_campaigns = self.memory.list_campaign_nodes(limit=50)
        history = []
        total_events = 0
        
        for campaign in all_campaigns[:5]:  # Look at top 5 recent campaigns
            events = self.memory.list_events(campaign.id, limit=20)
            
            # Skip campaigns with no recent events
            if not events:
                continue
            
            # Only include campaigns with execution results (not just polls)
            meaningful_events = [
                e for e in events 
                if e.event_type in {
                    "execution_result", "manager_decision", "obligation_analysis",
                    "aristotle_job_completed", "campaign_created",
                    "invention_batch_created", "invention_batch_distilled",
                    "invention_batch_falsified", "distilled_world_promoted",
                    "bake_attempt_recorded",
                }
            ]
            
            if not meaningful_events:
                continue
            
            problem_packet = self.memory.get_manager_packet(campaign_id=campaign.id, limit=1)
            statement = (problem_packet.problem.get("payload") or {}).get("statement", "")
            history.append({
                "campaign_id": campaign.id,
                "problem": statement[:200],  # Truncate long problem statements
                "recent_events": [e.asdict() for e in meaningful_events[:10]]  # Only last 10 meaningful events
            })
            total_events += len(meaningful_events)
        
        # If no meaningful history, skip
        if not history or total_events == 0:
            return {"status": "skipped", "reason": "no_meaningful_events"}
        
        self._last_event_count = total_events

        # 2. Get current policy (from memory store or root file)
        current_policy = self.memory.get_latest_policy() or get_policy()
        current_version = current_policy.get("version", "1.0.0")
        
        # Skip if we just analyzed this version
        if self._last_run_policy_version == current_version:
            return {"status": "skipped", "reason": "policy_unchanged"}
        
        self._last_run_policy_version = current_version

        # 3. Call LLM for proposal
        try:
            proposal = self._call_llm(history, current_policy)
            if not proposal:
                return None
            
            # 4. Validate and Apply Patch
            # Allowed mutable areas:
            allowed_areas = {
                "world_family_priors",
                "failure_penalties",
                "success_rewards",
                "blocked_state_rules",
                "confidence_rules",
                "prompt_insertions",
                "learned_patterns",
                "invention_policy",
                "invention_scoring",
                "falsifier_policy",
                "retrieval_policy",
            }
            
            patch = proposal.get("patch", {})
            reason = proposal.get("reason", "No reason provided.")
            
            new_policy = current_policy.copy()
            validated_patch = {}
            rejected_keys = []
            
            for key, value in patch.items():
                if key in allowed_areas:
                    new_policy[key] = value
                    validated_patch[key] = value
                else:
                    rejected_keys.append(key)
                    logger.warning(f"Self-improvement tried to modify restricted area: {key}")

            if validated_patch:
                # Update version
                version_parts = new_policy.get("version", "1.0.0").split(".")
                version_parts[-1] = str(int(version_parts[-1]) + 1)
                new_policy["version"] = ".".join(version_parts)
                
                self.memory.save_policy_snapshot(new_policy, validated_patch, reason)
                logger.info(f"Policy updated to version {new_policy['version']}")
                
                # Reset rejection counter on success
                self._consecutive_rejections = 0
                
                return {
                    "status": "updated",
                    "version": new_policy["version"],
                    "patch": validated_patch,
                    "rejected_keys": rejected_keys
                }
            else:
                # All proposals were rejected
                self._consecutive_rejections += 1
                logger.warning(
                    f"Self-improvement: all proposals rejected ({self._consecutive_rejections}/{self._max_consecutive_rejections}). "
                    f"Rejected keys: {rejected_keys}"
                )
                return {
                    "status": "all_rejected",
                    "rejected_keys": rejected_keys,
                    "consecutive_rejections": self._consecutive_rejections
                }
            
        except Exception as e:
            logger.error(f"Self-improvement cycle failed: {e}")
            return {"status": "failed", "error": str(e)}
    
    def _has_new_data(self) -> bool:
        """Check if there's new execution data worth analyzing."""
        # Count recent execution results across all campaigns
        all_campaigns = self.memory.list_campaign_nodes(limit=10)
        total_events = 0
        
        for campaign in all_campaigns[:5]:
            events = self.memory.list_events(campaign.id, limit=10)
            meaningful_events = [
                e for e in events 
                if e.event_type in {
                    "execution_result", "aristotle_job_completed",
                    "invention_batch_falsified", "distilled_world_promoted",
                    "bake_attempt_recorded",
                }
            ]
            total_events += len(meaningful_events)
        
        # Only run if we have new events since last run
        has_new = total_events > self._last_event_count
        
        if not has_new:
            logger.debug(f"Self-improvement: no new data (events: {total_events}, last: {self._last_event_count})")
        
        return has_new

    def _call_llm(self, history: list[dict[str, Any]], current_policy: dict[str, Any]) -> dict[str, Any] | None:
        if not self.settings.llm_api_key:
            return None

        prompt = get_self_improvement_prompt()
        
        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": (
                    "Review the following campaign history and current policy, then propose a JSON patch.\n\n"
                    f"HISTORY:\n{json.dumps(history, indent=2)}\n\n"
                    f"CURRENT POLICY:\n{json.dumps(current_policy, indent=2)}\n\n"
                    "Return a JSON object with 'patch' and 'reason'."
                )
            }
        ]
        
        payload = {
            "model": self.settings.llm_model,
            "temperature": 0.1,
            "messages": messages,
            "response_format": {"type": "json_object"}
        }
        
        response = requests.post(
            self.settings.llm_base_url.rstrip("/") + "/chat/completions",
            headers={
                "Authorization": f"Bearer {self.settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
