# ADR-006: Expiry and Supersession

**Date:** March 16, 2026
**Status:** Accepted
**Decider:** Jonathan Openshaw

---

## Context

AegisRelay stores provider responses that have varying shelf lives. A real-time job market analysis from Lexi is accurate today and stale in 30 days. A description of the TSH-9 governance framework is evergreen. A statement about a specific job posting's status may be invalidated the moment the position is filled.

Without explicit expiry and supersession semantics, the retrieval layer cannot distinguish current from stale, and the corpus accumulates dead weight that degrades retrieval quality over time — the same semantic contamination problem that drove the decision to build a new store (ADR-002), now from within.

Two related but distinct concepts require separate handling:
- **Expiry** — a record becomes stale based on time, without a replacement
- **Supersession** — a record is replaced by a newer record that covers the same ground with updated or corrected content

---

## Decision

**Expiry is not deletion.**

Expired records remain in the store, remain fully auditable, and can be retrieved with explicit opt-in (`include_expired=True`). Default retrieval excludes expired records silently — callers do not need to filter for them; the query service handles this automatically.

Expiry policy by `temporal_scope`:

| temporal_scope | Default expires_at behavior |
|---|---|
| `evergreen` | No expiry set; manually reviewed on policy cadence |
| `time_sensitive` | `ingested_at + 30 days` (configurable) |
| `event_bound` | Set to the event date if extractable; else `ingested_at + 7 days` |
| `session_bound` | `ingested_at + 24 hours` |
| `unknown` | `ingested_at + 90 days` (conservative default) |

Governance pipeline Stage 5 (Apply temporal policy) is responsible for setting `expires_at`. Individual records can have `expires_at` overridden by the caller or by a manual review process.

**Supersession is not deletion either.**

When a newer relay produces a `MemoryRecord` that covers the same ground as an existing record, the older record's `status` is set to `superseded` and `superseded_at` is recorded. The newer record's `parent_memory_id` points to the superseded record. Both records remain in the store.

Superseded records are excluded from default retrieval (same as expired). The full chain — original, superseded, current — is reconstructible via `parent_memory_id` traversal for any audit query.

**State machine for `MemoryRecord.status`:**

```
active → expired        (time passes, expires_at reached)
active → superseded     (newer record covers same ground)
active → redacted       (governance or manual redaction)
active → quarantined    (flagged for review, not yet adjudicated)
quarantined → active    (review passed)
quarantined → redacted  (review failed)
```

No transitions go back to `active` from `expired` or `superseded`. Those are terminal states for a given record version. Re-ingestion creates a new record.

---

## Alternatives Considered

**Hard delete expired records**
Rejected. Deletion destroys audit lineage. A record that was retrieved and acted upon, then deleted, leaves a gap in the provenance chain. "Why did the system recommend X?" cannot be answered if the record that drove that recommendation no longer exists. Expired records are governance artifacts, not garbage.

**Soft delete with a `deleted_at` column**
Rejected. Soft delete with a boolean or timestamp conflates "no longer valid for retrieval" with "should not exist." Expiry and supersession have distinct semantics that deserve distinct state values.

**TTL-based automatic purge at the database level**
Rejected. Database-level TTL removes records without preserving audit trail or allowing for exception handling (e.g., a record that should be extended because it's still valid). Application-level expiry with explicit state transitions preserves control and auditability.

---

## Consequences

- Default retrieval queries include `WHERE status = 'active' AND (expires_at IS NULL OR expires_at > NOW())` — this is enforced in `retrieval/query_service.py`, not at each call site
- Audit queries use no default filter on `status` or `expires_at` — full corpus is visible
- A background job (or cron) runs periodically to transition records from `active` to `expired` based on `expires_at` — this is a state update, not a delete
- The `memory_links` table records supersession relationships for graph traversal
- Retrieval results include `status` and `expires_at` in the response envelope so callers can surface freshness signals to end users if desired
- OpenBrain sync (ADR-002) only exports `active` records with `expires_at` null or in the future — expired and superseded records never reach OpenBrain
