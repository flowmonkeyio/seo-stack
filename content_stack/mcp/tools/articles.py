"""``article.*``, ``asset.*``, ``source.*``, ``schema.*``, ``publish.*`` tools.

Implements the procedure-4 happy path through MCP per PLAN.md L928-L939:

    article.create → setBrief → setOutline → setDraft (x3) → markDrafted
    → setEdited → markEeatPassed → markPublished

Every mutating tool that touches the article fat row (setBrief, setOutline,
setDraft, setEdited, markDrafted, markEeatPassed, markPublished) takes
``expected_etag`` per audit B-07 — the repository raises ``ConflictError``
on mismatch (-32008).

``eeat.score`` and ``eeat.getReport`` live here (alongside articles)
because the EEAT evaluation grain hangs off ``article_id``; the rubric
itself lives in the projects module.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import ConfigDict

from content_stack.db.models import (
    ArticleAssetKind,
    ArticlePublishStatus,
    ArticleStatus,
    EeatVerdict,
)
from content_stack.mcp.context import MCPContext
from content_stack.mcp.contract import MCPInput, WriteEnvelope
from content_stack.mcp.server import ToolRegistry, ToolSpec
from content_stack.mcp.streaming import ProgressEmitter
from content_stack.repositories.articles import (
    ArticleAssetOut,
    ArticleAssetRepository,
    ArticleOut,
    ArticlePublishOut,
    ArticlePublishRepository,
    ArticleRepository,
    ArticleVersionOut,
    ResearchSourceOut,
    ResearchSourceRepository,
    SchemaEmitOut,
    SchemaEmitRepository,
)
from content_stack.repositories.base import Page
from content_stack.repositories.eeat import (
    EeatEvaluationCreate,
    EeatEvaluationOut,
    EeatEvaluationRepository,
    EeatScoreReport,
)

# ---------------------------------------------------------------------------
# article.* inputs.
# ---------------------------------------------------------------------------


class ArticleCreateInput(MCPInput):
    """Insert a fresh article in status='briefing'."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "project_id": 1,
                "topic_id": 1,
                "title": "Best parlay strategies",
                "slug": "best-parlay-strategies",
            }
        },
    )

    project_id: int
    topic_id: int | None = None
    title: str
    slug: str
    voice_id: int | None = None
    eeat_criteria_version: int | None = None
    author_id: int | None = None
    reviewer_author_id: int | None = None


class ArticleBulkCreateInput(MCPInput):
    """Insert N articles in one transaction."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"project_id": 1, "items": [{"title": "T1", "slug": "t1"}]}},
    )

    project_id: int
    items: list[dict[str, Any]]


class ArticleGetInput(MCPInput):
    """Fetch an article by id."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"article_id": 1}})

    article_id: int


class ArticleListInput(MCPInput):
    """List articles for a project."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"project_id": 1}})

    project_id: int
    status: ArticleStatus | None = None
    topic_id: int | None = None
    limit: int | None = None
    after_id: int | None = None


class ArticleListDueForRefreshInput(MCPInput):
    """List articles eligible for the refresh-detector pass."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"project_id": 1}})

    project_id: int
    limit: int | None = None
    after_id: int | None = None


class ArticleSetBriefInput(MCPInput):
    """Write brief_json; advances briefing → outlined."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"article_id": 1, "brief_json": {"thesis": "..."}, "expected_etag": "uuid"}
        },
    )

    article_id: int
    brief_json: dict[str, Any]
    expected_etag: str  # type: ignore[assignment]


class ArticleSetOutlineInput(MCPInput):
    """Write outline_md; status stays 'outlined'."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"article_id": 1, "outline_md": "## H2\n", "expected_etag": "uuid"}
        },
    )

    article_id: int
    outline_md: str
    expected_etag: str  # type: ignore[assignment]


