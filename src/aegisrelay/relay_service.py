"""Main relay orchestrator — two-transaction persistence (Gee review)."""

from __future__ import annotations

from datetime import datetime, timedelta

from aegisrelay.adapters.base import ProviderAdapter
from aegisrelay.admin.crud_service import CrudService
from aegisrelay.governance.lens_post_call import evaluate_post_call
from aegisrelay.governance.lens_pre_call import evaluate_pre_call
from aegisrelay.governance.pipeline import run_eight_stage_pipeline
from aegisrelay.models.audit_bundle import RelayAuditBundle
from aegisrelay.models.contracts import CanonicalRelayRequest, CanonicalRelayResponse


async def execute_relay(
    request: CanonicalRelayRequest,
    adapter: ProviderAdapter,
    crud: CrudService,
    provider_request_ts: datetime | None = None,
    provider_response_ts: datetime | None = None,
) -> RelayAuditBundle:
    """
    Full relay execution:

    1. Evaluate pre-call LENS hooks; persist request (status ``pending``) and those
       observations — transaction 1.
    2. Call the provider via ``adapter``.
    3. Evaluate post-call LENS hooks on the normalized provider body.
    4. Run the eight-stage governance pipeline (deterministic artifacts).
    5. Persist response, post-call + pipeline governance rows, memories, and outbox —
       transaction 2.
    6. Return the full ``RelayAuditBundle`` via ``get_relay``.
    """
    pre_observations = evaluate_pre_call(request)
    crud.create_relay(request, pre_observations)

    prov_req = provider_request_ts or request.submitted_at
    normalized = await adapter.send(request)
    prov_resp = provider_response_ts or (request.submitted_at + timedelta(seconds=1))

    post_observations = evaluate_post_call(request, normalized)

    canonical_response = CanonicalRelayResponse(
        relay_id=request.relay_id,
        provider_name=request.provider_name,
        provider_model=request.provider_model,
        response_text=normalized.body_text,
        provider_request_ts=prov_req,
        provider_response_ts=prov_resp,
        schema_version=normalized.schema_version,
        raw_provider_response=None,
    )

    artifacts = run_eight_stage_pipeline(
        request.relay_id,
        request,
        normalized,
        prov_req,
        prov_resp,
    )

    crud.finalize_relay(
        request.relay_id,
        canonical_response,
        post_observations,
        artifacts,
    )
    return crud.get_relay(request.relay_id)
