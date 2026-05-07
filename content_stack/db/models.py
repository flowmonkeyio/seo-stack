"""SQLModel declarations for the 28 content-stack tables.

Single-file layout per PLAN.md L137 / L202. Each table maps 1:1 to a
section in PLAN.md "Database schema (28 tables — full scope)". Status
enums are declared next to the table they serialise to; column-level
docstrings explain non-obvious *why* (per CLAUDE.md style guidance).

Persistence rules:

- Enums are stored as TEXT (`native_enum=False` so SQLite gets the
  string verbatim, not a numeric ordinal). The `values_callable`
  hook ensures we ship the canonical hyphenated PLAN.md spelling
  (e.g. ``aborted-publish``) and not the Python identifier.
- Foreign keys are declared at the SQLModel `Field(foreign_key=...)`
  level so SQLModel/SQLAlchemy emit them; ON DELETE behaviour is
  attached via an explicit `sa.Column(ForeignKey(..., ondelete=...))`
  where it differs from the default RESTRICT.
- Composite / partial / unique indexes that SQLModel cannot express
  declaratively (notably the partial-unique constraints from PLAN.md
  L479 / L485 + audit B-08 / B-09 / M-20) are issued by the M1
  initial-schema Alembic migration. They are *also* declared here in
  the per-table ``__table_args__`` for the indexes that SQLAlchemy
  *can* express, so introspection of `SQLModel.metadata` matches the
  on-disk database after an autogenerate diff.

State-machine invariants are enforced in the M1.B repository layer.
This module exports `ARTICLE_STATUS_TRANSITIONS` so tests can defend
the legal-transition map without duplicating it.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    LargeBinary,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel

# ---------------------------------------------------------------------------
# Enum helper
# ---------------------------------------------------------------------------


def _enum_column(
    enum_cls: type[enum.Enum],
    *,
    nullable: bool = False,
    name: str | None = None,
) -> Column[Any]:
    """Build a portable TEXT-backed Enum column.

    SQLite has no native ENUM type; using ``native_enum=False`` forces a
    CHECK-constrained TEXT column, which matches PLAN.md L383
    ("string columns, validated by pydantic"). ``values_callable``
    returns the canonical hyphenated value string (PLAN.md spellings
    like ``aborted-publish`` cannot be Python identifiers, so we keep
    the Python member ``ABORTED_PUBLISH`` while persisting the value).
    """
    return Column(
        SAEnum(
            enum_cls,
            native_enum=False,
            length=64,
            values_callable=lambda cls: [m.value for m in cls],
            name=name or f"ck_{enum_cls.__name__.lower()}",
        ),
        nullable=nullable,
    )


def _utcnow() -> datetime:
    """Naive UTC default for ``created_at`` / ``updated_at`` columns.

    SQLite stores datetimes as ISO-8601 text; we keep the value naive but
    explicitly UTC for consistency. Tests rely on a callable default so
    rows inserted in the same transaction don't share a frozen timestamp.
    """
    return datetime.now(tz=UTC).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Enums (one block per table, ordered alphabetically by table name)
# ---------------------------------------------------------------------------


class ArticleAssetKind(enum.StrEnum):
    """Persists to ``article_assets.kind`` per PLAN.md L396."""

    HERO = "hero"
    INLINE = "inline"
    THUMBNAIL = "thumbnail"
    OG = "og"
    TWITTER = "twitter"
    INFOGRAPHIC = "infographic"
    SCREENSHOT = "screenshot"
    GALLERY = "gallery"


class ArticlePublishStatus(enum.StrEnum):
    """Persists to ``article_publishes.status`` per PLAN.md L397."""

    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"
    REVERTED = "reverted"


class ArticleStatus(enum.StrEnum):
    """Persists to ``articles.status`` per PLAN.md L388.

    Note ``aborted-publish`` (hyphen) is the canonical wire spelling —
    the Python member name is ``ABORTED_PUBLISH``.
    """

    BRIEFING = "briefing"
    OUTLINED = "outlined"
    DRAFTED = "drafted"
    EDITED = "edited"
    EEAT_PASSED = "eeat_passed"
    PUBLISHED = "published"
    REFRESH_DUE = "refresh_due"
    ABORTED_PUBLISH = "aborted-publish"


# Legal transitions used by the repository layer (M1.B). Defined here so
# unit tests can lock the map down without duplicating it.
ARTICLE_STATUS_TRANSITIONS: dict[ArticleStatus, frozenset[ArticleStatus]] = {
    ArticleStatus.BRIEFING: frozenset({ArticleStatus.OUTLINED, ArticleStatus.ABORTED_PUBLISH}),
    ArticleStatus.OUTLINED: frozenset({ArticleStatus.DRAFTED, ArticleStatus.ABORTED_PUBLISH}),
    ArticleStatus.DRAFTED: frozenset({ArticleStatus.EDITED, ArticleStatus.ABORTED_PUBLISH}),
    ArticleStatus.EDITED: frozenset(
        {
            ArticleStatus.EEAT_PASSED,
            ArticleStatus.DRAFTED,  # editor → re-draft loop on FIX verdict
            ArticleStatus.ABORTED_PUBLISH,
        }
    ),
    ArticleStatus.EEAT_PASSED: frozenset(
        {ArticleStatus.PUBLISHED, ArticleStatus.EDITED, ArticleStatus.ABORTED_PUBLISH}
    ),
    ArticleStatus.PUBLISHED: frozenset({ArticleStatus.REFRESH_DUE}),
    ArticleStatus.REFRESH_DUE: frozenset({ArticleStatus.EDITED, ArticleStatus.PUBLISHED}),
    ArticleStatus.ABORTED_PUBLISH: frozenset(),  # terminal
}


class ClusterType(enum.StrEnum):
    """Persists to ``clusters.type`` per PLAN.md L395."""

    PILLAR = "pillar"
    SPOKE = "spoke"
    HUB = "hub"
    COMPARISON = "comparison"
    RESOURCE = "resource"


class ComplianceRuleKind(enum.StrEnum):
    """Persists to ``compliance_rules.kind`` per PLAN.md L393."""

    RESPONSIBLE_GAMBLING = "responsible-gambling"
    AFFILIATE_DISCLOSURE = "affiliate-disclosure"
    JURISDICTION = "jurisdiction"
    AGE_GATE = "age-gate"
    PRIVACY = "privacy"
    TERMS = "terms"
    CUSTOM = "custom"


class CompliancePosition(enum.StrEnum):
    """Persists to ``compliance_rules.position`` per PLAN.md L394."""

    HEADER = "header"
    AFTER_INTRO = "after-intro"
    FOOTER = "footer"
    EVERY_SECTION = "every-section"
    SIDEBAR = "sidebar"
    HIDDEN_META = "hidden-meta"


class EeatCategory(enum.StrEnum):
    """Persists to ``eeat_criteria.category``.

    PLAN.md L351 narrates "E/E/A/T" but L444 enumerates the rubric using
    8 dimensions ``C, O, R, E, Exp, Ept, A, T`` and the canonical 80-item
    benchmark (`.upstream/seo-geo-claude-skills/references/core-eeat-benchmark.md`)
    is structured as 8 x 10. We persist all 8 - the EEAT gate ("refuses
    to score if any dimension has 0 active items", PLAN.md L1620) cannot
    work with the collapsed 4-letter taxonomy. Surfaced as a deliberate
    tightening of the schema in the M1 implementation report.
    """

    C = "C"  # Contextual Clarity
    O = "O"  # Organization  # noqa: E741 — single-letter dimension code
    R = "R"  # Referenceability
    E = "E"  # Exclusivity
    EXP = "Exp"  # Experience
    EPT = "Ept"  # Expertise
    A = "A"  # Authority
    T = "T"  # Trust


class EeatTier(enum.StrEnum):
    """Persists to ``eeat_criteria.tier`` per PLAN.md L402 (D7 lock)."""

    CORE = "core"
    RECOMMENDED = "recommended"
    PROJECT = "project"


class EeatVerdict(enum.StrEnum):
    """Persists to ``eeat_evaluations.verdict`` per PLAN.md L401."""

    PASS = "pass"
    PARTIAL = "partial"
    FAIL = "fail"


class InternalLinkStatus(enum.StrEnum):
    """Persists to ``internal_links.status`` per PLAN.md L392."""

    SUGGESTED = "suggested"
    APPLIED = "applied"
    DISMISSED = "dismissed"
    BROKEN = "broken"


class ProcedureRunStepStatus(enum.StrEnum):
    """Persists to ``procedure_run_steps.status`` per PLAN.md L399."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class PublishTargetKind(enum.StrEnum):
    """Persists to ``publish_targets.kind`` per PLAN.md L398."""

    NUXT_CONTENT = "nuxt-content"
    WORDPRESS = "wordpress"
    GHOST = "ghost"
    HUGO = "hugo"
    ASTRO = "astro"
    CUSTOM_WEBHOOK = "custom-webhook"


class RedirectKind(enum.StrEnum):
    """Persists to ``redirects.kind`` per PLAN.md L404."""

    R301 = "301"
    R302 = "302"


class RunKind(enum.StrEnum):
    """Persists to ``runs.kind`` per PLAN.md L391 (16 values)."""

    PROCEDURE = "procedure"
    SKILL_RUN = "skill-run"
    GSC_PULL = "gsc-pull"
    DRIFT_CHECK = "drift-check"
    REFRESH_DETECTOR = "refresh-detector"
    EEAT_AUDIT = "eeat-audit"
    EEAT_GATE = "eeat-gate"
    PUBLISH_PUSH = "publish-push"
    MANUAL_EDIT = "manual-edit"
    CRAWL_ERROR_WATCH = "crawl-error-watch"
    HUMANIZE_PASS = "humanize-pass"
    BULK_LAUNCH = "bulk-launch"
    INTERLINK_SUGGEST = "interlink-suggest"
    SCHEDULED_JOB = "scheduled-job"
    MAINTENANCE = "maintenance"
    ADVERSARIAL_REVIEW = "adversarial-review"


class RunStatus(enum.StrEnum):
    """Persists to ``runs.status`` per PLAN.md L390."""

    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ABORTED = "aborted"


class RunStepStatus(enum.StrEnum):
    """Persists to ``run_steps.status`` per PLAN.md L400."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class TopicIntent(enum.StrEnum):
    """Persists to ``topics.intent`` per PLAN.md L387."""

    INFORMATIONAL = "informational"
    COMMERCIAL = "commercial"
    TRANSACTIONAL = "transactional"
    NAVIGATIONAL = "navigational"
    MIXED = "mixed"


class TopicSource(enum.StrEnum):
    """Persists to ``topics.source`` per PLAN.md L386."""

    MANUAL = "manual"
    DATAFORSEO = "dataforseo"
    AHREFS = "ahrefs"
    REDDIT = "reddit"
    PAA = "paa"
    COMPETITOR_SITEMAP = "competitor-sitemap"
    GSC_OPPORTUNITY = "gsc-opportunity"
    REFRESH_DETECTOR = "refresh-detector"


class TopicStatus(enum.StrEnum):
    """Persists to ``topics.status`` per PLAN.md L385."""

    QUEUED = "queued"
    APPROVED = "approved"
    DRAFTING = "drafting"
    PUBLISHED = "published"
    REJECTED = "rejected"


# ---------------------------------------------------------------------------
# Tables — order chosen so referenced parents are declared before children.
# ---------------------------------------------------------------------------


class Project(SQLModel, table=True):
    """Site registrations (PLAN.md L347).

    ``slug`` is globally unique (no ``project_id`` prefix). ``locale`` is
    singular per D3; multi-locale = separate row.
    """

    __tablename__ = "projects"

    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(max_length=80, unique=True, index=True)
    name: str = Field(max_length=200)
    domain: str = Field(max_length=255)
    niche: str | None = Field(default=None, max_length=200)
    locale: str = Field(max_length=16)
    is_active: bool = Field(default=False)
    schedule_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=_utcnow, nullable=False)


class VoiceProfile(SQLModel, table=True):
    """Voice/tone variant per project (PLAN.md L348).

    The articles snapshot ``voice_id`` at brief time and copy the resolved
    text into ``articles.brief_json``; later edits to the row do not
    retroactively rewrite drafts.
    """

    __tablename__ = "voice_profiles"
    __table_args__ = (Index("ix_voice_profiles_project", "project_id"),)

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(
        sa_column=Column(
            ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    name: str = Field(max_length=120)
    voice_md: str = Field(default="")
    is_default: bool = Field(default=False)
    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)


class Author(SQLModel, table=True):
    """Per-article author attribution (PLAN.md L349).

    Required for E-E-A-T `Experience`/`Expertise` dimensions. Self-describing
    JSON columns drive ``schema.org/Person`` JSON-LD emission.
    """

    __tablename__ = "authors"
    __table_args__ = (
        UniqueConstraint("project_id", "slug", name="uq_authors_project_slug"),
        Index("ix_authors_project", "project_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(
        sa_column=Column(
            ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    name: str = Field(max_length=200)
    slug: str = Field(max_length=80)
    bio_md: str | None = Field(default=None)
    headshot_url: str | None = Field(default=None, max_length=2048)
    role: str | None = Field(default=None, max_length=120)
    credentials_md: str | None = Field(default=None)
    social_links_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    schema_person_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=_utcnow, nullable=False)


class ComplianceRule(SQLModel, table=True):
    """RG / affiliate / jurisdiction / age-gate rules (PLAN.md L350).

    ``params_json`` carries structured fields for built-in kinds; ``validator``
    names a registered Python callable (built-ins for predefined kinds; required
    for ``custom``).
    """

    __tablename__ = "compliance_rules"
    __table_args__ = (Index("ix_compliance_rules_project", "project_id"),)

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(
        sa_column=Column(
            ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    kind: ComplianceRuleKind = Field(sa_column=_enum_column(ComplianceRuleKind))
    title: str = Field(max_length=200)
    body_md: str = Field(default="")
    jurisdictions: str | None = Field(default=None, max_length=500)
    position: CompliancePosition = Field(sa_column=_enum_column(CompliancePosition))
    params_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    validator: str | None = Field(default=None, max_length=120)
    is_active: bool = Field(default=True)


class EeatCriterion(SQLModel, table=True):
    """Per-project quality gate items (PLAN.md L351, D7 lock).

    Rows with ``tier=core`` are non-deactivatable / non-non-required (repository
    invariant + 422). T04, C01, R10 are seeded as ``tier='core'``.
    """

    __tablename__ = "eeat_criteria"
    __table_args__ = (
        UniqueConstraint("project_id", "code", name="uq_eeat_criteria_project_code"),
        Index("ix_eeat_criteria_project", "project_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(
        sa_column=Column(
            ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    code: str = Field(max_length=16)
    category: EeatCategory = Field(sa_column=_enum_column(EeatCategory))
    description: str = Field(default="")
    text: str = Field(default="")
    weight: int = Field(default=10)
    required: bool = Field(default=False)
    active: bool = Field(default=True)
    tier: EeatTier = Field(sa_column=_enum_column(EeatTier))
    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)


class Cluster(SQLModel, table=True):
    """Topical map (PLAN.md L352).

    Self-referential ``parent_id`` permits arbitrary nesting (pillar→hub→spoke).
    """

    __tablename__ = "clusters"
    __table_args__ = (Index("ix_clusters_project", "project_id"),)

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(
        sa_column=Column(
            ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    name: str = Field(max_length=200)
    type: ClusterType = Field(sa_column=_enum_column(ClusterType))
    parent_id: int | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("clusters.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)


class Topic(SQLModel, table=True):
    """Topic queue with provenance (PLAN.md L353).

    ``priority`` 0-100 (NULL=50, higher=sooner); tiebreaker
    ``(priority DESC, created_at ASC, id ASC)`` is enforced by
    ``idx_topics_queue`` (PLAN.md L471).
    """

    __tablename__ = "topics"
    __table_args__ = (
        # Hot-path queue index per PLAN.md L471; the trailing ASC on
        # created_at is the SQLite default.
        Index(
            "idx_topics_queue",
            "project_id",
            "status",
            "priority",
            "created_at",
        ),
        CheckConstraint(
            "(priority IS NULL) OR (priority BETWEEN 0 AND 100)",
            name="ck_topics_priority_range",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(
        sa_column=Column(
            ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    cluster_id: int | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("clusters.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    title: str = Field(max_length=300)
    primary_kw: str = Field(default="", max_length=300)
    secondary_kws: list[str] | None = Field(default=None, sa_column=Column(JSON))
    intent: TopicIntent = Field(sa_column=_enum_column(TopicIntent))
    status: TopicStatus = Field(sa_column=_enum_column(TopicStatus))
    priority: int | None = Field(default=None)
    source: TopicSource = Field(sa_column=_enum_column(TopicSource))
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=_utcnow, nullable=False)


class PublishTarget(SQLModel, table=True):
    """Per-project publish destinations (PLAN.md L366).

    ``is_primary`` exactly-one-per-project is enforced by partial unique
    index ``uq_publish_targets_primary`` (PLAN.md L485 + audit B-08), emitted
    in the M1 migration.
    """

    __tablename__ = "publish_targets"
    __table_args__ = (Index("ix_publish_targets_project", "project_id"),)

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(
        sa_column=Column(
            ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    kind: PublishTargetKind = Field(sa_column=_enum_column(PublishTargetKind))
    config_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    is_primary: bool = Field(default=False)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)


class Run(SQLModel, table=True):
    """Top-level pipeline audit (PLAN.md L374).

    ``parent_run_id`` enables ``run.children`` / cascade abort; ``heartbeat_at``
    is the daemon-restart-orphan signal.
    """

    __tablename__ = "runs"
    __table_args__ = (
        # Primary look-ups per PLAN.md L472-L474.
        Index("idx_runs_project_started", "project_id", "started_at"),
        Index("idx_runs_parent", "parent_run_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    project_id: int | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    kind: RunKind = Field(sa_column=_enum_column(RunKind))
    parent_run_id: int | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    procedure_slug: str | None = Field(default=None, max_length=120)
    client_session_id: str | None = Field(default=None, max_length=120)
    started_at: datetime = Field(default_factory=_utcnow, nullable=False)
    ended_at: datetime | None = Field(default=None)
    status: RunStatus = Field(sa_column=_enum_column(RunStatus))
    error: str | None = Field(default=None)
    heartbeat_at: datetime | None = Field(default=None)
    last_step: str | None = Field(default=None, max_length=120)
    last_step_at: datetime | None = Field(default=None)
    metadata_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))


class Article(SQLModel, table=True):
    """Content lifecycle row, current version only (PLAN.md L354, D6).

    ``slug`` is unique per project (``uq_article_slug``, PLAN.md L484) and
    immutable post-publish (M1.B repository invariant; documented here per
    PLAN.md L354 "CHECK + repository invariant"; we keep it as a repository
    invariant only because SQLite CHECK can't reference the row's own
    *prior* state without a trigger, which we add in M1.B alongside the
    state-machine guard).

    Publish gate: ``status='published'`` requires ``eeat_criteria_version_used
    IS NOT NULL`` AND a successful ``eeat-gate`` run with verdict ``SHIP``.
    Enforced in repository layer at M1.B.
    """

    __tablename__ = "articles"
    __table_args__ = (
        # Per PLAN.md L468 / L470. ``uq_article_slug`` ships in the migration
        # because SQLModel can't express the partial-immutable invariant.
        UniqueConstraint("project_id", "slug", name="uq_article_slug"),
        Index("idx_articles_status_project", "project_id", "status"),
        Index(
            "idx_articles_refresh_eval",
            "project_id",
            "status",
            "last_evaluated_for_refresh_at",
        ),
        Index("idx_articles_canonical_target", "canonical_target_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(
        sa_column=Column(
            ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    topic_id: int | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("topics.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    author_id: int | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("authors.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    reviewer_author_id: int | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("authors.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    canonical_target_id: int | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("publish_targets.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    owner_run_id: int | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    slug: str = Field(max_length=80)
    title: str = Field(max_length=300)
    status: ArticleStatus = Field(sa_column=_enum_column(ArticleStatus))
    brief_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    outline_md: str | None = Field(default=None)
    draft_md: str | None = Field(default=None)
    edited_md: str | None = Field(default=None)
    voice_id_used: int | None = Field(default=None)
    eeat_criteria_version_used: int | None = Field(default=None)
    last_refreshed_at: datetime | None = Field(default=None)
    last_evaluated_for_refresh_at: datetime | None = Field(default=None)
    last_link_audit_at: datetime | None = Field(default=None)
    version: int = Field(default=1)
    current_step: str | None = Field(default=None, max_length=120)
    last_completed_step: str | None = Field(default=None, max_length=120)
    step_started_at: datetime | None = Field(default=None)
    step_etag: str | None = Field(default=None, max_length=36)
    lock_token: str | None = Field(default=None, max_length=36)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=_utcnow, nullable=False)


class ArticleVersion(SQLModel, table=True):
    """Historical bodies (PLAN.md L355, D6).

    ``article.createVersion`` MCP copies the live row here BEFORE mutating;
    refresh runs append a new row.
    """

    __tablename__ = "article_versions"
    __table_args__ = (
        UniqueConstraint("article_id", "version", name="uq_article_versions_article_version"),
        Index("ix_article_versions_article", "article_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    article_id: int = Field(
        sa_column=Column(
            ForeignKey("articles.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    version: int = Field(nullable=False)
    brief_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    outline_md: str | None = Field(default=None)
    draft_md: str | None = Field(default=None)
    edited_md: str | None = Field(default=None)
    frontmatter_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    published_url: str | None = Field(default=None, max_length=2048)
    published_at: datetime | None = Field(default=None)
    voice_id_used: int | None = Field(default=None)
    eeat_criteria_version_used: int | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    refreshed_at: datetime | None = Field(default=None)
    refresh_reason: str | None = Field(default=None, max_length=200)


class ArticleAsset(SQLModel, table=True):
    """Hero + inline images (PLAN.md L356)."""

    __tablename__ = "article_assets"
    __table_args__ = (Index("ix_article_assets_article", "article_id"),)

    id: int | None = Field(default=None, primary_key=True)
    article_id: int = Field(
        sa_column=Column(
            ForeignKey("articles.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    kind: ArticleAssetKind = Field(sa_column=_enum_column(ArticleAssetKind))
    prompt: str | None = Field(default=None)
    url: str = Field(max_length=2048)
    alt_text: str | None = Field(default=None, max_length=500)
    width: int | None = Field(default=None)
    height: int | None = Field(default=None)
    position: int | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)


class ArticlePublish(SQLModel, table=True):
    """Per-target publish records (PLAN.md L357).

    PK is composite ``(article_id, target_id, version_published)``. ``id`` is
    a synthetic surrogate for FastAPI / repository ergonomics — the unique
    constraint guarantees no per-version dup.
    """

    __tablename__ = "article_publishes"
    __table_args__ = (
        UniqueConstraint(
            "article_id",
            "target_id",
            "version_published",
            name="uq_article_publishes_pk",
        ),
        Index("ix_article_publishes_article", "article_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    article_id: int = Field(
        sa_column=Column(
            ForeignKey("articles.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    target_id: int = Field(
        sa_column=Column(
            ForeignKey("publish_targets.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    version_published: int = Field(nullable=False)
    published_url: str | None = Field(default=None, max_length=2048)
    frontmatter_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    published_at: datetime | None = Field(default=None)
    status: ArticlePublishStatus = Field(sa_column=_enum_column(ArticlePublishStatus))
    error: str | None = Field(default=None)


class InternalLink(SQLModel, table=True):
    """Interlink graph (PLAN.md L358).

    Partial-unique index excluding ``status='dismissed'`` lives in the
    migration (audit B-09); the per-direction indexes are declarative.
    """

    __tablename__ = "internal_links"
    __table_args__ = (
        Index("idx_internal_links_from", "from_article_id"),
        Index("idx_internal_links_to", "to_article_id"),
        Index("ix_internal_links_project", "project_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(
        sa_column=Column(
            ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    from_article_id: int = Field(
        sa_column=Column(
            ForeignKey("articles.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    to_article_id: int = Field(
        sa_column=Column(
            ForeignKey("articles.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    anchor_text: str = Field(max_length=300)
    position: int | None = Field(default=None)
    status: InternalLinkStatus = Field(sa_column=_enum_column(InternalLinkStatus))
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=_utcnow, nullable=False)


class ResearchSource(SQLModel, table=True):
    """Citation tracking (PLAN.md L360)."""

    __tablename__ = "research_sources"
    __table_args__ = (Index("ix_research_sources_article", "article_id"),)

    id: int | None = Field(default=None, primary_key=True)
    article_id: int = Field(
        sa_column=Column(
            ForeignKey("articles.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    url: str = Field(max_length=2048)
    title: str | None = Field(default=None, max_length=500)
    snippet: str | None = Field(default=None)
    fetched_at: datetime = Field(default_factory=_utcnow, nullable=False)
    used: bool = Field(default=False)


class SchemaEmit(SQLModel, table=True):
    """JSON-LD blobs per article (PLAN.md L361).

    ``is_primary`` exactly-one-per-article is enforced in the repository
    layer at M1.B (no DB-level partial unique because SchemaEmit is also
    used for the per-project *templates* seeded with ``article_id IS NULL``;
    those templates never have ``is_primary=true``).
    """

    __tablename__ = "schema_emits"
    __table_args__ = (Index("ix_schema_emits_article", "article_id"),)

    id: int | None = Field(default=None, primary_key=True)
    article_id: int | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("articles.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    type: str = Field(max_length=120)
    # `schema_json` is the canonical PLAN.md L361 column name. SQLModel /
    # pydantic's parent class exposes a `schema_json` classmethod, which
    # mypy flags as an override. The runtime works correctly (with a benign
    # UserWarning silenced in pyproject.toml's pytest filter); the
    # `type: ignore` here is the narrowest fix that does not require
    # renaming a column the spec freezes.
    schema_json: dict[str, Any] | None = Field(  # type: ignore[assignment]
        default=None, sa_column=Column(JSON)
    )
    position: int | None = Field(default=None)
    is_primary: bool = Field(default=False)
    version_published: int | None = Field(default=None)
    validated_at: datetime | None = Field(default=None)


class DriftBaseline(SQLModel, table=True):
    """Drift detection baseline (PLAN.md L362)."""

    __tablename__ = "drift_baselines"
    __table_args__ = (Index("ix_drift_baselines_article", "article_id"),)

    id: int | None = Field(default=None, primary_key=True)
    article_id: int = Field(
        sa_column=Column(
            ForeignKey("articles.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    baseline_md: str = Field(default="")
    baseline_at: datetime = Field(default_factory=_utcnow, nullable=False)
    current_score: float | None = Field(default=None)


class GscMetric(SQLModel, table=True):
    """Search Console snapshots, raw, retained 90 days (PLAN.md L363)."""

    __tablename__ = "gsc_metrics"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "article_id",
            "captured_at",
            "dimensions_hash",
            name="uq_gsc_metrics_dedup",
        ),
        Index("idx_gsc_metrics_article_time", "article_id", "captured_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(
        sa_column=Column(
            ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    article_id: int | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("articles.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    captured_at: datetime = Field(default_factory=_utcnow, nullable=False)
    query: str | None = Field(default=None, max_length=500)
    query_normalized: str | None = Field(default=None, max_length=500)
    page: str | None = Field(default=None, max_length=2048)
    country: str | None = Field(default=None, max_length=8)
    device: str | None = Field(default=None, max_length=32)
    dimensions_hash: str = Field(max_length=64)
    impressions: int = Field(default=0)
    clicks: int = Field(default=0)
    ctr: float = Field(default=0.0)
    avg_position: float = Field(default=0.0)


class GscMetricDaily(SQLModel, table=True):
    """Aggregated GSC reads (PLAN.md L364)."""

    __tablename__ = "gsc_metrics_daily"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "article_id",
            "day",
            name="uq_gsc_metrics_daily",
        ),
        Index(
            "idx_gsc_metrics_daily_lookup",
            "project_id",
            "article_id",
            "day",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(
        sa_column=Column(
            ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    article_id: int | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("articles.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    day: datetime = Field(nullable=False)
    impressions_sum: int = Field(default=0)
    clicks_sum: int = Field(default=0)
    ctr_avg: float = Field(default=0.0)
    avg_position_avg: float = Field(default=0.0)
    queries_count: int = Field(default=0)


class EeatEvaluation(SQLModel, table=True):
    """Per-criterion EEAT result grain (PLAN.md L365)."""

    __tablename__ = "eeat_evaluations"
    __table_args__ = (Index("idx_eeat_evals_article", "article_id", "run_id"),)

    id: int | None = Field(default=None, primary_key=True)
    article_id: int = Field(
        sa_column=Column(
            ForeignKey("articles.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    criterion_id: int = Field(
        sa_column=Column(
            ForeignKey("eeat_criteria.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    run_id: int = Field(
        sa_column=Column(
            ForeignKey("runs.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    verdict: EeatVerdict = Field(sa_column=_enum_column(EeatVerdict))
    notes: str | None = Field(default=None)
    evaluated_at: datetime = Field(default_factory=_utcnow, nullable=False)


class Redirect(SQLModel, table=True):
    """301/302 records (PLAN.md L359)."""

    __tablename__ = "redirects"
    __table_args__ = (Index("ix_redirects_project", "project_id"),)

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(
        sa_column=Column(
            ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    from_url: str = Field(max_length=2048)
    to_article_id: int | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("articles.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    kind: RedirectKind = Field(sa_column=_enum_column(RedirectKind))
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)


class IntegrationCredential(SQLModel, table=True):
    """API keys per integration (PLAN.md L367).

    ``project_id`` is nullable for global credentials. ``encrypted_payload`` +
    ``nonce`` are AES-256-GCM ciphertext; AAD is composed at the repository
    layer (M5).
    """

    __tablename__ = "integration_credentials"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "kind",
            name="uq_integration_credentials_project_kind",
        ),
        Index("ix_integration_credentials_project", "project_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    project_id: int | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    kind: str = Field(max_length=120)
    encrypted_payload: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    nonce: bytes = Field(sa_column=Column(LargeBinary(12), nullable=False))
    expires_at: datetime | None = Field(default=None)
    last_refreshed_at: datetime | None = Field(default=None)
    config_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=_utcnow, nullable=False)


class IntegrationBudget(SQLModel, table=True):
    """Pre-emptive cost cap + rate limit (PLAN.md L368)."""

    __tablename__ = "integration_budgets"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "kind",
            name="uq_integration_budgets_project_kind",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(
        sa_column=Column(
            ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    kind: str = Field(max_length=120)
    monthly_budget_usd: float = Field(default=50.0)
    alert_threshold_pct: int = Field(default=80)
    current_month_spend: float = Field(default=0.0)
    current_month_calls: int = Field(default=0)
    qps: float = Field(default=1.0)
    last_reset: datetime = Field(default_factory=_utcnow, nullable=False)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=_utcnow, nullable=False)


class ProcedureRunStep(SQLModel, table=True):
    """One row per procedure step (PLAN.md L375)."""

    __tablename__ = "procedure_run_steps"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "step_index",
            name="uq_procedure_run_steps_run_step",
        ),
        Index("ix_procedure_run_steps_run", "run_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(
        sa_column=Column(
            ForeignKey("runs.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    step_index: int = Field(nullable=False)
    step_id: str = Field(max_length=120)
    status: ProcedureRunStepStatus = Field(sa_column=_enum_column(ProcedureRunStepStatus))
    started_at: datetime | None = Field(default=None)
    ended_at: datetime | None = Field(default=None)
    output_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    error: str | None = Field(default=None)


class RunStep(SQLModel, table=True):
    """Per-skill audit grain (PLAN.md L376).

    ``cost_cents`` is the cost-of-truth (PLAN.md L376); ``runs.metadata_json.cost``
    is denormalised for fast UI display.
    """

    __tablename__ = "run_steps"
    __table_args__ = (Index("idx_run_steps_run", "run_id", "step_index"),)

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(
        sa_column=Column(
            ForeignKey("runs.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    step_index: int = Field(nullable=False)
    skill_name: str = Field(max_length=120)
    started_at: datetime | None = Field(default=None)
    ended_at: datetime | None = Field(default=None)
    status: RunStepStatus = Field(sa_column=_enum_column(RunStepStatus))
    input_snapshot_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    output_snapshot_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    error: str | None = Field(default=None)
    cost_cents: int = Field(default=0)
    integration_calls_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))


class RunStepCall(SQLModel, table=True):
    """Per-MCP-call audit grain inside a skill step (PLAN.md L377)."""

    __tablename__ = "run_step_calls"
    __table_args__ = (Index("idx_run_step_calls_step", "run_step_id"),)

    id: int | None = Field(default=None, primary_key=True)
    run_step_id: int = Field(
        sa_column=Column(
            ForeignKey("run_steps.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    mcp_tool: str = Field(max_length=120)
    request_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    response_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    duration_ms: int | None = Field(default=None)
    error: str | None = Field(default=None)
    cost_cents: int = Field(default=0)


class IdempotencyKey(SQLModel, table=True):
    """Mutating-tool dedup (PLAN.md L378).

    UNIQUE ``(project_id, tool_name, idempotency_key)``; replays within the
    24 h window short-circuit to ``response_json``.
    """

    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "tool_name",
            "idempotency_key",
            name="uq_idempotency",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(
        sa_column=Column(
            ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    tool_name: str = Field(max_length=120)
    idempotency_key: str = Field(max_length=120)
    run_id: int | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    response_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)


class ScheduledJob(SQLModel, table=True):
    """Per-project schedules (PLAN.md L379)."""

    __tablename__ = "scheduled_jobs"
    __table_args__ = (Index("ix_scheduled_jobs_project", "project_id"),)

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(
        sa_column=Column(
            ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    kind: str = Field(max_length=120)
    cron_expr: str = Field(max_length=120)
    next_run_at: datetime | None = Field(default=None)
    last_run_at: datetime | None = Field(default=None)
    last_run_status: str | None = Field(default=None, max_length=32)
    enabled: bool = Field(default=True)


# ---------------------------------------------------------------------------
# Public re-exports — used by tests + future repository layer.
# ---------------------------------------------------------------------------


__all__ = [
    "ARTICLE_STATUS_TRANSITIONS",
    "Article",
    "ArticleAsset",
    "ArticleAssetKind",
    "ArticlePublish",
    "ArticlePublishStatus",
    "ArticleStatus",
    "ArticleVersion",
    "Author",
    "Cluster",
    "ClusterType",
    "CompliancePosition",
    "ComplianceRule",
    "ComplianceRuleKind",
    "DriftBaseline",
    "EeatCategory",
    "EeatCriterion",
    "EeatEvaluation",
    "EeatTier",
    "EeatVerdict",
    "GscMetric",
    "GscMetricDaily",
    "IdempotencyKey",
    "IntegrationBudget",
    "IntegrationCredential",
    "InternalLink",
    "InternalLinkStatus",
    "ProcedureRunStep",
    "ProcedureRunStepStatus",
    "Project",
    "PublishTarget",
    "PublishTargetKind",
    "Redirect",
    "RedirectKind",
    "ResearchSource",
    "Run",
    "RunKind",
    "RunStatus",
    "RunStep",
    "RunStepCall",
    "RunStepStatus",
    "ScheduledJob",
    "SchemaEmit",
    "Topic",
    "TopicIntent",
    "TopicSource",
    "TopicStatus",
    "VoiceProfile",
]