class ArticleSetDraftInput(MCPInput):
    """Write or append draft_md."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "article_id": 1,
                "draft_md": "...",
                "expected_etag": "uuid",
                "append": False,
            }
        },
    )

    article_id: int
    draft_md: str
    expected_etag: str  # type: ignore[assignment]
    append: bool = False


class ArticleMarkDraftedInput(MCPInput):
    """Advance outlined → drafted."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"article_id": 1, "expected_etag": "uuid"}}
    )

    article_id: int
    expected_etag: str  # type: ignore[assignment]


class ArticleSetEditedInput(MCPInput):
    """Write edited_md; advances drafted → edited."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"article_id": 1, "edited_md": "...", "expected_etag": "uuid"}
        },
    )

    article_id: int
    edited_md: str
    expected_etag: str  # type: ignore[assignment]


class ArticleMarkEeatPassedInput(MCPInput):
    """Advance edited → eeat_passed."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "article_id": 1,
                "expected_etag": "uuid",
                "run_id": 1,
                "eeat_criteria_version": 1,
            }
        },
    )

    article_id: int
    expected_etag: str  # type: ignore[assignment]
    run_id: int
    eeat_criteria_version: int


class ArticleMarkPublishedInput(MCPInput):
    """Advance eeat_passed → published; slug becomes immutable."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"article_id": 1, "expected_etag": "uuid", "run_id": 1}},
    )

    article_id: int
    expected_etag: str  # type: ignore[assignment]
    run_id: int


class ArticleMarkAbortedPublishInput(MCPInput):
    """Advance a pre-publish article to aborted-publish."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"article_id": 1, "expected_etag": "uuid", "run_id": 1}},
    )

    article_id: int
    expected_etag: str  # type: ignore[assignment]
    run_id: int


class ArticleMarkRefreshDueInput(MCPInput):
    """Advance published → refresh_due."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"article_id": 1, "reason": "drift detected"}}
    )

    article_id: int
    reason: str


class ArticleRefreshDueInput(MCPInput):
    """Convenience alias for markRefreshDue (mirrors PLAN catalog spelling)."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"article_id": 1, "reason": "drift"}}
    )

    article_id: int
    reason: str


class ArticleCreateVersionInput(MCPInput):
    """Snapshot the live article row into article_versions."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"article_id": 1}})

    article_id: int


class ArticleListVersionsInput(MCPInput):
    """List version snapshots for an article."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"article_id": 1}})

    article_id: int
    limit: int | None = None
    after_id: int | None = None


