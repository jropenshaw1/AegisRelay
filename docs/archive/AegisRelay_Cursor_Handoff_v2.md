# AegisRelay — Cursor Implementation Handoff v2
**Date:** March 21, 2026 MST
**Session:** LENS Integration Build — Phase 1
**Spec authority:** `docs/03_Integration_Design_v1.0.md`
**ADR authority:** `docs/02_ADR_Log_v1.0.md`
**Supersedes:** AegisRelay_Cursor_Handoff.md (v1)

## Changes from v1 (pre-build dual review — Claude + Cursor)
1. `pyproject.toml` added — required for package imports and pytest
2. `BehaviorId` Literal type added to `LensObservation.behavior` — was bare `str`
3. `Field(ge=0.0, le=1.0)` added to `LensObservation.confidence` — was unvalidated
4. Docstrings in `lens_pre_call.py` and `lens_post_call.py` corrected — said "Returns empty list if no triggers fire"; corrected to "Always returns exactly two observations"
5. `pipeline_stage_3` and `pipeline_stage_4` documented as explicit spec extension to `LensObservation.hook`
6. Persistence policy decided and documented — always emit all observations to `governance_events`
7. `confidence == 0.0` assertions added to all no-trigger test cases
8. Test count corrected — 14 tests (not 17 as stated in v1)

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

## Step 1 — Project Structure

```
aegisrelay/
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── relay_request.py       ← Pydantic: CanonicalRelayRequest
│   ├── relay_response.py      ← Pydantic: CanonicalRelayResponse
│   ├── memory_record.py       ← Pydantic: MemoryRecord (stub)
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

pyproject.toml                 ← NEW in v2 — required for package imports
requirements-dev.txt
```

---

