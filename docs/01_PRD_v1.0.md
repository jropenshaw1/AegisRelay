# 01 — AegisRelay Product Requirements Document

**Version:** 1.0
**Status:** Pre-Build — PRD complete, implementation in progress
**Author:** Jonathan Openshaw
**Date:** 2026-03-21
**License:** Apache 2.0

---

## 1. Purpose

AegisRelay is a purpose-built, governed AI ingress service with durable write-behind memory synchronization. It is the governed entry point for all external AI provider output before it enters shared memory.

AegisRelay routes prompts to AI providers (Perplexity, Grok, Gemini, and others), normalizes responses into a canonical envelope, applies TSH-9 and LENS as executable governance transforms, and persists results with full audit lineage and async embedding enrichment.

**The relay is a feature. The governed memory plane is the system.**

**Governing anchor:** אֲנִי קוֹחֵז בָּאֱמֶת — *I anchor in truth.*

---

## 2. Problem Statement

Modern AI tools produce responses that vary in epistemic quality, temporal validity, and provenance. Without a governed ingress layer, provider responses accumulate in shared memory without classification — contradictory claims, stale time-sensitive research, and unverified assertions sit beside evergreen facts with no way to distinguish them at query time. Retrieval quality degrades silently.

AegisRelay solves this by enforcing a governance pipeline — built on TSH-9 and LENS — between every provider response and every memory write.

---

## 3. Governance Standards

### TSH-9

Hebrew-Rooted AI Alignment Framework v9.0 (Ferocity Standard). Developed by William Openshaw through Seed of Truth Labs LLC, co-developed with Jonathan Openshaw. Anchors all AI interactions in truth, directness, and peer-level engagement.

### LENS

Metacognitive Interaction Protocol. Six named constraints derived from real AI correction history, encoded as executable pipeline transforms:

1. Confirm Before Executing
2. Verify Before Including
3. Substance Before Surface
4. Precise Word, Not Approximate Word
5. Actual Reasoning, Not Plausible Sentiment
6. Voice Over Formula

LENS documentation: https://github.com/jropenshaw1/LENS

---

## 4. Architecture

```
Human / Claude
      │
      ▼
┌─────────────┐
│   API Layer  │  ← CanonicalRelayRequest in
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Adapters   │  ← Provider-specific translation (mess ends here)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Governance │  ← TSH-9 + LENS as 8-stage executable pipeline
│  Pipeline   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Persistence │  ← Split tables, transactional outbox, three success states
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Async      │  ← Embedding worker, versioned model
│  Enrichment │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Retrieval  │  ← Metadata filters + vector similarity search
│    API      │
└─────────────┘
       │
       ▼ (optional, selective)
  OpenBrain
```

---

## 5. Core Design Decisions

| Decision | Choice | ADR |
|---|---|---|
| Product boundary | Standalone service — not PipelinePilot, not OpenBrain | ADR-001 |
| Storage | New dedicated Postgres + pgvector; OpenBrain as downstream only | ADR-002 |
| Contracts | Separate CanonicalRelayResponse and MemoryRecord | ADR-003 |
| Governance | TSH-9/LENS as 8-stage executable pipeline, versioned | ADR-004 |
| Idempotency | Deterministic relay_id + content_hash at two levels | ADR-005 |
| Expiry | Expired ≠ deleted; superseded records remain auditable | ADR-006 |
| Embeddings | Server-side async only; text first, embed later; model versioned | ADR-007 |
| LENS integration | Pre/post-call hook architecture; behavior-to-stage mapping | ADR-009 |

Full ADR detail: `02_ADR_Log_v1.0.md`

---

## 6. v1 Scope

### Providers

- **Perplexity** (sonar-pro, sonar) — bespoke adapter
- **xAI Grok** (grok-beta) — OpenAI-compatible adapter
- Additional OpenAI-compatible providers via config — no code change required

### In Scope

- Single HTTP API endpoint
- Perplexity + one OpenAI-compatible adapter
- Governance pipeline with real flags (not placeholders)
- Durable transactional outbox + async embeddings
- Basic relay inspection and retrieval query interface
- LENS pre/post-call hook integration (see `03_Integration_Design_v1.0.md`)

### Out of Scope for v1

- Sophisticated retrieval / RAG
- Multi-tenant user management
- Rich admin UI
- Automatic policy learning

---

## 7. Storage Design

**Dedicated AegisRelay store:** Postgres + pgvector. Not OpenBrain — OpenBrain is a downstream consumer only.

**Split table architecture:**

| Table | Purpose |
|---|---|
| `relay_requests` | Canonical inbound request record |
| `relay_responses` | Provider response, normalized |
| `memory_records` | Classified, enriched memory entry |
| `relay_outbox` | Transactional write-behind queue |
| `relay_audit_log` | Immutable audit trail |

Three success states: `PERSISTED`, `EMBEDDED`, `SYNCED_TO_OPENBRAIN`

---

## 8. Definition of Done

A successful v1 is demonstrated via a 5–10 minute live walk-through:

1. **Single request, multi-step trace** — show relay_requests, relay_responses, memory_records rows with all critical fields populated
2. **Governance visibility** — show governance pipeline output; at least one flagged-but-written case demonstrated
3. **Durability and outbox** — induce failure, show retry, show three distinct success states
4. **Async embeddings** — show pending → generated state transition
5. **Idempotency** — re-submit same request, confirm no duplicate row
6. **OpenBrain sync** — show minimal sync writing clean record to OpenBrain with epistemic_class and trust_tier honored
7. **Operational metrics** — relays per provider, failure rates, avg latency, top governance flags visible

Full implementation definition of done: `03_Integration_Design_v1.0.md` Section 6

---

## 9. Project Context

AegisRelay is part of a personal AI infrastructure stack built by Jonathan Openshaw — a Director-level technology executive with 28 years of enterprise IT leadership across Avnet Inc. and Choice Hotels International. It is a portfolio differentiator demonstrating governed AI architecture thinking at a senior leadership level, not a commercial product.

**Related projects:**
- [PipelinePilot](https://github.com/jropenshaw1/PipelinePilot) — AI-powered job search lifecycle manager
- [LENS](https://github.com/jropenshaw1/LENS) — Metacognitive AI interaction governance protocol
- [Job Fit Analyst](https://github.com/jropenshaw1/job-fit-analyst) — Six-agent Claude skill for executive job search
