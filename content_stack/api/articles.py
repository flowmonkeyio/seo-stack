"""Articles router — full procedure-4 + sub-resources.

PLAN.md L580-L591. Two prefixes:

- ``/api/v1/projects/{id}/articles`` — list, create, refresh-due
- ``/api/v1/articles/{id}`` — fat-row GET + UI-permissive PATCH +
  typed verbs (brief / outline / draft / edit / eeat-pass / publish /
  refresh-due / version) + sub-resources (assets / sources / schema /
  publishes / eeat / drift / interlinks).

Optimistic concurrency:

- Typed verbs (POST ``.../brief|outline|draft|...``) carry ``expected_etag``
  in the body; the repo's ``set_*`` methods compare against the row's
  ``step_etag`` UUID and rotate on success.
- UI-permissive PATCH (``PATCH /articles/{id}``) carries
  ``If-Match: <updated_at iso>`` per PLAN.md L803-L809; on stale we
  return 412 Precondition Failed.

Slug immutability post-publish is enforced in ``ArticleRepository.update_slug``
which surfaces ``ConflictError`` (-32008 / 409 here mapped to 422 since the
PATCH body validates the field; see the inline notes).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session

from content_stack.api.deps import get_if_match, get_session
from content_stack.api.envelopes import WriteResponse, write_response
from content_stack.api.pagination import (
    PageResponse,
    PaginationParams,
    page_response,
    pagination_params,
)
from content_stack.db.models import (
    ArticleAssetKind,
    ArticlePublishStatus,
    ArticleStatus,
    EeatVerdict,
    RunKind,
    RunStatus,
)
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
from content_stack.repositories.eeat import (
    EeatEvaluationCreate,
    EeatEvaluationOut,
    EeatEvaluationRepository,
    EeatScoreReport,
)
from content_stack.repositories.gsc import DriftBaselineOut, DriftBaselineRepository
from content_stack.repositories.interlinks import InterlinkRepository, InternalLinkOut
from content_stack.repositories.runs import RunRepository

project_router = APIRouter(prefix="/api/v1/projects", tags=["articles"])
article_router = APIRouter(prefix="/api/v1/articles", tags=["articles"])


# ---------------------------------------------------------------------------
# Request / response shapes.
# ---------------------------------------------------------------------------


class ArticleCreateRequest(BaseModel):
    """Body for ``POST /projects/{id}/articles``."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "topic_id": 1,
                "title": "How to evaluate a sportsbook",
                "slug": "evaluate-a-sportsbook",
                "voice_id": None,
                "eeat_criteria_version": 1,
                "author_id": None,
                "reviewer_author_id": None,
            }
        }
    )

    topic_id: int | None = None
    title: str = Field(min_length=1, max_length=300)
    slug: str = Field(min_length=1, max_length=80)
    voice_id: int | None = None
    eeat_criteria_version: int | None = None
    author_id: int | None = None
    reviewer_author_id: int | None = None


