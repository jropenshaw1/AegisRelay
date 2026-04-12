# AegisRelay — Cursor Implementation Handoff
**Date:** March 21, 2026 MST
**Session:** LENS Integration Build — Phase 1
**Spec authority:** `docs/03_Integration_Design_v1.0.md`
**ADR authority:** `docs/02_ADR_Log_v1.0.md`

---

## Current State

The AegisRelay repo currently contains:
- `docs/01_PRD_v1.0.md`
- `docs/02_ADR_Log_v1.0.md`
- `docs/03_Integration_Design_v1.0.md`
- `docs/TEAM_UPDATE_2026-03-16.md`
- `LICENSE`, `README.md`

**No source code exists.** This is a greenfield implementation starting from the ratified design docs.

---

## Your Task — Phase 1

Build the foundational project structure and the three LENS governance modules. These are the first source files in the repo and everything that follows depends on them being correct.

Do not write implementation code beyond what is specified below. Do not introduce dependencies that are not listed. Follow the specs precisely — this is a portfolio-grade system, not a prototype.

---

## Step 1 — Project Structure

Create the following directory and file skeleton. Empty files are fine for anything not in scope for Phase 1 — stubs with docstrings only.

```
aegisrelay/
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── relay_request.py       ← Pydantic: CanonicalRelayRequest
│   ├── relay_response.py      ← Pydantic: CanonicalRelayResponse
│   ├── memory_record.py       ← Pydantic: MemoryRecord
│   └── lens_observation.py    ← Pydantic: LensObservation  ← IMPLEMENT THIS
├── governance/
│   ├── __init__.py
│   ├── pipeline.py            ← Stub only — 8-stage skeleton with docstrings
│   ├── lens_constants.py      ← IMPLEMENT THIS
│   ├── lens_pre_call.py       ← IMPLEMENT THIS
│   └── lens_post_call.py      ← IMPLEMENT THIS
├── adapters/
│   └── __init__.py            ← Stub only
├── admin/
│   └── __init__.py            ← Stub only
└── db/
    └── __init__.py            ← Stub only

tests/
├── __init__.py
└── governance/
    ├── __init__.py
    ├── test_lens_constants.py    ← IMPLEMENT THIS
    ├── test_lens_pre_call.py     ← IMPLEMENT THIS
    └── test_lens_post_call.py    ← IMPLEMENT THIS

requirements.txt
```

---

## Step 2 — Pydantic Models

### `models/lens_observation.py`

Implement the `LensObservation` model exactly as specified in `docs/03_Integration_Design_v1.0.md` Section 3.1:

```python
from pydantic import BaseModel
from typing import Literal

class LensObservation(BaseModel):
    behavior: str            # LENS behavior ID from lens_constants.py
    trigger_fired: bool      # Whether the behavior's trigger condition was met
    confidence: float        # 0.0–1.0
    observation: str         # One sentence describing what was detected
    hook: Literal["pre_call", "post_call", "pipeline_stage_3", "pipeline_stage_4"]
    lens_version: str        # "1.0"
```

### `models/relay_request.py` — Stub with key fields

Implement a working `CanonicalRelayRequest` with enough fields to support the LENS pre-call evaluations. Minimum required fields per ADR-003 and ADR-005:

```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class CanonicalRelayRequest(BaseModel):
    relay_id: str
    human_actor_id: str
    provider_name: str
    provider_model: str
    input_text: str
    session_id: Optional[str] = None
    submitted_at: datetime
    schema_version: str = "1.0"
    # Operation metadata — used by LENS Decision Checkpoint evaluation
    operation_type: Optional[str] = None    # "read" | "write" | "delete" | "publish"
    is_irreversible: Optional[bool] = None  # Explicit irreversibility flag
```

### `models/relay_response.py` — Stub with key fields

```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class CanonicalRelayResponse(BaseModel):
    relay_id: str
    provider_name: str
    provider_model: str
    response_text: str
    provider_request_ts: datetime
    provider_response_ts: datetime
    schema_version: str = "1.0"
    raw_provider_response: Optional[dict] = None
```

### `models/memory_record.py` — Stub only

