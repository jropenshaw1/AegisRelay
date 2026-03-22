"""LENS behavior registry and string tags (03_Integration_Design_v1.0.md §3.3)."""

from __future__ import annotations

from typing import Literal, TypedDict


class LensBehaviorMeta(TypedDict):
    hook: Literal["pre_call", "post_call", "pipeline_stage_3", "pipeline_stage_4"]
    required: bool
    violation_on: str


# Registry documents hook placement and v2 semantics; v1 is observational only.
LENS_BEHAVIORS: dict[str, LensBehaviorMeta] = {
    "decision_checkpoints": {
        "hook": "pre_call",
        "required": True,
        "violation_on": "irreversible_action_taken_silently",
    },
    "assumption_surfacing": {
        "hook": "pre_call",
        "required": True,
        "violation_on": "consequential_output_assumptions_unstated",
    },
    "prompt_reflection": {
        "hook": "post_call",
        "required": True,
        "violation_on": "trigger_present_behavior_absent",
    },
    "reframe_offers": {
        "hook": "post_call",
        "required": False,
        "violation_on": "reframe_available_not_offered",
    },
    "uncertainty_flagging": {
        "hook": "pipeline_stage_4",
        "required": True,
        "violation_on": "uncertain_claim_presented_as_confident",
    },
    "cognitive_model_disclosure": {
        "hook": "pipeline_stage_3",
        "required": False,
        "violation_on": "material_frame_choice_not_surfaced",
    },
}

LENS_VERSION = "1.0"
LENS_TAG_PREFIX = "lens"
LENS_SOURCE_TAG = "[source:lens]"

# Heuristic keyword ids (Phase 1 — explicit, versioned signals for tests and audits).
SIGNAL_IRREVERSIBLE = "keyword:irreversible_action"
SIGNAL_WRITE_OP = "operation:write"
SIGNAL_CASCADE = "keyword:downstream_cascade"
SIGNAL_AMBIGUOUS_SCOPE = "pattern:ambiguous_scope"
SIGNAL_REFLECTION_PHRASE = "phrase:interpretation_disclosed"
SIGNAL_REFRAME_PHRASE = "phrase:reframe_suggestion"
