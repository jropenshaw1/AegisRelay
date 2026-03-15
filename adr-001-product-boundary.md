# ADR-001: Product Boundary

**Date:** March 16, 2026
**Status:** Accepted
**Decider:** Jonathan Openshaw

---

## Context

AegisRelay was initially conceived as a module inside PipelinePilot, Jonathan's existing job search desktop application. PipelinePilot already calls the Claude API and has a SQLite backend. The temptation was to extend it rather than build new.

A second option was to extend OpenBrain — the existing Supabase-backed PostgreSQL vector database serving as shared memory across Claude, ChatGPT, Cursor, and Perplexity.

The governing principle that resolved this decision:

> "AI has flipped the build paradigm. Planning and development are fast and easy now. Iteration can be done in hours instead of weeks or months. There is no longer a cost penalty for doing it right the first time. We never had time to do it right but always found time to do it over — that is the old model. It no longer applies."

---

## Decision

AegisRelay is a **standalone, independent service**. It shares no codebase, database, or process boundary with PipelinePilot or OpenBrain. Both existing systems remain untouched.

AegisRelay has its own repository, its own database, and its own deployment lifecycle.

---

## Alternatives Considered

**Extend PipelinePilot**
Rejected. PipelinePilot was built under a deliberate KISS mandate for a single purpose: managing job application lifecycle. A multi-provider AI ingress service with governed memory is a different system class. Forcing it into PipelinePilot would violate PipelinePilot's design integrity, create coupling between unrelated concerns, and produce a maintenance burden on both systems. Just because a tool exists and can call an API does not mean it should host unrelated functionality.

**Extend OpenBrain**
Rejected. Covered in ADR-002.

---

## Consequences

- AegisRelay is a new repository: `github.com/jropenshaw1/AegisRelay` (public, Apache 2.0)
- PipelinePilot can optionally become a *consumer* of AegisRelay's retrieval API in a future version — but that is a forward integration, not a dependency
- Build cost is the same as an extension given AI-accelerated development; correctness benefit is permanent
- AegisRelay's architecture, ADRs, and governance implementation stand as an independent portfolio artifact demonstrating Director-level AI infrastructure thinking