```python
from pydantic import BaseModel
# Full implementation in Phase 2
class MemoryRecord(BaseModel):
    memory_id: str
    relay_id: str
    body_text: str
    schema_version: str = "1.0"
```

---

## Step 3 — `governance/lens_constants.py`

Implement exactly as specified in `docs/03_Integration_Design_v1.0.md` Section 3.3:

```python
from typing import TypedDict, Literal

class LensBehaviorSpec(TypedDict):
    hook: str
    required: bool
    violation_on: str

LENS_BEHAVIORS: dict[str, LensBehaviorSpec] = {
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

LENS_VERSION: str = "1.0"
LENS_TAG_PREFIX: str = "lens"
LENS_SOURCE_TAG: str = "[source:lens]"

PRE_CALL_BEHAVIORS: list[str] = [
    k for k, v in LENS_BEHAVIORS.items() if v["hook"] == "pre_call"
]
POST_CALL_BEHAVIORS: list[str] = [
    k for k, v in LENS_BEHAVIORS.items() if v["hook"] == "post_call"
]
```

---

## Step 4 — `governance/lens_pre_call.py`

Implement per `docs/03_Integration_Design_v1.0.md` Section 3.1.

**Decision Checkpoint trigger conditions** (from Section 3.1):
- Request `operation_type` is a write, delete, or publish
- Request contains irreversibility signals in `input_text`: ("delete", "publish", "send", "commit", "remove", "drop", "destroy")
- Request `is_irreversible` is explicitly True

**Assumption Surfacing trigger conditions** (from Section 3.1):
- Input text contains ambiguous scope markers: ("it", "this", "that", "the thing", "everything", "all of them") without prior explicit reference
- Input text references entities that could resolve to multiple targets (detect via presence of unqualified plurals without constraints)
- Input text is under 20 words with no explicit constraints (short uncontextualized request)

**Confidence scoring:**
- Multiple trigger signals present → 0.8–1.0
- Single strong signal → 0.6–0.8
- Weak or ambiguous signal → 0.4–0.6
- Signal present but uncertain → 0.3–0.5

```python
from aegisrelay.models.relay_request import CanonicalRelayRequest
from aegisrelay.models.lens_observation import LensObservation
from aegisrelay.governance.lens_constants import LENS_VERSION

IRREVERSIBILITY_SIGNALS = frozenset([
    "delete", "publish", "send", "commit", "remove",
    "drop", "destroy", "wipe", "purge", "terminate"
])

WRITE_OPERATION_TYPES = frozenset(["write", "delete", "publish"])

AMBIGUITY_SIGNALS = frozenset([
    " it ", " this ", " that ", "all of them", "everything",
    "the thing", "those", "them"
])

def evaluate_pre_call(request: CanonicalRelayRequest) -> list[LensObservation]:
    """
    Evaluate Decision Checkpoints and Assumption Surfacing against the relay
    request before provider invocation. Returns a list of LensObservation
    objects. Returns empty list if no triggers fire.
    """
    observations: list[LensObservation] = []
    observations.extend(_evaluate_decision_checkpoints(request))
    observations.extend(_evaluate_assumption_surfacing(request))
    return observations


def _evaluate_decision_checkpoints(
    request: CanonicalRelayRequest
) -> list[LensObservation]:
    signals: list[str] = []
    input_lower = request.input_text.lower()

    if request.is_irreversible is True:
        signals.append("explicit_irreversible_flag")

    if request.operation_type in WRITE_OPERATION_TYPES:
        signals.append(f"operation_type:{request.operation_type}")

    found_signals = [s for s in IRREVERSIBILITY_SIGNALS if s in input_lower]
    signals.extend([f"keyword:{s}" for s in found_signals])

    if not signals:
        return [LensObservation(
            behavior="decision_checkpoints",
            trigger_fired=False,
            confidence=0.0,
            observation="No irreversibility signals detected in relay request.",
            hook="pre_call",
            lens_version=LENS_VERSION
        )]

    confidence = min(0.5 + (len(signals) * 0.15), 1.0)
    return [LensObservation(
        behavior="decision_checkpoints",
        trigger_fired=True,
        confidence=round(confidence, 2),
        observation=(
            f"Relay request contains irreversibility signals: "
            f"{', '.join(signals)}. Decision checkpoint warranted before execution."
        ),
        hook="pre_call",
        lens_version=LENS_VERSION
    )]


def _evaluate_assumption_surfacing(
    request: CanonicalRelayRequest
) -> list[LensObservation]:
    signals: list[str] = []
    input_lower = f" {request.input_text.lower()} "

    found_ambiguity = [s for s in AMBIGUITY_SIGNALS if s in input_lower]
    if found_ambiguity:
        signals.append(f"ambiguous_references:{','.join(found_ambiguity).strip()}")

    word_count = len(request.input_text.split())
    if word_count < 20:
        signals.append(f"short_uncontextualized_request:{word_count}_words")

    if not signals:
        return [LensObservation(
            behavior="assumption_surfacing",
            trigger_fired=False,
            confidence=0.0,
            observation="No material implicit assumptions detected in relay request.",
            hook="pre_call",
            lens_version=LENS_VERSION
        )]

    confidence = min(0.45 + (len(signals) * 0.2), 1.0)
    return [LensObservation(
        behavior="assumption_surfacing",
        trigger_fired=True,
        confidence=round(confidence, 2),
        observation=(
            f"Relay request contains implicit assumptions that may affect output: "
            f"{', '.join(signals)}."
        ),
        hook="pre_call",
        lens_version=LENS_VERSION
    )]
```

