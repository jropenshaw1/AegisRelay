# AegisRelay — Phase 2 Implementation Handoff
**Date:** April 11, 2026
**Prepared by:** Claude (Project Lead)
**Implementation owner:** Cursor
**Spec authority:** `docs/03_Integration_Design_v1.0.md`
**ADR authority:** `docs/02_ADR_Log_v1.0.md`
**Gee scope review:** OpenBrain thought `f648ab71` (March 31, 2026)

---

## Current State — Phase 1 Complete

Phase 1 is live, tested, and committed (`e651db3`, March 21, 2026). 14/14 tests passing.

### Existing source tree
```
src/aegisrelay/
├── __init__.py
├── health.py
├── models/
│   ├── __init__.py
│   ├── contracts.py        ← CanonicalRelayRequest, NormalizedProviderResponse
│   └── lens.py             ← LensObservation (if exists) — verify
├── governance/
│   ├── __init__.py
│   ├── lens_constants.py   ← LENS_BEHAVIORS registry, signal IDs, tags
│   ├── lens_pre_call.py    ← evaluate_pre_call() — 2 observations always
│   └── lens_post_call.py   ← evaluate_post_call() — 2 observations always
tests/
├── test_health.py
└── test_phase1.py           ← 14 tests covering constants, pre_call, post_call
```

### Phase 1 contracts (already implemented in `models/contracts.py`)
- `CanonicalRelayRequest` — `input_text`, `operation` (Literal["read","write","unknown"]), `schema_version`
- `NormalizedProviderResponse` — `body_text`, `schema_version`

### Phase 1 decisions still in force
- ALWAYS-TWO: Pre-call always returns exactly 2 observations; post-call always returns exactly 2
- `confidence = None` when `trigger_fired = False` (not zero — means "not evaluated")
- Persistence policy: ALL observations written regardless of trigger_fired
- Reframe Offers: strict AND (phrase match AND length ratio)
- Irreversibility matching: word-boundary regex
- Operation enum: locked to `["read", "write", "unknown"]` for Phase 2 (Gee review)

---

## Phase 2 Scope

### What to build (all items required for Phase 2 complete):

#### 1. Extended Pydantic Models (ADR-003)

**Extend `CanonicalRelayRequest`** — add fields from handoff v3:
- `relay_id: str`
- `human_actor_id: str`
- `provider_name: str`
- `provider_model: str`
- `session_id: Optional[str]`
- `submitted_at: datetime`
- `is_irreversible: Optional[bool]`

Keep existing `input_text`, `operation`, `schema_version`. Reconcile with Phase 1 model — extend, don't break existing tests.

**`CanonicalRelayResponse`** — full post-pipeline response:
- `relay_id: str`
- `provider_name: str`
- `provider_model: str`
- `response_text: str`
- `provider_request_ts: datetime`
- `provider_response_ts: datetime`
- `schema_version: str`
- `raw_provider_response: Optional[dict]`

**`MemoryRecord`** — governed, retrievable memory unit:
- `memory_id: str`
- `relay_id: str`
- `body_text: str`
- `content_hash: str` (ADR-005 idempotency)
- `trust_tier: Optional[str]`
- `temporal_scope: Optional[str]`
- `expires_at: Optional[datetime]`
- `embedding_status: str` (default "pending")
- `schema_version: str`

**`GovernanceEvent`** — new model for LENS observations and pipeline events:
- `event_id: str`
- `relay_id: str`
- `event_type: str` (e.g., "lens_observation")
- `stage: str` (e.g., "pre_call", "post_call", "pipeline_stage_3")
- `metadata: dict` (JSON — behavior, trigger_fired, confidence, observation, lens_version)
- `created_at: datetime`

#### 2. Postgres DDL (ADR-002)

Define SQL schema for the following tables. Use pgvector extension for embeddings.

