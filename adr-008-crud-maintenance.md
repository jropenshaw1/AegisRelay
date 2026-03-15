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
