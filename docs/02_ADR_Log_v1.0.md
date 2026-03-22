# AegisRelay — Architecture Decision Records (Compiled Reference)

**Project:** AegisRelay
**Owner:** Jonathan Openshaw
**Date:** March 16, 2026
**Status:** All ADRs accepted — approved for build

---

## ADR Index

| ADR | Title | Status |
|---|---|---|
| ADR-001 | Product Boundary | Accepted |
| ADR-002 | Storage Strategy | Accepted |
| ADR-003 | Canonical Contracts | Accepted |
| ADR-004 | Governance Semantics | Accepted |
| ADR-005 | Idempotency Strategy | Accepted |
| ADR-006 | Expiry and Supersession | Accepted |
| ADR-007 | Embedding Lifecycle | Accepted |
| ADR-008 | Data Maintenance and CRUD Strategy | Accepted |

---

## ADR-001: Product Boundary

**Date:** March 16, 2026 | **Status:** Accepted

### Context
AegisRelay was initially conceived as a module inside PipelinePilot. A second option was to extend OpenBrain. The governing principle: AI has flipped the build paradigm — there is no longer a cost penalty for doing it right the first time.

### Decision
AegisRelay is a standalone, independent service. It shares no codebase, database, or process boundary with PipelinePilot or OpenBrain. Both existing systems remain untouched.

### Alternatives Considered
- **Extend PipelinePilot** — rejected. PipelinePilot was built under a deliberate KISS mandate for a single purpose. A multi-provider AI ingress service is a different system class.
- **Extend OpenBrain** — rejected. Covered in ADR-002.

### Consequences
- AegisRelay is a new repository: `github.com/jropenshaw1/AegisRelay` (public, Apache 2.0)
- PipelinePilot may become a consumer of AegisRelay's retrieval API in a future version — forward integration, not a dependency
- AegisRelay's architecture and ADR discipline stand as an independent portfolio artifact

---

## ADR-002: Storage Strategy

**Date:** March 16, 2026 | **Status:** Accepted

### Context
OpenBrain exists as shared general-purpose memory. Writing unclassified provider responses into it creates semantic contamination — contradictory claims, stale research, and unverified assertions accumulate alongside evergreen facts with no way to distinguish them at query time.

### Decision
AegisRelay uses a new, dedicated PostgreSQL + pgvector database as its primary store. OpenBrain is a downstream consumer only — selective sync of high-trust, well-classified records via an optional module. OpenBrain is never the system of record for AegisRelay data.

### Alternatives Considered
- **Write directly to OpenBrain** — rejected. No epistemic classification, temporal scoping, trust tiering, or governance audit trail.
- **Extend OpenBrain schema** — rejected. Retrofitting purpose into general-purpose infrastructure produces a system that does two things poorly.
- **External vector DB** — deferred. pgvector on Postgres is sufficient for v1 scale.

### Consequences
- New Postgres + pgvector database provisioned for AegisRelay
- OpenBrain remains clean and uncontaminated
- Optional `/sync/openbrain.py` exports only: `trust_tier` ∈ {system_verified, provider_asserted with citations}, `status = active`, `embedding_status = complete`, `expires_at` null or future

---

## ADR-003: Canonical Contracts

**Date:** March 16, 2026 | **Status:** Accepted

### Context
Provider responses arrive in provider-specific shapes. Without a normalization boundary, provider-specific shape leaks into governance and persistence layers — every provider change becomes a multi-layer change.

### Decision
Three separate typed Pydantic contracts are maintained:
1. **CanonicalRelayRequest** — what was asked, of whom, and why (pre-provider call)
2. **CanonicalRelayResponse** — provider-normalized, governance-annotated result (post-governance pipeline)
3. **MemoryRecord** — governed, retrievable memory unit (written to persistence)

Provider-specific response shapes are normalized at the adapter boundary and never leak downstream.

### Alternatives Considered
- **Single unified contract** — rejected. Conflates provider transaction with governed memory; makes partial failures unrepresentable; couples provider semantics to storage.

### Consequences
- Provider adapters produce `CanonicalRelayResponse` only
- Governance pipeline consumes `CanonicalRelayResponse` → produces `MemoryRecord`
- Adding a new provider requires only a new adapter; governance and persistence unaffected
- `schema_version` field on both contracts enables safe evolution

