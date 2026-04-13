from __future__ import annotations

import threading
import time
import logging

from .service import CampaignService

logger = logging.getLogger(__name__)


class CampaignWorker:
    def __init__(self, service: CampaignService, poll_seconds: int) -> None:
        self.service = service
        self.poll_seconds = poll_seconds
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._failure_streak = 0
        self._max_backoff_seconds = max(5 * poll_seconds, poll_seconds)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.service.auto_step_once()
                if self.service.settings.enable_self_improvement:
                    self.service.run_self_improvement()
                self._failure_streak = 0
            except Exception:
                self._failure_streak += 1
                logger.exception("CampaignWorker auto_step_once failed")
            backoff_multiplier = min(2 ** self._failure_streak, max(1, self._max_backoff_seconds // self.poll_seconds))
            wait_seconds = self.poll_seconds * backoff_multiplier
            self._stop_event.wait(wait_seconds)
