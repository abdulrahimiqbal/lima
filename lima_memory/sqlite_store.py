from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .models import ArtifactRecord, EdgeRecord, EventRecord, NodeRecord
from .store import KnowledgeStore

class SqliteKnowledgeStore(KnowledgeStore):
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
                CREATE TABLE IF NOT EXISTS kb_nodes (
                    id TEXT PRIMARY KEY,
                    campaign_id TEXT NOT NULL,
                    node_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    status TEXT NOT NULL,
                    confidence REAL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_kb_nodes_campaign_type
                    ON kb_nodes(campaign_id, node_type, updated_at DESC);

                CREATE TABLE IF NOT EXISTS kb_edges (
                    id TEXT PRIMARY KEY,
                    campaign_id TEXT NOT NULL,
                    src_id TEXT NOT NULL,
                    edge_type TEXT NOT NULL,
                    dst_id TEXT NOT NULL,
                    weight REAL NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_kb_edges_campaign_src
                    ON kb_edges(campaign_id, src_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_kb_edges_campaign_dst
                    ON kb_edges(campaign_id, dst_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS kb_events (
                    id TEXT PRIMARY KEY,
                    campaign_id TEXT NOT NULL,
                    tick INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_kb_events_campaign_tick
                    ON kb_events(campaign_id, tick DESC, created_at DESC);

                CREATE TABLE IF NOT EXISTS kb_artifacts (
                    id TEXT PRIMARY KEY,
                    campaign_id TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    uri TEXT,
                    content_text TEXT,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_kb_artifacts_campaign_type
                    ON kb_artifacts(campaign_id, artifact_type, created_at DESC);
                """
            )

    def upsert_node(self, node: NodeRecord) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO kb_nodes (
                    id, campaign_id, node_type, title, summary, status,
                    confidence, payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    summary=excluded.summary,
                    status=excluded.status,
                    confidence=excluded.confidence,
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (
                    node.id,
                    node.campaign_id,
                    node.node_type,
                    node.title,
                    node.summary,
                    node.status,
                    node.confidence,
                    json.dumps(node.payload),
                    node.created_at,
                    node.updated_at,
                ),
            )

    def add_edge(self, edge: EdgeRecord) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO kb_edges (
                    id, campaign_id, src_id, edge_type, dst_id, weight,
                    payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    edge.id,
                    edge.campaign_id,
                    edge.src_id,
                    edge.edge_type,
                    edge.dst_id,
                    edge.weight,
                    json.dumps(edge.payload),
                    edge.created_at,
                ),
            )

    def add_event(self, event: EventRecord) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO kb_events (
                    id, campaign_id, tick, event_type, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.campaign_id,
                    event.tick,
                    event.event_type,
                    json.dumps(event.payload),
                    event.created_at,
                ),
            )

    def add_artifact(self, artifact: ArtifactRecord) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO kb_artifacts (
                    id, campaign_id, artifact_type, title, uri, content_text, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.id,
                    artifact.campaign_id,
                    artifact.artifact_type,
                    artifact.title,
                    artifact.uri,
                    artifact.content_text,
                    json.dumps(artifact.metadata),
                    artifact.created_at,
                ),
            )

    def get_node(self, campaign_id: str, node_id: str) -> NodeRecord | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM kb_nodes WHERE campaign_id = ? AND id = ?",
                (campaign_id, node_id),
            ).fetchone()
        return self._row_to_node(row) if row else None

    def list_nodes(self, campaign_id: str, *, node_type: str | None = None, limit: int = 100) -> list[NodeRecord]:
        query = "SELECT * FROM kb_nodes WHERE campaign_id = ?"
        params = [campaign_id]
        if node_type:
            query += " AND node_type = ?"
            params.append(node_type)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_node(row) for row in rows]

    def list_edges(self, campaign_id: str, *, src_id: str | None = None, dst_id: str | None = None, edge_type: str | None = None, limit: int = 200) -> list[EdgeRecord]:
        query = "SELECT * FROM kb_edges WHERE campaign_id = ?"
        params = [campaign_id]
        if src_id:
            query += " AND src_id = ?"
            params.append(src_id)
        if dst_id:
            query += " AND dst_id = ?"
            params.append(dst_id)
        if edge_type:
            query += " AND edge_type = ?"
            params.append(edge_type)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_edge(row) for row in rows]

    def list_events(self, campaign_id: str, *, limit: int = 100) -> list[EventRecord]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM kb_events WHERE campaign_id = ? ORDER BY tick DESC, created_at DESC LIMIT ?",
                (campaign_id, limit),
            ).fetchall()
        return [self._row_to_event(row) for row in rows]

    def list_artifacts(self, campaign_id: str, *, artifact_type: str | None = None, limit: int = 100) -> list[ArtifactRecord]:
        query = "SELECT * FROM kb_artifacts WHERE campaign_id = ?"
        params = [campaign_id]
        if artifact_type:
            query += " AND artifact_type = ?"
            params.append(artifact_type)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_artifact(row) for row in rows]

    @staticmethod
    def _row_to_node(row: sqlite3.Row) -> NodeRecord:
        return NodeRecord(
            id=row["id"],
            campaign_id=row["campaign_id"],
            node_type=row["node_type"],
            title=row["title"],
            summary=row["summary"],
            status=row["status"],
            confidence=row["confidence"],
            payload=json.loads(row["payload_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_edge(row: sqlite3.Row) -> EdgeRecord:
        return EdgeRecord(
            id=row["id"],
            campaign_id=row["campaign_id"],
            src_id=row["src_id"],
            edge_type=row["edge_type"],
            dst_id=row["dst_id"],
            weight=row["weight"],
            payload=json.loads(row["payload_json"]),
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> EventRecord:
        return EventRecord(
            id=row["id"],
            campaign_id=row["campaign_id"],
            tick=row["tick"],
            event_type=row["event_type"],
            payload=json.loads(row["payload_json"]),
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_artifact(row: sqlite3.Row) -> ArtifactRecord:
        return ArtifactRecord(
            id=row["id"],
            campaign_id=row["campaign_id"],
            artifact_type=row["artifact_type"],
            title=row["title"],
            uri=row["uri"],
            content_text=row["content_text"],
            metadata=json.loads(row["metadata_json"]),
            created_at=row["created_at"],
        )