---

## ADR-004: Governance Semantics

**Date:** March 16, 2026 | **Status:** Accepted

### Context
TSH-9 and LENS are the governing standards for all AI interactions. The question was how to implement them — as documentation, as prompt instructions, or as executable code. Governing anchor: אֲנִי קוֹחֵז בָּאֱמֶת.

### Decision
TSH-9 and LENS are implemented as a concrete, versioned, testable governance pipeline with eight sequential stages. Every stage appends to `governance_checks_applied`. Every transform is recorded in `governance_events`. Pipeline version is required on every `MemoryRecord`. Governance is inspectable, not asserted.

**Eight stages:** Normalize → Segment → Classify → Mark uncertainty → Apply temporal policy → Redact → Deduplicate → Persist (with governance events in same transaction)

### Alternatives Considered
- **Documentation/comments** — rejected. Not testable, not verifiable.
- **Prompt instructions** — rejected. Not deterministic, not auditable at record level.
- **Post-processing after storage** — rejected. Record exists in store before governance — already contaminated.
- **ML-based classifiers** — deferred to v2.

### Consequences
- `governance_pipeline_version` is required on every `MemoryRecord`
- Governance changes are releases, not patches
- Re-processing increments `relay_version` and creates new `MemoryRecord` via `parent_memory_id`

---

## ADR-005: Idempotency Strategy

**Date:** March 16, 2026 | **Status:** Accepted

### Context
A relay service writing to persistent store under unreliable conditions must handle retries without duplicate records. Two levels of deduplication required: relay transaction level and memory unit level.

### Decision
Idempotency enforced at two levels:

**Level 1 — Relay level:** `relay_id` is a deterministic key from `human_actor_id + provider_name + provider_model + sha256(normalized_input_text) + session_id`. `UNIQUE` constraint on `relay_requests.relay_id`. Same logical request always returns existing record. Force re-relay via `relay_version` increment.

**Level 2 — Memory unit level:** `content_hash` from normalized `body_text` after governance. `UNIQUE` constraint on `(relay_id, content_hash, segmentation_index)`. Prevents duplicate memory units under retry or replay.

**Key principle:** Idempotency keys on transaction intent, not just content. Two different requests that produce the same response text produce two relay records.

### Alternatives Considered
- **Timestamp-based IDs** — rejected. Not stable across retries.
- **Client-provided idempotency keys** — considered; deterministic server-side computation is simpler.
- **Content-only deduplication** — rejected. Loses audit trail for semantically different requests.

### Consequences
- `domain/idempotency.py` is the canonical implementation — no other module computes these keys
- `UNIQUE` constraints enforced at DB layer, not just application logic
- Outbox uses `relay_id` as correlation key for retry without re-invoking provider

---

## ADR-006: Expiry and Supersession

**Date:** March 16, 2026 | **Status:** Accepted

### Context
Records have varying shelf lives. Without explicit expiry semantics, the corpus accumulates stale content that degrades retrieval quality — the same semantic contamination problem that drove ADR-002, now from within.

### Decision
**Expiry is not deletion.** Expired records remain in store, remain auditable, and are retrievable with explicit `include_expired=True`. Default retrieval excludes expired records automatically.

**Expiry policy by temporal_scope:**

| temporal_scope | Default expires_at |
|---|---|
| evergreen | No expiry |
| time_sensitive | ingested_at + 30 days |
| event_bound | Event date or ingested_at + 7 days |
| session_bound | ingested_at + 24 hours |
| unknown | ingested_at + 90 days |

**Supersession is not deletion.** When a newer record covers the same ground, the older record's `status` → `superseded`, `superseded_at` is set. Both records remain. `parent_memory_id` links them for chain traversal.

**MemoryRecord state machine:**
```
active → expired | superseded | redacted | quarantined
quarantined → active | redacted
```
No transitions back to `active` from `expired` or `superseded`. Terminal states for a given version.

### Alternatives Considered
- **Hard delete** — rejected. Destroys audit lineage.
- **Soft delete with `deleted_at`** — rejected. Conflates "no longer valid" with "should not exist."
- **Database-level TTL** — rejected. Removes records without preserving audit trail.

