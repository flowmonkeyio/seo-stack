"""Lazy repository re-exports for the StackOS core."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, str] = {
    "AgentRequestClaimOut": "stackos.repositories.agent_requests",
    "AgentRequestOut": "stackos.repositories.agent_requests",
    "AgentRequestRepository": "stackos.repositories.agent_requests",
    "AgentSessionOut": "stackos.repositories.workspaces",
    "ArtifactOut": "stackos.repositories.resources",
    "ArtifactRepository": "stackos.repositories.resources",
    "BudgetExceededError": "stackos.repositories.base",
    "ConflictError": "stackos.repositories.base",
    "Envelope": "stackos.repositories.base",
    "IdempotencyKeyRepository": "stackos.repositories.runs",
    "IdempotencyOut": "stackos.repositories.runs",
    "IdempotencyReplayError": "stackos.repositories.base",
    "IntegrationBudgetOut": "stackos.repositories.projects",
    "IntegrationBudgetRepository": "stackos.repositories.projects",
    "IntegrationCredentialOut": "stackos.repositories.projects",
    "IntegrationCredentialRepository": "stackos.repositories.projects",
    "NotFoundError": "stackos.repositories.base",
    "Page": "stackos.repositories.base",
    "ProjectOut": "stackos.repositories.projects",
    "ProjectRepository": "stackos.repositories.projects",
    "RepositoryError": "stackos.repositories.base",
    "ResourceGetOut": "stackos.repositories.resources",
    "ResourceOut": "stackos.repositories.resources",
    "ResourceQueryOut": "stackos.repositories.resources",
    "ResourceRecordOut": "stackos.repositories.resources",
    "ResourceRepository": "stackos.repositories.resources",
    "RunOut": "stackos.repositories.runs",
    "RunRepository": "stackos.repositories.runs",
    "RunStepCallOut": "stackos.repositories.runs",
    "RunStepCallRepository": "stackos.repositories.runs",
    "RunStepOut": "stackos.repositories.runs",
    "RunStepRepository": "stackos.repositories.runs",
    "ScheduledJobOut": "stackos.repositories.projects",
    "ScheduledJobRepository": "stackos.repositories.projects",
    "ValidationError": "stackos.repositories.base",
    "WorkspaceBindingOut": "stackos.repositories.workspaces",
    "WorkspaceRepository": "stackos.repositories.workspaces",
    "WorkspaceResolutionOut": "stackos.repositories.workspaces",
    "cursor_paginate": "stackos.repositories.base",
    "validate_transition": "stackos.repositories.base",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value
