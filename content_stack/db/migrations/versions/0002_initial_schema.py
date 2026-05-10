"""initial schema — 28 tables (M1.A)

Builds on top of the empty `0001_initial_empty` head. We DROP/RECREATE in
reverse FK order on `downgrade()` so a `base → head` round-trip succeeds.

Includes the partial / hot-path indexes that SQLModel cannot express
declaratively:

- ``uq_internal_links_unique`` — partial unique excluding ``status='dismissed'``
  and treating ``position IS NULL`` as one bucket (PLAN.md L479 + audit B-09).
- ``uq_publish_targets_primary`` — partial unique enforcing at most one
  primary per project; repository code maintains at least one when rows exist
  (PLAN.md L485 + audit B-08).
- ``idx_runs_running_heartbeat`` — partial index for the daemon-restart
  orphan sweep (PLAN.md L474).

All other indexes / constraints are emitted by SQLModel's table args.

Revision ID: 0002_initial_schema
Revises: 0001_initial_empty
Create Date: 2026-05-06

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_initial_schema"
down_revision: str | None = "0001_initial_empty"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all 28 tables, indexes, and partial-unique constraints."""
    # ---- Root: projects (no FKs) -----------------------------------------
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sqlmodel.sql.sqltypes.AutoString(length=80), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
        sa.Column("domain", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("niche", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=True),
        sa.Column("locale", sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("schedule_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_slug", "projects", ["slug"], unique=True)

    # ---- Direct children of projects -------------------------------------
    op.create_table(
        "authors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
        sa.Column("slug", sqlmodel.sql.sqltypes.AutoString(length=80), nullable=False),
        sa.Column("bio_md", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("headshot_url", sqlmodel.sql.sqltypes.AutoString(length=2048), nullable=True),
        sa.Column("role", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=True),
        sa.Column("credentials_md", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("social_links_json", sa.JSON(), nullable=True),
        sa.Column("schema_person_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "slug", name="uq_authors_project_slug"),
    )
    op.create_index("ix_authors_project", "authors", ["project_id"], unique=False)

    op.create_table(
        "clusters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "pillar",
                "spoke",
                "hub",
                "comparison",
                "resource",
                name="ck_clustertype",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["clusters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clusters_project", "clusters", ["project_id"], unique=False)

    op.create_table(
        "compliance_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "responsible-gambling",
                "affiliate-disclosure",
                "jurisdiction",
                "age-gate",
                "privacy",
                "terms",
                "custom",
                name="ck_compliancerulekind",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
        sa.Column("body_md", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("jurisdictions", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column(
            "position",
            sa.Enum(
                "header",
                "after-intro",
                "footer",
                "every-section",
                "sidebar",
                "hidden-meta",
                name="ck_complianceposition",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("params_json", sa.JSON(), nullable=True),
        sa.Column("validator", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_compliance_rules_project", "compliance_rules", ["project_id"], unique=False
    )

    op.create_table(
        "eeat_criteria",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("code", sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "C",
                "O",
                "R",
                "E",
                "Exp",
                "Ept",
                "A",
                "T",
                name="ck_eeatcategory",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("text", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "tier",
            sa.Enum(
                "core",
                "recommended",
                "project",
                name="ck_eeattier",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "code", name="uq_eeat_criteria_project_code"),
    )
    op.create_index("ix_eeat_criteria_project", "eeat_criteria", ["project_id"], unique=False)

    op.create_table(
        "integration_budgets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
        sa.Column("monthly_budget_usd", sa.Float(), nullable=False),
        sa.Column("alert_threshold_pct", sa.Integer(), nullable=False),
        sa.Column("current_month_spend", sa.Float(), nullable=False),
        sa.Column("current_month_calls", sa.Integer(), nullable=False),
        sa.Column("qps", sa.Float(), nullable=False),
        sa.Column("last_reset", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "kind", name="uq_integration_budgets_project_kind"),
    )

    op.create_table(
        "integration_credentials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
        sa.Column("encrypted_payload", sa.LargeBinary(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(length=12), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_refreshed_at", sa.DateTime(), nullable=True),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "kind", name="uq_integration_credentials_project_kind"
        ),
    )
    op.create_index(
        "ix_integration_credentials_project",
        "integration_credentials",
        ["project_id"],
        unique=False,
    )

    op.create_table(
        "publish_targets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "nuxt-content",
                "wordpress",
                "ghost",
                "hugo",
                "astro",
                "custom-webhook",
                name="ck_publishtargetkind",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_publish_targets_project", "publish_targets", ["project_id"], unique=False)
    # Partial unique: exactly one is_primary=true row per project (PLAN.md L485, audit B-08).
    op.execute(
        "CREATE UNIQUE INDEX uq_publish_targets_primary "
        "ON publish_targets(project_id) WHERE is_primary = 1"
    )

    op.create_table(
        "runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column(
            "kind",
            sa.Enum(
                "procedure",
                "skill-run",
                "gsc-pull",
                "drift-check",
                "refresh-detector",
                "eeat-audit",
                "eeat-gate",
                "publish-push",
                "manual-edit",
                "crawl-error-watch",
                "humanize-pass",
                "bulk-launch",
                "interlink-suggest",
                "scheduled-job",
                "maintenance",
                name="ck_runkind",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("parent_run_id", sa.Integer(), nullable=True),
        sa.Column("procedure_slug", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=True),
        sa.Column(
            "client_session_id", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=True
        ),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "running",
                "success",
                "failed",
                "aborted",
                name="ck_runstatus",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("error", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("last_step", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=True),
        sa.Column("last_step_at", sa.DateTime(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["parent_run_id"], ["runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_runs_parent", "runs", ["parent_run_id"], unique=False)
    op.create_index(
        "idx_runs_project_started", "runs", ["project_id", "started_at"], unique=False
    )
    # Partial index used by the daemon-restart orphan sweep (PLAN.md L474).
    op.execute(
        "CREATE INDEX idx_runs_running_heartbeat "
        "ON runs(status, heartbeat_at) WHERE status = 'running'"
    )

    op.create_table(
        "scheduled_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
        sa.Column("cron_expr", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column(
            "last_run_status", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=True
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scheduled_jobs_project", "scheduled_jobs", ["project_id"], unique=False
    )

    op.create_table(
        "voice_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
        sa.Column("voice_md", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_voice_profiles_project", "voice_profiles", ["project_id"], unique=False
    )

    # ---- Children that depend on `runs` ---------------------------------
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("tool_name", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
        sa.Column(
            "idempotency_key", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False
        ),
        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column("response_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "tool_name", "idempotency_key", name="uq_idempotency"
        ),
    )

    op.create_table(
        "procedure_run_steps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("step_id", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "success",
                "failed",
                "skipped",
                name="ck_procedurerunstepstatus",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("output_json", sa.JSON(), nullable=True),
        sa.Column("error", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "step_index", name="uq_procedure_run_steps_run_step"),
    )
    op.create_index(
        "ix_procedure_run_steps_run", "procedure_run_steps", ["run_id"], unique=False
    )

    op.create_table(
        "run_steps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("skill_name", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "success",
                "failed",
                "skipped",
                name="ck_runstepstatus",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("input_snapshot_json", sa.JSON(), nullable=True),
        sa.Column("output_snapshot_json", sa.JSON(), nullable=True),
        sa.Column("error", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("cost_cents", sa.Integer(), nullable=False),
        sa.Column("integration_calls_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_run_steps_run", "run_steps", ["run_id", "step_index"], unique=False)

    op.create_table(
        "run_step_calls",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_step_id", sa.Integer(), nullable=False),
        sa.Column("mcp_tool", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
        sa.Column("request_json", sa.JSON(), nullable=True),
        sa.Column("response_json", sa.JSON(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("cost_cents", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["run_step_id"], ["run_steps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_run_step_calls_step", "run_step_calls", ["run_step_id"], unique=False
    )

    # ---- Topics depend on clusters --------------------------------------
    op.create_table(
        "topics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("cluster_id", sa.Integer(), nullable=True),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(length=300), nullable=False),
        sa.Column("primary_kw", sqlmodel.sql.sqltypes.AutoString(length=300), nullable=False),
        sa.Column("secondary_kws", sa.JSON(), nullable=True),
        sa.Column(
            "intent",
            sa.Enum(
                "informational",
                "commercial",
                "transactional",
                "navigational",
                "mixed",
                name="ck_topicintent",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "approved",
                "drafting",
                "published",
                "rejected",
                name="ck_topicstatus",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column(
            "source",
            sa.Enum(
                "manual",
                "dataforseo",
                "ahrefs",
                "reddit",
                "paa",
                "competitor-sitemap",
                "gsc-opportunity",
                "refresh-detector",
                name="ck_topicsource",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "(priority IS NULL) OR (priority BETWEEN 0 AND 100)",
            name="ck_topics_priority_range",
        ),
        sa.ForeignKeyConstraint(["cluster_id"], ["clusters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_topics_queue",
        "topics",
        ["project_id", "status", "priority", "created_at"],
        unique=False,
    )

    # ---- Articles depend on topics, authors, publish_targets, runs ------
    op.create_table(
        "articles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=True),
        sa.Column("author_id", sa.Integer(), nullable=True),
        sa.Column("reviewer_author_id", sa.Integer(), nullable=True),
        sa.Column("canonical_target_id", sa.Integer(), nullable=True),
        sa.Column("owner_run_id", sa.Integer(), nullable=True),
        sa.Column("slug", sqlmodel.sql.sqltypes.AutoString(length=80), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(length=300), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "briefing",
                "outlined",
                "drafted",
                "edited",
                "eeat_passed",
                "published",
                "refresh_due",
                "aborted-publish",
                name="ck_articlestatus",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("brief_json", sa.JSON(), nullable=True),
        sa.Column("outline_md", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("draft_md", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("edited_md", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("voice_id_used", sa.Integer(), nullable=True),
        sa.Column("eeat_criteria_version_used", sa.Integer(), nullable=True),
        sa.Column("last_refreshed_at", sa.DateTime(), nullable=True),
        sa.Column("last_evaluated_for_refresh_at", sa.DateTime(), nullable=True),
        sa.Column("last_link_audit_at", sa.DateTime(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("current_step", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=True),
        sa.Column(
            "last_completed_step",
            sqlmodel.sql.sqltypes.AutoString(length=120),
            nullable=True,
        ),
        sa.Column("step_started_at", sa.DateTime(), nullable=True),
        sa.Column("step_etag", sqlmodel.sql.sqltypes.AutoString(length=36), nullable=True),
        sa.Column("lock_token", sqlmodel.sql.sqltypes.AutoString(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["authors.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["canonical_target_id"], ["publish_targets.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["owner_run_id"], ["runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_author_id"], ["authors.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "slug", name="uq_article_slug"),
    )
    op.create_index(
        "idx_articles_canonical_target", "articles", ["canonical_target_id"], unique=False
    )
    op.create_index(
        "idx_articles_refresh_eval",
        "articles",
        ["project_id", "status", "last_evaluated_for_refresh_at"],
        unique=False,
    )
    op.create_index(
        "idx_articles_status_project", "articles", ["project_id", "status"], unique=False
    )

    # ---- Children of articles -------------------------------------------
    op.create_table(
        "article_assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "hero",
                "inline",
                "thumbnail",
                "og",
                "twitter",
                "infographic",
                "screenshot",
                "gallery",
                name="ck_articleassetkind",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("prompt", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("url", sqlmodel.sql.sqltypes.AutoString(length=2048), nullable=False),
        sa.Column("alt_text", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_article_assets_article", "article_assets", ["article_id"], unique=False
    )

    op.create_table(
        "article_publishes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("version_published", sa.Integer(), nullable=False),
        sa.Column("published_url", sqlmodel.sql.sqltypes.AutoString(length=2048), nullable=True),
        sa.Column("frontmatter_json", sa.JSON(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "published",
                "failed",
                "reverted",
                name="ck_articlepublishstatus",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("error", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["publish_targets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "article_id", "target_id", "version_published", name="uq_article_publishes_pk"
        ),
    )
    op.create_index(
        "ix_article_publishes_article", "article_publishes", ["article_id"], unique=False
    )

    op.create_table(
        "article_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("brief_json", sa.JSON(), nullable=True),
        sa.Column("outline_md", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("draft_md", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("edited_md", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("frontmatter_json", sa.JSON(), nullable=True),
        sa.Column("published_url", sqlmodel.sql.sqltypes.AutoString(length=2048), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("voice_id_used", sa.Integer(), nullable=True),
        sa.Column("eeat_criteria_version_used", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("refreshed_at", sa.DateTime(), nullable=True),
        sa.Column("refresh_reason", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=True),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "article_id", "version", name="uq_article_versions_article_version"
        ),
    )
    op.create_index(
        "ix_article_versions_article", "article_versions", ["article_id"], unique=False
    )

    op.create_table(
        "drift_baselines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("baseline_md", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("baseline_at", sa.DateTime(), nullable=False),
        sa.Column("current_score", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_drift_baselines_article", "drift_baselines", ["article_id"], unique=False
    )

    op.create_table(
        "eeat_evaluations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("criterion_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column(
            "verdict",
            sa.Enum(
                "pass",
                "partial",
                "fail",
                name="ck_eeatverdict",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["criterion_id"], ["eeat_criteria.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_eeat_evals_article", "eeat_evaluations", ["article_id", "run_id"], unique=False
    )

    op.create_table(
        "gsc_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("query", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column(
            "query_normalized", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True
        ),
        sa.Column("page", sqlmodel.sql.sqltypes.AutoString(length=2048), nullable=True),
        sa.Column("country", sqlmodel.sql.sqltypes.AutoString(length=8), nullable=True),
        sa.Column("device", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=True),
        sa.Column("dimensions_hash", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("impressions", sa.Integer(), nullable=False),
        sa.Column("clicks", sa.Integer(), nullable=False),
        sa.Column("ctr", sa.Float(), nullable=False),
        sa.Column("avg_position", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "article_id",
            "captured_at",
            "dimensions_hash",
            name="uq_gsc_metrics_dedup",
        ),
    )
    op.create_index(
        "idx_gsc_metrics_article_time",
        "gsc_metrics",
        ["article_id", "captured_at"],
        unique=False,
    )

    op.create_table(
        "gsc_metrics_daily",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=True),
        sa.Column("day", sa.DateTime(), nullable=False),
        sa.Column("impressions_sum", sa.Integer(), nullable=False),
        sa.Column("clicks_sum", sa.Integer(), nullable=False),
        sa.Column("ctr_avg", sa.Float(), nullable=False),
        sa.Column("avg_position_avg", sa.Float(), nullable=False),
        sa.Column("queries_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "article_id", "day", name="uq_gsc_metrics_daily"),
    )
    op.create_index(
        "idx_gsc_metrics_daily_lookup",
        "gsc_metrics_daily",
        ["project_id", "article_id", "day"],
        unique=False,
    )

    op.create_table(
        "internal_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("from_article_id", sa.Integer(), nullable=False),
        sa.Column("to_article_id", sa.Integer(), nullable=False),
        sa.Column("anchor_text", sqlmodel.sql.sqltypes.AutoString(length=300), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "suggested",
                "applied",
                "dismissed",
                "broken",
                name="ck_internallinkstatus",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["from_article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_internal_links_from", "internal_links", ["from_article_id"], unique=False
    )
    op.create_index(
        "idx_internal_links_to", "internal_links", ["to_article_id"], unique=False
    )
    op.create_index(
        "ix_internal_links_project", "internal_links", ["project_id"], unique=False
    )
    # Partial unique excluding dismissed (PLAN.md L479, audit B-09).
    op.execute(
        "CREATE UNIQUE INDEX uq_internal_links_unique "
        "ON internal_links(from_article_id, to_article_id, anchor_text, COALESCE(position, -1)) "
        "WHERE status != 'dismissed'"
    )

    op.create_table(
        "redirects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("from_url", sqlmodel.sql.sqltypes.AutoString(length=2048), nullable=False),
        sa.Column("to_article_id", sa.Integer(), nullable=True),
        sa.Column(
            "kind",
            sa.Enum(
                "301",
                "302",
                name="ck_redirectkind",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_article_id"], ["articles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_redirects_project", "redirects", ["project_id"], unique=False)

    op.create_table(
        "research_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("url", sqlmodel.sql.sqltypes.AutoString(length=2048), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column("snippet", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_research_sources_article", "research_sources", ["article_id"], unique=False
    )

    op.create_table(
        "schema_emits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=True),
        sa.Column("type", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
        sa.Column("schema_json", sa.JSON(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("version_published", sa.Integer(), nullable=True),
        sa.Column("validated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_schema_emits_article", "schema_emits", ["article_id"], unique=False)

    # ---- Seed data --------------------------------------------------------
    # Schema-emit *templates* are project-id-NULL, article-id-NULL global rows
    # that the per-project seed clones at project-creation time. EEAT criteria
    # are seeded per-project (see content_stack.db.seed.seed_eeat_criteria).
    # We import lazily to avoid pulling SQLModel into the migration import path.
    from content_stack.db.seed import seed_schema_emits_templates_via_op

    seed_schema_emits_templates_via_op()


def downgrade() -> None:
    """Drop everything in reverse FK order."""
    # Children of articles
    op.drop_index("ix_schema_emits_article", table_name="schema_emits")
    op.drop_table("schema_emits")
    op.drop_index("ix_research_sources_article", table_name="research_sources")
    op.drop_table("research_sources")
    op.drop_index("ix_redirects_project", table_name="redirects")
    op.drop_table("redirects")
    op.execute("DROP INDEX IF EXISTS uq_internal_links_unique")
    op.drop_index("ix_internal_links_project", table_name="internal_links")
    op.drop_index("idx_internal_links_to", table_name="internal_links")
    op.drop_index("idx_internal_links_from", table_name="internal_links")
    op.drop_table("internal_links")
    op.drop_index("idx_gsc_metrics_daily_lookup", table_name="gsc_metrics_daily")
    op.drop_table("gsc_metrics_daily")
    op.drop_index("idx_gsc_metrics_article_time", table_name="gsc_metrics")
    op.drop_table("gsc_metrics")
    op.drop_index("idx_eeat_evals_article", table_name="eeat_evaluations")
    op.drop_table("eeat_evaluations")
    op.drop_index("ix_drift_baselines_article", table_name="drift_baselines")
    op.drop_table("drift_baselines")
    op.drop_index("ix_article_versions_article", table_name="article_versions")
    op.drop_table("article_versions")
    op.drop_index("ix_article_publishes_article", table_name="article_publishes")
    op.drop_table("article_publishes")
    op.drop_index("ix_article_assets_article", table_name="article_assets")
    op.drop_table("article_assets")

    # Articles itself
    op.drop_index("idx_articles_status_project", table_name="articles")
    op.drop_index("idx_articles_refresh_eval", table_name="articles")
    op.drop_index("idx_articles_canonical_target", table_name="articles")
    op.drop_table("articles")

    # Topics + clusters
    op.drop_index("idx_topics_queue", table_name="topics")
    op.drop_table("topics")

    # Run-scoped tables
    op.drop_index("idx_run_step_calls_step", table_name="run_step_calls")
    op.drop_table("run_step_calls")
    op.drop_index("idx_run_steps_run", table_name="run_steps")
    op.drop_table("run_steps")
    op.drop_index("ix_procedure_run_steps_run", table_name="procedure_run_steps")
    op.drop_table("procedure_run_steps")
    op.drop_table("idempotency_keys")

    # Project-direct children
    op.drop_index("ix_voice_profiles_project", table_name="voice_profiles")
    op.drop_table("voice_profiles")
    op.drop_index("ix_scheduled_jobs_project", table_name="scheduled_jobs")
    op.drop_table("scheduled_jobs")
    op.execute("DROP INDEX IF EXISTS idx_runs_running_heartbeat")
    op.drop_index("idx_runs_project_started", table_name="runs")
    op.drop_index("idx_runs_parent", table_name="runs")
    op.drop_table("runs")
    op.execute("DROP INDEX IF EXISTS uq_publish_targets_primary")
    op.drop_index("ix_publish_targets_project", table_name="publish_targets")
    op.drop_table("publish_targets")
    op.drop_index("ix_integration_credentials_project", table_name="integration_credentials")
    op.drop_table("integration_credentials")
    op.drop_table("integration_budgets")
    op.drop_index("ix_eeat_criteria_project", table_name="eeat_criteria")
    op.drop_table("eeat_criteria")
    op.drop_index("ix_compliance_rules_project", table_name="compliance_rules")
    op.drop_table("compliance_rules")
    op.drop_index("ix_clusters_project", table_name="clusters")
    op.drop_table("clusters")
    op.drop_index("ix_authors_project", table_name="authors")
    op.drop_table("authors")

    # Root
    op.drop_index("ix_projects_slug", table_name="projects")
    op.drop_table("projects")