### Consequences
- Default retrieval query includes `WHERE status = 'active' AND (expires_at IS NULL OR expires_at > NOW())`
- Background job transitions `active` → `expired` based on `expires_at` (state update, not delete)
- OpenBrain sync only exports `active`, non-expired records
- Full version chain reconstructible via `parent_memory_id` traversal

---

## ADR-007: Embedding Lifecycle

**Date:** March 16, 2026 | **Status:** Accepted

### Context
Governed memory records require vector embeddings for semantic similarity retrieval. Embedding generation is external-API dependent, failure-prone, and slower than a DB write. Embedding models also change — without version tracking, corpus integrity cannot be guaranteed across model migrations.

### Decision
**Embeddings are generated server-side, asynchronously, after the memory record is written.**

Write path:
1. Governance produces `MemoryRecord` with `embedding_status = 'pending'`
2. `MemoryRecord` + `governance_events` written in single transaction
3. Embedding job enqueued to `outbox_jobs` in **same transaction**
4. Relay response returned to caller — no blocking on embedding
5. Worker processes job: calls embedding API → writes vector to `memory_embeddings` → updates `embedding_status = 'complete'`

**One embedding model for the entire corpus.** Model is a configuration value. Model changes trigger a migration job that re-embeds all active records. `embedding_model_version` tracked per row.

**`embedding_text_span`** records what was embedded: `full_response`, `answer_only`, or `governance_augmented`.

### Alternatives Considered
- **Synchronous embedding (blocking)** — rejected. Adds 200–2000ms latency; creates failure mode where embedding API unavailability blocks relay success.
- **Client-side embedding** — rejected. Requires API key on desktop; risks model drift across clients producing incompatible vector spaces.
- **On-demand embedding at query time** — rejected. First query after ingestion is slow; result not durably cached.
- **Vectors inline in memory_records** — rejected. ~6KB per record degrades non-vector query performance; migration requires rewriting main record table.

### Consequences
- Records with `embedding_status = 'pending'` are valid and retrievable via metadata filters; excluded from vector search only
- Embedding worker drains outbox independently; failures retried per outbox retry policy
- Re-embedding: set `embedding_status = 'pending'` on target records, enqueue new jobs — worker handles the rest
- Hybrid search (keyword GIN index + vector HNSW index) supported independently

---

*All seven ADRs accepted. AegisRelay approved for build. Next step: Cursor locks Pydantic models and DDL.*
# ADR-008: Data Maintenance and CRUD Strategy

**Date:** March 16, 2026
**Status:** Accepted
**Decider:** Jonathan Openshaw

---

## Context

AegisRelay stores governed memory records with a defined state machine (ADR-006), strict idempotency guarantees (ADR-005), immutable provenance fields, and a governance audit trail (ADR-004). These guarantees only hold if every write and update to the store — including maintenance operations — respects the same constraints that ingestion enforces.

The alternative is what was experienced with OpenBrain: no purpose-built maintenance interface means maintenance happens through Supabase's table editor, one-off SQL scripts, or ad-hoc queries written under pressure. Those paths bypass application-layer constraints, can violate state machine rules, can corrupt idempotency keys, and can silently undermine the provenance guarantees the system was designed to enforce. The semantic contamination problem AegisRelay was built to solve at ingress can be re-introduced at maintenance if there is no governed maintenance layer.

**Governing principle:** A CRUD mechanism intentionally designed with full schema knowledge is the only safe way to maintain governed memory. There is no safe shortcut.

---

## Decision

CRUD is a **core infrastructure component of v1**, designed in the same session as the schema. It is not a convenience feature, not a fast-follow, and not an admin afterthought.

Every maintenance operation against AegisRelay's memory store routes through the CRUD layer. Raw SQL, Supabase dashboard edits, and ad-hoc scripts are explicitly prohibited as maintenance paths in production.

The CRUD layer is:
- **Schema-aware** — knows which fields are immutable and refuses to update them
- **State-machine-aware** — enforces valid transitions from ADR-006; invalid transitions are rejected at the application layer before they reach the DB
- **Constraint-aware** — enforces idempotency rules from ADR-005; updates that would violate `relay_id` or `content_hash` uniqueness are rejected
- **Cascade-aware** — operations with side effects (supersession, expiry, re-embedding) automatically trigger all required downstream updates in a single transaction
- **Audit-emitting** — every maintenance operation produces a `governance_events` row, preserving the full change history

