"""StackOS generic auth provider REST routes."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query, status
from pydantic import BaseModel, ConfigDict
from sqlmodel import Session

from content_stack.api.deps import get_session, get_settings
from content_stack.api.envelopes import WriteResponse, write_response
from content_stack.auth_providers import (
    AuthProviderOut,
    AuthRepository,
    AuthRevokeOut,
    AuthStartOut,
    AuthStatusOut,
    AuthTestOut,
)
from content_stack.config import Settings

router = APIRouter(prefix="/api/v1", tags=["auth-providers"])


class AuthStartRequest(BaseModel):
    """Local-admin setup request. It never carries a secret."""

    model_config = ConfigDict(json_schema_extra={"example": {"redirect_uri": None}})

    redirect_uri: str | None = None


class AuthTestRequest(BaseModel):
    """Sanitized auth test request using an opaque ref or provider key."""

    model_config = ConfigDict(json_schema_extra={"example": {"provider_key": "firecrawl"}})

    credential_ref: str | None = None
    provider_key: str | None = None


class AuthRevokeRequest(BaseModel):
    """Local-admin revoke request using an opaque ref or provider key."""

    model_config = ConfigDict(json_schema_extra={"example": {"credential_ref": "cred_..."}})

    credential_ref: str | None = None
    provider_key: str | None = None


@router.get("/auth/providers", response_model=list[AuthProviderOut])
async def list_auth_providers(
    provider_key: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[AuthProviderOut]:
    """List provider auth metadata synced from StackOS plugin manifests."""
    return AuthRepository(session).list_providers(provider_key=provider_key)


@router.get("/projects/{project_id}/auth/status", response_model=AuthStatusOut)
async def auth_status(
    project_id: int,
    provider_key: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> AuthStatusOut:
    """Return sanitized auth status and opaque credential references."""
    return AuthRepository(session).status(project_id=project_id, provider_key=provider_key)


@router.post(
    "/projects/{project_id}/auth/{provider_key}/start",
    response_model=WriteResponse[AuthStartOut],
    status_code=status.HTTP_200_OK,
)
async def auth_start(
    project_id: int,
    provider_key: str,
    body: AuthStartRequest | None = Body(default=None),
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> WriteResponse[AuthStartOut]:
    """Start a local-human setup flow without accepting or returning secrets."""
    return write_response(
        AuthRepository(session).start(
            project_id=project_id,
            provider_key=provider_key,
            settings=settings,
            redirect_uri=body.redirect_uri if body is not None else None,
        )
    )


@router.post(
    "/projects/{project_id}/auth/test",
    response_model=WriteResponse[AuthTestOut],
)
async def auth_test(
    project_id: int,
    body: AuthTestRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[AuthTestOut]:
    """Run a sanitized provider credential test without returning secrets."""
    return write_response(
        await AuthRepository(session).test(
            project_id=project_id,
            credential_ref=body.credential_ref,
            provider_key=body.provider_key,
        )
    )


@router.post(
    "/projects/{project_id}/auth/revoke",
    response_model=WriteResponse[AuthRevokeOut],
)
async def auth_revoke(
    project_id: int,
    body: AuthRevokeRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[AuthRevokeOut]:
    """Revoke a provider credential through the local-admin REST surface."""
    return write_response(
        AuthRepository(session).revoke(
            project_id=project_id,
            credential_ref=body.credential_ref,
            provider_key=body.provider_key,
        )
    )


__all__ = ["router"]