```sql
-- relay_requests: inbound relay log
CREATE TABLE relay_requests (
    relay_id TEXT PRIMARY KEY,
    human_actor_id TEXT NOT NULL,
    provider_name TEXT NOT NULL,
    provider_model TEXT NOT NULL,
    input_text TEXT NOT NULL,
    operation TEXT DEFAULT 'unknown',
    is_irreversible BOOLEAN,
    session_id TEXT,
    submitted_at TIMESTAMPTZ NOT NULL,
    schema_version TEXT DEFAULT '1.0',
    status TEXT DEFAULT 'pending'  -- pending | in_progress | complete | failed
);

-- relay_responses: provider output (post-adapter, pre-pipeline)
CREATE TABLE relay_responses (
    relay_id TEXT PRIMARY KEY REFERENCES relay_requests(relay_id),
    provider_name TEXT NOT NULL,
    provider_model TEXT NOT NULL,
    response_text TEXT NOT NULL,
    provider_request_ts TIMESTAMPTZ NOT NULL,
    provider_response_ts TIMESTAMPTZ NOT NULL,
    raw_provider_response JSONB,
    schema_version TEXT DEFAULT '1.0'
);

-- memory_records: governed, retrievable memory units (post-pipeline)
CREATE TABLE memory_records (
    memory_id TEXT PRIMARY KEY,
    relay_id TEXT NOT NULL REFERENCES relay_requests(relay_id),
    body_text TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    trust_tier TEXT,
    temporal_scope TEXT,
    expires_at TIMESTAMPTZ,
    embedding_status TEXT DEFAULT 'pending',
    embedding vector(1536),
    schema_version TEXT DEFAULT '1.0',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- governance_events: LENS observations + pipeline audit trail
CREATE TABLE governance_events (
    event_id TEXT PRIMARY KEY,
    relay_id TEXT NOT NULL REFERENCES relay_requests(relay_id),
    event_type TEXT NOT NULL,
    stage TEXT NOT NULL,
    metadata JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- outbox: durable write-behind for async operations
CREATE TABLE outbox (
    outbox_id TEXT PRIMARY KEY,
    relay_id TEXT NOT NULL REFERENCES relay_requests(relay_id),
    operation TEXT NOT NULL,  -- 'embed' | 'sync_openbrain'
    payload JSONB NOT NULL,
    status TEXT DEFAULT 'pending',  -- pending | processing | complete | failed
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    last_attempted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_outbox_pending ON outbox(status) WHERE status = 'pending';
CREATE INDEX idx_memory_embedding ON memory_records(embedding_status) WHERE embedding_status = 'pending';
CREATE INDEX idx_governance_relay ON governance_events(relay_id);
```

Place DDL file at `db/schema.sql`.

**NOTE:** For Phase 2, tests should use SQLite where possible or mock the database layer. A live Postgres instance is not required for the portfolio demonstration. The DDL defines the production schema; the abstraction layer (see item 5) allows SQLite for tests.

#### 3. Provider Adapters

Create `adapters/` module with:

**`adapters/base.py`** — abstract base class:
```python
class ProviderAdapter(ABC):
    @abstractmethod
    async def send(self, request: CanonicalRelayRequest) -> NormalizedProviderResponse:
        ...
```

**`adapters/perplexity.py`** — Perplexity/Sonar adapter (primary — Lexi relay):
- Accepts CanonicalRelayRequest
- Calls Perplexity API (sonar-pro default)
- Returns NormalizedProviderResponse
- Handles API key via secrets abstraction (see item 5)

**`adapters/stub.py`** — test/demo adapter:
- Returns canned responses for testing
- No external API calls

Grok adapter is deferred — Grok is on sabbatical.

#### 4. Full Eight-Stage Governance Pipeline (ADR-004)

Replace the Phase 1 stub `governance/pipeline.py` with full implementation:

1. **Normalize** — provider response → canonical form
2. **Segment** — split response into discrete claims/units
3. **Classify** — epistemic class + trust tier; LENS Cognitive Model Disclosure hook
4. **Mark Uncertainty** — flag uncertain claims; LENS Uncertainty Flagging hook
5. **Apply Temporal Policy** — temporal_scope, expires_at per ADR-006
6. **Redact** — apply redaction rules (stub for Phase 2 — no sensitive data patterns defined yet)
7. **Deduplicate** — content_hash per ADR-005
8. **Persist** — write MemoryRecord + ALL governance_events in single transaction

Pipeline must be **deterministic under retries** (Gee review — idempotency + replay safety). Same input → same output. Content hash ensures deduplication on replay.

Stage 3/4 LENS hooks: implement Cognitive Model Disclosure and Uncertainty Flagging per `03_Integration_Design_v1.0.md` §5.

#### 5. Secrets / Config Abstraction

Per Gee review — hybrid model:
```python
class SecretsProvider(ABC):
    @abstractmethod
    def get(self, key: str) -> str: ...

class EnvSecretsProvider(SecretsProvider):
    """Reads from environment variables. Default for dev/demo."""
    def get(self, key: str) -> str:
        return os.environ[key]
```

API keys loaded via `SecretsProvider`, not hardcoded. `.env` file in `.gitignore`.

#### 6. CRUD Layer (`admin/`)