class ArticlePatchRequest(BaseModel):
    """UI-permissive PATCH body — slug allowed pre-publish."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    slug: str | None = Field(default=None, min_length=1, max_length=80)
    brief_json: dict[str, Any] | None = None
    outline_md: str | None = None
    draft_md: str | None = None
    edited_md: str | None = None
    author_id: int | None = None
    reviewer_author_id: int | None = None
    canonical_target_id: int | None = None


# Typed-verb bodies (brief / outline / draft / etc.).


class SetBriefRequest(BaseModel):
    expected_etag: str
    brief_json: dict[str, Any]


class SetOutlineRequest(BaseModel):
    expected_etag: str
    outline_md: str


class SetDraftRequest(BaseModel):
    expected_etag: str
    draft_md: str


class MarkDraftedRequest(BaseModel):
    expected_etag: str


class SetEditedRequest(BaseModel):
    expected_etag: str
    edited_md: str


class MarkEeatPassedRequest(BaseModel):
    expected_etag: str
    run_id: int | None = None
    eeat_criteria_version: int


class MarkPublishedRequest(BaseModel):
    expected_etag: str
    run_id: int | None = None


class MarkRefreshDueRequest(BaseModel):
    reason: str = Field(min_length=1)


# Sub-resource bodies.


class AssetCreateRequest(BaseModel):
    kind: ArticleAssetKind
    url: str = Field(min_length=1, max_length=2048)
    prompt: str | None = None
    alt_text: str | None = Field(default=None, max_length=500)
    width: int | None = None
    height: int | None = None
    position: int | None = None


class AssetUpdateRequest(BaseModel):
    kind: ArticleAssetKind | None = None
    url: str | None = Field(default=None, max_length=2048)
    prompt: str | None = None
    alt_text: str | None = Field(default=None, max_length=500)
    width: int | None = None
    height: int | None = None
    position: int | None = None


class SourceCreateRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    title: str | None = Field(default=None, max_length=500)
    snippet: str | None = None
    used: bool = False


class SchemaSetRequest(BaseModel):
    # ``schema_json`` shadows pydantic's classmethod (same caveat as
    # ``SchemaEmit`` / ``SchemaEmitOut`` in models.py / repositories);
    # the column name is fixed by PLAN.md L361 and the runtime works
    # correctly. mypy's override warning is suppressed here.
    schema_json: dict[str, Any]  # type: ignore[assignment]
    is_primary: bool = False
    position: int | None = None
    version_published: int | None = None


class PublishCreateRequest(BaseModel):
    target_id: int
    version_published: int
    published_url: str | None = Field(default=None, max_length=2048)
    frontmatter_json: dict[str, Any] | None = None
    status: ArticlePublishStatus = ArticlePublishStatus.PUBLISHED
    error: str | None = None
    published_at: datetime | None = None


class CanonicalSetRequest(BaseModel):
    target_id: int


class EeatEvaluationItem(BaseModel):
    criterion_id: int
    verdict: EeatVerdict
    notes: str | None = None


class EeatBulkRecordRequest(BaseModel):
    run_id: int
    evaluations: list[EeatEvaluationItem] = Field(min_length=1)


class EeatReportResponse(BaseModel):
    """Wire shape combining per-run evaluations + score report."""

    score: EeatScoreReport
    evaluations: list[EeatEvaluationOut]


class DriftSnapshotRequest(BaseModel):
    baseline_md: str


class InterlinksReport(BaseModel):
    """Wire shape for ``GET /articles/{id}/interlinks``."""

    incoming: list[InternalLinkOut]
    outgoing: list[InternalLinkOut]


# ---------------------------------------------------------------------------
# Project-scoped article list / create / refresh-due.
# ---------------------------------------------------------------------------


@project_router.get(
    "/{project_id}/articles",
    response_model=PageResponse[ArticleOut],
)
async def list_articles(
    project_id: int,
    page: PaginationParams = Depends(pagination_params),
    status: ArticleStatus | None = None,
    topic_id: int | None = None,
    session: Session = Depends(get_session),
) -> PageResponse[ArticleOut]:
    """List articles for a project; filterable by status and topic."""
    return page_response(
        ArticleRepository(session).list(
            project_id,
            status=status,
            topic_id=topic_id,
            limit=page.limit,
            after_id=page.after,
        )
    )


@project_router.post(
    "/{project_id}/articles",
    response_model=WriteResponse[ArticleOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_article(
    project_id: int,
    body: ArticleCreateRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[ArticleOut]:
    """Insert a fresh article in ``status='briefing'`` with a new ``step_etag``."""
    return write_response(
        ArticleRepository(session).create(
            project_id=project_id,
            topic_id=body.topic_id,
            title=body.title,
            slug=body.slug,
            voice_id=body.voice_id,
            eeat_criteria_version=body.eeat_criteria_version,
            author_id=body.author_id,
            reviewer_author_id=body.reviewer_author_id,
        )
    )


@project_router.get(
    "/{project_id}/articles/refresh-due",
    response_model=PageResponse[ArticleOut],
)
async def list_refresh_due(
    project_id: int,
    page: PaginationParams = Depends(pagination_params),
    session: Session = Depends(get_session),
) -> PageResponse[ArticleOut]:
    """Articles published 90+ days ago whose refresh evaluation is also stale."""
    return page_response(
        ArticleRepository(session).list_due_for_refresh(
            project_id, limit=page.limit, after_id=page.after
        )
    )


# ---------------------------------------------------------------------------
# Article-scoped read / patch / typed verbs.
# ---------------------------------------------------------------------------


def _check_if_match(article: ArticleOut, if_match: str | None) -> None:
    """Raise 412 if ``If-Match: <updated_at iso>`` doesn't match the row.

    PLAN.md L803-L809: UI PATCH carries the article's ``updated_at`` ISO
    string; we compare to the row's current ``updated_at`` and refuse
    stale writes. Absence of the header is allowed (UI may opt out for
    bulk-edits).
    """
    if if_match is None:
        return
    current = article.updated_at.isoformat()
    if if_match.strip() == current:
        return
    raise HTTPException(
        status_code=412,
        detail={
            "detail": "If-Match: stale article version",
            "code": -32008,
            "data": {
                "current_updated_at": current,
                "current_etag": article.step_etag,
            },
            "hint": "Reload the article and retry, or override by omitting If-Match.",
        },
    )


@article_router.get("/{article_id}", response_model=ArticleOut)
async def get_article(
    article_id: int,
    session: Session = Depends(get_session),
) -> ArticleOut:
    """Fetch one article (fat row)."""
    return ArticleRepository(session).get(article_id)


@article_router.patch("/{article_id}", response_model=WriteResponse[ArticleOut])
async def patch_article(
    article_id: int,
    body: ArticlePatchRequest,
    session: Session = Depends(get_session),
    if_match: str | None = Depends(get_if_match),
) -> WriteResponse[ArticleOut]:
    """UI-permissive PATCH; ``If-Match`` enforces optimistic concurrency.

    Slug immutability post-publish: if ``slug`` is in the patch and the
    article is published/refresh_due, the repo's ``update_slug`` raises
    ``ConflictError`` which we surface as 422 (the field is invalid for
    the current state).
    """
    from datetime import UTC
    from datetime import datetime as _dt

    from content_stack.db.models import Article

    repo = ArticleRepository(session)
    current = repo.get(article_id)
    _check_if_match(current, if_match)

    patch = body.model_dump(exclude_unset=True)
    new_slug = patch.pop("slug", None)
    if new_slug is not None and new_slug != current.slug:
        # update_slug commits its own transaction (and refuses post-publish).
        repo.update_slug(article_id, new_slug)

    if not patch:
        # Slug-only patch (or no-op) — re-read the row for the response.
        return WriteResponse[ArticleOut](data=repo.get(article_id), project_id=current.project_id)

    # Apply remaining fields directly — the repo doesn't expose a generic
    # UI-permissive PATCH on the fat row, so we set columns inline. We
    # write a ``manual-edit`` audit row in M3+ when the runs/MCP layer
    # owns the run context; for now the wire-side behaviour matches the
    # spec: arbitrary column updates land via REST.
    row = session.get(Article, article_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": f"article {article_id} not found", "code": -32004},
        )
    for k, v in patch.items():
        if not hasattr(row, k):
            raise HTTPException(
                status_code=422,
                detail={
                    "detail": f"unknown field {k!r}",
                    "code": -32602,
                    "data": {"field": k},
                },
            )
        setattr(row, k, v)
    row.updated_at = _dt.now(tz=UTC).replace(tzinfo=None)
    session.add(row)
    session.commit()
    session.refresh(row)
    return WriteResponse[ArticleOut](data=ArticleOut.model_validate(row), project_id=row.project_id)


# Typed verbs.


def _manual_run_id(
    session: Session,
    *,
    project_id: int,
    article_id: int,
    action: str,
    supplied_run_id: int | None,
) -> tuple[RunRepository, int, bool]:
    """Return a supplied run id or create a REST manual-edit audit run."""
    runs = RunRepository(session)
    if supplied_run_id is not None:
        return runs, supplied_run_id, False
    run = runs.start(
        project_id=project_id,
        kind=RunKind.MANUAL_EDIT,
        metadata_json={"source": "rest", "article_id": article_id, "action": action},
    ).data
    return runs, run.id, True


def _finish_manual_run(
    runs: RunRepository,
    run_id: int,
    *,
    created_here: bool,
    status: RunStatus,
    error: str | None = None,
) -> None:
    if created_here:
        runs.finish(run_id, status=status, error=error)


@article_router.post(
    "/{article_id}/brief",
    response_model=WriteResponse[ArticleOut],
)
async def set_brief(
    article_id: int,
    body: SetBriefRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[ArticleOut]:
    """Write ``brief_json`` and advance ``briefing → outlined``."""
    return write_response(
        ArticleRepository(session).set_brief(
            article_id, body.brief_json, expected_etag=body.expected_etag
        )
    )


@article_router.post(
    "/{article_id}/outline",
    response_model=WriteResponse[ArticleOut],
)
async def set_outline(
    article_id: int,
    body: SetOutlineRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[ArticleOut]:
    """Write ``outline_md`` (status stays ``outlined``)."""
    return write_response(
        ArticleRepository(session).set_outline(
            article_id, body.outline_md, expected_etag=body.expected_etag
        )
    )


@article_router.post(
    "/{article_id}/draft",
    response_model=WriteResponse[ArticleOut],
)
async def set_draft(
    article_id: int,
    body: SetDraftRequest,
    append: bool = False,
    session: Session = Depends(get_session),
) -> WriteResponse[ArticleOut]:
    """Write ``draft_md``; ``?append=true`` to concatenate (skills 7/8/9)."""
    return write_response(
        ArticleRepository(session).set_draft(
            article_id,
            body.draft_md,
            expected_etag=body.expected_etag,
            append=append,
        )
    )


@article_router.post(
    "/{article_id}/draft/mark-drafted",
    response_model=WriteResponse[ArticleOut],
)
async def mark_drafted(
    article_id: int,
    body: MarkDraftedRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[ArticleOut]:
    """Advance ``outlined → drafted`` once the procedure runner ends draft phase."""
    return write_response(
        ArticleRepository(session).mark_drafted(article_id, expected_etag=body.expected_etag)
    )


@article_router.post(
    "/{article_id}/edit",
    response_model=WriteResponse[ArticleOut],
)
async def set_edited(
    article_id: int,
    body: SetEditedRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[ArticleOut]:
    """Write ``edited_md`` and advance ``drafted → edited``."""
    return write_response(
        ArticleRepository(session).set_edited(
            article_id, body.edited_md, expected_etag=body.expected_etag
        )
    )


@article_router.post(
    "/{article_id}/eeat-pass",
    response_model=WriteResponse[ArticleOut],
)
async def mark_eeat_passed(
    article_id: int,
    body: MarkEeatPassedRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[ArticleOut]:
    """Advance ``edited → eeat_passed``; freeze rubric version + run id."""
    current = ArticleRepository(session).get(article_id)
    runs, run_id, created_here = _manual_run_id(
        session,
        project_id=current.project_id,
        article_id=article_id,
        action="mark-eeat-passed",
        supplied_run_id=body.run_id,
    )
    try:
        out = ArticleRepository(session).mark_eeat_passed(
            article_id,
            expected_etag=body.expected_etag,
            run_id=run_id,
            eeat_criteria_version=body.eeat_criteria_version,
        )
    except Exception as exc:
        _finish_manual_run(
            runs, run_id, created_here=created_here, status=RunStatus.FAILED, error=str(exc)
        )
        raise
    _finish_manual_run(runs, run_id, created_here=created_here, status=RunStatus.SUCCESS)
    return write_response(out)


@article_router.post(
    "/{article_id}/publish",
    response_model=WriteResponse[ArticleOut],
)
async def mark_published(
    article_id: int,
    body: MarkPublishedRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[ArticleOut]:
    """Advance ``eeat_passed → published``; slug immutable from here."""
    current = ArticleRepository(session).get(article_id)
    runs, run_id, created_here = _manual_run_id(
        session,
        project_id=current.project_id,
        article_id=article_id,
        action="publish",
        supplied_run_id=body.run_id,
    )
    try:
        out = ArticleRepository(session).mark_published(
            article_id, expected_etag=body.expected_etag, run_id=run_id
        )
    except Exception as exc:
        _finish_manual_run(
            runs, run_id, created_here=created_here, status=RunStatus.FAILED, error=str(exc)
        )
        raise
    _finish_manual_run(runs, run_id, created_here=created_here, status=RunStatus.SUCCESS)
    return write_response(out)


@article_router.post(
    "/{article_id}/refresh-due",
    response_model=WriteResponse[ArticleOut],
)
async def mark_refresh_due(
    article_id: int,
    body: MarkRefreshDueRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[ArticleOut]:
    """Manually move a published article to ``refresh_due`` (UI escape hatch)."""
    return write_response(
        ArticleRepository(session).mark_refresh_due(article_id, reason=body.reason)
    )


# Versioning.


@article_router.post(
    "/{article_id}/version",
    response_model=WriteResponse[ArticleVersionOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_version(
    article_id: int,
    session: Session = Depends(get_session),
) -> WriteResponse[ArticleVersionOut]:
    """Snapshot the live row into ``article_versions`` (procedure 7 / refresh)."""
    return write_response(ArticleRepository(session).create_version(article_id))


@article_router.get(
    "/{article_id}/versions",
    response_model=PageResponse[ArticleVersionOut],
)
async def list_versions(
    article_id: int,
    page: PaginationParams = Depends(pagination_params),
    session: Session = Depends(get_session),
) -> PageResponse[ArticleVersionOut]:
    """Cursor-paginated version history."""
    return page_response(
        ArticleRepository(session).list_versions(article_id, limit=page.limit, after_id=page.after)
    )


# ---------------------------------------------------------------------------
# Assets sub-resource.
# ---------------------------------------------------------------------------


@article_router.get(
    "/{article_id}/assets",
    response_model=list[ArticleAssetOut],
)
async def list_assets(
    article_id: int,
    session: Session = Depends(get_session),
) -> list[ArticleAssetOut]:
    """All assets for an article ordered by id."""
    return ArticleAssetRepository(session).list(article_id)


@article_router.post(
    "/{article_id}/assets",
    response_model=WriteResponse[ArticleAssetOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_asset(
    article_id: int,
    body: AssetCreateRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[ArticleAssetOut]:
    """Insert a hero / inline / OG asset row."""
    return write_response(
        ArticleAssetRepository(session).create(
            article_id=article_id,
            kind=body.kind,
            url=body.url,
            prompt=body.prompt,
            alt_text=body.alt_text,
            width=body.width,
            height=body.height,
            position=body.position,
        )
    )


@article_router.patch(
    "/{article_id}/assets/{asset_id}",
    response_model=WriteResponse[ArticleAssetOut],
)
async def update_asset(
    article_id: int,
    asset_id: int,
    body: AssetUpdateRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[ArticleAssetOut]:
    """Patch an asset (alt-text-auditor, hero-prompt-tweak)."""
    _ = article_id
    patch = body.model_dump(exclude_unset=True)
    return write_response(ArticleAssetRepository(session).update(asset_id, **patch))


@article_router.delete(
    "/{article_id}/assets/{asset_id}",
    response_model=WriteResponse[ArticleAssetOut],
)
async def delete_asset(
    article_id: int,
    asset_id: int,
    session: Session = Depends(get_session),
) -> WriteResponse[ArticleAssetOut]:
    """Hard-delete an asset row."""
    _ = article_id
    return write_response(ArticleAssetRepository(session).remove(asset_id))


# ---------------------------------------------------------------------------
# Sources sub-resource.
# ---------------------------------------------------------------------------


@article_router.get(
    "/{article_id}/sources",
    response_model=list[ResearchSourceOut],
)
async def list_sources(
    article_id: int,
    session: Session = Depends(get_session),
) -> list[ResearchSourceOut]:
    """All research sources / citations for an article."""
    return ResearchSourceRepository(session).list(article_id)


@article_router.post(
    "/{article_id}/sources",
    response_model=WriteResponse[ResearchSourceOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_source(
    article_id: int,
    body: SourceCreateRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[ResearchSourceOut]:
    """Insert a research-source / citation row."""
    return write_response(
        ResearchSourceRepository(session).add(
            article_id=article_id,
            url=body.url,
            title=body.title,
            snippet=body.snippet,
            used=body.used,
        )
    )


# ---------------------------------------------------------------------------
# Schema sub-resource.
# ---------------------------------------------------------------------------


@article_router.get(
    "/{article_id}/schema",
    response_model=list[SchemaEmitOut],
)
async def list_schema_emits(
    article_id: int,
    session: Session = Depends(get_session),
) -> list[SchemaEmitOut]:
    """All JSON-LD schema rows for an article ordered by position."""
    return SchemaEmitRepository(session).list_for_article(article_id)


@article_router.put(
    "/{article_id}/schema/{schema_type}",
    response_model=WriteResponse[SchemaEmitOut],
)
async def put_schema(
    article_id: int,
    schema_type: str,
    body: SchemaSetRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[SchemaEmitOut]:
    """Upsert a JSON-LD schema-emit row (``is_primary`` exactly-one)."""
    return write_response(
        SchemaEmitRepository(session).set(
            article_id=article_id,
            type=schema_type,
            schema_json=body.schema_json,
            is_primary=body.is_primary,
            position=body.position,
            version_published=body.version_published,
        )
    )


@article_router.post(
    "/{article_id}/schema/{schema_id}/validate",
    response_model=WriteResponse[SchemaEmitOut],
)
async def validate_schema(
    article_id: int,
    schema_id: int,
    session: Session = Depends(get_session),
) -> WriteResponse[SchemaEmitOut]:
    """Mark a schema-emit row as validated (M5 swaps in Google testing API)."""
    _ = article_id
    return write_response(SchemaEmitRepository(session).validate(schema_id))


# ---------------------------------------------------------------------------
# Publishes sub-resource.
# ---------------------------------------------------------------------------


@article_router.get(
    "/{article_id}/publishes",
    response_model=list[ArticlePublishOut],
)
async def list_publishes(
    article_id: int,
    session: Session = Depends(get_session),
) -> list[ArticlePublishOut]:
    """All publish records for an article."""
    return ArticlePublishRepository(session).list_for_article(article_id)


@article_router.post(
    "/{article_id}/publishes",
    response_model=WriteResponse[ArticlePublishOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_publish(
    article_id: int,
    body: PublishCreateRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[ArticlePublishOut]:
    """Upsert a publish record (``article_id, target_id, version_published``)."""
    return write_response(
        ArticlePublishRepository(session).record_publish(
            article_id=article_id,
            target_id=body.target_id,
            version_published=body.version_published,
            published_url=body.published_url,
            frontmatter_json=body.frontmatter_json,
            status=body.status,
            error=body.error,
            published_at=body.published_at,
        )
    )


@article_router.post(
    "/{article_id}/publishes/canonical",
    response_model=WriteResponse[ArticleOut],
)
async def set_canonical(
    article_id: int,
    body: CanonicalSetRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[ArticleOut]:
    """Set ``articles.canonical_target_id`` for SEO canonical-URL emission."""
    return write_response(
        ArticlePublishRepository(session).set_canonical(
            article_id=article_id, target_id=body.target_id
        )
    )


# ---------------------------------------------------------------------------
# EEAT sub-resource — ``GET`` returns score + evaluations; ``POST`` bulk-records.
# ---------------------------------------------------------------------------


@article_router.get(
    "/{article_id}/eeat",
    response_model=EeatReportResponse,
)
async def get_eeat_report(
    article_id: int,
    run_id: int | None = None,
    session: Session = Depends(get_session),
) -> EeatReportResponse:
    """Return the EEAT score + raw evaluations for an article (optional run filter).

    PLAN.md L588: ``GET /articles/{id}/eeat`` returns "rubric scores per
    dimension + failed items". ``run_id`` defaults to the most recent
    run that touched the article.
    """
    repo = EeatEvaluationRepository(session)
    evaluations = repo.list(article_id=article_id, run_id=run_id)
    if not evaluations:
        # No evaluations yet — return an empty report shape so the UI can
        # still render the gates as "not yet evaluated".
        empty = EeatScoreReport(
            dimension_scores={},
            system_scores={"GEO": 0.0, "SEO": 0.0},
            coverage={},
            vetoes_failed=[],
            total_evaluations=0,
        )
        return EeatReportResponse(score=empty, evaluations=[])
    target_run = run_id if run_id is not None else evaluations[-1].run_id
    return EeatReportResponse(
        score=repo.score(article_id=article_id, run_id=target_run),
        evaluations=evaluations,
    )


@article_router.post(
    "/{article_id}/eeat",
    response_model=WriteResponse[list[EeatEvaluationOut]],
    status_code=status.HTTP_201_CREATED,
)
async def bulk_record_eeat(
    article_id: int,
    body: EeatBulkRecordRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[list[EeatEvaluationOut]]:
    """Bulk-write the per-criterion EEAT verdicts for one run."""
    return write_response(
        EeatEvaluationRepository(session).bulk_record(
            article_id=article_id,
            run_id=body.run_id,
            evaluations=[
                EeatEvaluationCreate(criterion_id=e.criterion_id, verdict=e.verdict, notes=e.notes)
                for e in body.evaluations
            ],
        )
    )


# ---------------------------------------------------------------------------
# Drift sub-resource.
# ---------------------------------------------------------------------------


@article_router.get(
    "/{article_id}/drift",
    response_model=list[DriftBaselineOut],
)
async def list_drift(
    article_id: int,
    session: Session = Depends(get_session),
) -> list[DriftBaselineOut]:
    """All drift baselines for an article."""
    return DriftBaselineRepository(session).list(article_id)


@article_router.post(
    "/{article_id}/drift/snapshot",
    response_model=WriteResponse[DriftBaselineOut],
    status_code=status.HTTP_201_CREATED,
)
async def snapshot_drift(
    article_id: int,
    body: DriftSnapshotRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[DriftBaselineOut]:
    """Record a drift baseline (the diff engine itself ships in M5)."""
    return write_response(
        DriftBaselineRepository(session).snapshot(
            article_id=article_id, baseline_md=body.baseline_md
        )
    )


# ---------------------------------------------------------------------------
# Interlinks for one article.
# ---------------------------------------------------------------------------


@article_router.get(
    "/{article_id}/interlinks",
    response_model=InterlinksReport,
)
async def get_article_interlinks(
    article_id: int,
    session: Session = Depends(get_session),
) -> InterlinksReport:
    """Return both directions of internal-link rows touching ``article_id``.

    The repo's ``list`` filters by either ``from_article_id`` or
    ``to_article_id``; we fetch each direction with a generous limit
    so the article-detail UI doesn't paginate on the relationship view.
    """
    article = ArticleRepository(session).get(article_id)
    repo = InterlinkRepository(session)
    incoming = repo.list(article.project_id, to_article_id=article_id, limit=200).items
    outgoing = repo.list(article.project_id, from_article_id=article_id, limit=200).items
    return InterlinksReport(incoming=list(incoming), outgoing=list(outgoing))


# Path validators (just so mypy / runtime see they're declared).
_ = Path

__all__ = ["article_router", "project_router"]