class ArticleListPublishesInput(MCPInput):
    """List publish records for an article."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"article_id": 1}})

    article_id: int


# ---------------------------------------------------------------------------
# article.* handlers.
# ---------------------------------------------------------------------------


async def _article_create(
    inp: ArticleCreateInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ArticleOut]:
    env = ArticleRepository(ctx.session).create(
        project_id=inp.project_id,
        topic_id=inp.topic_id,
        title=inp.title,
        slug=inp.slug,
        voice_id=inp.voice_id,
        eeat_criteria_version=inp.eeat_criteria_version,
        author_id=inp.author_id,
        reviewer_author_id=inp.reviewer_author_id,
    )
    return WriteEnvelope[ArticleOut](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


async def _article_bulk_create(
    inp: ArticleBulkCreateInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[list[ArticleOut]]:
    """Insert N articles serially in one transaction."""
    repo = ArticleRepository(ctx.session)
    rows: list[ArticleOut] = []
    for item in inp.items:
        env = repo.create(
            project_id=inp.project_id,
            topic_id=item.get("topic_id"),
            title=item["title"],
            slug=item["slug"],
            voice_id=item.get("voice_id"),
            eeat_criteria_version=item.get("eeat_criteria_version"),
            author_id=item.get("author_id"),
            reviewer_author_id=item.get("reviewer_author_id"),
        )
        rows.append(env.data)
    return WriteEnvelope[list[ArticleOut]](data=rows, run_id=ctx.run_id, project_id=inp.project_id)


async def _article_get(inp: ArticleGetInput, ctx: MCPContext, _emit: ProgressEmitter) -> ArticleOut:
    return ArticleRepository(ctx.session).get(inp.article_id)


async def _article_list(
    inp: ArticleListInput, ctx: MCPContext, _emit: ProgressEmitter
) -> Page[ArticleOut]:
    return ArticleRepository(ctx.session).list(
        inp.project_id,
        status=inp.status,
        topic_id=inp.topic_id,
        limit=inp.limit,
        after_id=inp.after_id,
    )


async def _article_list_due_for_refresh(
    inp: ArticleListDueForRefreshInput, ctx: MCPContext, _emit: ProgressEmitter
) -> Page[ArticleOut]:
    return ArticleRepository(ctx.session).list_due_for_refresh(
        inp.project_id, limit=inp.limit, after_id=inp.after_id
    )


async def _article_set_brief(
    inp: ArticleSetBriefInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ArticleOut]:
    env = ArticleRepository(ctx.session).set_brief(
        inp.article_id, inp.brief_json, expected_etag=inp.expected_etag
    )
    return WriteEnvelope[ArticleOut](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


async def _article_set_outline(
    inp: ArticleSetOutlineInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ArticleOut]:
    env = ArticleRepository(ctx.session).set_outline(
        inp.article_id, inp.outline_md, expected_etag=inp.expected_etag
    )
    return WriteEnvelope[ArticleOut](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


async def _article_set_draft(
    inp: ArticleSetDraftInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ArticleOut]:
    env = ArticleRepository(ctx.session).set_draft(
        inp.article_id, inp.draft_md, expected_etag=inp.expected_etag, append=inp.append
    )
    return WriteEnvelope[ArticleOut](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


async def _article_mark_drafted(
    inp: ArticleMarkDraftedInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ArticleOut]:
    env = ArticleRepository(ctx.session).mark_drafted(
        inp.article_id, expected_etag=inp.expected_etag
    )
    return WriteEnvelope[ArticleOut](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


async def _article_set_edited(
    inp: ArticleSetEditedInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ArticleOut]:
    env = ArticleRepository(ctx.session).set_edited(
        inp.article_id, inp.edited_md, expected_etag=inp.expected_etag
    )
    return WriteEnvelope[ArticleOut](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


async def _article_mark_eeat_passed(
    inp: ArticleMarkEeatPassedInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ArticleOut]:
    env = ArticleRepository(ctx.session).mark_eeat_passed(
        inp.article_id,
        expected_etag=inp.expected_etag,
        run_id=inp.run_id,
        eeat_criteria_version=inp.eeat_criteria_version,
    )
    return WriteEnvelope[ArticleOut](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


async def _article_mark_published(
    inp: ArticleMarkPublishedInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ArticleOut]:
    env = ArticleRepository(ctx.session).mark_published(
        inp.article_id, expected_etag=inp.expected_etag, run_id=inp.run_id
    )
    return WriteEnvelope[ArticleOut](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


async def _article_mark_aborted_publish(
    inp: ArticleMarkAbortedPublishInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ArticleOut]:
    env = ArticleRepository(ctx.session).mark_aborted_publish(
        inp.article_id, expected_etag=inp.expected_etag, run_id=inp.run_id
    )
    return WriteEnvelope[ArticleOut](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


async def _article_mark_refresh_due(
    inp: ArticleMarkRefreshDueInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ArticleOut]:
    env = ArticleRepository(ctx.session).mark_refresh_due(inp.article_id, reason=inp.reason)
    return WriteEnvelope[ArticleOut](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


async def _article_refresh_due(
    inp: ArticleRefreshDueInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ArticleOut]:
    """Alias of markRefreshDue per PLAN catalog (article.refreshDue)."""
    env = ArticleRepository(ctx.session).mark_refresh_due(inp.article_id, reason=inp.reason)
    return WriteEnvelope[ArticleOut](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


async def _article_create_version(
    inp: ArticleCreateVersionInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ArticleVersionOut]:
    env = ArticleRepository(ctx.session).create_version(inp.article_id)
    return WriteEnvelope[ArticleVersionOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


async def _article_list_versions(
    inp: ArticleListVersionsInput, ctx: MCPContext, _emit: ProgressEmitter
) -> Page[ArticleVersionOut]:
    return ArticleRepository(ctx.session).list_versions(
        inp.article_id, limit=inp.limit, after_id=inp.after_id
    )


async def _article_list_publishes(
    inp: ArticleListPublishesInput, ctx: MCPContext, _emit: ProgressEmitter
) -> list[ArticlePublishOut]:
    return ArticlePublishRepository(ctx.session).list_for_article(inp.article_id)


# ---------------------------------------------------------------------------
# asset.* tools.
# ---------------------------------------------------------------------------


class AssetCreateInput(MCPInput):
    """Insert an asset row for an article."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"article_id": 1, "kind": "hero", "url": "https://..."}},
    )

    article_id: int
    kind: ArticleAssetKind
    url: str
    prompt: str | None = None
    alt_text: str | None = None
    width: int | None = None
    height: int | None = None
    position: int | None = None