**`admin/crud_service.py`**:
- `create_relay(request: CanonicalRelayRequest) -> str` — persist request, return relay_id
- `get_relay(relay_id: str) -> RelayAuditBundle` — returns request + response + memory records + ALL governance events (including LENS observations)
- `list_relays(limit, offset, filters) -> list[RelaySummary]`

**`RelayAuditBundle`** — the full retrieval type:
```python
class RelayAuditBundle(BaseModel):
    request: CanonicalRelayRequest
    response: Optional[CanonicalRelayResponse]
    memory_records: list[MemoryRecord]
    governance_events: list[GovernanceEvent]
```

This is the portfolio money shot — `get_relay()` returns the complete audit trail showing every governance decision made on a single relay.

#### 7. Outbox + Async Workers (ADR-007)

**Outbox pattern:**
- Stage 8 persist writes outbox entries alongside memory records (same transaction)
- Two outbox operation types: `embed` (trigger embedding), `sync_openbrain` (selective OB sync)

**Embedding worker** (`workers/embedding_worker.py`):
- Polls outbox for `operation = 'embed'` with `status = 'pending'`
- Generates embedding (stub — returns zero vector for Phase 2; real implementation uses OpenAI/Anthropic embedding API)
- Updates `memory_records.embedding` and `memory_records.embedding_status = 'complete'`
- Marks outbox entry complete
- Retry logic: increment attempts, fail after max_attempts

**OB sync worker** (`workers/ob_sync_worker.py`):
- Polls outbox for `operation = 'sync_openbrain'` with `status = 'pending'`
- Filters: only sync records where `trust_tier IN ('system_verified', 'provider_asserted_with_citations')` AND `embedding_status = 'complete'` AND `expires_at IS NULL OR expires_at > NOW()`
- Writes to OpenBrain with `[source:aegisrelay]` tag
- Stub for Phase 2 — define interface, implement sync logic as pass-through

#### 8. Relay Service — Main Orchestrator

**`relay_service.py`**:
```python
async def execute_relay(request: CanonicalRelayRequest, adapter: ProviderAdapter) -> RelayAuditBundle:
    """
    Full relay execution:
    1. Persist request (status = 'pending')
    2. Run pre-call LENS hooks
    3. Call provider via adapter
    4. Persist response
    5. Run post-call LENS hooks
    6. Run eight-stage governance pipeline (with pre+post observations injected)
    7. Update request status = 'complete'
    8. Return RelayAuditBundle
    """
```

Two-transaction model (Gee review, decided March 21):
- Transaction 1: persist request (status tracking)
- Transaction 2: persist response + memory records + governance events + outbox entries (atomic)

#### 9. Cascade Trigger (Decision Checkpoints enhancement)

Add `has_downstream_effects: Optional[bool] = None` to `CanonicalRelayRequest`.
When True, fires an additional signal in `evaluate_pre_call()`.
Deferred from Phase 1 — now in scope.

---

## Database Abstraction for Testing

Implement a `db/` module with:
```python
class DatabaseProvider(ABC):
    @abstractmethod
    def execute(self, query: str, params: dict) -> Any: ...
    @abstractmethod
    def transaction(self) -> ContextManager: ...

class SQLiteProvider(DatabaseProvider):
    """For tests and local demo."""

class PostgresProvider(DatabaseProvider):
    """For production. Requires psycopg2/asyncpg."""
```

All CRUD and pipeline persistence goes through `DatabaseProvider`. Tests use `SQLiteProvider`. DDL in `db/schema.sql` is the Postgres definition; a parallel `db/schema_sqlite.sql` can be generated for test compatibility (drop pgvector column, use TEXT for vector).

---

## Test Requirements (Phase 2)

Target: ≥22 tests (up from 14). All existing Phase 1 tests must continue to pass.

**New test categories:**
- Model validation (extended contracts, GovernanceEvent, RelayAuditBundle)
- Pipeline stages (at least one test per stage with real logic)
- CRUD operations (create_relay, get_relay with full audit bundle)
- Outbox (entries created on persist, retry logic)
- Idempotency (same relay replayed → same content_hash, no duplicate memory records)
- End-to-end (relay → pre-call → adapter → post-call → pipeline → persist → get_relay returns complete bundle)

---

## File Structure — Phase 2 Target

