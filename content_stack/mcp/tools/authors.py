"""``author.*`` tools — per-project author CRUD."""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict

from content_stack.mcp.context import MCPContext
from content_stack.mcp.contract import MCPInput, WriteEnvelope
from content_stack.mcp.server import ToolRegistry, ToolSpec
from content_stack.mcp.streaming import ProgressEmitter
from content_stack.repositories.authors import AuthorOut, AuthorRepository
from content_stack.repositories.base import Page

# ---------------------------------------------------------------------------
# Inputs.
# ---------------------------------------------------------------------------


class AuthorCreateInput(MCPInput):
    """Insert an author row; (project_id, slug) unique."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"project_id": 1, "name": "Jane Doe", "slug": "jane-doe"}},
    )

    project_id: int
    name: str
    slug: str
    bio_md: str | None = None
    headshot_url: str | None = None
    role: str | None = None
    credentials_md: str | None = None
    social_links_json: dict[str, Any] | None = None
    schema_person_json: dict[str, Any] | None = None


class AuthorGetInput(MCPInput):
    """Fetch an author by id."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"author_id": 1}})

    author_id: int


class AuthorListInput(MCPInput):
    """Cursor-paginated list."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"project_id": 1}})

    project_id: int
    limit: int | None = None
    after_id: int | None = None


class AuthorUpdateInput(MCPInput):
    """Patch an author."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"author_id": 1, "patch": {"role": "Editor"}}}
    )

    author_id: int
    patch: dict[str, Any]


class AuthorRemoveInput(MCPInput):
    """Hard-delete; FK SET NULL clears references."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"author_id": 1}})

    author_id: int


# ---------------------------------------------------------------------------
# Handlers.
# ---------------------------------------------------------------------------


async def _author_create(
    inp: AuthorCreateInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[AuthorOut]:
    env = AuthorRepository(ctx.session).create(
        project_id=inp.project_id,
        name=inp.name,
        slug=inp.slug,
        bio_md=inp.bio_md,
        headshot_url=inp.headshot_url,
        role=inp.role,
        credentials_md=inp.credentials_md,
        social_links_json=inp.social_links_json,
        schema_person_json=inp.schema_person_json,
    )
    return WriteEnvelope[AuthorOut](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


async def _author_get(inp: AuthorGetInput, ctx: MCPContext, _emit: ProgressEmitter) -> AuthorOut:
    return AuthorRepository(ctx.session).get(inp.author_id)


async def _author_list(
    inp: AuthorListInput, ctx: MCPContext, _emit: ProgressEmitter
) -> Page[AuthorOut]:
    return AuthorRepository(ctx.session).list(
        inp.project_id, limit=inp.limit, after_id=inp.after_id
    )


async def _author_update(
    inp: AuthorUpdateInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[AuthorOut]:
    env = AuthorRepository(ctx.session).update(inp.author_id, **inp.patch)
    return WriteEnvelope[AuthorOut](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


async def _author_delete(
    inp: AuthorRemoveInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[AuthorOut]:
    env = AuthorRepository(ctx.session).remove(inp.author_id)
    return WriteEnvelope[AuthorOut](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


# ---------------------------------------------------------------------------
# Registration.
# ---------------------------------------------------------------------------


def register(registry: ToolRegistry) -> None:
    """Register every author.* tool."""
    registry.register(
        ToolSpec(
            "author.create",
            "Insert an author row; (project_id, slug) unique.",
            AuthorCreateInput,
            WriteEnvelope[AuthorOut],
            _author_create,
        )
    )
    registry.register(
        ToolSpec("author.get", "Fetch an author by id.", AuthorGetInput, AuthorOut, _author_get)
    )
    registry.register(
        ToolSpec(
            "author.list", "Cursor-paginated list.", AuthorListInput, Page[AuthorOut], _author_list
        )
    )
    registry.register(
        ToolSpec(
            "author.update",
            "Patch an author.",
            AuthorUpdateInput,
            WriteEnvelope[AuthorOut],
            _author_update,
        )
    )
    registry.register(
        ToolSpec(
            "author.delete",
            "Hard-delete; FK SET NULL clears references.",
            AuthorRemoveInput,
            WriteEnvelope[AuthorOut],
            _author_delete,
        )
    )


__all__ = ["register"]
