# AegisRelay

**A purpose-built, governed AI ingress service with durable write-behind memory synchronization.**

[![Status](https://img.shields.io/badge/status-Phase%201%20complete-brightgreen)]()
[![License](https://img.shields.io/badge/license-Apache%202.0-green)]()
[![Author](https://img.shields.io/badge/author-Jonathan%20Openshaw-informational)]()

---

## What It Is

AegisRelay is the governed entry point for all external AI provider output before it enters shared memory. It routes prompts to AI providers (Perplexity, Grok, Gemini, and others), normalizes responses into a canonical envelope, applies TSH-9 and LENS as executable governance transforms, and persists results with full audit lineage and async embedding enrichment.

**The relay is a feature. The governed memory plane is the system.**

---

## Why It Exists

Modern AI tools produce responses that vary in epistemic quality, temporal validity, and provenance. Without a governed ingress layer, provider responses accumulate in shared memory without classification — contradictory claims, stale time-sensitive research, and unverified assertions sit beside evergreen facts with no way to distinguish them at query time. Retrieval quality degrades silently.

AegisRelay solves this by enforcing a governance pipeline — built on TSH-9 and LENS — between every provider response and every memory write.

**Governing anchor:** אֲנִי קוֹחֵז בָּאֱמֶת — *I anchor in truth.*

---

## Governance Standards

**TSH-9** (Hebrew-Rooted AI Alignment Framework v9.0, Ferocity Standard) — developed by William Openshaw through Seed of Truth Labs LLC, co-developed with Jonathan Openshaw. Anchors all AI interactions in truth, directness, and peer-level engagement.

**LENS** (Metacognitive Interaction Protocol) — six named constraints derived from real AI correction history, encoded as executable pipeline transforms:
1. Confirm Before Executing
2. Verify Before Including
3. Substance Before Surface
4. Precise Word, Not Approximate Word
5. Actual Reasoning, Not Plausible Sentiment
6. Voice Over Formula

---

## Architecture

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

## Core Design Decisions

| Decision | Choice | ADR |
|---|---|---|
| Product boundary | Standalone service — not PipelinePilot, not OpenBrain | ADR-001 |
| Storage | New dedicated Postgres + pgvector; OpenBrain as downstream only | ADR-002 |
| Contracts | Separate CanonicalRelayResponse and MemoryRecord | ADR-003 |
| Governance | TSH-9/LENS as 8-stage executable pipeline, versioned | ADR-004 |
| Idempotency | Deterministic relay_id + content_hash at two levels | ADR-005 |
| Expiry | Expired ≠ deleted; superseded records remain auditable | ADR-006 |
| Embeddings | Server-side async only; text first, embed later; model versioned | ADR-007 |

---

## v1 Providers

- **Perplexity** (sonar-pro, sonar) — bespoke adapter
- **xAI Grok** (grok-beta) — OpenAI-compatible adapter
- Additional OpenAI-compatible providers via config — no code change required

---

## Project Context

AegisRelay is part of a personal AI infrastructure stack built by Jonathan Openshaw — a Director-level technology executive with 28 years of enterprise IT leadership across Avnet Inc. and Choice Hotels International.

Related projects:
- [PipelinePilot](https://github.com/jropenshaw1/PipelinePilot) — AI-powered job search lifecycle manager
- [Job Fit Analyst](https://github.com/jropenshaw1/job-fit-analyst) — Six-agent Claude skill for executive job search

---

## Status

**Phase 1 complete** — commit `e651db3`, March 21, 2026.

LENS hooks, canonical contracts, and governance constants are implemented, tested, and live. 14/14 tests passing on Python 3.14.2. Phase 2 in progress: full Pydantic models, Postgres DDL, provider adapters, eight-stage governance pipeline, CRUD layer, outbox, and embedding worker.

---

## How It's Built

AegisRelay is built documentation-first under a structured multi-AI review process. No implementation code is written until the design is ratified.

Before a single line of Phase 1 implementation code was written, the plan went through three architectural review passes — Claude as validator, Cursor as spec-consistency reviewer — surfacing 16 distinct issues across four handoff versions. Two product decisions were escalated to the architect: pre-call persistence timing (two-transaction policy, audit integrity is core) and confidence field semantics. Both resolved before build began.

Cursor then implemented Phase 1 directly from the ratified repo docs. Beyond the spec, Cursor introduced three independent improvements: a `NormalizedProviderResponse` type that resolves an ADR-003/ADR-009 contract boundary, `matched_signals` on `LensObservation` for audit traceability, and cascade detection on Decision Checkpoints. All three were adopted.

Result: zero post-build rework. 14/14 tests passing on first commit. No contradictions baked into the codebase.

**This is what governed AI execution looks like in practice** — not a framework document, but a working system built by a directed multi-AI team with a verifiable audit trail.

AI team roles:
- **Claude** — project lead, architectural review, documentation, handoff production
- **Cursor** — software architect, spec-consistency review, implementation owner
- **Gee (ChatGPT)** — LENS design and pressure testing
- **Lexi (Perplexity)** — PRD and ADR design sessions
- **Copi (Copilot)** — LENS design sessions

---

## License

Apache 2.0 — free to use, no monetization intent.