---

## Step 5 — `governance/lens_post_call.py`

Implement per `docs/03_Integration_Design_v1.0.md` Section 3.2.

**Prompt Reflection trigger conditions** (from Section 3.2):
- Response contains interpretation language: ("i assumed", "interpreting this as", "based on my understanding", "i interpreted", "treating this as", "i'll assume")
- Response word count differs from request word count by more than 5x (scope mismatch signal)
- Response contains a clarifying question directed back at the user

**Reframe Offers trigger conditions** (from Section 3.2):
- Response contains reframe signal phrases: ("a better question might be", "what you may actually need", "the underlying question", "more useful to ask", "consider reframing", "the root question")
- Response length is > 3x the request length AND contains a direct suggestion

```python
from aegisrelay.models.relay_request import CanonicalRelayRequest
from aegisrelay.models.relay_response import CanonicalRelayResponse
from aegisrelay.models.lens_observation import LensObservation
from aegisrelay.governance.lens_constants import LENS_VERSION

INTERPRETATION_SIGNALS = frozenset([
    "i assumed", "interpreting this as", "based on my understanding",
    "i interpreted", "treating this as", "i'll assume", "i am assuming",
    "assuming you meant", "i understand this to mean"
])

REFRAME_SIGNALS = frozenset([
    "a better question might be", "what you may actually need",
    "the underlying question", "more useful to ask",
    "consider reframing", "the root question", "what you're really asking"
])

def evaluate_post_call(
    request: CanonicalRelayRequest,
    response: CanonicalRelayResponse
) -> list[LensObservation]:
    """
    Evaluate Prompt Reflection and Reframe Offers against the completed
    exchange. Returns a list of LensObservation objects. Returns empty
    list if no triggers fire.
    """
    observations: list[LensObservation] = []
    observations.extend(_evaluate_prompt_reflection(request, response))
    observations.extend(_evaluate_reframe_offers(request, response))
    return observations


def _evaluate_prompt_reflection(
    request: CanonicalRelayRequest,
    response: CanonicalRelayResponse
) -> list[LensObservation]:
    signals: list[str] = []
    response_lower = response.response_text.lower()

    found_interpretation = [s for s in INTERPRETATION_SIGNALS if s in response_lower]
    if found_interpretation:
        signals.append(f"interpretation_language:{','.join(found_interpretation[:2])}")

    request_words = len(request.input_text.split())
    response_words = len(response.response_text.split())
    if request_words > 0 and response_words / request_words > 5:
        signals.append(f"scope_expansion_ratio:{round(response_words/request_words, 1)}x")

    if "?" in response.response_text:
        question_sentences = [
            s.strip() for s in response.response_text.split(".")
            if "?" in s and len(s.strip()) > 10
        ]
        if question_sentences:
            signals.append("response_contains_clarifying_question")

    if not signals:
        return [LensObservation(
            behavior="prompt_reflection",
            trigger_fired=False,
            confidence=0.0,
            observation="No prompt reflection triggers detected in provider response.",
            hook="post_call",
            lens_version=LENS_VERSION
        )]

    confidence = min(0.5 + (len(signals) * 0.15), 1.0)
    return [LensObservation(
        behavior="prompt_reflection",
        trigger_fired=True,
        confidence=round(confidence, 2),
        observation=(
            f"Provider response indicates interpretation was required: "
            f"{', '.join(signals)}."
        ),
        hook="post_call",
        lens_version=LENS_VERSION
    )]


def _evaluate_reframe_offers(
    request: CanonicalRelayRequest,
    response: CanonicalRelayResponse
) -> list[LensObservation]:
    signals: list[str] = []
    response_lower = response.response_text.lower()

    found_reframe = [s for s in REFRAME_SIGNALS if s in response_lower]
    if found_reframe:
        signals.append(f"reframe_language:{','.join(found_reframe[:2])}")

    request_words = len(request.input_text.split())
    response_words = len(response.response_text.split())
    if request_words > 0 and response_words / request_words > 3:
        signals.append("extended_response_may_indicate_reframe_opportunity")

    if not signals:
        return [LensObservation(
            behavior="reframe_offers",
            trigger_fired=False,
            confidence=0.0,
            observation="No reframe opportunity signals detected in provider response.",
            hook="post_call",
            lens_version=LENS_VERSION
        )]

    confidence = min(0.4 + (len(signals) * 0.2), 0.9)
    return [LensObservation(
        behavior="reframe_offers",
        trigger_fired=True,
        confidence=round(confidence, 2),
        observation=(
            f"Response suggests the question asked may not be the question needed: "
            f"{', '.join(signals)}."
        ),
        hook="post_call",
        lens_version=LENS_VERSION
    )]
```

