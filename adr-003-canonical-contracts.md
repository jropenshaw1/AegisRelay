# ADR-003: Canonical Contracts

**Date:** March 16, 2026
**Status:** Accepted
**Decider:** Jonathan Openshaw

---

## Context

The system routes prompts to external AI providers and persists governed responses as durable memory. Two concerns need to be cleanly separated: the provider transaction (what was asked, what came back, did it succeed) and the governed memory unit (what was classified, transformed, and accepted as durable retrieval-quality knowledge).

Provider responses arrive in provider-specific shapes — Perplexity's response schema differs from Grok's OpenAI-compatible format, which differs from Gemini's structure. Without a normalization boundary, provider-specific shape leaks into the governance and persistence layers, making every provider change a multi-layer change.

---

## Decision

Three separate typed contracts are maintained as the authoritative internal API:

**1. `CanonicalRelayRequest`**
The internal contract for "what we asked whom, and why." Created by the caller before any provider call. Contains: identity fields, actor metadata, provider target, input content, pre-classification intent, and governance profile selection.

**2. `CanonicalRelayResponse`**
The provider-normalized, governance-annotated result of a single relay. Produced by the governance pipeline after the provider adapter normalizes the raw response. Contains: provider outcome, governed text, governance trace, and the three distinct success states.

**3. `MemoryRecord`**
The governed, retrievable memory unit. Written to the persistence plane by the governance pipeline after all transforms complete. Contains: full semantic classification, temporal metadata, provenance, governance audit fields, retrieval metadata, and state.

Provider-specific response shapes are normalized at the adapter boundary and **never leak** into the governance or persistence layers.

---

## Alternatives Considered

**Single unified contract**
Rejected. Collapsing the relay transaction and the memory record into one object conflates "what the provider said" with "what the system accepted as governed memory." This makes partial failures harder to model (provider succeeded, memory write pending cannot be represented cleanly), removes the ability to re-process a relay under an updated governance pipeline without corrupting the original transaction record, and couples provider-specific semantics to retrieval-quality storage.

**Two contracts (relay + memory), no intermediate response**
Rejected. Without `CanonicalRelayResponse` as an explicit intermediate, the governance pipeline has no clean typed input and the audit trail cannot distinguish the raw provider output from the governed transformation. The intermediate contract is the evidence of what governance changed.

---

## Consequences

- Three Pydantic models in `domain/models.py` are the authoritative internal contract; no other layer defines its own provider response types
- Provider adapters translate raw provider JSON → `CanonicalRelayResponse`; they never produce `MemoryRecord`
- Governance pipeline consumes `CanonicalRelayResponse` → produces `MemoryRecord`
- Persistence layer consumes `MemoryRecord`; it has no knowledge of provider specifics
- Adding a new provider requires only a new adapter file; governance and persistence are unaffected
- Schema versioning (`schema_version` field) on both `CanonicalRelayResponse` and `MemoryRecord` allows safe evolution without breaking existing stored records
