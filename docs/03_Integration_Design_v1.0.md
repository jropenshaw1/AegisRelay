# AegisRelay + LENS Integration Design
**Version:** 1.0
**Date:** March 22, 2026
**Status:** Ratified
**Author:** Jonathan Openshaw
**Follows:** AegisRelay ADR-009, LENS ADR-009

---

## 1. Purpose

This document is the single reference for how LENS constraint evaluation integrates into
AegisRelay's call flow. It is the definition of done for the integration backlog item and
the implementation specification Cursor will use to build the integration.

---

## 2. Full Call Flow — Annotated

```
CanonicalRelayRequest
        │
        ▼
╔═══════════════════════════════════╗
║  PRE-CALL HOOK (lens_pre_call.py) ║  ← NEW
║                                   ║
║  1. Decision Checkpoint eval      ║
║     • Is this a high-stakes or    ║
║       irreversible relay call?    ║
║     • Write governance_event if   ║
║       checkpoint-worthy           ║
║                                   ║
║  2. Assumption Surfacing eval     ║
║     • Does the request contain    ║
║       implicit assumptions that   ║
║       materially affect output?   ║
║     • Write governance_event if   ║
║       assumptions detected        ║
╚═══════════════╤═══════════════════╝
                │
                ▼
        Provider Adapters
        (unchanged — ADR-003)
                │
                ▼
╔════════════════════════════════════╗
║  POST-CALL HOOK (lens_post_call.py)║  ← NEW
║                                    ║
║  1. Prompt Reflection eval         ║
║     • Did the response reveal      ║
║       the request was under-       ║
║       specified or required        ║
║       interpretation choices?      ║
║     • Write governance_event if    ║
║       reflection warranted         ║
║                                    ║
║  2. Reframe Offers eval            ║
║     • Does the response suggest    ║
║       the question asked was not   ║
║       the question needed?         ║
║     • Write governance_event if    ║
║       reframe candidate detected   ║
╚═══════════════╤════════════════════╝
                │
                ▼
╔═══════════════════════════════════╗
║  GOVERNANCE PIPELINE (ADR-004)    ║  ← UNCHANGED — LENS trigger conditions
║                                   ║    added to Stages 3 and 4 only
║  Stage 1: Normalize               ║
║  Stage 2: Segment                 ║
║  Stage 3: Classify                ║  ← Cognitive Model Disclosure
║  Stage 4: Mark Uncertainty        ║  ← Uncertainty Flagging
║  Stage 5: Apply Temporal Policy   ║
║  Stage 6: Redact                  ║
║  Stage 7: Deduplicate             ║
║  Stage 8: Persist                 ║  ← governance_events written here
╚═══════════════╤═══════════════════╝
                │
                ▼
        Async Enrichment
        (unchanged — ADR-007)
                │
                ▼ (optional)
          OpenBrain Sync
```

---

## 3. New Module Specifications

### 3.1 `governance/lens_pre_call.py`

**Inputs:** `CanonicalRelayRequest`
**Outputs:** `list[LensObservation]`
**Side effects:** None — observations written to governance_events by the caller

```python
class LensObservation:
    behavior: str          # LENS behavior ID from lens_constants.py
    trigger_fired: bool    # Whether the behavior's trigger condition was met
    confidence: float      # 0.0–1.0 confidence that trigger condition is met
    observation: str       # One sentence describing what was detected
    hook: str              # "pre_call" | "post_call"
    lens_version: str      # "1.0"

def evaluate_pre_call(request: CanonicalRelayRequest) -> list[LensObservation]:
    """
    Evaluate Decision Checkpoints and Assumption Surfacing
    against the relay request before provider invocation.
    Returns a list of LensObservation objects (empty if no triggers fired).
    """
```

**Decision Checkpoint trigger conditions:**
- Request targets a write operation (not read-only)
- Request contains explicit irreversibility signals ("delete", "publish", "send", "commit")
- Request triggers a cascade with downstream effects

**Assumption Surfacing trigger conditions:**
- Request contains ambiguous scope without explicit constraints
- Request references entities that could resolve to multiple targets
- Request omits context that would materially affect the provider's interpretation

---

### 3.2 `governance/lens_post_call.py`

**Inputs:** `CanonicalRelayRequest`, `CanonicalRelayResponse`
**Outputs:** `list[LensObservation]`
**Side effects:** None — observations written to governance_events by the caller

```python
def evaluate_post_call(
    request: CanonicalRelayRequest,
    response: CanonicalRelayResponse
) -> list[LensObservation]:
    """
    Evaluate Prompt Reflection and Reframe Offers
    against the completed exchange.
    Returns a list of LensObservation objects (empty if no triggers fired).
    """
```

**Prompt Reflection trigger conditions:**
- Response contains language indicating interpretation was required
  ("I assumed", "interpreting this as", "based on my understanding")
- Response answers a different question than was literally asked
- Response scope materially differs from request scope

**Reframe Offers trigger conditions:**
- Response reveals that the stated question has a more useful underlying form
- Response contains signals that the root need differs from the stated request
- Response quality would improve significantly if the question were reframed

---

### 3.3 `governance/lens_constants.py`

