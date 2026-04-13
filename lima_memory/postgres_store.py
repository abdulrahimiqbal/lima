from __future__ import annotations

import json
from pathlib import Path

from .models import ArtifactRecord, EdgeRecord, EventRecord, NodeRecord
from .store import KnowledgeStore


class PostgresKnowledgeStore(KnowledgeStore):
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def connect(self):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "psycopg is required for Postgres memory store; install psycopg[binary]."
            ) from exc
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def init(self) -> None:
        schema_path = Path(__file__).with_name("postgres_schema.sql")
        schema_sql = schema_path.read_text()
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(schema_sql)
            conn.commit()

    def upsert_node(self, node: NodeRecord) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO kb_nodes (
                        id, campaign_id, node_type, title, summary, status,
                        confidence, payload_json, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::timestamptz, %s::timestamptz)
                    ON CONFLICT(id) DO UPDATE SET
                        title = EXCLUDED.title,
                        summary = EXCLUDED.summary,
                        status = EXCLUDED.status,
                        confidence = EXCLUDED.confidence,
                        payload_json = EXCLUDED.payload_json,
                        updated_at = EXCLUDED.updated_at
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
            conn.commit()

    def add_edge(self, edge: EdgeRecord) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO kb_edges (
                        id, campaign_id, src_id, edge_type, dst_id, weight,
                        payload_json, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::timestamptz)
                    ON CONFLICT(id) DO UPDATE SET
                        campaign_id = EXCLUDED.campaign_id,
                        src_id = EXCLUDED.src_id,
                        edge_type = EXCLUDED.edge_type,
                        dst_id = EXCLUDED.dst_id,
                        weight = EXCLUDED.weight,
                        payload_json = EXCLUDED.payload_json,
                        created_at = EXCLUDED.created_at
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
            conn.commit()

    def add_event(self, event: EventRecord) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO kb_events (
                        id, campaign_id, tick, event_type, payload_json, created_at
                    ) VALUES (%s, %s, %s, %s, %s::jsonb, %s::timestamptz)
                    ON CONFLICT(id) DO UPDATE SET
                        campaign_id = EXCLUDED.campaign_id,
                        tick = EXCLUDED.tick,
                        event_type = EXCLUDED.event_type,
                        payload_json = EXCLUDED.payload_json,
                        created_at = EXCLUDED.created_at
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
            conn.commit()

    def add_artifact(self, artifact: ArtifactRecord) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO kb_artifacts (
                        id, campaign_id, artifact_type, title, uri, content_text,
                        metadata_json, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::timestamptz)
                    ON CONFLICT(id) DO UPDATE SET
                        campaign_id = EXCLUDED.campaign_id,
                        artifact_type = EXCLUDED.artifact_type,
                        title = EXCLUDED.title,
                        uri = EXCLUDED.uri,
                        content_text = EXCLUDED.content_text,
                        metadata_json = EXCLUDED.metadata_json,
                        created_at = EXCLUDED.created_at
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
            conn.commit()

    def get_node(self, campaign_id: str, node_id: str) -> NodeRecord | None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM kb_nodes WHERE campaign_id = %s AND id = %s",
                    (campaign_id, node_id),
                )
                row = cur.fetchone()
        return self._row_to_node(row) if row else None

    def list_nodes(
        self,
        campaign_id: str,
        *,
        node_type: str | None = None,
        limit: int = 100,
    ) -> list[NodeRecord]:
        query = "SELECT * FROM kb_nodes WHERE campaign_id = %s"
        params: list[object] = [campaign_id]
        if node_type:
            query += " AND node_type = %s"
            params.append(node_type)
        query += " ORDER BY updated_at DESC LIMIT %s"
        params.append(limit)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
        return [self._row_to_node(row) for row in rows]

    def list_edges(
        self,
        campaign_id: str,
        *,
        src_id: str | None = None,
        dst_id: str | None = None,
        edge_type: str | None = None,
        limit: int = 200,
    ) -> list[EdgeRecord]:
        query = "SELECT * FROM kb_edges WHERE campaign_id = %s"
        params: list[object] = [campaign_id]
        if src_id:
            query += " AND src_id = %s"
            params.append(src_id)
        if dst_id:
            query += " AND dst_id = %s"
            params.append(dst_id)
        if edge_type:
            query += " AND edge_type = %s"
            params.append(edge_type)
        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
        return [self._row_to_edge(row) for row in rows]

    def list_events(self, campaign_id: str, *, limit: int = 100) -> list[EventRecord]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM kb_events
                    WHERE campaign_id = %s
                    ORDER BY tick DESC, created_at DESC
                    LIMIT %s
                    """,
                    (campaign_id, limit),
                )
                rows = cur.fetchall()
        return [self._row_to_event(row) for row in rows]

    def list_artifacts(
        self,
        campaign_id: str,
        *,
        artifact_type: str | None = None,
        limit: int = 100,
    ) -> list[ArtifactRecord]:
        query = "SELECT * FROM kb_artifacts WHERE campaign_id = %s"
        params: list[object] = [campaign_id]
        if artifact_type:
            query += " AND artifact_type = %s"
            params.append(artifact_type)
        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
        return [self._row_to_artifact(row) for row in rows]

    @staticmethod
    def _row_to_node(row: dict) -> NodeRecord:
        return NodeRecord(
            id=row["id"],
            campaign_id=row["campaign_id"],
            node_type=row["node_type"],
            title=row["title"],
            summary=row["summary"],
            status=row["status"],
            confidence=row["confidence"],
            payload=row["payload_json"] or {},
            created_at=row["created_at"].isoformat(),
            updated_at=row["updated_at"].isoformat(),
        )

    @staticmethod
    def _row_to_edge(row: dict) -> EdgeRecord:
        return EdgeRecord(
            id=row["id"],
            campaign_id=row["campaign_id"],
            src_id=row["src_id"],
            edge_type=row["edge_type"],
            dst_id=row["dst_id"],
            weight=row["weight"],
            payload=row["payload_json"] or {},
            created_at=row["created_at"].isoformat(),
        )

    @staticmethod
    def _row_to_event(row: dict) -> EventRecord:
        return EventRecord(
            id=row["id"],
            campaign_id=row["campaign_id"],
            tick=row["tick"],
            event_type=row["event_type"],
            payload=row["payload_json"] or {},
            created_at=row["created_at"].isoformat(),
        )

    @staticmethod
    def _row_to_artifact(row: dict) -> ArtifactRecord:
        return ArtifactRecord(
            id=row["id"],
            campaign_id=row["campaign_id"],
            artifact_type=row["artifact_type"],
            title=row["title"],
            uri=row["uri"],
            content_text=row["content_text"],
            metadata=row["metadata_json"] or {},
            created_at=row["created_at"].isoformat(),
        )
