from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from .schemas import CampaignRecord, EventRecord, FrontierNode, MemoryState


class Database:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS campaigns (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    problem_statement TEXT NOT NULL,
                    status TEXT NOT NULL,
                    auto_run INTEGER NOT NULL,
                    operator_notes TEXT NOT NULL,
                    frontier_json TEXT NOT NULL,
                    memory_json TEXT NOT NULL,
                    current_candidate_answer_json TEXT,
                    tick_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_manager_context_json TEXT,
                    last_manager_decision_json TEXT,
                    last_execution_result_json TEXT,
                    manager_backend TEXT NOT NULL,
                    executor_backend TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id TEXT NOT NULL,
                    tick INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(campaign_id) REFERENCES campaigns(id)
                );
                CREATE INDEX IF NOT EXISTS idx_events_campaign_id
                ON events(campaign_id, id DESC);

                CREATE TABLE IF NOT EXISTS policy_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version TEXT NOT NULL,
                    policy_json TEXT NOT NULL,
                    patch_json TEXT,
                    reason TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )

    def create_campaign(
        self,
        *,
        title: str,
        problem_statement: str,
        operator_notes: list[str],
        auto_run: bool,
        frontier: list[FrontierNode],
        memory: MemoryState,
        manager_backend: str,
        executor_backend: str,
    ) -> CampaignRecord:
        campaign_id = f"C-{uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO campaigns (
                    id, title, problem_statement, status, auto_run, operator_notes,
                    frontier_json, memory_json, current_candidate_answer_json, tick_count, created_at, updated_at,
                    manager_backend, executor_backend
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    campaign_id,
                    title,
                    problem_statement,
                    "running",
                    1 if auto_run else 0,
                    json.dumps(operator_notes),
                    json.dumps([node.model_dump() for node in frontier]),
                    memory.model_dump_json(),
                    None,
                    0,
                    now,
                    now,
                    manager_backend,
                    executor_backend,
                ),
            )
        self.add_event(campaign_id=campaign_id, tick=0, kind="campaign_created", payload={"title": title})
        return self.get_campaign(campaign_id)

    def get_campaign(self, campaign_id: str) -> CampaignRecord:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM campaigns WHERE id = ?",
                (campaign_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Campaign not found: {campaign_id}")
        return self._row_to_campaign(row)

    def list_campaigns(self) -> list[CampaignRecord]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM campaigns ORDER BY updated_at DESC"
            ).fetchall()
        return [self._row_to_campaign(row) for row in rows]

    def update_campaign(self, campaign: CampaignRecord) -> CampaignRecord:
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE campaigns
                SET status = ?, auto_run = ?, operator_notes = ?, frontier_json = ?, memory_json = ?,
                    current_candidate_answer_json = ?, tick_count = ?, updated_at = ?, last_manager_context_json = ?,
                    last_manager_decision_json = ?, last_execution_result_json = ?,
                    manager_backend = ?, executor_backend = ?
                WHERE id = ?
                """,
                (
                    campaign.status,
                    1 if campaign.auto_run else 0,
                    json.dumps(campaign.operator_notes),
                    json.dumps([node.model_dump() for node in campaign.frontier]),
                    campaign.memory.model_dump_json(),
                    campaign.current_candidate_answer.model_dump_json() if campaign.current_candidate_answer else None,
                    campaign.tick_count,
                    now,
                    json.dumps(campaign.last_manager_context),
                    json.dumps(campaign.last_manager_decision),
                    json.dumps(campaign.last_execution_result),
                    campaign.manager_backend,
                    campaign.executor_backend,
                    campaign.id,
                ),
            )
        return self.get_campaign(campaign.id)

    def add_event(self, *, campaign_id: str, tick: int, kind: str, payload: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO events (campaign_id, tick, kind, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    campaign_id,
                    tick,
                    kind,
                    json.dumps(payload),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def list_events(self, campaign_id: str, limit: int = 50) -> list[EventRecord]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM events
                WHERE campaign_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (campaign_id, limit),
            ).fetchall()
        results = []
        for row in rows:
            results.append(
                EventRecord(
                    id=row["id"],
                    campaign_id=row["campaign_id"],
                    tick=row["tick"],
                    kind=row["kind"],
                    payload=json.loads(row["payload_json"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
            )
        return results

    def save_policy_snapshot(self, policy: dict[str, Any], patch: dict[str, Any] | None = None, reason: str | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO policy_snapshots (version, policy_json, patch_json, reason, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    policy.get("version", "unknown"),
                    json.dumps(policy),
                    json.dumps(patch) if patch else None,
                    reason,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def get_latest_policy(self) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT policy_json FROM policy_snapshots ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if row:
            return json.loads(row["policy_json"])
        return None

    def list_policy_history(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM policy_snapshots ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def _row_to_campaign(self, row: sqlite3.Row) -> CampaignRecord:
        return CampaignRecord(
            id=row["id"],
            title=row["title"],
            problem_statement=row["problem_statement"],
            status=row["status"],
            auto_run=bool(row["auto_run"]),
            operator_notes=json.loads(row["operator_notes"]),
            frontier=[FrontierNode.model_validate(item) for item in json.loads(row["frontier_json"])],
            memory=MemoryState.model_validate_json(row["memory_json"]),
            current_candidate_answer=self._load_candidate_answer(row["current_candidate_answer_json"]),
            tick_count=row["tick_count"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            last_manager_context=self._loads_nullable(row["last_manager_context_json"]),
            last_manager_decision=self._loads_nullable(row["last_manager_decision_json"]),
            last_execution_result=self._loads_nullable(row["last_execution_result_json"]),
            manager_backend=row["manager_backend"],
            executor_backend=row["executor_backend"],
        )

    @staticmethod
    def _loads_nullable(value: str | None) -> dict[str, Any] | None:
        if not value:
            return None
        return json.loads(value)

    @staticmethod
    def _load_candidate_answer(value: str | None) -> CandidateAnswer | None:
        from .schemas import CandidateAnswer
        if not value:
            return None
        return CandidateAnswer.model_validate_json(value)
