# AegisRelay

**A purpose-built, governed AI ingress service with durable write-behind memory synchronization.**

[![Status](https://img.shields.io/badge/status-pre--build-blue)]()
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

**Pre-build.** PRD and ADRs complete. Pydantic models and DDL in progress. No production code written yet — by design.

Documentation-first. Engineering discipline applied before the first line of implementation code.

---

## License

Apache 2.0 — free to use, no monetization intent.
