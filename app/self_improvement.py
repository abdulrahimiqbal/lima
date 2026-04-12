from __future__ import annotations

import json
import logging
from typing import Any

import requests

from .config import Settings
from .db import Database
from .manager import get_self_improvement_prompt, get_policy

logger = logging.getLogger(__name__)


class SelfImprovementService:
    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    def run_cycle(self) -> dict[str, Any] | None:
        if not self.settings.enable_self_improvement:
            return None

        logger.info("Starting self-improvement cycle.")
        
        # 1. Load history
        # For simplicity, we'll take recent events from all campaigns
        all_campaigns = self.db.list_campaigns()
        history = []
        for campaign in all_campaigns[:3]: # Look at top 3 recent campaigns
            events = self.db.list_events(campaign.id, limit=20)
            history.append({
                "campaign_id": campaign.id,
                "problem": campaign.problem_statement,
                "recent_events": [e.model_dump() for e in events]
            })

        # 2. Get current policy (from DB or root file)
        current_policy = self.db.get_latest_policy() or get_policy()

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
                "learned_patterns"
            }
            
            patch = proposal.get("patch", {})
            reason = proposal.get("reason", "No reason provided.")
            
            new_policy = current_policy.copy()
            validated_patch = {}
            
            for key, value in patch.items():
                if key in allowed_areas:
                    new_policy[key] = value
                    validated_patch[key] = value
                else:
                    logger.warning(f"Self-improvement tried to modify restricted area: {key}")

            if validated_patch:
                # Update version
                version_parts = new_policy.get("version", "1.0.0").split(".")
                version_parts[-1] = str(int(version_parts[-1]) + 1)
                new_policy["version"] = ".".join(version_parts)
                
                self.db.save_policy_snapshot(new_policy, validated_patch, reason)
                logger.info(f"Policy updated to version {new_policy['version']}")
                return {"status": "updated", "version": new_policy["version"], "patch": validated_patch}
            
            return {"status": "no_changes"}
            
        except Exception as e:
            logger.error(f"Self-improvement cycle failed: {e}")
            return {"status": "failed", "error": str(e)}

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
