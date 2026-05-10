# content-stack — security notes

This document records security trade-offs and threat-model decisions that
deviate from the simplest "lock everything down" posture. Each section
explains *what* is loosened, *why*, and *what* still defends the surface.

## Auth posture (PLAN.md §D5)

The daemon binds to `127.0.0.1` only. Every `/api/v1/*` and `/mcp/*` call
must carry `Authorization: Bearer <token>` where the token is the contents
of `~/.local/state/content-stack/auth.token` (32 bytes, mode 0600,
generated atomically at first boot, rotated on `make install`).

Three middlewares form the request gauntlet, applied in this order
(outermost first):

1. **`HostHeaderMiddleware`** rejects any `Host:` header that is not
   `localhost`, `127.0.0.1`, or `[::1]` with HTTP 421. Defends against
   DNS rebinding and stray cross-origin probes.
2. **`CORSMiddleware`** is configured `same-origin` only — a cross-origin
   browser fetch can never read responses even if the request went out.
3. **`BearerTokenMiddleware`** enforces the constant-time bearer check,
   minus an explicit whitelist (see below).

## Whitelisted paths

`WHITELIST_PREFIXES` in `content_stack/auth.py` lists paths that bypass
the bearer-token check. Currently:

| Path | Why it is whitelisted | Residual exposure |
|---|---|---|
| `/api/v1/health` | `doctor` probes liveness before it has resolved the token (when diagnosing token-related failures). | None worth caring about; the response carries only liveness booleans + version. |
| `/api/v1/auth/ui-token` | The Vue SPA cannot read the on-disk token file from the browser, so it fetches the bearer token at app boot via this endpoint. | **See below.** |
| `/api/v1/integrations/gsc/oauth/callback` | Google redirects the operator's browser back to the daemon and cannot attach the SPA's bearer header. | The route accepts only a callback with a matching stored OAuth `state` nonce, then removes that nonce from persisted config. |

## Token-bootstrap trade-off (M5.A)

Adding `/api/v1/auth/ui-token` accepts a small reduction in defence depth.

**What's gained.** The browser-based UI works without prompting the user
to paste a token by hand. The token never leaves the daemon machine and
never lands in a localStorage / sessionStorage where a hostile script
could read it (the SPA holds the token in a Pinia-store ref only).

**What's lost.** Any other process on the same machine that can connect
to `127.0.0.1:5180` can fetch the token by sending `GET
/api/v1/auth/ui-token` with no credentials. Previously, only a process
that could read `auth.token` (mode 0600, owned by the daemon's user)
could obtain it; now any process running as *any* local user that can
open a TCP connection to loopback also can. On a single-user macOS or
Linux box that's a near-zero delta (other users can't loopback-connect
across sessions in practice, and same-user processes already had file
access). On a multi-user / shared-tenant box the regression is real.

**Mitigations already in place.**

- The endpoint never logs the token. Server logs and structured-logging
  output redact it as part of normal practice.
- The `HostHeaderMiddleware` rejects requests with a forged `Host:`
  header, so a remote attacker who has somehow proxied to the loopback
  port (e.g. through a compromised tunnel) is rebuffed.
- `CORSMiddleware` is same-origin, so a malicious page in another tab of
  the user's browser cannot read the response — the browser will refuse
  to expose the body to the attacker's JavaScript.
- The daemon binds to loopback only and rejects `--host 0.0.0.0` at CLI
  parse time, so off-machine callers get connection-refused before any
  middleware runs.

**When to reach for stricter posture.** Operators who run multi-user
machines and want the file-mode-0600 isolation back can:

1. **Run the UI in a separate browser profile** that has no other tabs.
   This eliminates same-origin script attacks against the SPA itself.
2. **Disable the bootstrap and paste the token by hand.** A future
   hardening flag (out of scope for M5) will let operators turn the
   bootstrap off; the SPA will then prompt for the token at first load
   and store it in `sessionStorage` for the tab's lifetime. Operators
   who need this today can `chmod 0400` the token file and short-circuit
   the bootstrap by editing `content_stack/auth.py`'s
   `WHITELIST_PREFIXES`. This is intentionally a code change, not a
   runtime flag, to make sure any operator going down that path has read
   the implications.

## Per-tool rate limits (PLAN.md §828)

Middleware enforces 100 calls/min per MCP tool and 1000 calls/min
aggregate per `Authorization: Bearer` token. Breach returns 429 with
`retry_after` seconds and JSON-RPC code -32011. Bulk tools count as N
calls. This caps blast radius if a token is exfiltrated and an attacker
tries to drive a tight loop against a paid integration.

## Distribution + install posture (M9)

Both the clone-mode `make install` and the pipx-mode
`content-stack install` paths share the same install code:

- **Auth token**: created by `content-stack init`, `content-stack install`,
  or `make install` before MCP registration. `pipx upgrade` does NOT rotate
  by itself; operators rotate explicitly via `content-stack rotate-token
  --yes` or `make rotate-token`. Rotation refreshes saved MCP configs, but a
  daemon that is already running keeps the token it loaded at startup until it
  is restarted.
- **Seed file**: never rotated by install. Cross-machine moves
  require copying `seed.bin` alongside the DB; without it,
  `integration_credentials` rows are unrecoverable. See
  [`./upgrade.md#cross-machine-moves`](./upgrade.md). Rotation stages
  `seed.bin.new` before committing re-encrypted rows; if a crash leaves
  that staged file behind, daemon startup refuses to continue until the
  operator finishes or restores the rotation.
- **Wheel layout (pipx)**: skills + procedures are bundled under
  `content_stack/_assets/`. The console script copies them via
  `importlib.resources` so users without the repo on disk get the
  same install. The committed `ui_dist/` ships inside the package
  (D8) — no `pnpm` needed at user install time.
- **launchd plist**: optional. The plist runs the daemon as the
  invoking user; never as root. `make install-launchd` writes the
  plist with mode 0644 (world-readable, owner-writable). The plist
  itself does not store the auth token; the daemon reads it from
  `~/.local/state/content-stack/auth.token` at startup.

The M9 pipx + launchd path does not change the threat model: the
daemon binds loopback only, the bearer token gates every call, and
the seed encrypts integration credentials at rest. The only delta is
installation ergonomics.