---

## Step 6 — `governance/pipeline.py` — Stub with LENS Stage Hooks

Create a stub pipeline with the 8 stages as skeleton functions. Stages 3 and 4 must include the LENS trigger condition comments from `docs/03_Integration_Design_v1.0.md` Section 5 — these are placeholders for Phase 2 full pipeline implementation.

```python
"""
AegisRelay Governance Pipeline — ADR-004
Eight-stage pipeline: Normalize → Segment → Classify → Mark Uncertainty →
Apply Temporal Policy → Redact → Deduplicate → Persist

Stage 3 and Stage 4 include LENS trigger condition hooks per ADR-009.
Full implementation: Phase 2.
"""
from aegisrelay.models.relay_response import CanonicalRelayResponse
from aegisrelay.models.memory_record import MemoryRecord
from aegisrelay.governance.lens_constants import LENS_VERSION


def run_pipeline(response: CanonicalRelayResponse, relay_id: str) -> MemoryRecord:
    """Entry point. Runs all eight stages in sequence."""
    result = _stage_1_normalize(response)
    result = _stage_2_segment(result)
    result = _stage_3_classify(result, relay_id)
    result = _stage_4_mark_uncertainty(result, relay_id)
    result = _stage_5_temporal_policy(result)
    result = _stage_6_redact(result)
    result = _stage_7_deduplicate(result)
    return _stage_8_persist(result, relay_id)


def _stage_1_normalize(response: CanonicalRelayResponse) -> dict:
    """Stage 1 — Normalize provider response to canonical form. Phase 2."""
    return {"response": response, "segments": [], "governance_events": []}


def _stage_2_segment(state: dict) -> dict:
    """Stage 2 — Segment response into discrete claims/units. Phase 2."""
    return state


def _stage_3_classify(state: dict, relay_id: str) -> dict:
    """
    Stage 3 — Classify segments by epistemic class and trust tier.

    LENS — Cognitive Model Disclosure hook (ADR-009):
    Fires when: (a) a structural framing choice was made AND
                (b) a different frame would materially change the output.
    Both conditions must be true. Write governance_event if triggered.
    Implementation: Phase 2.
    """
    return state


def _stage_4_mark_uncertainty(state: dict, relay_id: str) -> dict:
    """
    Stage 4 — Mark uncertain claims explicitly.

    LENS — Uncertainty Flagging hook (ADR-009):
    Fires when: a claim is based on incomplete information or assumption
    and was presented without qualification.
    An unflagged uncertain claim = LENS violation (trigger_fired=True, violation=True).
    Implementation: Phase 2.
    """
    return state


def _stage_5_temporal_policy(state: dict) -> dict:
    """Stage 5 — Apply temporal_scope and expires_at per ADR-006. Phase 2."""
    return state


def _stage_6_redact(state: dict) -> dict:
    """Stage 6 — Apply redaction rules. Phase 2."""
    return state


def _stage_7_deduplicate(state: dict) -> dict:
    """Stage 7 — Deduplicate per ADR-005 content_hash. Phase 2."""
    return state


def _stage_8_persist(state: dict, relay_id: str) -> MemoryRecord:
    """
    Stage 8 — Write MemoryRecord and governance_events in single transaction.
    LENS observations from pre/post hooks also written here.
    Phase 2.
    """
    return MemoryRecord(
        memory_id="stub",
        relay_id=relay_id,
        body_text="stub — Phase 2",
        schema_version="1.0"
    )
```

