"""FastAPI app factory.

Wires middleware in the order: Host header check (outermost so it runs
even on auth-whitelisted paths) → CORS (same-origin) → bearer-token auth.
Lifespan ensures dirs/seed/token before the first request lands.
"""

from __future__ import annotations

import os
import secrets
import stat
import time
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlmodel import SQLModel
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from content_stack import __version__
from content_stack.api import register_routers
from content_stack.auth import BearerTokenMiddleware, ensure_token
from content_stack.config import Settings, get_settings
from content_stack.db.connection import make_engine
from content_stack.logging import configure_logging, get_logger
from content_stack.mcp import register_mcp

_SEED_BYTES = 32
_REQUIRED_MODE = 0o600

# Hosts the daemon will respond to. The port-suffix variants are accepted
# because some clients send `Host: 127.0.0.1:5180`. We do *not* hard-code
# the port here so non-default ports still work; the suffix is stripped
# before comparison.
_ALLOWED_HOSTS: frozenset[str] = frozenset({"localhost", "127.0.0.1", "[::1]", "::1"})


class HostHeaderMiddleware(BaseHTTPMiddleware):
    """Reject requests whose `Host:` header is not loopback with 421.

    Defence-in-depth against DNS rebinding and stray cross-origin probes
    (curl from another machine, browser plugins, etc.). The CLI already
    refuses non-loopback `--host`, so this is the runtime backstop.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Strip the optional `:port` suffix and compare to the allow-list."""
        host_header = request.headers.get("host", "")
        # Strip port from forms like "127.0.0.1:5180" or "[::1]:5180".
        if host_header.startswith("["):
            # IPv6 literal: "[::1]:5180" -> "[::1]"
            host_only, _, _ = host_header.partition("]")
            host_only = host_only + "]"
        else:
            host_only = host_header.split(":", 1)[0] if host_header else ""

        if host_only not in _ALLOWED_HOSTS:
            return JSONResponse(
                {"detail": f"Host header {host_header!r} is not loopback"},
                status_code=421,
            )
        return await call_next(request)


_PARTIAL_INDEX_DDL: tuple[str, ...] = (
    # Partial unique on internal_links (audit B-09)
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_internal_links_unique "
    "ON internal_links(from_article_id, to_article_id, anchor_text, position) "
    "WHERE status != 'dismissed'",
    # Primary publish target (audit B-08)
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_publish_targets_primary "
    "ON publish_targets(project_id) WHERE is_primary = 1",
)


def _ensure_partial_indexes(engine: object) -> None:
    """Emit the partial-unique indexes that SQLModel can't express declaratively.

    The Alembic 0002 migration is the canonical source of truth for these;
    this fallback runs them only if absent (``IF NOT EXISTS``) so a daemon
    started against a freshly-``create_all``'d schema still enforces the
    M1.B invariants (B-08 / B-09).
    """
    with engine.begin() as conn:  # type: ignore[attr-defined]
        for ddl in _PARTIAL_INDEX_DDL:
            conn.execute(text(ddl))


def _ensure_seed(seed_path: Path) -> None:
    """Generate `seed.bin` if absent; refuse to start if mode is wrong.

    The seed only matters once integrations land (M5), but we generate it at
    M0 so install ordering doesn't matter and so doctor can verify mode 0600
    on every fresh install.
    """
    if seed_path.exists():
        mode = stat.S_IMODE(seed_path.stat().st_mode)
        if mode != _REQUIRED_MODE:
            raise RuntimeError(
                f"seed file at {seed_path} has mode {oct(mode)}; expected {oct(_REQUIRED_MODE)}"
            )
        return
    seed_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(seed_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, _REQUIRED_MODE)
    try:
        os.write(fd, secrets.token_bytes(_SEED_BYTES))
    finally:
        os.close(fd)
    os.chmod(seed_path, _REQUIRED_MODE)


