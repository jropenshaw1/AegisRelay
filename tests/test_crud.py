"""CRUD service — create, get, list."""

from __future__ import annotations

from datetime import datetime, timezone

from aegisrelay.admin.crud_service import CrudService, lens_observation_to_governance_event
from aegisrelay.governance.lens_pre_call import evaluate_pre_call
from aegisrelay.models.contracts import CanonicalRelayRequest


def test_create_and_get_relay(crud: CrudService) -> None:
    req = CanonicalRelayRequest(
        relay_id="crud-1",
        input_text="Hello CRUD",
        operation="read",
        human_actor_id="u1",
        provider_name="stub",
        provider_model="v0",
        submitted_at=datetime(2026, 4, 11, 8, 0, tzinfo=timezone.utc),
    )
    pre = evaluate_pre_call(req)
    rid = crud.create_relay(req, pre)
    assert rid == "crud-1"
    bundle = crud.get_relay(rid)
    assert bundle.request.input_text == "Hello CRUD"
    assert bundle.response is None
    lens_pre = [e for e in bundle.governance_events if e.stage == "pre_call"]
    assert len(lens_pre) == len(pre)


def test_lens_observation_to_governance_event_stable_id() -> None:
    req = CanonicalRelayRequest(relay_id="x", input_text="a")
    obs_list = evaluate_pre_call(req)
    if not obs_list:
        from aegisrelay.models.lens import LensObservation

        from aegisrelay.governance import LENS_VERSION

        obs_list = [
            LensObservation(
                behavior="decision_checkpoints",
                trigger_fired=True,
                confidence=0.5,
                observation="test",
                hook="pre_call",
                lens_version=LENS_VERSION,
            )
        ]
    ge = lens_observation_to_governance_event("x", obs_list[0], "0", req.submitted_at)
    ge2 = lens_observation_to_governance_event("x", obs_list[0], "0", req.submitted_at)
    assert ge.event_id == ge2.event_id


def test_list_relays_filter(crud: CrudService) -> None:
    req = CanonicalRelayRequest(
        relay_id="list-1",
        input_text="L",
        operation="read",
        submitted_at=datetime(2026, 4, 11, 9, 0, tzinfo=timezone.utc),
    )
    crud.create_relay(req, [])
    rows = crud.list_relays(limit=10, offset=0, filters={"status": "pending"})
    assert any(r.relay_id == "list-1" for r in rows)
