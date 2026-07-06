# AegisRelay

**A purpose-built, governed AI ingress service with durable write-behind memory synchronization.**

[![Status](https://img.shields.io/badge/status-Phase%202%20complete-brightgreen)]()
[![License](https://img.shields.io/badge/license-Apache%202.0-green)]()
[![Author](https://img.shields.io/badge/author-Jonathan%20Openshaw-informational)]()

---

## Getting Started

For a linear walkthrough — local Python setup, governed OpenBrain sync context, and environment variables — see **[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)**.

---

## What It Is

AegisRelay is the governed entry point for all external AI provider output before it enters shared memory. It routes prompts to implemented and planned AI providers, normalizes responses into a canonical envelope, applies TSH-9 and LENS as executable governance transforms, and persists results with full audit lineage and async embedding enrichment.

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
│ Persistence │  ← Split tables, transactional outbox
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Async      │  ← Embedding worker, versioned model
│  Enrichment │
└──────┬──────┘
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

## Providers

**Implemented**

- **Perplexity** (`PerplexityAdapter`) — bespoke adapter
- **Stub** (`StubAdapter`) — deterministic testing and offline demo adapter

**Planned**

- **xAI Grok** (grok-beta) — OpenAI-compatible adapter
- **Gemini**
- **OpenAI-compatible providers** (generic)

---

## Project Context

AegisRelay is part of a personal AI infrastructure stack built by Jonathan Openshaw.

Related projects:
- [PipelinePilot](https://github.com/jropenshaw1/PipelinePilot) — AI-powered job search lifecycle manager
- [Job Fit Analyst](https://github.com/jropenshaw1/job-fit-analyst) — Six-agent Claude skill for executive job search

---

## Status

| Area | Status | Notes |
|---|---|---|
| Phase 1 | Complete | Relay pipeline, LENS hooks, governance events, async enrichment, and OpenBrain sync path are implemented. |
| Phase 2 | In Progress | Additional providers and the broader admin module remain in active build-out. |
| Phase 2 | Planned | Retrieval API, deterministic `relay_id`, and the richer memory lifecycle state machine are not implemented yet. |

Phase 1 baseline: commit `e651db3`, March 21, 2026 (LENS hooks, canonical contracts, governance constants).

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