## Step 2 — `pyproject.toml`
**[FIX #1 — v2]** Required for `from aegisrelay.models...` imports to resolve in pytest.
Install with: `pip install -e ".[dev]"`

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "aegisrelay"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["pydantic>=2.0.0"]

[project.optional-dependencies]
dev = ["pytest>=7.0.0"]
```

---

## Step 3 — `requirements-dev.txt`

```
# Install the package itself in editable mode first: pip install -e ".[dev]"
pydantic>=2.0.0
pytest>=7.0.0
```

---

## Step 4 — Pydantic Models

### `models/lens_observation.py`
**[FIX #2 — v2]** `behavior` field typed as `BehaviorId` Literal, not bare `str`.
**[FIX #3 — v2]** `confidence` field validated 0.0–1.0 via `Field(ge=0.0, le=1.0)`.
**[FIX #5 — v2]** `pipeline_stage_3` and `pipeline_stage_4` documented as spec extension.

```python
from typing import Literal
from pydantic import BaseModel, Field

# Spec extension note: pipeline_stage_3 and pipeline_stage_4 are additions
# beyond the pre_call/post_call hooks described in 03_Integration_Design_v1.0.md
# §3.1-3.2. They allow a single LensObservation type to cover all hook points
# in the call flow. A one-line note has been added to §3 of the integration doc.
HookId = Literal["pre_call", "post_call", "pipeline_stage_3", "pipeline_stage_4"]

BehaviorId = Literal[
    "decision_checkpoints",
    "assumption_surfacing",
    "prompt_reflection",
    "reframe_offers",
    "uncertainty_flagging",
    "cognitive_model_disclosure"
]

class LensObservation(BaseModel):
    behavior: BehaviorId                          # validated at construction
    trigger_fired: bool
    confidence: float = Field(ge=0.0, le=1.0)    # enforced bounds
    observation: str
    hook: HookId
    lens_version: str
```

### `models/relay_request.py`

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
    operation_type: Optional[str] = None    # "read" | "write" | "delete" | "publish"
    is_irreversible: Optional[bool] = None
```

### `models/relay_response.py`

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

# Full implementation Phase 2
class MemoryRecord(BaseModel):
    memory_id: str
    relay_id: str
    body_text: str
    schema_version: str = "1.0"
```

---

## Step 5 — `governance/lens_constants.py`

```python
from typing import TypedDict

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

## Step 6 — `governance/lens_pre_call.py`
**[FIX #4 — v2]** Docstrings corrected — always returns exactly two observations.
**[FIX #8 — v2]** Ambiguity signals use `re.search` word boundaries, not space-padding.

```python
import re
from aegisrelay.models.relay_request import CanonicalRelayRequest
from aegisrelay.models.lens_observation import LensObservation
from aegisrelay.governance.lens_constants import LENS_VERSION

IRREVERSIBILITY_SIGNALS = frozenset([
    "delete", "publish", "send", "commit", "remove",
    "drop", "destroy", "wipe", "purge", "terminate"
])

WRITE_OPERATION_TYPES = frozenset(["write", "delete", "publish"])

# Word-boundary patterns — more precise than space-padding
AMBIGUITY_PATTERNS = [
    r"\bit\b", r"\bthis\b", r"\bthat\b", r"\bthose\b", r"\bthem\b",
    r"\beverything\b", r"\bthe thing\b", r"\ball of them\b"
]


def evaluate_pre_call(request: CanonicalRelayRequest) -> list[LensObservation]:
    """
    Evaluate Decision Checkpoints and Assumption Surfacing against the relay
    request before provider invocation.

    Always returns exactly two LensObservation objects — one per behavior.
    trigger_fired=False and confidence=0.0 when a behavior's conditions are
    not met. Never returns an empty list.
    """
    return [
        _evaluate_decision_checkpoints(request),
        _evaluate_assumption_surfacing(request),
    ]


def _evaluate_decision_checkpoints(
    request: CanonicalRelayRequest,
) -> LensObservation:
    signals: list[str] = []
    input_lower = request.input_text.lower()

    if request.is_irreversible is True:
        signals.append("explicit_irreversible_flag")

    if request.operation_type in WRITE_OPERATION_TYPES:
        signals.append(f"operation_type:{request.operation_type}")

    found = [s for s in IRREVERSIBILITY_SIGNALS if s in input_lower]
    signals.extend(f"keyword:{s}" for s in found)

    if not signals:
        return LensObservation(
            behavior="decision_checkpoints",
            trigger_fired=False,
            confidence=0.0,
            observation="No irreversibility signals detected in relay request.",
            hook="pre_call",
            lens_version=LENS_VERSION,
        )

    confidence = round(min(0.5 + len(signals) * 0.15, 1.0), 2)
    return LensObservation(
        behavior="decision_checkpoints",
        trigger_fired=True,
        confidence=confidence,
        observation=(
            f"Relay request contains irreversibility signals: "
            f"{', '.join(signals)}. Decision checkpoint warranted before execution."
        ),
        hook="pre_call",
        lens_version=LENS_VERSION,
    )


def _evaluate_assumption_surfacing(
    request: CanonicalRelayRequest,
) -> LensObservation:
    signals: list[str] = []
    input_lower = request.input_text.lower()

    matched = [p for p in AMBIGUITY_PATTERNS if re.search(p, input_lower)]
    if matched:
        signals.append(f"ambiguous_references:{len(matched)}_patterns_matched")

    word_count = len(request.input_text.split())
    if word_count < 20:
        signals.append(f"short_uncontextualized_request:{word_count}_words")

    if not signals:
        return LensObservation(
            behavior="assumption_surfacing",
            trigger_fired=False,
            confidence=0.0,
            observation="No material implicit assumptions detected in relay request.",
            hook="pre_call",
            lens_version=LENS_VERSION,
        )

    confidence = round(min(0.45 + len(signals) * 0.2, 1.0), 2)
    return LensObservation(
        behavior="assumption_surfacing",
        trigger_fired=True,
        confidence=confidence,
        observation=(
            f"Relay request contains implicit assumptions that may affect output: "
            f"{', '.join(signals)}."
        ),
        hook="pre_call",
        lens_version=LENS_VERSION,
    )
```

---

## Step 7 — `governance/lens_post_call.py`
**[FIX #4 — v2]** Docstrings corrected — always returns exactly two observations.

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
    response: CanonicalRelayResponse,
) -> list[LensObservation]:
    """
    Evaluate Prompt Reflection and Reframe Offers against the completed
    exchange after provider invocation.

    Always returns exactly two LensObservation objects — one per behavior.
    trigger_fired=False and confidence=0.0 when a behavior's conditions are
    not met. Never returns an empty list.
    """
    return [
        _evaluate_prompt_reflection(request, response),
        _evaluate_reframe_offers(request, response),
    ]


def _evaluate_prompt_reflection(
    request: CanonicalRelayRequest,
    response: CanonicalRelayResponse,
) -> LensObservation:
    signals: list[str] = []
    response_lower = response.response_text.lower()

    found = [s for s in INTERPRETATION_SIGNALS if s in response_lower]
    if found:
        signals.append(f"interpretation_language:{','.join(found[:2])}")

    request_words = len(request.input_text.split())
    response_words = len(response.response_text.split())
    if request_words > 0 and response_words / request_words > 5:
        signals.append(
            f"scope_expansion_ratio:{round(response_words / request_words, 1)}x"
        )

    # Only flag clarifying questions — not rhetorical or informational "?"
    clarifying_questions = [
        s.strip()
        for s in response.response_text.split(".")
        if "?" in s
        and any(
            marker in s.lower()
            for marker in ("could you", "can you", "do you mean", "which", "what did you")
        )
    ]
    if clarifying_questions:
        signals.append("response_contains_clarifying_question")

    if not signals:
        return LensObservation(
            behavior="prompt_reflection",
            trigger_fired=False,
            confidence=0.0,
            observation="No prompt reflection triggers detected in provider response.",
            hook="post_call",
            lens_version=LENS_VERSION,
        )

    confidence = round(min(0.5 + len(signals) * 0.15, 1.0), 2)
    return LensObservation(
        behavior="prompt_reflection",
        trigger_fired=True,
        confidence=confidence,
        observation=(
            f"Provider response indicates interpretation was required: "
            f"{', '.join(signals)}."
        ),
        hook="post_call",
        lens_version=LENS_VERSION,
    )


def _evaluate_reframe_offers(
    request: CanonicalRelayRequest,
    response: CanonicalRelayResponse,
) -> LensObservation:
    signals: list[str] = []
    response_lower = response.response_text.lower()

    found = [s for s in REFRAME_SIGNALS if s in response_lower]
    if found:
        signals.append(f"reframe_language:{','.join(found[:2])}")

    request_words = len(request.input_text.split())
    response_words = len(response.response_text.split())
    if request_words > 0 and response_words / request_words > 3 and found:
        signals.append("extended_response_with_reframe_language")

    if not signals:
        return LensObservation(
            behavior="reframe_offers",
            trigger_fired=False,
            confidence=0.0,
            observation="No reframe opportunity signals detected in provider response.",
            hook="post_call",
            lens_version=LENS_VERSION,
        )

    confidence = round(min(0.4 + len(signals) * 0.2, 0.9), 2)
    return LensObservation(
        behavior="reframe_offers",
        trigger_fired=True,
        confidence=confidence,
        observation=(
            f"Response suggests the question asked may not be the question needed: "
            f"{', '.join(signals)}."
        ),
        hook="post_call",
        lens_version=LENS_VERSION,
    )
```

---

## Step 8 — `governance/pipeline.py` — Stub with LENS Stage Hooks

```python
"""
AegisRelay Governance Pipeline — ADR-004
Eight-stage pipeline: Normalize → Segment → Classify → Mark Uncertainty →
Apply Temporal Policy → Redact → Deduplicate → Persist

Stage 3 and Stage 4 include LENS trigger condition hooks per ADR-009.
Full implementation: Phase 2.
"""
from dataclasses import dataclass, field
from aegisrelay.models.relay_response import CanonicalRelayResponse
from aegisrelay.models.memory_record import MemoryRecord
from aegisrelay.models.lens_observation import LensObservation
from aegisrelay.governance.lens_constants import LENS_VERSION


@dataclass
class PipelineState:
    """
    Typed pipeline state passed between stages. Replaces bare dict —
    provides IDE autocomplete and prevents silent key drops across stages.
    Full field set populated in Phase 2.
    """
    response: CanonicalRelayResponse
    relay_id: str
    segments: list = field(default_factory=list)
    governance_events: list = field(default_factory=list)
    lens_observations: list[LensObservation] = field(default_factory=list)


def run_pipeline(
    response: CanonicalRelayResponse,
    relay_id: str,
    pre_call_observations: list[LensObservation] | None = None,
    post_call_observations: list[LensObservation] | None = None,
) -> MemoryRecord:
    """
    Entry point. Accepts pre/post call LENS observations so Stage 8 can
    persist them to governance_events alongside pipeline observations.
    """
    state = PipelineState(response=response, relay_id=relay_id)
    if pre_call_observations:
        state.lens_observations.extend(pre_call_observations)
    if post_call_observations:
        state.lens_observations.extend(post_call_observations)

    state = _stage_1_normalize(state)
    state = _stage_2_segment(state)
    state = _stage_3_classify(state)
    state = _stage_4_mark_uncertainty(state)
    state = _stage_5_temporal_policy(state)
    state = _stage_6_redact(state)
    state = _stage_7_deduplicate(state)
    return _stage_8_persist(state)


def _stage_1_normalize(state: PipelineState) -> PipelineState:
    """Stage 1 — Normalize provider response to canonical form. Phase 2."""
    return state


def _stage_2_segment(state: PipelineState) -> PipelineState:
    """Stage 2 — Segment response into discrete claims/units. Phase 2."""
    return state


def _stage_3_classify(state: PipelineState) -> PipelineState:
    """
    Stage 3 — Classify segments by epistemic class and trust tier.

    LENS — Cognitive Model Disclosure hook (ADR-009):
    Fires when: (a) a structural framing choice was made AND
                (b) a different frame would materially change the output.
    Both conditions must be true. Write LensObservation to
    state.lens_observations if triggered. Phase 2.
    """
    return state


def _stage_4_mark_uncertainty(state: PipelineState) -> PipelineState:
    """
    Stage 4 — Mark uncertain claims explicitly.

    LENS — Uncertainty Flagging hook (ADR-009):
    Fires when: a claim is based on incomplete information or assumption
    and was presented without qualification.
    An unflagged uncertain claim = LENS violation
    (trigger_fired=True, violation=True in governance_event metadata).
    Write LensObservation to state.lens_observations if triggered. Phase 2.
    """
    return state


def _stage_5_temporal_policy(state: PipelineState) -> PipelineState:
    """Stage 5 — Apply temporal_scope and expires_at per ADR-006. Phase 2."""
    return state


def _stage_6_redact(state: PipelineState) -> PipelineState:
    """Stage 6 — Apply redaction rules. Phase 2."""
    return state


def _stage_7_deduplicate(state: PipelineState) -> PipelineState:
    """Stage 7 — Deduplicate per ADR-005 content_hash. Phase 2."""
    return state


def _stage_8_persist(state: PipelineState) -> MemoryRecord:
    """
    Stage 8 — Write MemoryRecord and ALL governance_events in single transaction.

    PERSISTENCE POLICY (v1, decided March 21 2026):
    All LensObservations are written to governance_events regardless of
    trigger_fired value. This means every relay produces exactly four
    governance_event rows from LENS hooks (two pre_call + two post_call),
    plus any observations from pipeline Stages 3 and 4 if triggered.

    Rationale: complete audit trail — downstream queries can distinguish
    "behavior evaluated, not triggered" from "behavior never evaluated."
    Consistent row count per relay makes querying and the portfolio demo
    predictable. trigger_fired=False rows are cheap; missing audit rows
    are not recoverable.

    Phase 2 implementation: write state.lens_observations to
    governance_events with event_type='lens_observation' in same
    transaction as MemoryRecord insert.
    """
    return MemoryRecord(
        memory_id="stub",
        relay_id=state.relay_id,
        body_text="stub — Phase 2",
        schema_version="1.0",
    )
```

---

## Step 9 — Unit Tests (14 tests)

### `tests/governance/test_lens_constants.py` (5 tests)

```python
from aegisrelay.governance.lens_constants import (
    LENS_BEHAVIORS, LENS_VERSION, PRE_CALL_BEHAVIORS, POST_CALL_BEHAVIORS,
)


def test_all_six_behaviors_present():
    expected = {
        "decision_checkpoints", "assumption_surfacing", "prompt_reflection",
        "reframe_offers", "uncertainty_flagging", "cognitive_model_disclosure",
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

### `tests/governance/test_lens_pre_call.py` (5 tests)

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


def test_always_returns_two_observations():
    obs = evaluate_pre_call(_make_request())
    assert len(obs) == 2


def test_no_triggers_returns_false_and_zero_confidence():
    # [FIX #7 — v2] confidence==0.0 asserted on no-trigger cases
    obs = evaluate_pre_call(_make_request())
    assert all(not o.trigger_fired for o in obs)
    assert all(o.confidence == 0.0 for o in obs)


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
    assert asm.confidence > 0.0
```

### `tests/governance/test_lens_post_call.py` (4 tests)

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


def test_always_returns_two_observations():
    obs = evaluate_post_call(
        _make_request(),
        _make_response("France is a country in Western Europe.")
    )
    assert len(obs) == 2


def test_no_triggers_returns_false_and_zero_confidence():
    # [FIX #7 — v2] confidence==0.0 asserted on no-trigger cases
    obs = evaluate_post_call(
        _make_request(),
        _make_response("France is a country in Western Europe.")
    )
    assert all(not o.trigger_fired for o in obs)
    assert all(o.confidence == 0.0 for o in obs)


def test_interpretation_language_fires_prompt_reflection():
    obs = evaluate_post_call(
        _make_request(),
        _make_response("I assumed you were asking about the executive summary.")
    )
    pr = next(o for o in obs if o.behavior == "prompt_reflection")
    assert pr.trigger_fired is True
    assert pr.confidence > 0.0


def test_reframe_language_fires_reframe_offers():
    obs = evaluate_post_call(
        _make_request(),
        _make_response(
            "A better question might be what outcomes you need from the report."
        )
    )
    rf = next(o for o in obs if o.behavior == "reframe_offers")
    assert rf.trigger_fired is True
    assert rf.confidence > 0.0
```

---

## Definition of Done for Phase 1

- [ ] `pyproject.toml` created and package installed with `pip install -e ".[dev]"`
- [ ] Directory structure created per Step 1
- [ ] `LensObservation` model with `BehaviorId` Literal and `Field(ge=0.0, le=1.0)`
- [ ] `CanonicalRelayRequest`, `CanonicalRelayResponse`, `MemoryRecord` stubs implemented
- [ ] `lens_constants.py` implemented with all 6 behaviors
- [ ] `lens_pre_call.py` implemented — always returns exactly 2 observations
- [ ] `lens_post_call.py` implemented — always returns exactly 2 observations
- [ ] `pipeline.py` stub with `PipelineState` dataclass and LENS hook comments in Stages 3 and 4
- [ ] All 14 unit tests pass: `pytest tests/`
- [ ] No import errors anywhere in the `aegisrelay/` package

---

## Persistence Policy Decision (v1)
**[FIX #6 — v2]** Decided March 21, 2026 MST.

Every relay write in Stage 8 emits ALL LensObservation rows to `governance_events`
regardless of `trigger_fired` value. A relay with pre_call + post_call hooks always
produces exactly **4 LENS rows** plus any Stage 3/4 observations if triggered.

`trigger_fired=False` rows are retained because:
- Audit trail is complete — "evaluated, not triggered" is distinct from "never evaluated"
- Consistent row count per relay makes querying and portfolio demonstration predictable
- Storage cost is negligible; missing audit rows are unrecoverable

---

## What Comes Next (Phase 2 — not in scope now)

- Full `CanonicalRelayRequest` / `CanonicalRelayResponse` / `MemoryRecord` models
- DDL — Postgres schema, pgvector, outbox tables
- Provider adapters (Perplexity, Grok)
- Full eight-stage governance pipeline
- CRUD layer (`admin/`)
- Outbox and embedding worker
- Wiring: pre/post hooks → pipeline → Stage 8 persistence
- `get_relay()` returns full LENS observation ledger

---

*Spec authority: `docs/03_Integration_Design_v1.0.md`*
*ADR authority: `docs/02_ADR_Log_v1.0.md`*
*Handoff version: v2 — all dual-review findings resolved*
*Implementation owner: Cursor*
