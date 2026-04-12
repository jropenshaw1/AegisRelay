-- SQLite schema for tests / local demo (no pgvector — embedding stored as TEXT stub).
CREATE TABLE relay_requests (
    relay_id TEXT PRIMARY KEY,
    human_actor_id TEXT NOT NULL,
    provider_name TEXT NOT NULL,
    provider_model TEXT NOT NULL,
    input_text TEXT NOT NULL,
    operation TEXT DEFAULT 'unknown',
    is_irreversible INTEGER,
    session_id TEXT,
    submitted_at TEXT NOT NULL,
    schema_version TEXT DEFAULT '1.0',
    status TEXT DEFAULT 'pending'
);

CREATE TABLE relay_responses (
    relay_id TEXT PRIMARY KEY REFERENCES relay_requests(relay_id),
    provider_name TEXT NOT NULL,
    provider_model TEXT NOT NULL,
    response_text TEXT NOT NULL,
    provider_request_ts TEXT NOT NULL,
    provider_response_ts TEXT NOT NULL,
    raw_provider_response TEXT,
    schema_version TEXT DEFAULT '1.0'
);

CREATE TABLE memory_records (
    memory_id TEXT PRIMARY KEY,
    relay_id TEXT NOT NULL REFERENCES relay_requests(relay_id),
    body_text TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    trust_tier TEXT,
    temporal_scope TEXT,
    expires_at TEXT,
    embedding_status TEXT DEFAULT 'pending',
    embedding TEXT,
    schema_version TEXT DEFAULT '1.0',
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE (relay_id, content_hash)
);

CREATE TABLE governance_events (
    event_id TEXT PRIMARY KEY,
    relay_id TEXT NOT NULL REFERENCES relay_requests(relay_id),
    event_type TEXT NOT NULL,
    stage TEXT NOT NULL,
    metadata TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE outbox (
    outbox_id TEXT PRIMARY KEY,
    relay_id TEXT NOT NULL REFERENCES relay_requests(relay_id),
    operation TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    last_attempted_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_outbox_pending ON outbox(status) WHERE status = 'pending';
CREATE INDEX idx_memory_embedding ON memory_records(embedding_status) WHERE embedding_status = 'pending';
CREATE INDEX idx_governance_relay ON governance_events(relay_id);