---

## Immutable Fields

The following fields are set at write time and can never be updated by any interface, including the CRUD layer:

| Table | Immutable Fields |
|---|---|
| `relay_requests` | `relay_id`, `relay_version`, `input_text`, `submitted_at`, `prompt_fingerprint` |
| `relay_responses` | `relay_id`, `raw_provider_response`, `provider_request_ts`, `provider_response_ts` |
| `memory_records` | `memory_id`, `relay_id`, `content_hash`, `produced_at`, `ingested_at`, `source_type` |
| `governance_events` | All fields — append-only, no updates ever |
| `relay_requests` (raw payloads) | All fields — forensic archive, never modified |

Any CRUD operation that attempts to update an immutable field returns a `ImmutableFieldViolation` error with the field name and rejected value. No partial updates on rows containing immutable fields.

---

## Valid State Transitions (CRUD-enforced)

The CRUD layer is the sole enforcer of the state machine defined in ADR-006:

```
active      → expired       (manual or background expiry job)
active      → superseded    (supersede operation — requires successor memory_id)
active      → redacted      (redact operation — requires rationale)
active      → quarantined   (quarantine operation — requires reason)
quarantined → active        (release operation — requires reviewer note)
quarantined → redacted      (redact operation — requires rationale)
```

Invalid transitions (e.g., `expired → active`, `superseded → active`, `redacted → anything`) are rejected with a `InvalidStateTransition` error. No exceptions.

---

## CRUD Operations — v1 Scope

### Memory Record Operations

**`redact(memory_id, rationale)`**
Sets `status = 'redacted'`, `is_retrievable = false`, records rationale in `governance_events`. Does not delete `body_text` from DB — stores a redaction marker in its place. Original text preserved in `governance_events` before-snapshot for audit.

**`expire(memory_id)`** / **`expire_by_criteria(filters)`**
Sets `status = 'expired'`, `is_retrievable = false`. Bulk variant accepts filters: `provider_name`, `epistemic_class`, `trust_tier`, `before_date`. Produces one `governance_events` row per affected record.

**`supersede(memory_id, successor_memory_id)`**
Sets `status = 'superseded'`, `superseded_at = now()` on the target. Sets `parent_memory_id` on the successor. Both operations in a single transaction. Rejects if successor does not exist or is not `active`.

**`quarantine(memory_id, reason)`**
Sets `status = 'quarantined'`, `is_retrievable = false`. Records reason in `governance_events`. Used for records flagged for review — not yet adjudicated.

**`release(memory_id, reviewer_note)`**
Transitions `quarantined → active`. Sets `is_retrievable = true`. Records reviewer note in `governance_events`. Only valid from `quarantined` state.

**`extend_expiry(memory_id, new_expires_at)`**
Updates `expires_at` on an `active` record. Validates new date is in the future. Records old and new values in `governance_events`. Cannot be applied to `expired`, `superseded`, or `redacted` records.

**`clear_expiry(memory_id)`**
Sets `expires_at = null` on an `active` record — makes it evergreen. Records in `governance_events`. Cannot be applied to non-active records.

**`reembed(memory_id)`** / **`reembed_by_criteria(filters)`**
Sets `embedding_status = 'pending'`, enqueues new embedding job to outbox. Used when embedding model changes or embedding failed. Does not delete existing vector until new one is successfully written.

**`update_tags(memory_id, tags)`** / **`update_namespaces(memory_id, namespaces)`**
Updates retrieval metadata. Permitted on `active` records only. Records before/after in `governance_events`.

### Relay Operations

**`get_relay(relay_id)`**
Returns full relay audit chain: `relay_requests` + `relay_responses` + all associated `memory_records` + `governance_events` + embedding status. Single call, complete lineage.

**`inspect_outbox(status_filter)`**
Returns outbox jobs filtered by status. Supports `pending`, `failed`, `dead_letter`.

**`retry_outbox_job(job_id)`**
Manually triggers retry of a specific outbox job. Resets `attempt_count` if in `dead_letter` state.

**`drain_outbox()`**
Triggers immediate processing of all `pending` outbox jobs. For use after a network outage or DB unavailability event.

---

## Module Structure

