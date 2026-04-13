-- Postgres-first schema for long-term LIMA deployment.
-- Start with this when moving from SQLite projection to a durable knowledge base.

CREATE TABLE IF NOT EXISTS kb_nodes (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    node_type TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    confidence DOUBLE PRECISION,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kb_nodes_campaign_type
    ON kb_nodes (campaign_id, node_type, updated_at DESC);

CREATE TABLE IF NOT EXISTS kb_edges (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    src_id TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    dst_id TEXT NOT NULL,
    weight DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kb_edges_campaign_src
    ON kb_edges (campaign_id, src_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_kb_edges_campaign_dst
    ON kb_edges (campaign_id, dst_id, created_at DESC);

CREATE TABLE IF NOT EXISTS kb_events (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kb_events_campaign_tick
    ON kb_events (campaign_id, tick DESC, created_at DESC);

CREATE TABLE IF NOT EXISTS kb_artifacts (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    title TEXT NOT NULL,
    uri TEXT,
    content_text TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kb_artifacts_campaign_type
    ON kb_artifacts (campaign_id, artifact_type, created_at DESC);
