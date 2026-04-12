# AegisRelay — Team Update: Sunday March 16, 2026

**From:** Jonathan Openshaw  
**To:** Gee, Copi, Lexi, Cursor  
**Re:** Session close — what we built today

---

## The headline

AegisRelay has a public GitHub repo, a complete PRD, and eight accepted ADRs. Not a single line of implementation code has been written. That is exactly right.

https://github.com/jropenshaw1/AegisRelay

---

## What happened today

This morning started as a sprint to wire Perplexity into PipelinePilot. By midday Jonathan made the call that changed the trajectory of the entire project: stop, reset, plan correctly before writing a single line of code.

That decision — anchored in the principle that AI has flipped the build paradigm and there is no longer a cost penalty for doing things right the first time — produced everything that followed.

Your four independent architectural reviews were the foundation. You did not know what each other said. You converged on the same core architecture anyway. That convergence is the strongest possible signal that the design is correct.

---

## What is decided and locked

**The system:** AegisRelay — a purpose-built, standalone multi-provider AI ingress service with durable write-behind memory synchronization. Governed by TSH-9 and LENS. Designed for auditability, retrieval quality, and extensibility from day one.

**The governing reframe — from Gee:** The relay is a feature. The governed memory plane is the system.

**Eight founding decisions:**

| Decision | Answer | Product |
|----------|--------|---------|
| **Boundary** | Standalone — not PipelinePilot, not OpenBrain | Storage |
| **Storage** | New Postgres + pgvector; OpenBrain downstream only | Contracts |
| **Contracts** | Separate CanonicalRelayResponse + MemoryRecord | Governance |
| **Governance** | 8-stage executable pipeline, versioned | Idempotency |
| **Idempotency** | Deterministic relay_id + content_hash at two levels | Expiry / Supersession |
| **Expiry / Supersession** | Expired ≠ deleted; superseded records remain auditable | Embeddings |
| **Embeddings** | Server-side async, text first, model versioned | CRUD / Maintenance |
| **CRUD / Maintenance** | Core infrastructure in v1 — designed alongside schema, not after | |

**Additional decisions locked today:**

- **Name:** AegisRelay
- **License:** Apache 2.0
- **Language:** Python
- **Retrieval API:** Included in v1 (minimal)
- **Schema:** Split tables
- **v1 optimization target:** Integrity and demonstrability
- **Raw provider payloads:** Cold storage, separate table
- **Write path:** AegisRelay is the sole write path — human_input adapter for manual entries

---

## What each of you contributed that shaped the final design

**Gee** — The governing reframe. "The relay is a feature. The governed memory plane is the system." Also: the most complete canonical envelope, the semantic contamination warning that made the new store decision easy, and the sharpest sharp-edges section — trust is not truth, expiry is not deletion, memory unit granularity matters.

**Copi** — The cleanest module structure. The tsh9/ and lens/ separation inside governance. Two questions that unlocked the final schema decisions (payload coldness and sole write path). The trace_id and write_origin fields nobody else thought of.

**Lexi** — The fields nobody else surfaced: relay_version, invoking_agent_id, correlation_id, parent_relay_id, temporal_focus_start/end, governance_flags as a queryable string array, embedding_text_span. All adopted. Also the strongest Definition of Done — the 10-minute live walk-through format is now the v1 acceptance criteria.

**Cursor** — The dual outbox pattern (SQLite client-side + Postgres server-side). Python as the language decision. The most implementation-ready response. Proposed the clean next step: lock Pydantic models and DDL before any other code.

---

## What is in the repo right now

```
AegisRelay/
├── README.md              — architecture, governance story, project context
├── LICENSE                — Apache 2.0
└── docs/
    ├── adr-001-product-boundary.md
    ├── adr-002-storage-strategy.md
    ├── adr-003-canonical-contracts.md
    ├── adr-004-governance-semantics.md
    ├── adr-005-idempotency.md
    ├── adr-006-expiry-supersession.md
    ├── adr-007-embedding-lifecycle.md
    ├── adr-008-crud-maintenance.md
    └── adr-all-compiled.md
```

---

## What is open — two questions answered today that unblock the schema

Both questions Copi raised in the PRD session have been resolved by Jonathan:

1. **Raw provider payloads:** Cold. Separate table. Retrieved only on explicit relay_id audit queries.
2. **Sole write path:** Yes — AegisRelay is the only write path. No external writers. Manual entries route through a human_input adapter with full governance pipeline treatment.

---

## Next session agenda

1. **Cursor** locks the Pydantic models and Postgres DDL — schema is now fully unblocked
2. **admin/crud_service.py** designed alongside the schema in the same session
3. **relay_service.execute_relay()** skeleton end-to-end so success states and outbox wiring are concrete before build begins

---

## Governing standard — active for all subsequent sessions

- **TSH-9:** אֲנִי קוֹחֵז בָּאֱמֶת — truth-anchored, direct, peer-level.
- **LENS:** substance before surface, actual reasoning not plausible sentiment, precise word not approximate word.

Today was a strong session. The foundation is solid. See you next sprint.

— Jonathan Openshaw  
Coordinated via Claude, Project Lead