class AssetListInput(MCPInput):
    """List assets for an article."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"article_id": 1}})

    article_id: int


class AssetUpdateInput(MCPInput):
    """Patch an asset (commonly used by alt-text-auditor)."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"asset_id": 1, "patch": {"alt_text": "..."}}}
    )

    asset_id: int
    patch: dict[str, Any]


class AssetRemoveInput(MCPInput):
    """Hard-delete an asset row."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"asset_id": 1}})

    asset_id: int


async def _asset_create(
    inp: AssetCreateInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ArticleAssetOut]:
    env = ArticleAssetRepository(ctx.session).create(
        article_id=inp.article_id,
        kind=inp.kind,
        url=inp.url,
        prompt=inp.prompt,
        alt_text=inp.alt_text,
        width=inp.width,
        height=inp.height,
        position=inp.position,
    )
    return WriteEnvelope[ArticleAssetOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


async def _asset_list(
    inp: AssetListInput, ctx: MCPContext, _emit: ProgressEmitter
) -> list[ArticleAssetOut]:
    return ArticleAssetRepository(ctx.session).list(inp.article_id)


async def _asset_update(
    inp: AssetUpdateInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ArticleAssetOut]:
    env = ArticleAssetRepository(ctx.session).update(inp.asset_id, **inp.patch)
    return WriteEnvelope[ArticleAssetOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


async def _asset_remove(
    inp: AssetRemoveInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ArticleAssetOut]:
    env = ArticleAssetRepository(ctx.session).remove(inp.asset_id)
    return WriteEnvelope[ArticleAssetOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


# ---------------------------------------------------------------------------
# source.* tools.
# ---------------------------------------------------------------------------


class SourceAddInput(MCPInput):
    """Insert a research-source citation."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"article_id": 1, "url": "https://..."}}
    )

    article_id: int
    url: str
    title: str | None = None
    snippet: str | None = None
    used: bool = False


class SourceListInput(MCPInput):
    """List sources for an article."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"article_id": 1, "used": True}}
    )

    article_id: int
    used: bool | None = None


class SourceUpdateInput(MCPInput):
    """Patch the used flag on a research-source row."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"source_id": 1, "used": True}}
    )

    source_id: int
    used: bool