```
aegisrelay/
├── admin/
│   ├── crud_service.py        # All CRUD operations — single entrypoint
│   ├── state_machine.py       # Valid transition map and enforcement
│   ├── immutable_fields.py    # Field immutability registry and validator
│   ├── cascade_handler.py     # Side-effect orchestration (supersession, expiry)
│   └── audit_emitter.py       # governance_events writes for all CRUD ops
```

`admin/crud_service.py` is the **only** permitted interface for maintenance operations. No other module writes directly to `memory_records` outside of the ingestion pipeline.

---

## CLI Surface (v1)

A CLI wrapping `crud_service.py` for direct use:

```bash
aegisrelay admin redact <memory_id> --rationale "..."
aegisrelay admin expire <memory_id>
aegisrelay admin expire-bulk --provider perplexity --before 2026-01-01
aegisrelay admin supersede <memory_id> --successor <memory_id>
aegisrelay admin quarantine <memory_id> --reason "..."
aegisrelay admin release <memory_id> --note "..."
aegisrelay admin extend-expiry <memory_id> --until 2026-06-01
aegisrelay admin clear-expiry <memory_id>
aegisrelay admin reembed <memory_id>
aegisrelay admin reembed-bulk --embedding-status failed
aegisrelay admin get-relay <relay_id>
aegisrelay admin outbox inspect --status failed
aegisrelay admin outbox retry <job_id>
aegisrelay admin outbox drain
```

All CLI commands print a structured summary of what changed and the resulting `governance_events` row ID for traceability.

---

## Admin API (v1.5)

HTTP endpoints under `/admin` exposing the same `crud_service.py` operations for programmatic access by Claude and other AI team members. Deferred to v1.5 — CLI is sufficient for v1 single-user operation.

---

## Alternatives Considered

**CRUD as a fast-follow (v1.5)**
Rejected. Designing CRUD after the schema is final means maintenance semantics were not considered during schema design. Immutable fields, cascade requirements, and state machine transitions directly affect DDL decisions — specifically which fields need `NOT NULL` constraints, which transitions need FK enforcement, and which operations require multi-table transactions. CRUD must be designed alongside the schema, not after it.

**Raw SQL / Supabase dashboard for maintenance**
Rejected. Bypasses all application-layer constraints. Can violate state machine rules, corrupt idempotency keys, update immutable fields, and produce records with incomplete or incorrect governance metadata. The OpenBrain experience demonstrated that an ungoverned maintenance path creates more operational problems than it solves.

**Expose UPDATE/DELETE directly on the API**
Rejected. Generic update endpoints with no constraint awareness are equivalent to raw SQL with an HTTP wrapper. Every maintenance operation is a named, intentional action with defined pre-conditions, post-conditions, and audit requirements. Generic CRUD verbs do not express intent.

---

## Consequences

- `aegisrelay/admin/` is a first-class module in the v1 codebase
- Cursor designs `crud_service.py` interfaces in the same session as the Pydantic models and DDL
- Every maintenance operation is covered by unit tests validating constraint enforcement and state machine rules
- The `governance_events` table grows with every maintenance operation — this is correct and expected; the audit trail is the integrity guarantee
- No maintenance operation ever requires direct DB access — if something cannot be done through the CRUD layer, the CRUD layer needs a new operation, not a bypass
- Future Admin API (v1.5) is a thin HTTP wrapper over `crud_service.py` — no new business logic at the API layer

---

## ADR-009: LENS Constraint Integration

**Date:** March 22, 2026
**Status:** Accepted
**Decided by:** Jonathan Openshaw
**Related:** LENS ADR-009 (mirror decision from LENS perspective)

### Context

ADR-004 established that TSH-9 and LENS are implemented as an eight-stage executable
governance pipeline. It named both standards and defined the pipeline stages. What it did
not define was the precise mapping between LENS's six behaviors and those pipeline stages —
or where in the call flow LENS constraint evaluation sits relative to provider invocation.

This ADR closes that gap. It defines the integration architecture: where LENS hooks into
AegisRelay's call flow, which behaviors map to which pipeline stages, and what the
enforcement boundary looks like at v1.

### The Gap in ADR-004

ADR-004 describes an eight-stage pipeline that operates on the provider *response* — they
are post-call transforms. This is correct for memory governance. But three of LENS's six
behaviors are pre-call or structural — they must fire before or during execution, not after.
ADR-004 did not account for this distinction.

