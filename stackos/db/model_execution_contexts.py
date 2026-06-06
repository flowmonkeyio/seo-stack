"""SQLModel declarations for provider action execution contexts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column, ForeignKey, Index, UniqueConstraint
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ExecutionContext(SQLModel, table=True):
    """Reusable provider/action execution defaults for agents.

    Execution contexts are agent-facing scoped defaults. They deliberately do
    not replace run-plan grants or generated action inventory state.
    """

    __tablename__ = "execution_contexts"
    __table_args__ = (
        UniqueConstraint("project_id", "context_ref", name="uq_execution_contexts_project_ref"),
        Index("ix_execution_contexts_project", "project_id"),
        Index("ix_execution_contexts_project_status", "project_id", "status"),
        Index("ix_execution_contexts_provider", "project_id", "provider_key"),
        Index("ix_execution_contexts_plugin", "project_id", "plugin_slug"),
    )

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(
        sa_column=Column(
            ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    context_ref: str = Field(max_length=160)
    name: str = Field(max_length=200)
    description: str = Field(default="")
    plugin_slug: str | None = Field(default=None, max_length=120)
    provider_key: str | None = Field(default=None, max_length=160)
    action_ref: str | None = Field(default=None, max_length=240)
    credential_ref: str | None = Field(default=None, max_length=120)
    credential_locked: bool = Field(default=False)
    provider_context_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    provider_context_locked_fields_json: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )
    output_policy_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    request_budget_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    artifact_namespace: str | None = Field(default=None, max_length=200)
    status: str = Field(default="active", max_length=40)
    metadata_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    created_by: str | None = Field(default=None, max_length=120)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=_utcnow, nullable=False)


class ExecutionContextLink(SQLModel, table=True):
    """Project relationship from an execution context to work state."""

    __tablename__ = "execution_context_links"
    __table_args__ = (
        UniqueConstraint(
            "context_id",
            "link_type",
            "link_ref",
            "role",
            name="uq_execution_context_links_context_ref_role",
        ),
        Index("ix_execution_context_links_project", "project_id"),
        Index("ix_execution_context_links_context", "context_id"),
        Index("ix_execution_context_links_ref", "project_id", "link_type", "link_ref"),
    )

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(
        sa_column=Column(
            ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    context_id: int = Field(
        sa_column=Column(
            ForeignKey("execution_contexts.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    link_type: str = Field(max_length=80)
    link_ref: str = Field(max_length=240)
    role: str = Field(default="default", max_length=80)
    metadata_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)


class ExecutionContextArtifact(SQLModel, table=True):
    """Association between a context and a provider action output artifact."""

    __tablename__ = "execution_context_artifacts"
    __table_args__ = (
        UniqueConstraint(
            "context_id",
            "artifact_id",
            name="uq_execution_context_artifacts_context_artifact",
        ),
        Index("ix_execution_context_artifacts_project", "project_id"),
        Index("ix_execution_context_artifacts_context", "context_id"),
        Index("ix_execution_context_artifacts_artifact", "artifact_id"),
        Index("ix_execution_context_artifacts_action_call", "action_call_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(
        sa_column=Column(
            ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    context_id: int = Field(
        sa_column=Column(
            ForeignKey("execution_contexts.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    artifact_id: int = Field(
        sa_column=Column(
            ForeignKey("artifacts.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    action_call_id: int | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("action_calls.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    semantic_name: str | None = Field(default=None, max_length=300)
    action_ref: str | None = Field(default=None, max_length=240)
    input_hash: str | None = Field(default=None, max_length=120)
    metadata_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)


__all__ = [
    "ExecutionContext",
    "ExecutionContextArtifact",
    "ExecutionContextLink",
]
