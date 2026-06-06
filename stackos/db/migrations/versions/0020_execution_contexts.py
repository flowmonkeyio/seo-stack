"""Add provider action execution contexts.

Revision ID: 0020_execution_contexts
Revises: 0019_action_call_provider_context
Create Date: 2026-06-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0020_execution_contexts"
down_revision: str | None = "0019_action_call_provider_context"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "execution_contexts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("context_ref", sa.String(length=160), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("plugin_slug", sa.String(length=120), nullable=True),
        sa.Column("provider_key", sa.String(length=160), nullable=True),
        sa.Column("action_ref", sa.String(length=240), nullable=True),
        sa.Column("credential_ref", sa.String(length=120), nullable=True),
        sa.Column("credential_locked", sa.Boolean(), nullable=False),
        sa.Column("provider_context_json", sa.JSON(), nullable=True),
        sa.Column("provider_context_locked_fields_json", sa.JSON(), nullable=True),
        sa.Column("output_policy_json", sa.JSON(), nullable=True),
        sa.Column("request_budget_json", sa.JSON(), nullable=True),
        sa.Column("artifact_namespace", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "context_ref", name="uq_execution_contexts_project_ref"),
    )
    op.create_index(
        "ix_execution_contexts_project",
        "execution_contexts",
        ["project_id"],
    )
    op.create_index(
        "ix_execution_contexts_project_status",
        "execution_contexts",
        ["project_id", "status"],
    )
    op.create_index(
        "ix_execution_contexts_provider",
        "execution_contexts",
        ["project_id", "provider_key"],
    )
    op.create_index(
        "ix_execution_contexts_plugin",
        "execution_contexts",
        ["project_id", "plugin_slug"],
    )

    op.create_table(
        "execution_context_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("context_id", sa.Integer(), nullable=False),
        sa.Column("link_type", sa.String(length=80), nullable=False),
        sa.Column("link_ref", sa.String(length=240), nullable=False),
        sa.Column("role", sa.String(length=80), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["context_id"], ["execution_contexts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "context_id",
            "link_type",
            "link_ref",
            "role",
            name="uq_execution_context_links_context_ref_role",
        ),
    )
    op.create_index(
        "ix_execution_context_links_project",
        "execution_context_links",
        ["project_id"],
    )
    op.create_index(
        "ix_execution_context_links_context",
        "execution_context_links",
        ["context_id"],
    )
    op.create_index(
        "ix_execution_context_links_ref",
        "execution_context_links",
        ["project_id", "link_type", "link_ref"],
    )

    op.create_table(
        "execution_context_artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("context_id", sa.Integer(), nullable=False),
        sa.Column("artifact_id", sa.Integer(), nullable=False),
        sa.Column("action_call_id", sa.Integer(), nullable=True),
        sa.Column("semantic_name", sa.String(length=300), nullable=True),
        sa.Column("action_ref", sa.String(length=240), nullable=True),
        sa.Column("input_hash", sa.String(length=120), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["action_call_id"], ["action_calls.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["context_id"], ["execution_contexts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "context_id",
            "artifact_id",
            name="uq_execution_context_artifacts_context_artifact",
        ),
    )
    op.create_index(
        "ix_execution_context_artifacts_project",
        "execution_context_artifacts",
        ["project_id"],
    )
    op.create_index(
        "ix_execution_context_artifacts_context",
        "execution_context_artifacts",
        ["context_id"],
    )
    op.create_index(
        "ix_execution_context_artifacts_artifact",
        "execution_context_artifacts",
        ["artifact_id"],
    )
    op.create_index(
        "ix_execution_context_artifacts_action_call",
        "execution_context_artifacts",
        ["action_call_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_execution_context_artifacts_action_call", table_name="execution_context_artifacts")
    op.drop_index("ix_execution_context_artifacts_artifact", table_name="execution_context_artifacts")
    op.drop_index("ix_execution_context_artifacts_context", table_name="execution_context_artifacts")
    op.drop_index("ix_execution_context_artifacts_project", table_name="execution_context_artifacts")
    op.drop_table("execution_context_artifacts")
    op.drop_index("ix_execution_context_links_ref", table_name="execution_context_links")
    op.drop_index("ix_execution_context_links_context", table_name="execution_context_links")
    op.drop_index("ix_execution_context_links_project", table_name="execution_context_links")
    op.drop_table("execution_context_links")
    op.drop_index("ix_execution_contexts_plugin", table_name="execution_contexts")
    op.drop_index("ix_execution_contexts_provider", table_name="execution_contexts")
    op.drop_index("ix_execution_contexts_project_status", table_name="execution_contexts")
    op.drop_index("ix_execution_contexts_project", table_name="execution_contexts")
    op.drop_table("execution_contexts")