---

## Step 7 — Unit Tests

### `tests/governance/test_lens_constants.py`

```python
from aegisrelay.governance.lens_constants import (
    LENS_BEHAVIORS, LENS_VERSION, PRE_CALL_BEHAVIORS, POST_CALL_BEHAVIORS
)

def test_all_six_behaviors_present():
    expected = {
        "decision_checkpoints", "assumption_surfacing", "prompt_reflection",
        "reframe_offers", "uncertainty_flagging", "cognitive_model_disclosure"
    }
    assert set(LENS_BEHAVIORS.keys()) == expected

def test_pre_call_behaviors():
    assert set(PRE_CALL_BEHAVIORS) == {"decision_checkpoints", "assumption_surfacing"}

def test_post_call_behaviors():
    assert set(POST_CALL_BEHAVIORS) == {"prompt_reflection", "reframe_offers"}

def test_lens_version():
    assert LENS_VERSION == "1.0"

def test_all_behaviors_have_required_fields():
    for name, spec in LENS_BEHAVIORS.items():
        assert "hook" in spec, f"{name} missing hook"
        assert "required" in spec, f"{name} missing required"
        assert "violation_on" in spec, f"{name} missing violation_on"
```

### `tests/governance/test_lens_pre_call.py`

```python
from datetime import datetime, timezone
from aegisrelay.models.relay_request import CanonicalRelayRequest
from aegisrelay.governance.lens_pre_call import evaluate_pre_call

def _make_request(**kwargs) -> CanonicalRelayRequest:
    defaults = {
        "relay_id": "test-relay-001",
        "human_actor_id": "jonathan",
        "provider_name": "perplexity",
        "provider_model": "sonar-pro",
        "input_text": "What is the capital of France?",
        "submitted_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    return CanonicalRelayRequest(**defaults)

def test_no_triggers_returns_two_observations():
    observations = evaluate_pre_call(_make_request())
    assert len(observations) == 2
    assert all(not o.trigger_fired for o in observations)

def test_delete_keyword_fires_decision_checkpoint():
    req = _make_request(input_text="Please delete all records from the archive.")
    obs = evaluate_pre_call(req)
    dc = next(o for o in obs if o.behavior == "decision_checkpoints")
    assert dc.trigger_fired is True
    assert dc.confidence > 0.5

def test_explicit_irreversible_flag_fires_decision_checkpoint():
    req = _make_request(is_irreversible=True)
    obs = evaluate_pre_call(req)
    dc = next(o for o in obs if o.behavior == "decision_checkpoints")
    assert dc.trigger_fired is True

def test_short_ambiguous_request_fires_assumption_surfacing():
    req = _make_request(input_text="Do it now.")
    obs = evaluate_pre_call(req)
    asm = next(o for o in obs if o.behavior == "assumption_surfacing")
    assert asm.trigger_fired is True

def test_observations_have_correct_hook():
    obs = evaluate_pre_call(_make_request())
    assert all(o.hook == "pre_call" for o in obs)

def test_observations_have_correct_lens_version():
    obs = evaluate_pre_call(_make_request())
    assert all(o.lens_version == "1.0" for o in obs)

def test_confidence_between_zero_and_one():
    obs = evaluate_pre_call(_make_request(input_text="Delete everything now."))
    assert all(0.0 <= o.confidence <= 1.0 for o in obs)
```

