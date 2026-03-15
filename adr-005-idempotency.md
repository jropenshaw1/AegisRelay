# ADR-005: Idempotency Strategy

**Date:** March 16, 2026
**Status:** Accepted
**Decider:** Jonathan Openshaw

---

## Context

A relay service that writes to a persistent store under unreliable network conditions must handle retries without creating duplicate records. Two levels of deduplication are required: at the relay transaction level (did we already process this request?) and at the memory unit level (did we already store this specific governed content?).

A single relay may produce multiple memory records through segmentation (ADR-004, Stage 2). Idempotency must be enforced at both levels independently.

---

## Decision

Idempotency is enforced at **two levels** with different key strategies.

**Level 1 — Relay level**

`relay_id` is a deterministic key computed from stable input dimensions:
- `human_actor_id`
- `provider_name`
- `provider_model`
- `sha256(normalized_input_text)`
- `session_id` (if present)
- `correlation_id` (if present)

The same logical request always produces the same `relay_id`. A `UNIQUE` constraint on `relay_requests.relay_id` enforces at-most-one write. A retry that produces the same `relay_id` returns the existing record without re-calling the provider or re-running governance.

If the caller needs to force a re-relay (e.g., under an updated governance pipeline version), they provide a new `relay_version` increment. This produces a new `CanonicalRelayResponse` and new `MemoryRecord` rows, linked to the original via `parent_relay_id` and `parent_memory_id`.

**Level 2 — Memory unit level**

`content_hash` is computed from the normalized `body_text` of each memory candidate after governance transforms complete. A `UNIQUE` constraint on `(relay_id, content_hash, segmentation_index)` prevents duplicate memory units under retry or replay scenarios.

If a retry produces the same `content_hash` under the same `relay_id` and `segmentation_index`, the persistence layer returns the existing `MemoryRecord` without a new write. If the governance pipeline produced different content (e.g., pipeline version changed), the hash will differ and a new record is written with `parent_memory_id` linking it to the original.

---

## Key Design Principle

Idempotency must key on **transaction intent**, not just content. Two different requests that happen to produce the same response text should produce two separate relay records. The relay-level key captures intent (who asked whom what); the memory-level key captures content (what was stored).

---

## Alternatives Considered

**Timestamp-based IDs**
Rejected. Timestamps are not stable across retries. A request retried 200ms later produces a different timestamp and therefore a different ID, defeating idempotency entirely.

**UUID v4 (random) relay IDs with client-provided idempotency keys**
Considered. Requires callers to generate and track idempotency keys, adding coordination burden. Deterministic server-side computation is simpler and requires no client state.

**Content-only deduplication (no relay-level key)**
Rejected. Two identical prompts sent to the same provider at different times are semantically different relay transactions — the provider's response may differ, the governance pipeline version may differ, and the temporal context may differ. Collapsing them into one record loses the audit trail.

---

## Consequences

- `domain/idempotency.py` owns `relay_id` computation and `content_hash` computation as the canonical implementations — no other module computes these
- `UNIQUE` constraints at both levels are enforced at the database layer, not just application logic; the DB is the last line of defense against duplicates
- Callers that need to force re-relay (governance reprocessing, provider retry after failure) use `relay_version` increment to produce a new deterministic but distinct `relay_id`
- The outbox (ADR pending) uses `relay_id` as its correlation key so failed writes can be retried without re-invoking the provider
- Audit queries can reconstruct the full evolution of any memory record by following the `parent_relay_id` and `parent_memory_id` chain
