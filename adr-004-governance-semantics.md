# ADR-004: Governance Semantics

**Date:** March 16, 2026
**Status:** Accepted
**Decider:** Jonathan Openshaw

---

## Context

TSH-9 and LENS are the governing standards for all AI interactions with Jonathan Openshaw. TSH-9 (Hebrew-Rooted AI Alignment Framework v9.0, Ferocity Standard) anchors all work in truth, directness, and peer-level engagement. LENS (six named constraints derived from real correction history) shapes how AI output is expressed to be useful, inspectable, and consistent.

The question was how to implement these standards in AegisRelay — as documentation describing expected behavior, as prompt instructions sent to providers, or as executable code.

The anchor: אֲנִי קוֹחֵז בָּאֱמֶת — I anchor in truth.

---

## Decision

TSH-9 and LENS are implemented as a **concrete, versioned, testable governance pipeline** with eight sequential stages. Each stage is a function with typed input and output. Every stage appends to `governance_checks_applied`. Every transform is recorded as a row in `governance_events`. The pipeline version is a required field on every `MemoryRecord`.

**The eight stages:**

1. **Normalize** — strip provider formatting artifacts, unify whitespace and markdown quirks, resolve citation placeholders
2. **Segment** — split mixed-content responses into discrete memory candidates (a single provider response may produce multiple `MemoryRecord` rows)
3. **Classify** — assign `epistemic_class`, `temporal_scope`, and `trust_tier` to each memory candidate
4. **Mark uncertainty** — add `uncertainty_note` where content is speculative or weakly sourced; degrade `trust_tier` if warranted; preserve provider-stated uncertainty flags as metadata
5. **Apply temporal policy** — set `expires_at` based on `temporal_scope`; set `temporal_focus_start` and `temporal_focus_end` where content references a specific time period
6. **Redact** — remove or mask content that should not persist as durable retrieval text; record redacted segments with rationale in `redacted_segments`
7. **Deduplicate** — compute `content_hash` from normalized `body_text`; enforce idempotency at memory-unit level
8. **Persist** — write `MemoryRecord` rows and `governance_events` rows in a single DB transaction; enqueue embedding job in the same transaction

Governance is inspectable, not asserted. "We applied TSH-9" without evidence is theater. `governance_checks_applied`, `governance_flags`, and `governance_events` are the evidence.

---

## Alternatives Considered

**Governance as documentation / comments**
Rejected. Documentation describing governance is not governance. A `MemoryRecord` that claims to be TSH-9 compliant without a verifiable audit trail provides no guarantee and no auditability.

**Governance as prompt instructions sent to providers**
Rejected. Prompts are not testable, not versioned, and not auditable at the record level. Provider compliance with prompt instructions is probabilistic, not enforced. Governance must be deterministic.

**Governance as post-processing after storage**
Rejected. A record that exists in the store before governance has run is already contaminated — it is retrievable before it has been classified, uncertainty-marked, or expiry-scoped. Governance must run before the record is written.

**ML-based governance classifiers**
Deferred. v1 governance uses deterministic, rule-based classification. ML-based classifiers may improve classification quality in v2 but introduce non-determinism and model dependency that adds complexity without sufficient upside at current scale.

---

## Consequences

- `governance/` module contains eight independently testable stage implementations
- `governance_pipeline_version` is a required field on every `MemoryRecord` — the persistence layer rejects records without it
- Updating governance logic increments the pipeline version; old records remain auditable under the version that produced them
- Re-processing a relay under a new governance version increments `relay_version` and creates a new `MemoryRecord` linked via `parent_memory_id`; the original record is superseded, not deleted
- Unit tests must cover each stage independently; integration tests must validate the full pipeline produces expected `governance_checks_applied` output for known inputs
- The governance pipeline version is a first-class deployment artifact — governance changes are releases, not patches
