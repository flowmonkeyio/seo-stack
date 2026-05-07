"""Per-install bearer-token authentication.

Single token at `state_dir/auth.token`. Generated on first daemon start.
Required on every REST and MCP request. The `/api/v1/health` endpoint is
explicitly whitelisted so `doctor` can probe liveness *before* it has the
token resolved (e.g., when diagnosing token-related failures).
"""

from __future__ import annotations

import os
import secrets
import stat
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

# Bearer-token enforcement is scoped to API surfaces only. The browser must
# be able to load the static UI bundle (`/`, `/assets/*`, `/favicon.ico`)
# *without* a token — the HTML/JS shell is harmless on its own; subsequent
# `/api/v1/*` calls from the loaded UI carry the token via fetch headers
# (token plumbing per D5; full UI flow lands in M2/M3). OpenAPI/docs paths
# (`/api/openapi.json`, `/api/docs`) are also public for local-dev ergonomics
# — they expose schema only, never grant access.
PROTECTED_PREFIXES: tuple[str, ...] = ("/api/v1", "/mcp")

# Inside the protected surfaces, these paths bypass the bearer-token check.
# Health is required so `doctor` can probe liveness *before* it has resolved
# the token (e.g., when diagnosing token-related failures themselves).
WHITELIST_PREFIXES: tuple[str, ...] = ("/api/v1/health",)

_TOKEN_BYTES = 32
_REQUIRED_MODE = 0o600


class TokenFileError(RuntimeError):
    """Raised when the auth token file exists but has the wrong permissions.

    We refuse to start the daemon rather than silently fix the mode — a
    too-wide token file is a "wrong machine, wrong user, or wrong umask"
    signal worth surfacing to the operator.
    """


def _file_mode_bits(path: Path) -> int:
    """Return the permission bits of `path`, masked to standard rwx triplets."""
    return stat.S_IMODE(path.stat().st_mode)


def ensure_token(token_path: Path) -> str:
    """Return the bearer token at `token_path`, generating it if absent.

    On generation: 32 bytes from `os.urandom`, urlsafe-base64 encoded, written
    with mode 0600 via `os.open(O_CREAT|O_EXCL, 0o600)` so we never race a
    co-tenant into reading a freshly-created world-readable file.

    On existing file: refuse if the mode is anything other than 0600 — the
    operator has likely run a `chmod` or restored from a sloppy backup; the
    daemon must not paper over that.
    """
    if token_path.exists():
        mode = _file_mode_bits(token_path)
        if mode != _REQUIRED_MODE:
            raise TokenFileError(
                f"auth token at {token_path} has mode {oct(mode)}; expected {oct(_REQUIRED_MODE)}"
            )
        return token_path.read_text(encoding="utf-8").strip()

    # Atomic create-and-restrict; defends against TOCTOU.
    token_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(
        token_path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        _REQUIRED_MODE,
    )
    try:
        token = secrets.token_urlsafe(_TOKEN_BYTES)
        os.write(fd, token.encode("utf-8"))
    finally:
        os.close(fd)
    # `os.open` honours umask on some platforms — re-chmod to be sure.
    os.chmod(token_path, _REQUIRED_MODE)
    return token


def requires_auth(path: str) -> bool:
    """Return True if `path` must carry a valid bearer token.

    True only for protected API surfaces (`/api/v1/*`, `/mcp/*`) minus the
    explicit whitelist. Everything else — static UI, openapi.json, docs UI —
    passes through without auth.
    """
    for whitelisted in WHITELIST_PREFIXES:
        if path == whitelisted or path.startswith(whitelisted + "/"):
            return False
    for protected in PROTECTED_PREFIXES:
        if path == protected or path.startswith(protected + "/"):
            return True
    return False


def is_whitelisted(path: str) -> bool:
    """Backwards-compat alias retained for any test that still imports it."""
    return not requires_auth(path)


class BearerTokenMiddleware(BaseHTTPMiddleware):
    """Reject requests whose `Authorization: Bearer <token>` does not match.

    The token is supplied at construction time so middleware setup never
    re-reads the file at request time. Token rotation requires a daemon
    restart, which matches the spec (rotation runs via `make install`).
    """

    def __init__(self, app: object, *, token: str) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._token = token

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Compare the bearer token in constant time before forwarding."""
        if not requires_auth(request.url.path):
            return await call_next(request)

        header = request.headers.get("authorization", "")
        scheme, _, value = header.partition(" ")
        if scheme.lower() != "bearer" or not value:
            return JSONResponse(
                {"detail": "missing bearer token"},
                status_code=401,
                headers={"www-authenticate": 'Bearer realm="content-stack"'},
            )
        if not secrets.compare_digest(value, self._token):
            return JSONResponse(
                {"detail": "invalid bearer token"},
                status_code=401,
                headers={"www-authenticate": 'Bearer realm="content-stack"'},
            )
        return await call_next(request)