### `tests/governance/test_lens_post_call.py`

```python
from datetime import datetime, timezone
from aegisrelay.models.relay_request import CanonicalRelayRequest
from aegisrelay.models.relay_response import CanonicalRelayResponse
from aegisrelay.governance.lens_post_call import evaluate_post_call

def _make_request(input_text: str = "Summarize the report.") -> CanonicalRelayRequest:
    return CanonicalRelayRequest(
        relay_id="test-relay-002",
        human_actor_id="jonathan",
        provider_name="perplexity",
        provider_model="sonar-pro",
        input_text=input_text,
        submitted_at=datetime.now(timezone.utc),
    )

def _make_response(response_text: str) -> CanonicalRelayResponse:
    return CanonicalRelayResponse(
        relay_id="test-relay-002",
        provider_name="perplexity",
        provider_model="sonar-pro",
        response_text=response_text,
        provider_request_ts=datetime.now(timezone.utc),
        provider_response_ts=datetime.now(timezone.utc),
    )

def test_no_triggers_returns_two_observations():
    obs = evaluate_post_call(
        _make_request(),
        _make_response("France is a country in Western Europe.")
    )
    assert len(obs) == 2
    assert all(not o.trigger_fired for o in obs)

def test_interpretation_language_fires_prompt_reflection():
    obs = evaluate_post_call(
        _make_request(),
        _make_response("I assumed you were asking about the executive summary.")
    )
    pr = next(o for o in obs if o.behavior == "prompt_reflection")
    assert pr.trigger_fired is True

def test_reframe_language_fires_reframe_offers():
    obs = evaluate_post_call(
        _make_request(),
        _make_response("A better question might be what outcomes you need from the report.")
    )
    rf = next(o for o in obs if o.behavior == "reframe_offers")
    assert rf.trigger_fired is True

def test_observations_have_correct_hook():
    obs = evaluate_post_call(_make_request(), _make_response("Simple response."))
    assert all(o.hook == "post_call" for o in obs)

def test_confidence_between_zero_and_one():
    obs = evaluate_post_call(
        _make_request(),
        _make_response("Interpreting this as a request for a brief overview.")
    )
    assert all(0.0 <= o.confidence <= 1.0 for o in obs)
```

---

## Step 8 — `requirements.txt`

```
pydantic>=2.0.0
pytest>=7.0.0
```

---

## Definition of Done for Phase 1

- [ ] Directory structure created per Step 1
- [ ] `LensObservation` Pydantic model implemented
- [ ] `CanonicalRelayRequest` and `CanonicalRelayResponse` stubs implemented
- [ ] `lens_constants.py` implemented with all 6 behaviors
- [ ] `lens_pre_call.py` implemented with both evaluators
- [ ] `lens_post_call.py` implemented with both evaluators
- [ ] `pipeline.py` stub created with Stages 3 and 4 LENS comment hooks
- [ ] All unit tests pass: `pytest tests/`
- [ ] No import errors anywhere in the `aegisrelay/` package

---

## What Comes Next (Phase 2 — not in scope now)

- Full `CanonicalRelayRequest` / `CanonicalRelayResponse` / `MemoryRecord` models
- Pydantic models + DDL (database schema)
- Provider adapters (Perplexity, Grok)
- Full eight-stage governance pipeline implementation
- CRUD layer (`admin/`)
- Outbox and embedding worker
- Wiring pre/post hooks into the main relay call flow
- `get_relay()` returns LENS observations

---

*Spec authority: `docs/03_Integration_Design_v1.0.md`*
*ADR authority: `docs/02_ADR_Log_v1.0.md`*
*Implementation owner: Cursor*