```
src/aegisrelay/
├── __init__.py
├── health.py
├── relay_service.py              ← NEW — main orchestrator
├── models/
│   ├── __init__.py
│   ├── contracts.py              ← EXTEND — add relay_id, provider fields, etc.
│   ├── lens.py                   ← existing (verify)
│   ├── memory_record.py          ← NEW — full MemoryRecord
│   ├── governance_event.py       ← NEW
│   └── audit_bundle.py           ← NEW — RelayAuditBundle
├── governance/
│   ├── __init__.py
│   ├── lens_constants.py         ← existing (no changes)
│   ├── lens_pre_call.py          ← UPDATE — add cascade trigger
│   ├── lens_post_call.py         ← existing (no changes)
│   └── pipeline.py               ← REPLACE stub with full implementation
├── adapters/
│   ├── __init__.py
│   ├── base.py                   ← NEW — ProviderAdapter ABC
│   ├── perplexity.py             ← NEW — Perplexity/Sonar adapter
│   └── stub.py                   ← NEW — test adapter
├── admin/
│   ├── __init__.py
│   └── crud_service.py           ← NEW — create_relay, get_relay, list_relays
├── db/
│   ├── __init__.py
│   ├── schema.sql                ← NEW — Postgres DDL
│   ├── schema_sqlite.sql         ← NEW — SQLite DDL for tests
│   ├── base.py                   ← NEW — DatabaseProvider ABC
│   ├── sqlite_provider.py        ← NEW
│   └── postgres_provider.py      ← NEW (can be stub with interface)
├── workers/
│   ├── __init__.py
│   ├── embedding_worker.py       ← NEW (stub implementation)
│   └── ob_sync_worker.py         ← NEW (stub implementation)
└── config/
    ├── __init__.py
    └── secrets.py                ← NEW — SecretsProvider abstraction
tests/
├── test_health.py                ← existing
├── test_phase1.py                ← existing — must still pass
├── test_models.py                ← NEW
├── test_pipeline.py              ← NEW
├── test_crud.py                  ← NEW
├── test_outbox.py                ← NEW
├── test_idempotency.py           ← NEW
└── test_end_to_end.py            ← NEW
```

---

## Decisions Locked (do not revisit)

| Decision | Source | Date |
|---|---|---|
| ALWAYS-TWO observation pattern | Claude + Gee | March 21, 2026 |
| Pre-call persistence: two transactions | Claude + Cursor v3 | March 21, 2026 |
| confidence = None when not fired | Cursor v3 | March 21, 2026 |
| Reframe: strict AND | Cursor v3 | March 21, 2026 |
| Operation enum: ["read","write","unknown"] | Gee review | March 31, 2026 |
| Idempotency + replay safety in scope | Gee review | March 31, 2026 |
| Lexi = read-only OB, writes via relay only | Gee review | March 31, 2026 |
| Hybrid secrets: env + abstraction | Gee review | March 31, 2026 |
| NormalizedProviderResponse formalized | Gee review | March 31, 2026 |
| All observations persisted (not sparse) | Claude + Gee | March 21, 2026 |

---

## Definition of Done — Phase 2

- [ ] Extended Pydantic models per ADR-003 (request, response, memory, governance event, audit bundle)
- [ ] DDL defined (`db/schema.sql` and `db/schema_sqlite.sql`)
- [ ] Database abstraction layer (SQLiteProvider working for tests)
- [ ] At least one provider adapter (stub) + Perplexity adapter (interface complete, can stub API call)
- [ ] Full eight-stage pipeline replaces Phase 1 stubs — at least normalize, deduplicate, persist implemented with real logic
- [ ] LENS Stage 3 (Cognitive Model Disclosure) and Stage 4 (Uncertainty Flagging) hooks implemented
- [ ] CRUD service: create_relay, get_relay (returns RelayAuditBundle with full audit trail)
- [ ] Outbox table populated on persist; worker interfaces defined
- [ ] Cascade trigger added to pre-call Decision Checkpoints
- [ ] Secrets abstraction (EnvSecretsProvider)
- [ ] relay_service.execute_relay() orchestrates full flow
- [ ] ≥22 tests passing (14 Phase 1 + ≥8 Phase 2)
- [ ] Idempotency test: replay produces same result, no duplicates
- [ ] End-to-end test: relay → full pipeline → get_relay returns complete bundle
- [ ] README updated: status badge "Phase 2 complete", scope description updated
- [ ] All changes committed and pushed to GitHub

---

## Standards

- TSH-9 and LENS apply to all implementation
- Pydantic v2 with `model_config = {"extra": "forbid"}` on all models
- Type hints on all functions
- Docstrings on all public functions
- No credentials in repo — `.env` in `.gitignore`

---

*Handoff prepared from: Phase 1 codebase review, Handoff v3, Integration Design v1.0, ADR Log v1.0, Gee scope review (OB f648ab71)*
*Implementation owner: Cursor*
