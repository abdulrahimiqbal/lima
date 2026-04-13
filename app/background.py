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
            except Exception:
                logger.exception("CampaignWorker auto_step_once failed")
            self._stop_event.wait(self.poll_seconds)