async def _source_add(
    inp: SourceAddInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ResearchSourceOut]:
    env = ResearchSourceRepository(ctx.session).add(
        article_id=inp.article_id, url=inp.url, title=inp.title, snippet=inp.snippet, used=inp.used
    )
    return WriteEnvelope[ResearchSourceOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


async def _source_list(
    inp: SourceListInput, ctx: MCPContext, _emit: ProgressEmitter
) -> list[ResearchSourceOut]:
    return ResearchSourceRepository(ctx.session).list(inp.article_id, used=inp.used)


async def _source_update(
    inp: SourceUpdateInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ResearchSourceOut]:
    env = ResearchSourceRepository(ctx.session).update_used(inp.source_id, used=inp.used)
    return WriteEnvelope[ResearchSourceOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


# ---------------------------------------------------------------------------
# schema.* tools.
# ---------------------------------------------------------------------------


class SchemaSetInput(MCPInput):
    """Upsert a JSON-LD schema-emit row."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"article_id": 1, "type": "Article", "schema_json": {"@type": "Article"}}
        },
    )

    article_id: int
    type: str
    # ``schema_json`` shadows ``BaseModel.schema_json`` (a classmethod).
    # The same shadow is suppressed across the project for the same column
    # name (per pyproject.toml filterwarnings); we silence the mypy
    # "incompatible-types" mirror here for the same reason.
    schema_json: dict[str, Any]  # type: ignore[assignment]
    is_primary: bool = False
    position: int | None = None
    version_published: int | None = None


class SchemaGetInput(MCPInput):
    """Fetch a schema-emit row by id."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"schema_id": 1}})

    schema_id: int


class SchemaListInput(MCPInput):
    """List schema-emit rows for an article."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"article_id": 1}})

    article_id: int


class SchemaValidateInput(MCPInput):
    """Mark a schema-emit row as validated (M5 will add real JSON-LD validation)."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"schema_id": 1}})

    schema_id: int


async def _schema_set(
    inp: SchemaSetInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[SchemaEmitOut]:
    env = SchemaEmitRepository(ctx.session).set(
        article_id=inp.article_id,
        type=inp.type,
        schema_json=inp.schema_json,
        is_primary=inp.is_primary,
        position=inp.position,
        version_published=inp.version_published,
    )
    return WriteEnvelope[SchemaEmitOut](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


async def _schema_get(
    inp: SchemaGetInput, ctx: MCPContext, _emit: ProgressEmitter
) -> SchemaEmitOut:
    return SchemaEmitRepository(ctx.session).get(inp.schema_id)


async def _schema_list(
    inp: SchemaListInput, ctx: MCPContext, _emit: ProgressEmitter
) -> list[SchemaEmitOut]:
    return SchemaEmitRepository(ctx.session).list_for_article(inp.article_id)


async def _schema_validate(
    inp: SchemaValidateInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[SchemaEmitOut]:
    env = SchemaEmitRepository(ctx.session).validate(inp.schema_id)
    return WriteEnvelope[SchemaEmitOut](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


# ---------------------------------------------------------------------------
# publish.* tools.
# ---------------------------------------------------------------------------


class PublishPreviewInput(MCPInput):
    """Render a publish preview without committing.

    M3 returns a stub envelope; M5/M7 will wire real publisher previews.
    """

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"article_id": 1, "target_id": 1}}
    )

    article_id: int
    target_id: int


class PublishRecordInput(MCPInput):
    """Record an article-publish row after successful publication."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"article_id": 1, "target_id": 1, "version_published": 1}},
    )

    article_id: int
    target_id: int
    version_published: int
    published_url: str | None = None
    frontmatter_json: dict[str, Any] | None = None
    status: ArticlePublishStatus = ArticlePublishStatus.PUBLISHED
    error: str | None = None


class PublishSetCanonicalInput(MCPInput):
    """Set articles.canonical_target_id."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"article_id": 1, "target_id": 1}}
    )

    article_id: int
    target_id: int


class PublishPreviewOutput(MCPInput):
    """Output for ``publish.preview`` — composed preview view."""

    article_id: int
    target_id: int
    rendered_at: datetime
    status: str
    notes: str


async def _publish_preview(
    inp: PublishPreviewInput, ctx: MCPContext, _emit: ProgressEmitter
) -> PublishPreviewOutput:
    """Compose a preview from the current article body + target config.

    M3 returns a stub object that surfaces the raw inputs and a status
    string. M5 will compose the real publisher-side render. The output
    shape is locked here so the wire contract is forward-compatible.
    """
    article = ArticleRepository(ctx.session).get(inp.article_id)
    return PublishPreviewOutput(
        article_id=inp.article_id,
        target_id=inp.target_id,
        rendered_at=datetime.utcnow(),
        status="stub",
        notes=(
            "M3 stub: returns the article slug + status. M5 wires real publisher-side rendering. "
            f"slug={article.slug}, status={article.status.value}"
        ),
    )


async def _publish_record(
    inp: PublishRecordInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ArticlePublishOut]:
    env = ArticlePublishRepository(ctx.session).record_publish(
        article_id=inp.article_id,
        target_id=inp.target_id,
        version_published=inp.version_published,
        published_url=inp.published_url,
        frontmatter_json=inp.frontmatter_json,
        status=inp.status,
        error=inp.error,
    )
    return WriteEnvelope[ArticlePublishOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


async def _publish_set_canonical(
    inp: PublishSetCanonicalInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ArticleOut]:
    env = ArticlePublishRepository(ctx.session).set_canonical(
        article_id=inp.article_id, target_id=inp.target_id
    )
    return WriteEnvelope[ArticleOut](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


# ---------------------------------------------------------------------------
# eeat.* (evaluations grain — score/getReport).
# ---------------------------------------------------------------------------


class EeatRecordInput(MCPInput):
    """Insert one EEAT evaluation."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"article_id": 1, "criterion_id": 1, "run_id": 1, "verdict": "pass"}
        },
    )

    article_id: int
    criterion_id: int
    run_id: int
    verdict: EeatVerdict
    notes: str | None = None


class EeatBulkRecordInput(MCPInput):
    """Insert N EEAT evaluations atomically."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"article_id": 1, "run_id": 1, "evaluations": []}},
    )

    article_id: int
    run_id: int
    evaluations: list[EeatEvaluationCreate]


class EeatScoreReportInput(MCPInput):
    """Aggregate evaluations into per-dimension and per-system scores."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"article_id": 1, "run_id": 1}}
    )

    article_id: int
    run_id: int


class EeatGetReportInput(MCPInput):
    """Alias of eeat.score per PLAN catalog spelling (eeat.getReport)."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"article_id": 1, "run_id": 1}}
    )

    article_id: int
    run_id: int


class EeatListEvalsInput(MCPInput):
    """List EEAT evaluations filtered by article and/or run.

    NOTE: ``eeat.list`` for *criteria* (rubric) lives in
    ``content_stack.mcp.tools.projects``; this tool is the evaluations
    counterpart, used by skill #11.
    """

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"article_id": 1}})

    article_id: int | None = None
    run_id: int | None = None


