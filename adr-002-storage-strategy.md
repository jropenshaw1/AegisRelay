# ADR-002: Storage Strategy

**Date:** March 16, 2026
**Status:** Accepted
**Decider:** Jonathan Openshaw

---

## Context

OpenBrain exists as a Supabase-backed PostgreSQL vector database serving as shared memory across Claude, ChatGPT, Cursor, and Perplexity. It uses a four-tag schema (`[domain]`, `[artifact]`, `[lifecycle]`, `[memory_type]`) with source tagging and stores 36+ structured thoughts covering professional identity, job search pipeline, projects, and working preferences.

The question was whether AegisRelay should write governed records into OpenBrain or build a new dedicated store.

The core concern driving this decision: as the corpus of provider responses grows, retrieval quality in a general-purpose store degrades silently. Contradictory claims, stale time-sensitive research, and unverified provider assertions accumulate alongside evergreen facts with no way to distinguish them at query time. This is the semantic contamination problem.

---

## Decision

AegisRelay uses a **new, dedicated PostgreSQL + pgvector database** as its primary store.

OpenBrain is treated as a **downstream consumer only**. AegisRelay may optionally sync a selective subset of high-trust, well-classified records into OpenBrain via a thin `/sync/openbrain.py` module, but OpenBrain is never the system of record for AegisRelay data.

The sync criteria for OpenBrain export (when enabled):
- `trust_tier` = `system_verified` or `provider_asserted` with supporting citations
- `epistemic_class` = `fact_claim`, `recommendation`, or `evergreen_knowledge`
- `embedding_status` = `complete`
- `status` = `active`
- `expires_at` is null or in the future

Records that do not meet these criteria remain in AegisRelay and are not exported.

---

## Alternatives Considered

**Write directly to OpenBrain**
Rejected. OpenBrain has no epistemic classification, temporal scoping, trust tiering, governance audit trail, or expiry semantics. Writing unclassified provider responses into it creates semantic contamination that degrades retrieval quality over time without any visible signal that degradation is occurring.

**Extend OpenBrain schema**
Rejected. Adding the required governance fields (`epistemic_class`, `temporal_scope`, `trust_tier`, `governance_checks_applied`, `expires_at`, segmentation support, contradiction tracking, etc.) to a general-purpose store retrofits purpose into infrastructure designed for something different. The result would be a system that does two things poorly instead of two systems that each do one thing well.

**External vector database (Pinecone, Weaviate, etc.)**
Deferred. pgvector running on Postgres is sufficient for v1 given single-user scale. A dedicated vector database can be evaluated if retrieval performance requires it. Keeping everything in Postgres simplifies joins between relay audit data and vector search results.

---

## Consequences

- New Postgres + pgvector database provisioned for AegisRelay — separate from OpenBrain's Supabase project
- OpenBrain remains clean, general-purpose, and uncontaminated
- Two databases to maintain; accepted as correct given they serve fundamentally different purposes
- The optional OpenBrain sync module provides continuity for cross-platform memory without coupling the systems
- AegisRelay becomes the authoritative, governance-grade record; OpenBrain holds curated downstream artifacts
