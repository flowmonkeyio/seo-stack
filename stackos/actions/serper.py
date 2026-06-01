"""Serper.dev action connector."""

from __future__ import annotations

import httpx

from stackos.actions.connectors import (
    ActionConnectorRequest,
    ActionConnectorResult,
    ActionValidationIssue,
)
from stackos.actions.vendor_utils import (
    credential_payload,
    int_range,
    optional_str,
    required_str,
    result,
    unknown_operation,
)
from stackos.integrations.serper import SerperIntegration


class SerperActionConnector:
    """Decision-free adapter for Serper search actions."""

    key = "serper"

    def validate(self, request: ActionConnectorRequest) -> list[ActionValidationIssue]:
        if request.operation != "search":
            return unknown_operation(request)
        issues: list[ActionValidationIssue] = []
        required_str(request.input_json, "query", issues)
        int_range(request.input_json, "num", issues, minimum=1, maximum=100)
        int_range(request.input_json, "page", issues, minimum=1, maximum=10)
        optional_str(request.input_json, "country", issues)
        optional_str(request.input_json, "language", issues)
        optional_str(request.input_json, "tbs", issues)
        return issues

    def estimate_cost_cents(self, _request: ActionConnectorRequest) -> int:
        return 0

    async def execute(self, request: ActionConnectorRequest) -> ActionConnectorResult:
        payload = request.input_json
        async with httpx.AsyncClient(timeout=30.0) as http:
            client = SerperIntegration(
                payload=credential_payload(request),
                project_id=request.project_id,
                http=http,
            )
            call_result = await client.search(
                query=str(payload["query"]),
                num=int(payload.get("num", 10)),
                country=str(payload["country"]) if payload.get("country") else None,
                language=str(payload["language"]) if payload.get("language") else None,
                page=int(payload["page"]) if payload.get("page") is not None else None,
                tbs=str(payload["tbs"]) if payload.get("tbs") else None,
            )
        return result("serper", request.operation, call_result.data, call_result.cost_usd)


__all__ = ["SerperActionConnector"]