async def _eeat_record(
    inp: EeatRecordInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[EeatEvaluationOut]:
    env = EeatEvaluationRepository(ctx.session).record(
        article_id=inp.article_id,
        criterion_id=inp.criterion_id,
        run_id=inp.run_id,
        verdict=inp.verdict,
        notes=inp.notes,
    )
    return WriteEnvelope[EeatEvaluationOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


async def _eeat_bulk_record(
    inp: EeatBulkRecordInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[list[EeatEvaluationOut]]:
    env = EeatEvaluationRepository(ctx.session).bulk_record(
        article_id=inp.article_id, run_id=inp.run_id, evaluations=inp.evaluations
    )
    return WriteEnvelope[list[EeatEvaluationOut]](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


async def _eeat_score_report(
    inp: EeatScoreReportInput, ctx: MCPContext, _emit: ProgressEmitter
) -> EeatScoreReport:
    return EeatEvaluationRepository(ctx.session).score(article_id=inp.article_id, run_id=inp.run_id)


async def _eeat_list_evals(
    inp: EeatListEvalsInput, ctx: MCPContext, _emit: ProgressEmitter
) -> list[EeatEvaluationOut]:
    return EeatEvaluationRepository(ctx.session).list(article_id=inp.article_id, run_id=inp.run_id)


# ---------------------------------------------------------------------------
# Registration.
# ---------------------------------------------------------------------------


def register(registry: ToolRegistry) -> None:
    """Register every article / asset / source / schema / publish tool."""
    # article.*
    registry.register(
        ToolSpec(
            "article.create",
            "Insert an article in status='briefing'.",
            ArticleCreateInput,
            WriteEnvelope[ArticleOut],
            _article_create,
        )
    )
    registry.register(
        ToolSpec(
            "article.bulkCreate",
            "Insert N articles in one transaction.",
            ArticleBulkCreateInput,
            WriteEnvelope[list[ArticleOut]],
            _article_bulk_create,
        )
    )
    registry.register(
        ToolSpec(
            "article.get", "Fetch one article by id.", ArticleGetInput, ArticleOut, _article_get
        )
    )
    registry.register(
        ToolSpec(
            "article.list",
            "List articles for a project with filters.",
            ArticleListInput,
            Page[ArticleOut],
            _article_list,
        )
    )
    registry.register(
        ToolSpec(
            "article.listDueForRefresh",
            "List articles eligible for the refresh-detector pass.",
            ArticleListDueForRefreshInput,
            Page[ArticleOut],
            _article_list_due_for_refresh,
        )
    )
    registry.register(
        ToolSpec(
            "article.setBrief",
            "Write brief_json; advances briefing → outlined.",
            ArticleSetBriefInput,
            WriteEnvelope[ArticleOut],
            _article_set_brief,
        )
    )
    registry.register(
        ToolSpec(
            "article.setOutline",
            "Write outline_md (no transition).",
            ArticleSetOutlineInput,
            WriteEnvelope[ArticleOut],
            _article_set_outline,
        )
    )
    registry.register(
        ToolSpec(
            "article.setDraft",
            "Write or append draft_md.",
            ArticleSetDraftInput,
            WriteEnvelope[ArticleOut],
            _article_set_draft,
        )
    )
    registry.register(
        ToolSpec(
            "article.markDrafted",
            "Advance outlined → drafted.",
            ArticleMarkDraftedInput,
            WriteEnvelope[ArticleOut],
            _article_mark_drafted,
        )
    )
    registry.register(
        ToolSpec(
            "article.setEdited",
            "Write edited_md; advances drafted → edited.",
            ArticleSetEditedInput,
            WriteEnvelope[ArticleOut],
            _article_set_edited,
        )
    )
    registry.register(
        ToolSpec(
            "article.markEeatPassed",
            "Advance edited → eeat_passed.",
            ArticleMarkEeatPassedInput,
            WriteEnvelope[ArticleOut],
            _article_mark_eeat_passed,
        )
    )
    registry.register(
        ToolSpec(
            "article.markPublished",
            "Advance eeat_passed → published; slug becomes immutable.",
            ArticleMarkPublishedInput,
            WriteEnvelope[ArticleOut],
            _article_mark_published,
        )
    )
    registry.register(
        ToolSpec(
            "article.markAbortedPublish",
            "Advance a pre-publish article to aborted-publish.",
            ArticleMarkAbortedPublishInput,
            WriteEnvelope[ArticleOut],
            _article_mark_aborted_publish,
        )
    )
    registry.register(
        ToolSpec(
            "article.markRefreshDue",
            "Advance published → refresh_due.",
            ArticleMarkRefreshDueInput,
            WriteEnvelope[ArticleOut],
            _article_mark_refresh_due,
        )
    )
    registry.register(
        ToolSpec(
            "article.refreshDue",
            "Alias of markRefreshDue (PLAN catalog spelling).",
            ArticleRefreshDueInput,
            WriteEnvelope[ArticleOut],
            _article_refresh_due,
        )
    )
    registry.register(
        ToolSpec(
            "article.createVersion",
            "Snapshot the live article into article_versions.",
            ArticleCreateVersionInput,
            WriteEnvelope[ArticleVersionOut],
            _article_create_version,
        )
    )
    registry.register(
        ToolSpec(
            "article.listVersions",
            "List version snapshots.",
            ArticleListVersionsInput,
            Page[ArticleVersionOut],
            _article_list_versions,
        )
    )
    registry.register(
        ToolSpec(
            "article.listPublishes",
            "List publish records.",
            ArticleListPublishesInput,
            list[ArticlePublishOut],
            _article_list_publishes,
        )
    )

    # asset.*
    registry.register(
        ToolSpec(
            "asset.create",
            "Insert an asset row.",
            AssetCreateInput,
            WriteEnvelope[ArticleAssetOut],
            _asset_create,
        )
    )
    registry.register(
        ToolSpec(
            "asset.list",
            "List assets for an article.",
            AssetListInput,
            list[ArticleAssetOut],
            _asset_list,
        )
    )
    registry.register(
        ToolSpec(
            "asset.update",
            "Patch an asset row.",
            AssetUpdateInput,
            WriteEnvelope[ArticleAssetOut],
            _asset_update,
        )
    )
    registry.register(
        ToolSpec(
            "asset.remove",
            "Hard-delete an asset row.",
            AssetRemoveInput,
            WriteEnvelope[ArticleAssetOut],
            _asset_remove,
        )
    )

    # source.*
    registry.register(
        ToolSpec(
            "source.add",
            "Insert a research-source citation.",
            SourceAddInput,
            WriteEnvelope[ResearchSourceOut],
            _source_add,
        )
    )
    registry.register(
        ToolSpec(
            "source.list",
            "List sources for an article.",
            SourceListInput,
            list[ResearchSourceOut],
            _source_list,
        )
    )
    registry.register(
        ToolSpec(
            "source.update",
            "Patch a research-source citation.",
            SourceUpdateInput,
            WriteEnvelope[ResearchSourceOut],
            _source_update,
        )
    )

    # schema.*
    registry.register(
        ToolSpec(
            "schema.set",
            "Upsert a JSON-LD schema-emit row.",
            SchemaSetInput,
            WriteEnvelope[SchemaEmitOut],
            _schema_set,
        )
    )
    registry.register(
        ToolSpec(
            "schema.get",
            "Fetch a schema-emit row by id.",
            SchemaGetInput,
            SchemaEmitOut,
            _schema_get,
        )
    )
    registry.register(
        ToolSpec(
            "schema.list",
            "List schema-emit rows for an article.",
            SchemaListInput,
            list[SchemaEmitOut],
            _schema_list,
        )
    )
    registry.register(
        ToolSpec(
            "schema.validate",
            "Mark a schema-emit row as validated.",
            SchemaValidateInput,
            WriteEnvelope[SchemaEmitOut],
            _schema_validate,
        )
    )

    # publish.*
    registry.register(
        ToolSpec(
            "publish.preview",
            "Render a publish preview without committing.",
            PublishPreviewInput,
            PublishPreviewOutput,
            _publish_preview,
        )
    )
    registry.register(
        ToolSpec(
            "publish.recordPublish",
            "Record an article-publish row after publication.",
            PublishRecordInput,
            WriteEnvelope[ArticlePublishOut],
            _publish_record,
        )
    )
    registry.register(
        ToolSpec(
            "publish.setCanonical",
            "Set articles.canonical_target_id.",
            PublishSetCanonicalInput,
            WriteEnvelope[ArticleOut],
            _publish_set_canonical,
        )
    )

    # eeat.* (evaluations grain).
    registry.register(
        ToolSpec(
            "eeat.record",
            "Insert one EEAT evaluation.",
            EeatRecordInput,
            WriteEnvelope[EeatEvaluationOut],
            _eeat_record,
        )
    )
    registry.register(
        ToolSpec(
            "eeat.bulkRecord",
            "Insert N EEAT evaluations atomically.",
            EeatBulkRecordInput,
            WriteEnvelope[list[EeatEvaluationOut]],
            _eeat_bulk_record,
        )
    )
    registry.register(
        ToolSpec(
            "eeat.score",
            "Aggregate evaluations into per-dimension scores.",
            EeatScoreReportInput,
            EeatScoreReport,
            _eeat_score_report,
        )
    )
    registry.register(
        ToolSpec(
            "eeat.getReport",
            "Aggregate evaluations into a report (alias of eeat.score).",
            EeatGetReportInput,
            EeatScoreReport,
            _eeat_score_report,
        )
    )
    registry.register(
        ToolSpec(
            "eeat.listEvaluations",
            "List EEAT evaluations.",
            EeatListEvalsInput,
            list[EeatEvaluationOut],
            _eeat_list_evals,
        )
    )


__all__ = ["register"]
