# ADR-007: Embedding Lifecycle

**Date:** March 16, 2026
**Status:** Accepted
**Decider:** Jonathan Openshaw

---

## Context

AegisRelay stores governed memory records that must support semantic similarity retrieval via vector search. This requires embedding generation — converting `body_text` into a vector representation using an embedding model.

Embedding generation is external-API dependent, failure-prone, and slower than a DB write. The question was whether to generate embeddings synchronously (blocking the relay response), client-side (on the desktop application), or asynchronously server-side.

A secondary concern: embedding models change. Text embedded with `text-embedding-3-small` at v1 will need to be re-embedded if a better model is adopted at v2. Without version tracking, re-embedding is difficult and corpus integrity cannot be guaranteed.

---

## Decision

**Embeddings are generated server-side, asynchronously, after the memory record is written.**

The write path is:
1. Governance pipeline produces `MemoryRecord` with `embedding_status = 'pending'`
2. `MemoryRecord` and `governance_events` are written to Postgres in a single transaction
3. An embedding job is enqueued to `outbox_jobs` in the **same transaction**
4. The relay response is returned to the caller — no blocking on embedding generation
5. The embedding worker processes the outbox job: calls the embedding API, writes the vector to `memory_embeddings`, updates `memory_records.embedding_status` to `complete` and sets `embedding_model`, `embedding_model_version`, `embedding_text_span`

**One embedding model for the entire corpus.** The active embedding model is a configuration value, not a per-record choice. When the embedding model is changed, a migration job re-embeds all active records and updates `embedding_model_version` on each row. Old vectors in `memory_embeddings` are retained until the migration is verified complete.

**`embedding_text_span` records what was embedded** — `full_response`, `answer_only`, or `governance_augmented` (body_text enriched with governance metadata). This allows retrieval quality tuning without schema changes.

---

## Alternatives Considered

**Synchronous embedding generation (blocking)**
Rejected. Embedding API calls add 200–2000ms latency. Blocking the relay response on embedding generation degrades user experience and creates a failure mode where a successful provider call and governance transform fail to return a result because the embedding API is unavailable. The relay should succeed or fail independently of embedding.

**Client-side embedding generation (on the desktop application)**
Rejected. Client-side embedding requires the embedding API key on the desktop, introduces a dependency on the client runtime for a server-side concern, and risks embedding model drift — different clients using different models produce vectors in incompatible spaces that cannot be compared. Centralized server-side generation ensures one model, one vector space.

**On-demand embedding (generate at query time, not ingestion time)**
Rejected. On-demand generation means the first query after ingestion is slow and the result is not cached durably. For a memory system optimized for retrieval quality, having embeddings pre-computed at ingestion time is the correct tradeoff.

**Storing vectors in the `memory_records` table**
Rejected. Vectors are large (1536 floats for `text-embedding-3-small` = ~6KB per record). Storing them inline with the main record degrades query performance for non-vector operations (audit queries, metadata filters) that do not need the vector. `memory_embeddings` as a separate table allows the vector index to be maintained independently and re-built during model migrations without touching the main record table.

---

## Consequences

- `memory_records` is always written before `memory_embeddings` — a record with `embedding_status = 'pending'` is a valid, retrievable record (filtered from vector search but available via metadata filters)
- The embedding worker in `embeddings/worker.py` drains the outbox independently of the main relay path; failures are retried per the outbox retry policy
- `embedding_model_version` is required on every `memory_embeddings` row — queries can filter to a specific model version for consistency during migrations
- Re-embedding is a first-class operation: set `embedding_status = 'pending'` on target records, enqueue new embedding jobs, worker generates new vectors under the new model version
- Hybrid search (keyword + vector) is supported by combining the `keywords` text array (GIN index) with the `memory_embeddings` HNSW index — neither alone is required for the other to function
- The embedding model is a deployment configuration value documented in the operational runbook; changes to it trigger a migration, not a code change
