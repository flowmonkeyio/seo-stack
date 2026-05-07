"""Request-id middleware tests.

Every response carries an ``X-Request-Id`` header — fresh on outbound
requests, echoed back when the client supplied one inbound.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_response_carries_request_id(api: TestClient) -> None:
    """Outbound requests get a freshly minted UUID."""
    resp = api.get("/api/v1/health")
    rid = resp.headers.get("x-request-id")
    assert rid is not None and len(rid) >= 32


def test_request_id_echoed_back_when_inbound_provided(api: TestClient) -> None:
    """A caller-supplied id passes through verbatim."""
    fake = "abcd-1234-deadbeef"
    resp = api.get("/api/v1/health", headers={"x-request-id": fake})
    assert resp.headers["x-request-id"] == fake


def test_request_id_unique_across_requests(api: TestClient) -> None:
    """Two consecutive requests get distinct ids by default."""
    rid1 = api.get("/api/v1/health").headers["x-request-id"]
    rid2 = api.get("/api/v1/health").headers["x-request-id"]
    assert rid1 != rid2
