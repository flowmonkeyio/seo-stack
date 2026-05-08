"""Daily GSC pull job — happy + budget pre-emption + missing creds skipping."""

from __future__ import annotations

import json
from collections.abc import Iterator

import httpx
import pytest
from sqlmodel import Session

from content_stack.crypto.aes_gcm import encrypt as crypto_encrypt
from content_stack.db.models import IntegrationCredential, Project
from content_stack.jobs.gsc_pull import (
    GSC_PER_CALL_COST_USD,
    daily_gsc_pull,
    make_session_factory,
)
from content_stack.repositories.projects import IntegrationBudgetRepository


def _seed_project_with_gsc(
    session: Session, *, slug: str, payload: dict[str, object] | None = None
) -> int:
    """Insert an active project + a kind='gsc' credential."""
    project = Project(
        slug=slug,
        name=slug,
        domain=f"{slug}.example.com",
        locale="en-US",
        is_active=True,
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    assert project.id is not None
    pid = project.id

    bundle = payload or {
        "access_token": "tok",
        "refresh_token": "ref",
        "expires_at": "2099-01-01T00:00:00",
    }
    encrypted, nonce = crypto_encrypt(
        json.dumps(bundle).encode("utf-8"),
        project_id=pid,
        kind="gsc",
    )
    cred = IntegrationCredential(
        project_id=pid,
        kind="gsc",
        encrypted_payload=encrypted,
        nonce=nonce,
    )
    session.add(cred)
    session.commit()
    return pid


@pytest.fixture
def mock_transport() -> Iterator[httpx.MockTransport]:
    """Stub the GSC API with two rows of fake metrics."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "rows": [
                    {
                        "keys": ["test query", "/foo", "us", "desktop"],
                        "clicks": 5,
                        "impressions": 100,
                        "ctr": 0.05,
                        "position": 4.5,
                    },
                    {
                        "keys": ["another", "/bar", "us", "mobile"],
                        "clicks": 1,
                        "impressions": 30,
                        "ctr": 0.033,
                        "position": 11.0,
                    },
                ]
            },
        )

    yield httpx.MockTransport(handler)


async def test_gsc_pull_happy_path(engine: object, mock_transport: httpx.MockTransport) -> None:
    """Active project + valid credential + mocked API → rows ingested."""
    with Session(engine) as s:  # type: ignore[arg-type]
        _seed_project_with_gsc(s, slug="happy-1")

    async with httpx.AsyncClient(transport=mock_transport) as http:
        summary = await daily_gsc_pull(
            session_factory=make_session_factory(engine),  # type: ignore[arg-type]
            http=http,
        )
    assert summary["checked"] == 1
    assert summary["ok"] == 1
    assert summary["skipped"] == 0


async def test_gsc_pull_budget_exceeded_skips_project(
    engine: object, mock_transport: httpx.MockTransport
) -> None:
    """Budget already at cap → project skipped without API call."""
    with Session(engine) as s:  # type: ignore[arg-type]
        pid = _seed_project_with_gsc(s, slug="budget-1")
        budget_repo = IntegrationBudgetRepository(s)
        budget_repo.set(
            project_id=pid,
            kind="gsc",
            monthly_budget_usd=GSC_PER_CALL_COST_USD * 0.5,  # below the per-call cost
        )

    async with httpx.AsyncClient(transport=mock_transport) as http:
        summary = await daily_gsc_pull(
            session_factory=make_session_factory(engine),  # type: ignore[arg-type]
            http=http,
        )
    assert summary["checked"] == 1
    assert summary["ok"] == 0
    assert summary["skipped"] == 1


async def test_gsc_pull_no_active_projects(
    engine: object, mock_transport: httpx.MockTransport
) -> None:
    """No active projects → 0 in every counter."""
    async with httpx.AsyncClient(transport=mock_transport) as http:
        summary = await daily_gsc_pull(
            session_factory=make_session_factory(engine),  # type: ignore[arg-type]
            http=http,
        )
    assert summary == {"checked": 0, "ok": 0, "skipped": 0}


async def test_gsc_pull_skips_project_without_credentials(
    engine: object, mock_transport: httpx.MockTransport
) -> None:
    """Active project but no GSC credential → not counted."""
    with Session(engine) as s:  # type: ignore[arg-type]
        # Just a project, no cred.
        project = Project(
            slug="no-cred",
            name="no-cred",
            domain="no-cred.example.com",
            locale="en-US",
            is_active=True,
        )
        s.add(project)
        s.commit()

    async with httpx.AsyncClient(transport=mock_transport) as http:
        summary = await daily_gsc_pull(
            session_factory=make_session_factory(engine),  # type: ignore[arg-type]
            http=http,
        )
    assert summary == {"checked": 0, "ok": 0, "skipped": 0}