```python
# LENS behavior identifiers and hook assignments
LENS_BEHAVIORS = {
    "decision_checkpoints": {
        "hook": "pre_call",
        "required": True,
        "violation_on": "irreversible_action_taken_silently"
    },
    "assumption_surfacing": {
        "hook": "pre_call",
        "required": True,
        "violation_on": "consequential_output_assumptions_unstated"
    },
    "prompt_reflection": {
        "hook": "post_call",
        "required": True,
        "violation_on": "trigger_present_behavior_absent"
    },
    "reframe_offers": {
        "hook": "post_call",
        "required": False,
        "violation_on": "reframe_available_not_offered"
    },
    "uncertainty_flagging": {
        "hook": "pipeline_stage_4",
        "required": True,
        "violation_on": "uncertain_claim_presented_as_confident"
    },
    "cognitive_model_disclosure": {
        "hook": "pipeline_stage_3",
        "required": False,
        "violation_on": "material_frame_choice_not_surfaced"
    }
}

LENS_VERSION = "1.0"
LENS_TAG_PREFIX = "lens"
LENS_SOURCE_TAG = "[source:lens]"
```

---

## 4. governance_events Schema — LENS Rows

All LENS observations write to the existing `governance_events` table. No schema changes
required. LENS rows are distinguished by `event_type = 'lens_observation'`.

```sql
-- Pre-call observation example
INSERT INTO governance_events (
    relay_id,
    event_type,    -- 'lens_observation'
    stage,         -- 'pre_call'
    metadata       -- JSON: behavior, trigger_fired, confidence, observation, lens_version
) VALUES (
    :relay_id,
    'lens_observation',
    'pre_call',
    '{"behavior": "decision_checkpoints", "trigger_fired": true,
      "confidence": 0.85, "lens_version": "1.0",
      "observation": "Request targets a write operation with downstream cascade effects."}'
);

-- Post-call observation example
INSERT INTO governance_events (
    relay_id,
    event_type,
    stage,         -- 'post_call'
    metadata
) VALUES (
    :relay_id,
    'lens_observation',
    'post_call',
    '{"behavior": "prompt_reflection", "trigger_fired": true,
      "confidence": 0.72, "lens_version": "1.0",
      "observation": "Response indicates AI interpreted ambiguous scope as broad rather than narrow."}'
);
```

---

## 5. Pipeline Stage Additions — Stages 3 and 4

### Stage 3 (Classify) — Cognitive Model Disclosure

Add to the existing classify stage. Both conditions from the LENS two-condition gate must
be true before firing:

```python
# LENS: Cognitive Model Disclosure
# Fires when: (a) a structural framing choice was made AND
#             (b) a different frame would materially change the output
lens_frame = detect_analytical_frame(segment)
if lens_frame.is_material and lens_frame.user_could_choose_differently:
    emit_governance_event(
        relay_id=relay_id,
        event_type='lens_observation',
        stage='pipeline_stage_3',
        metadata={
            "behavior": "cognitive_model_disclosure",
            "trigger_fired": True,
            "frame_detected": lens_frame.name,
            "confidence": lens_frame.confidence,
            "lens_version": LENS_VERSION
        }
    )
```

### Stage 4 (Mark Uncertainty) — Uncertainty Flagging

Add to the existing mark uncertainty stage:

```python
# LENS: Uncertainty Flagging
# Fires when: claim is based on incomplete information or assumption
# and was presented without qualification
for claim in segment.claims:
    if claim.is_uncertain and not claim.is_flagged:
        emit_governance_event(
            relay_id=relay_id,
            event_type='lens_observation',
            stage='pipeline_stage_4',
            metadata={
                "behavior": "uncertainty_flagging",
                "trigger_fired": True,
                "violation": True,   # Uncertain claim not flagged = violation
                "claim_text": claim.text[:200],
                "confidence": claim.uncertainty_score,
                "lens_version": LENS_VERSION
            }
        )
```

---

## 6. Definition of Done

The integration is complete when all of the following are checked:

### New modules
- [ ] `governance/lens_pre_call.py` implemented and unit tested
- [ ] `governance/lens_post_call.py` implemented and unit tested
- [ ] `governance/lens_constants.py` implemented

### Wiring
- [ ] Pre-call hook wired into main relay call flow before provider adapter
- [ ] Post-call hook wired into main relay call flow after provider adapter,
      before governance pipeline
- [ ] Stage 3 updated with Cognitive Model Disclosure trigger condition
- [ ] Stage 4 updated with Uncertainty Flagging trigger condition

### Data
- [ ] All LENS observations write to governance_events with correct schema
- [ ] `get_relay()` in CRUD layer returns LENS observations in its output

### Validation
- [ ] At least one end-to-end test: relay call → pre-call observation → provider
      → post-call observation → pipeline → governance_events contains LENS rows

### Documentation
- [ ] AegisRelay ADR-009 committed to `docs/02_ADR_Log_v1.0.md`
- [ ] LENS ADR-009 committed to LENS `docs/05_ADR_Log_v1.0.md`

### Out of scope for v1
- Blocking behavior in pre-call hook
- Automated violation detection in post-call hook
- LENS compliance scoring
- OpenBrain sync of LENS observations

---

## 7. Portfolio Narrative

When complete, AegisRelay demonstrates end-to-end governed AI execution:

1. A relay request comes in
2. LENS pre-call hook evaluates it for decision checkpoints and assumptions
3. Provider responds
4. LENS post-call hook evaluates the exchange for reflection and reframe opportunities
5. Eight-stage pipeline classifies, marks uncertainty, applies temporal policy
6. All LENS observations are retrievable via `get_relay()` with full governance lineage

This is the concrete, demonstrable answer to "what does governed AI execution look like
in production?" — not a framework document, but a working system with an audit trail.

---

*03_Integration_Design_v1.0.md — Ratified March 22, 2026*
*Implementation owner: Cursor*
*Pending: commit of ADR-009 in both repos, then implementation begins*
