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

## Adversarial-review prompt-injection hygiene (PLAN.md §1162)

The eeat-gate skill (#11) optional `codex-plugin-cc` adversarial-review
helper passes the article body via a `tempfile.NamedTemporaryFile`
(mode 0600) referenced by path, never via `argv`. The temp file is
deleted in `finally`. The article body is wrapped in an
`<article_under_review>` XML tag in the helper's prompt for prompt-
injection hygiene. Wall-clock budget per call is 90 s; on timeout the
gate logs `runs.metadata_json.adversarial_review.skipped='timeout'` and
proceeds — slow plugins do not block the article.

## Per-tool rate limits (PLAN.md §828)

Middleware enforces 100 calls/min per MCP tool and 1000 calls/min
aggregate per `Authorization: Bearer` token. Breach returns 429 with
`retry_after` seconds and JSON-RPC code -32011. Bulk tools count as N
calls. This caps blast radius if a token is exfiltrated and an attacker
tries to drive a tight loop against a paid integration.