def _build_lifespan(
    settings: Settings,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    """Build a FastAPI lifespan for the given settings (closure binds settings)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Startup: ensure dirs, seed, token, engine. Shutdown: clean log."""
        settings.ensure_dirs()
        configure_logging(log_path=settings.log_path, level=settings.log_level)
        log = get_logger("content_stack.server")

        _ensure_seed(settings.seed_path)
        token = ensure_token(settings.token_path)

        engine = make_engine(settings.db_path)

        # Ensure schema exists. In production the M0 cli runs ``make migrate``
        # before starting the daemon; the lifespan's ``create_all`` is a
        # safety net for fresh installs and tests that don't pre-run alembic.
        # ``create_all`` is a no-op when the tables are already there, so it
        # adds zero cost on warm starts.
        SQLModel.metadata.create_all(engine)
        # Emit the migration-only partial-unique indexes so the M1.B
        # invariants exercised by integration tests (B-08, B-09, M-20) are
        # active even when the lifespan path didn't go through alembic.
        _ensure_partial_indexes(engine)

        app.state.settings = settings
        app.state.token = token
        app.state.engine = engine
        app.state.started_at = time.monotonic()
        app.state.scheduler_running = False  # APScheduler lands in M9.

        log.info(
            "daemon.started",
            host=settings.host,
            port=settings.port,
            version=__version__,
            milestone="M0",
            data_dir=str(settings.data_dir),
            state_dir=str(settings.state_dir),
        )
        try:
            yield
        finally:
            log.info("daemon.shutdown.clean")
            engine.dispose()

    return lifespan


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a FastAPI app with middleware, lifespan, and routes wired.

    `settings` may be supplied for tests that want isolated paths; in
    production, callers pass `None` and we resolve the global Settings.
    """
    settings = settings or get_settings()
    # Pre-flight ensure so the token exists before middleware reads it.
    settings.ensure_dirs()
    _ensure_seed(settings.seed_path)
    token = ensure_token(settings.token_path)

    app = FastAPI(
        title="content-stack",
        version=__version__,
        summary="Multi-project SEO content pipelines for any LLM client.",
        description=(
            "A globally-installed Python daemon (FastAPI + SQLite/WAL + MCP "
            "Streamable HTTP) plus Vue UI giving any LLM client a stateful "
            "CRUD seam over multi-project SEO content pipelines."
        ),
        lifespan=_build_lifespan(settings),
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )

    # Middleware order — Starlette runs the *last-added* first on the
    # request path, so we add inside-out: auth, then CORS, then host check.
    app.add_middleware(BearerTokenMiddleware, token=token)
    app.add_middleware(
        CORSMiddleware,
        # Same-origin only: no cross-origin browser fetches.
        allow_origins=[f"http://{settings.host}:{settings.port}"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["authorization", "content-type", "if-match", "x-request-id"],
    )
    app.add_middleware(HostHeaderMiddleware)

    register_routers(app)

    # Mount the MCP Streamable HTTP transport at /mcp. Bearer-token
    # middleware already covers ``/mcp/*`` via ``PROTECTED_PREFIXES``,
    # so the MCP layer never re-checks auth — every request landing on
    # a tool handler has already cleared the BearerTokenMiddleware.
    register_mcp(app)

    _mount_ui(app, settings)

    return app


def _mount_ui(app: FastAPI, settings: Settings) -> None:
    """Mount static UI bundle at `/`; serve a placeholder if not yet built."""
    ui_dist = Path(__file__).parent / "ui_dist"
    index = ui_dist / "index.html"

    # Always register the placeholder/static branch *after* API routes are
    # included so router precedence is deterministic.
    if index.is_file():
        app.mount("/", StaticFiles(directory=ui_dist, html=True), name="ui")
        return

    @app.get("/", include_in_schema=False)
    async def _ui_placeholder() -> HTMLResponse:
        """Placeholder shown until `make build-ui` populates ui_dist/."""
        body = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>content-stack</title></head><body>"
            "<h1>content-stack daemon is running.</h1>"
            "<p>UI not built yet — run <code>make build-ui</code>.</p>"
            f"<p>API docs: <a href='/api/docs'>/api/docs</a></p>"
            f"<p>Version: {__version__}</p>"
            "</body></html>"
        )
        return HTMLResponse(body, status_code=200)

    # Touch the variable so linters know it's intentionally registered as a route.
    _ = _ui_placeholder