The integration therefore requires two additions to the call flow:
1. A **pre-call evaluation hook** that runs before the provider adapter is invoked
2. A **post-call evaluation hook** that runs after the response is received but before
   the eight-stage pipeline begins

The eight pipeline stages themselves are unchanged.

### Decision

LENS constraint evaluation is integrated into AegisRelay via two hooks that bracket the
provider call. The eight existing pipeline stages are not modified.

**Complete call flow with LENS hooks:**

```
CanonicalRelayRequest in
        │
        ▼
┌─────────────────────┐
│  PRE-CALL HOOK      │  ← LENS: Decision Checkpoints + Assumption Surfacing
│  (lens_pre_call.py) │     Evaluates the request before provider is invoked
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Provider Adapters  │  ← Provider-specific translation (unchanged)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  POST-CALL HOOK     │  ← LENS: Prompt Reflection + Reframe Offers
│  (lens_post_call.py)│     Evaluates the exchange after response received
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Governance         │  ← Eight-stage pipeline (ADR-004) — unchanged
│  Pipeline           │     Stage 3 (Classify): Cognitive Model Disclosure
│                     │     Stage 4 (Mark Uncertainty): Uncertainty Flagging
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Persistence        │  ← LENS observations written to governance_events
│  (Stage 8)          │     tagged [source:lens]
└─────────────────────┘
```

### LENS Behavior to Pipeline Stage Mapping

| LENS Behavior | Hook / Stage | Rationale |
|---------------|-------------|----------|
| Decision Checkpoints | Pre-call hook | Must fire before irreversible action. Evaluates whether the relay request warrants a checkpoint before executing. |
| Assumption Surfacing | Pre-call hook | Key assumptions in the relay request should be surfaced before the provider call commits to an interpretation. |
| Prompt Reflection | Post-call hook | Retrospective — evaluates the exchange after the response is received. |
| Reframe Offers | Post-call hook | Retrospective — evaluates whether the question asked was the question needed. |
| Uncertainty Flagging | Stage 4 — Mark Uncertainty | Direct mapping. LENS defines the trigger conditions; AegisRelay implements the detection. |
| Cognitive Model Disclosure | Stage 3 — Classify | Identifying the analytical frame applied to a response is a classification decision. |

### New Module Structure

```
aegisrelay/
├── governance/
│   ├── pipeline.py          # Existing eight-stage pipeline (ADR-004)
│   ├── lens_pre_call.py     # NEW — Decision Checkpoints + Assumption Surfacing
│   ├── lens_post_call.py    # NEW — Prompt Reflection + Reframe Offers
│   └── lens_constants.py    # NEW — LENS behavior IDs, tags, constraint schema
```

### v1 Enforcement Boundary

**Observational enforcement at v1:** Pre-call and post-call hooks fire, evaluate against
LENS trigger conditions, and write observations to `governance_events`. No blocking, no
automatic retry, no automated violation writes. Human operator reviews governance_events.

**v2 path (defined, not yet implemented):**
- Pre-call hook becomes a blocking gate for Decision Checkpoint events
- Post-call hook evaluates against the full LENS compliance rubric (Functional Spec S7.2)
  and writes LENS-correction thoughts automatically tagged `[source:automated]`

### What Does Not Change

ADR-001 through ADR-008 are unaffected. The eight pipeline stages are unchanged — Stages 3
and 4 gain LENS-specific trigger conditions but their structure and sequence are unmodified.
The canonical contracts gain no new required fields; hook outputs write to governance_events.

### Consequences

- AegisRelay's governance pipeline now fully implements all six LENS behaviors
- The "LENS as executable governance" claim in ADR-004 is fully specified, not asserted
- `governance_events` becomes the LENS observation ledger within AegisRelay
- v1 enforcement is observational — no blocking, no retry, no automated violation writes
- v2 path is defined for both pre-call blocking and automated violation detection
- LENS remains a portable protocol — these hooks implement LENS inside AegisRelay;
  other AI clients implement LENS via canonical reference without requiring AegisRelay
- Full integration specification in `docs/03_Integration_Design_v1.0.md`

---

*AegisRelay ADR Log v1.0 — All ADRs accepted*
*ADR-009 added March 22, 2026*
*Next step: Implementation per 03_Integration_Design_v1.0.md*
