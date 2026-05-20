"""Hidden vendor-operation tools for the agent toolkit.

These tools are registered in the daemon MCP catalog so the bridge can
describe/call them through ``toolbox.describe`` and ``toolbox.call``. They
must stay out of the plugin's direct visible tool list; agents should see them
only when setup grants or the current procedure step's ``allowed_tools`` expose
them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
from pydantic import ConfigDict, Field

from content_stack.config import Settings
from content_stack.integrations.ahrefs import AhrefsIntegration
from content_stack.integrations.dataforseo import DataForSeoIntegration
from content_stack.integrations.firecrawl import FirecrawlIntegration
from content_stack.integrations.google_paa import GooglePaaIntegration
from content_stack.integrations.gsc import GscIntegration
from content_stack.integrations.jina_reader import JinaReaderIntegration
from content_stack.integrations.openai_images import OpenAIImagesIntegration
from content_stack.integrations.reddit import RedditIntegration
from content_stack.mcp.context import MCPContext
from content_stack.mcp.contract import MCPInput
from content_stack.mcp.server import ToolRegistry, ToolSpec
from content_stack.mcp.streaming import ProgressEmitter
from content_stack.repositories.base import NotFoundError, ValidationError
from content_stack.repositories.projects import (
    IntegrationBudgetRepository,
    IntegrationCredentialRepository,
)
from content_stack.repositories.runs import RunStepCallRepository


class VendorToolInput(MCPInput):
    """Shared fields for project-scoped hidden vendor tools."""

    project_id: int
    run_step_id: int | None = None


class DataForSeoSerpInput(VendorToolInput):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"project_id": 1, "keyword": "best crm software"}},
    )

    keyword: str
    location: str = "United States"
    language: str = "en"
    depth: int = Field(default=100, ge=1, le=700)


class DataForSeoKeywordVolumeInput(VendorToolInput):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"project_id": 1, "keywords": ["crm software"]}},
    )

    keywords: list[str] = Field(min_length=1)
    location: str = "United States"
    language: str = "en"


class DataForSeoDomainIntersectionInput(VendorToolInput):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"project_id": 1, "domains": ["a.com", "b.com"]}},
    )

    domains: list[str] = Field(min_length=2, max_length=2)
    location: str = "United States"
    language: str = "en"


class DataForSeoKeywordsForSiteInput(VendorToolInput):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"project_id": 1, "target": "example.com"}},
    )

    target: str
    location: str = "United States"
    language: str = "en"


class DataForSeoPaaInput(VendorToolInput):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"project_id": 1, "keyword": "crm software"}},
    )

    keyword: str
    location: str = "United States"
    language: str = "en"


class FirecrawlScrapeInput(VendorToolInput):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"project_id": 1, "url": "https://example.com"}},
    )

    url: str
    formats: list[str] | None = None
    only_main_content: bool = True


class FirecrawlCrawlInput(VendorToolInput):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"project_id": 1, "url": "https://example.com"}},
    )

    url: str
    max_depth: int = Field(default=2, ge=0, le=10)
    limit: int = Field(default=25, ge=1, le=1000)


class FirecrawlMapInput(VendorToolInput):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"project_id": 1, "url": "https://example.com"}},
    )

    url: str
    search: str | None = None


class FirecrawlExtractInput(VendorToolInput):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        json_schema_extra={"example": {"project_id": 1, "url": "https://example.com"}},
    )

    url: str
    extraction_schema: dict[str, Any] | None = Field(default=None, alias="schema")
    prompt: str | None = None


class OpenAIImagesGenerateInput(VendorToolInput):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "project_id": 1,
                "prompt": "Editorial hero image for an article about technical SEO",
            }
        },
    )

    prompt: str
    size: str = "1536x1024"
    quality: str = "medium"
    n: int = Field(default=1, ge=1, le=10)
    model: str = "gpt-image-1.5"
    output_format: str = "webp"


class RedditSearchSubredditInput(VendorToolInput):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"project_id": 1, "subreddit": "SEO", "query": "content brief"}
        },
    )

    subreddit: str
    query: str
    sort: str = "relevance"
    limit: int = Field(default=25, ge=1, le=100)


class RedditTopQuestionsInput(VendorToolInput):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"project_id": 1, "subreddit": "SEO"}},
    )

    subreddit: str
    time_filter: str = "month"
    limit: int = Field(default=50, ge=1, le=100)


class GooglePaaExtractInput(VendorToolInput):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"project_id": 1, "query": "best seo tools"}},
    )

    query: str


class JinaReadInput(VendorToolInput):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"project_id": 1, "url": "https://example.com"}},
    )

    url: str


class AhrefsKeywordsForSiteInput(VendorToolInput):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"project_id": 1, "target": "example.com"}},
    )

    target: str
    country: str = "us"
    limit: int = Field(default=100, ge=1, le=1000)
    date_: str | None = None


class AhrefsTopBacklinksInput(VendorToolInput):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"project_id": 1, "target": "example.com"}},
    )

    target: str
    mode: str = "domain"
    limit: int = Field(default=100, ge=1, le=1000)


class GscSearchAnalyticsInput(VendorToolInput):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "project_id": 1,
                "site_url": "sc-domain:example.com",
                "start_date": "2026-05-01",
                "end_date": "2026-05-07",
                "dimensions": ["page", "query"],
            }
        },
    )

    site_url: str
    start_date: str
    end_date: str
    dimensions: list[str] | None = None
    row_limit: int = Field(default=1000, ge=1, le=25000)


class GscInspectUrlInput(VendorToolInput):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "project_id": 1,
                "site_url": "sc-domain:example.com",
                "inspection_url": "https://example.com/blog/post",
            }
        },
    )

    site_url: str
    inspection_url: str


class GscBulkInspectInput(VendorToolInput):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "project_id": 1,
                "site_url": "sc-domain:example.com",
                "urls": ["https://example.com/blog/post"],
            }
        },
    )

    site_url: str
    urls: list[str] = Field(min_length=1, max_length=100)


class GscPagespeedInput(VendorToolInput):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"project_id": 1, "url": "https://example.com"}},
    )

    url: str
    strategy: str = "mobile"


def _result_payload(
    *,
    vendor: str,
    credential_id: int | None,
    data: Any,
    cost_usd: float | None = None,
    duration_ms: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "vendor": vendor,
        "credential_id": credential_id,
        "data": data,
    }
    if cost_usd is not None:
        payload["cost_usd"] = cost_usd
    if duration_ms is not None:
        payload["duration_ms"] = duration_ms
    return payload


def _run_step_call_repo(ctx: MCPContext, run_step_id: int | None) -> RunStepCallRepository | None:
    if run_step_id is None:
        return None
    return RunStepCallRepository(ctx.session)


def _credential(
    ctx: MCPContext,
    *,
    project_id: int,
    kind: str,
) -> tuple[int, bytes, dict[str, Any]]:
    repo = IntegrationCredentialRepository(ctx.session)
    credential_id, payload = repo.get_decrypted_for(project_id, kind)
    row = repo.fetch_row(credential_id)
    return credential_id, payload, row.config_json or {}


def _dataforseo(
    ctx: MCPContext,
    *,
    project_id: int,
    run_step_id: int | None,
    http: httpx.AsyncClient,
) -> tuple[int, DataForSeoIntegration]:
    credential_id, payload, config = _credential(ctx, project_id=project_id, kind="dataforseo")
    login = str(config.get("login") or "")
    if not login:
        raise ValidationError(
            "DataForSEO credential requires config_json.login",
            data={"project_id": project_id, "kind": "dataforseo"},
        )
    return credential_id, DataForSeoIntegration(
        payload=payload,
        project_id=project_id,
        http=http,
        login=login,
        budget_repo=IntegrationBudgetRepository(ctx.session),
        run_step_call_repo=_run_step_call_repo(ctx, run_step_id),
        run_step_id=run_step_id,
        run_id=ctx.run_id,
    )


def _firecrawl(
    ctx: MCPContext,
    *,
    project_id: int,
    run_step_id: int | None,
    http: httpx.AsyncClient,
) -> tuple[int, FirecrawlIntegration]:
    credential_id, payload, _config = _credential(ctx, project_id=project_id, kind="firecrawl")
    return credential_id, FirecrawlIntegration(
        payload=payload,
        project_id=project_id,
        http=http,
        budget_repo=IntegrationBudgetRepository(ctx.session),
        run_step_call_repo=_run_step_call_repo(ctx, run_step_id),
        run_step_id=run_step_id,
        run_id=ctx.run_id,
    )


def _openai_images(
    ctx: MCPContext,
    *,
    project_id: int,
    run_step_id: int | None,
    http: httpx.AsyncClient,
) -> tuple[int, OpenAIImagesIntegration]:
    credential_id, payload, _config = _credential(ctx, project_id=project_id, kind="openai-images")
    return credential_id, OpenAIImagesIntegration(
        payload=payload,
        project_id=project_id,
        http=http,
        asset_dir=_generated_assets_dir(ctx),
        budget_repo=IntegrationBudgetRepository(ctx.session),
        run_step_call_repo=_run_step_call_repo(ctx, run_step_id),
        run_step_id=run_step_id,
        run_id=ctx.run_id,
    )


def _generated_assets_dir(ctx: MCPContext) -> Path:
    settings = getattr(getattr(ctx, "procedure_runner", None), "_settings", None)
    if settings is not None:
        return settings.generated_assets_dir
    return Settings().generated_assets_dir


def _reddit(
    ctx: MCPContext,
    *,
    project_id: int,
    run_step_id: int | None,
    http: httpx.AsyncClient,
) -> tuple[int, RedditIntegration]:
    credential_id, payload, _config = _credential(ctx, project_id=project_id, kind="reddit")
    return credential_id, RedditIntegration(
        payload=payload,
        project_id=project_id,
        http=http,
        budget_repo=IntegrationBudgetRepository(ctx.session),
        run_step_call_repo=_run_step_call_repo(ctx, run_step_id),
        run_step_id=run_step_id,
        run_id=ctx.run_id,
    )


def _jina(
    ctx: MCPContext,
    *,
    project_id: int,
    run_step_id: int | None,
    http: httpx.AsyncClient,
) -> tuple[int | None, JinaReaderIntegration]:
    try:
        credential_id, payload, _config = _credential(ctx, project_id=project_id, kind="jina")
    except NotFoundError:
        credential_id = None
        payload = b""
    return credential_id, JinaReaderIntegration(
        payload=payload,
        project_id=project_id,
        http=http,
        budget_repo=IntegrationBudgetRepository(ctx.session),
        run_step_call_repo=_run_step_call_repo(ctx, run_step_id),
        run_step_id=run_step_id,
        run_id=ctx.run_id,
    )


def _ahrefs(
    ctx: MCPContext,
    *,
    project_id: int,
    run_step_id: int | None,
    http: httpx.AsyncClient,
) -> tuple[int, AhrefsIntegration]:
    credential_id, payload, _config = _credential(ctx, project_id=project_id, kind="ahrefs")
    return credential_id, AhrefsIntegration(
        payload=payload,
        project_id=project_id,
        http=http,
        budget_repo=IntegrationBudgetRepository(ctx.session),
        run_step_call_repo=_run_step_call_repo(ctx, run_step_id),
        run_step_id=run_step_id,
        run_id=ctx.run_id,
    )


def _gsc(
    ctx: MCPContext,
    *,
    project_id: int,
    run_step_id: int | None,
    http: httpx.AsyncClient,
    require_credential: bool = True,
) -> tuple[int | None, GscIntegration]:
    try:
        credential_id, payload, _config = _credential(ctx, project_id=project_id, kind="gsc")
    except NotFoundError:
        if require_credential:
            raise
        credential_id = None
        payload = b'{"access_token":""}'
    return credential_id, GscIntegration(
        payload=payload,
        project_id=project_id,
        http=http,
        budget_repo=IntegrationBudgetRepository(ctx.session),
        run_step_call_repo=_run_step_call_repo(ctx, run_step_id),
        run_step_id=run_step_id,
        run_id=ctx.run_id,
    )


async def _dataforseo_serp(
    inp: DataForSeoSerpInput, ctx: MCPContext, _emit: ProgressEmitter
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as http:
        credential_id, client = _dataforseo(
            ctx, project_id=inp.project_id, run_step_id=inp.run_step_id, http=http
        )
        result = await client.serp(
            keyword=inp.keyword,
            location=inp.location,
            language=inp.language,
            depth=inp.depth,
        )
    return _result_payload(
        vendor="dataforseo",
        credential_id=credential_id,
        data=result.data,
        cost_usd=result.cost_usd,
        duration_ms=result.duration_ms,
    )


async def _dataforseo_keyword_volume(
    inp: DataForSeoKeywordVolumeInput, ctx: MCPContext, _emit: ProgressEmitter
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as http:
        credential_id, client = _dataforseo(
            ctx, project_id=inp.project_id, run_step_id=inp.run_step_id, http=http
        )
        result = await client.keyword_volume(
            keywords=inp.keywords,
            location=inp.location,
            language=inp.language,
        )
    return _result_payload(
        vendor="dataforseo",
        credential_id=credential_id,
        data=result.data,
        cost_usd=result.cost_usd,
        duration_ms=result.duration_ms,
    )


async def _dataforseo_domain_intersection(
    inp: DataForSeoDomainIntersectionInput, ctx: MCPContext, _emit: ProgressEmitter
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as http:
        credential_id, client = _dataforseo(
            ctx, project_id=inp.project_id, run_step_id=inp.run_step_id, http=http
        )
        result = await client.intersection(
            domains=inp.domains,
            location=inp.location,
            language=inp.language,
        )
    return _result_payload(
        vendor="dataforseo",
        credential_id=credential_id,
        data=result.data,
        cost_usd=result.cost_usd,
        duration_ms=result.duration_ms,
    )


async def _dataforseo_keywords_for_site(
    inp: DataForSeoKeywordsForSiteInput, ctx: MCPContext, _emit: ProgressEmitter
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as http:
        credential_id, client = _dataforseo(
            ctx, project_id=inp.project_id, run_step_id=inp.run_step_id, http=http
        )
        result = await client.keywords_for_site(
            target=inp.target,
            location=inp.location,
            language=inp.language,
        )
    return _result_payload(
        vendor="dataforseo",
        credential_id=credential_id,
        data=result.data,
        cost_usd=result.cost_usd,
        duration_ms=result.duration_ms,
    )


async def _dataforseo_paa(
    inp: DataForSeoPaaInput, ctx: MCPContext, _emit: ProgressEmitter
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as http:
        credential_id, client = _dataforseo(
            ctx, project_id=inp.project_id, run_step_id=inp.run_step_id, http=http
        )
        result = await client.paa(
            keyword=inp.keyword,
            location=inp.location,
            language=inp.language,
        )
    return _result_payload(
        vendor="dataforseo",
        credential_id=credential_id,
        data=result.data,
        cost_usd=result.cost_usd,
        duration_ms=result.duration_ms,
    )


async def _firecrawl_scrape(
    inp: FirecrawlScrapeInput, ctx: MCPContext, _emit: ProgressEmitter
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as http:
        credential_id, client = _firecrawl(
            ctx, project_id=inp.project_id, run_step_id=inp.run_step_id, http=http
        )
        result = await client.scrape(
            url=inp.url,
            formats=inp.formats,
            only_main_content=inp.only_main_content,
        )
    return _result_payload(
        vendor="firecrawl",
        credential_id=credential_id,
        data=result.data,
        cost_usd=result.cost_usd,
        duration_ms=result.duration_ms,
    )


async def _firecrawl_crawl(
    inp: FirecrawlCrawlInput, ctx: MCPContext, _emit: ProgressEmitter
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as http:
        credential_id, client = _firecrawl(
            ctx, project_id=inp.project_id, run_step_id=inp.run_step_id, http=http
        )
        result = await client.crawl(url=inp.url, max_depth=inp.max_depth, limit=inp.limit)
    return _result_payload(
        vendor="firecrawl",
        credential_id=credential_id,
        data=result.data,
        cost_usd=result.cost_usd,
        duration_ms=result.duration_ms,
    )


async def _firecrawl_map(
    inp: FirecrawlMapInput, ctx: MCPContext, _emit: ProgressEmitter
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as http:
        credential_id, client = _firecrawl(
            ctx, project_id=inp.project_id, run_step_id=inp.run_step_id, http=http
        )
        result = await client.map(url=inp.url, search=inp.search)
    return _result_payload(
        vendor="firecrawl",
        credential_id=credential_id,
        data=result.data,
        cost_usd=result.cost_usd,
        duration_ms=result.duration_ms,
    )


async def _firecrawl_extract(
    inp: FirecrawlExtractInput, ctx: MCPContext, _emit: ProgressEmitter
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as http:
        credential_id, client = _firecrawl(
            ctx, project_id=inp.project_id, run_step_id=inp.run_step_id, http=http
        )
        result = await client.extract(
            url=inp.url,
            schema=inp.extraction_schema,
            prompt=inp.prompt,
        )
    return _result_payload(
        vendor="firecrawl",
        credential_id=credential_id,
        data=result.data,
        cost_usd=result.cost_usd,
        duration_ms=result.duration_ms,
    )


async def _openai_images_generate(
    inp: OpenAIImagesGenerateInput, ctx: MCPContext, _emit: ProgressEmitter
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as http:
        credential_id, client = _openai_images(
            ctx, project_id=inp.project_id, run_step_id=inp.run_step_id, http=http
        )
        result = await client.generate(
            prompt=inp.prompt,
            size=inp.size,
            quality=inp.quality,
            n=inp.n,
            model=inp.model,
            output_format=inp.output_format,
        )
    return _result_payload(
        vendor="openai-images",
        credential_id=credential_id,
        data=result.data,
        cost_usd=result.cost_usd,
        duration_ms=result.duration_ms,
    )


async def _reddit_search_subreddit(
    inp: RedditSearchSubredditInput, ctx: MCPContext, _emit: ProgressEmitter
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as http:
        credential_id, client = _reddit(
            ctx, project_id=inp.project_id, run_step_id=inp.run_step_id, http=http
        )
        result = await client.search_subreddit(
            subreddit=inp.subreddit,
            query=inp.query,
            sort=inp.sort,
            limit=inp.limit,
        )
    return _result_payload(
        vendor="reddit",
        credential_id=credential_id,
        data=result.data,
        cost_usd=result.cost_usd,
        duration_ms=result.duration_ms,
    )


async def _reddit_top_questions(
    inp: RedditTopQuestionsInput, ctx: MCPContext, _emit: ProgressEmitter
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as http:
        credential_id, client = _reddit(
            ctx, project_id=inp.project_id, run_step_id=inp.run_step_id, http=http
        )
        result = await client.top_questions(
            subreddit=inp.subreddit,
            time_filter=inp.time_filter,
            limit=inp.limit,
        )
    return _result_payload(
        vendor="reddit",
        credential_id=credential_id,
        data=result.data,
        cost_usd=result.cost_usd,
        duration_ms=result.duration_ms,
    )


async def _google_paa_extract(
    inp: GooglePaaExtractInput, ctx: MCPContext, _emit: ProgressEmitter
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as http:
        credential_id, firecrawl = _firecrawl(
            ctx, project_id=inp.project_id, run_step_id=inp.run_step_id, http=http
        )
        client = GooglePaaIntegration(
            payload=b"",
            project_id=inp.project_id,
            http=http,
            firecrawl=firecrawl,
        )
        data = await client.extract(query=inp.query)
    return _result_payload(vendor="google-paa", credential_id=credential_id, data=data)


async def _jina_read(inp: JinaReadInput, ctx: MCPContext, _emit: ProgressEmitter) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as http:
        credential_id, client = _jina(
            ctx, project_id=inp.project_id, run_step_id=inp.run_step_id, http=http
        )
        result = await client.read(url=inp.url)
    return _result_payload(
        vendor="jina",
        credential_id=credential_id,
        data=result.data,
        cost_usd=result.cost_usd,
        duration_ms=result.duration_ms,
    )


async def _ahrefs_keywords_for_site(
    inp: AhrefsKeywordsForSiteInput, ctx: MCPContext, _emit: ProgressEmitter
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as http:
        credential_id, client = _ahrefs(
            ctx, project_id=inp.project_id, run_step_id=inp.run_step_id, http=http
        )
        result = await client.keywords_for_site(
            target=inp.target,
            country=inp.country,
            limit=inp.limit,
            date_=inp.date_,
        )
    return _result_payload(
        vendor="ahrefs",
        credential_id=credential_id,
        data=result.data,
        cost_usd=result.cost_usd,
        duration_ms=result.duration_ms,
    )


async def _ahrefs_top_backlinks(
    inp: AhrefsTopBacklinksInput, ctx: MCPContext, _emit: ProgressEmitter
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as http:
        credential_id, client = _ahrefs(
            ctx, project_id=inp.project_id, run_step_id=inp.run_step_id, http=http
        )
        result = await client.top_backlinks(
            target=inp.target,
            mode=inp.mode,
            limit=inp.limit,
        )
    return _result_payload(
        vendor="ahrefs",
        credential_id=credential_id,
        data=result.data,
        cost_usd=result.cost_usd,
        duration_ms=result.duration_ms,
    )


async def _gsc_search_analytics(
    inp: GscSearchAnalyticsInput, ctx: MCPContext, _emit: ProgressEmitter
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as http:
        credential_id, client = _gsc(
            ctx, project_id=inp.project_id, run_step_id=inp.run_step_id, http=http
        )
        result = await client.search_analytics(
            site_url=inp.site_url,
            start_date=inp.start_date,
            end_date=inp.end_date,
            dimensions=inp.dimensions,
            row_limit=inp.row_limit,
        )
    return _result_payload(
        vendor="gsc",
        credential_id=credential_id,
        data=result.data,
        cost_usd=result.cost_usd,
        duration_ms=result.duration_ms,
    )


async def _gsc_inspect_url(
    inp: GscInspectUrlInput, ctx: MCPContext, _emit: ProgressEmitter
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as http:
        credential_id, client = _gsc(
            ctx, project_id=inp.project_id, run_step_id=inp.run_step_id, http=http
        )
        result = await client.inspect_url(
            site_url=inp.site_url,
            inspection_url=inp.inspection_url,
        )
    return _result_payload(
        vendor="gsc",
        credential_id=credential_id,
        data=result.data,
        cost_usd=result.cost_usd,
        duration_ms=result.duration_ms,
    )


async def _gsc_bulk_inspect(
    inp: GscBulkInspectInput, ctx: MCPContext, _emit: ProgressEmitter
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as http:
        credential_id, client = _gsc(
            ctx, project_id=inp.project_id, run_step_id=inp.run_step_id, http=http
        )
        results = await client.bulk_inspect(site_url=inp.site_url, urls=inp.urls)
    return _result_payload(
        vendor="gsc",
        credential_id=credential_id,
        data=[result.data for result in results],
        cost_usd=sum(result.cost_usd for result in results),
        duration_ms=sum(result.duration_ms for result in results),
    )


async def _gsc_pagespeed(
    inp: GscPagespeedInput, ctx: MCPContext, _emit: ProgressEmitter
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as http:
        credential_id, client = _gsc(
            ctx,
            project_id=inp.project_id,
            run_step_id=inp.run_step_id,
            http=http,
            require_credential=False,
        )
        result = await client.pagespeed(url=inp.url, strategy=inp.strategy)
    return _result_payload(
        vendor="gsc",
        credential_id=credential_id,
        data=result.data,
        cost_usd=result.cost_usd,
        duration_ms=result.duration_ms,
    )


def register(registry: ToolRegistry) -> None:
    """Register hidden vendor-operation tools."""
    registry.register(
        ToolSpec(
            "dataforseo.serp",
            "Fetch Google organic SERP results for one keyword.",
            DataForSeoSerpInput,
            dict[str, Any],
            _dataforseo_serp,
        )
    )
    registry.register(
        ToolSpec(
            "dataforseo.keywordVolume",
            "Fetch Google Ads search volume metrics for keywords.",
            DataForSeoKeywordVolumeInput,
            dict[str, Any],
            _dataforseo_keyword_volume,
        )
    )
    registry.register(
        ToolSpec(
            "dataforseo.domainIntersection",
            "Fetch overlapping organic keywords for two domains.",
            DataForSeoDomainIntersectionInput,
            dict[str, Any],
            _dataforseo_domain_intersection,
        )
    )
    registry.register(
        ToolSpec(
            "dataforseo.keywordsForSite",
            "Fetch organic keyword inventory for a domain or URL.",
            DataForSeoKeywordsForSiteInput,
            dict[str, Any],
            _dataforseo_keywords_for_site,
        )
    )
    registry.register(
        ToolSpec(
            "dataforseo.paa",
            "Fetch People Also Ask SERP data for one keyword.",
            DataForSeoPaaInput,
            dict[str, Any],
            _dataforseo_paa,
        )
    )
    registry.register(
        ToolSpec(
            "firecrawl.scrape",
            "Scrape one URL via Firecrawl.",
            FirecrawlScrapeInput,
            dict[str, Any],
            _firecrawl_scrape,
        )
    )
    registry.register(
        ToolSpec(
            "firecrawl.crawl",
            "Submit a Firecrawl crawl job.",
            FirecrawlCrawlInput,
            dict[str, Any],
            _firecrawl_crawl,
        )
    )
    registry.register(
        ToolSpec(
            "firecrawl.map",
            "Map URLs discoverable on a site via Firecrawl.",
            FirecrawlMapInput,
            dict[str, Any],
            _firecrawl_map,
        )
    )
    registry.register(
        ToolSpec(
            "firecrawl.extract",
            "Run Firecrawl structured extraction for one URL.",
            FirecrawlExtractInput,
            dict[str, Any],
            _firecrawl_extract,
        )
    )
    registry.register(
        ToolSpec(
            "openaiImages.generate",
            "Generate article images via the OpenAI Images API.",
            OpenAIImagesGenerateInput,
            dict[str, Any],
            _openai_images_generate,
        )
    )
    registry.register(
        ToolSpec(
            "reddit.searchSubreddit",
            "Search posts in one subreddit.",
            RedditSearchSubredditInput,
            dict[str, Any],
            _reddit_search_subreddit,
        )
    )
    registry.register(
        ToolSpec(
            "reddit.topQuestions",
            "Fetch top question-shaped Reddit posts for one subreddit.",
            RedditTopQuestionsInput,
            dict[str, Any],
            _reddit_top_questions,
        )
    )
    registry.register(
        ToolSpec(
            "googlePaa.extract",
            "Extract People Also Ask questions through Firecrawl-backed Google SERP scraping.",
            GooglePaaExtractInput,
            dict[str, Any],
            _google_paa_extract,
        )
    )
    registry.register(
        ToolSpec(
            "jina.read",
            "Fetch a URL through Jina Reader and return Markdown.",
            JinaReadInput,
            dict[str, Any],
            _jina_read,
        )
    )
    registry.register(
        ToolSpec(
            "ahrefs.keywordsForSite",
            "Fetch Ahrefs organic keyword inventory for a domain.",
            AhrefsKeywordsForSiteInput,
            dict[str, Any],
            _ahrefs_keywords_for_site,
        )
    )
    registry.register(
        ToolSpec(
            "ahrefs.topBacklinks",
            "Fetch Ahrefs top backlinks for a target.",
            AhrefsTopBacklinksInput,
            dict[str, Any],
            _ahrefs_top_backlinks,
        )
    )
    registry.register(
        ToolSpec(
            "gsc.searchAnalytics",
            "Fetch Search Console performance rows for a verified property.",
            GscSearchAnalyticsInput,
            dict[str, Any],
            _gsc_search_analytics,
        )
    )
    registry.register(
        ToolSpec(
            "gsc.inspectUrl",
            "Inspect one URL with the Search Console URL Inspection API.",
            GscInspectUrlInput,
            dict[str, Any],
            _gsc_inspect_url,
        )
    )
    registry.register(
        ToolSpec(
            "gsc.bulkInspect",
            "Inspect multiple URLs with the Search Console URL Inspection API.",
            GscBulkInspectInput,
            dict[str, Any],
            _gsc_bulk_inspect,
        )
    )
    registry.register(
        ToolSpec(
            "gsc.pagespeed",
            "Fetch PageSpeed Insights data for one URL.",
            GscPagespeedInput,
            dict[str, Any],
            _gsc_pagespeed,
        )
    )


__all__ = ["register"]
