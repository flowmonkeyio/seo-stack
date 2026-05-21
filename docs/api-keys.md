# API key + OAuth setup

This guide walks through obtaining credentials for every M4 vendor
integration. Every key is stored encrypted at rest in
``integration_credentials`` (AES-256-GCM with a per-row 12-byte nonce
and a project-bound AAD; PLAN.md L1106-L1124).

The "First-run flows" section in PLAN.md L1065-L1088 is the canonical
spec; this doc is the operator-facing how-to.

Recommended setup flow:

1. Let the agent identify the vendors needed for the current procedure.
2. Let the agent call `auth.status` to see which provider refs already exist.
3. Open the project integrations page the agent gives you, for example
   ``http://localhost:5180/projects/1/integrations?required=dataforseo,firecrawl``.
4. Connect vendors from the named cards. Do not paste secrets into agent
   chat and do not add vendor keys to the website repository.
5. Return to the agent. The agent should run `auth.test` with the opaque
   `credential_ref` or provider key before continuing.

`integration_credentials` is still the encrypted backing table, but agents use
the generic auth-provider boundary. `auth.status` and `auth.test` return
sanitized provider state and credential refs; local UI/REST setup is the only
place plaintext keys or OAuth secrets are accepted.

---

## DataForSEO

Used by: ``keyword-discovery``, ``serp-analyzer``.

1. Sign up at <https://app.dataforseo.com>.
2. Top up a small balance (~$5 covers thousands of test queries).
3. From the dashboard copy your **API login** + **API password**.
4. In the content-stack UI Integrations tab pick "DataForSEO" and paste
   the pair. The login lands in ``config_json.login``; the password
   lands in the encrypted payload.

Cost notes: ~$0.001-$0.003 per SERP call; the wrapper reads the
vendor's ``tasks[].cost`` value back into the budget so the cap stays
accurate.

Env var equivalent (server side / tests):

```
DATAFORSEO_LOGIN=...
DATAFORSEO_PASSWORD=...
```

---

## Firecrawl

Used by: ``serp-analyzer``, ``content-brief``, ``drift-watch``.

1. Sign up at <https://firecrawl.dev>.
2. Verify email; the dashboard issues an API key starting ``fc-...``.
3. Paste the key into Integrations → Firecrawl.

Cost: ~$0.001 per scrape; crawl runs ~$0.002 per page. Set the project
budget cap in Settings → Budgets.

Env var equivalent:

```
FIRECRAWL_API_KEY=fc-...
```

---

## Google Search Console (12-step OAuth setup)

Used by: ``gsc-opportunity-finder``, ``crawl-error-watch``.

This section is intentionally text-first. Google Cloud Console changes
its layout frequently, so screenshots are deferred until the first
published operator guide for a specific console version.

1. Open <https://console.cloud.google.com>.
2. Create a new project (or pick an existing one).
3. Navigate to **APIs & Services → Library** and enable
   **Google Search Console API**.
4. Enable **PageSpeed Insights API**.
5. Go to **OAuth consent screen** → choose "External" if you have a
   personal Google account, "Internal" if you have a Google Workspace
   organisation.
6. Add scope: ``https://www.googleapis.com/auth/webmasters.readonly``.
7. Add yourself as a test user (External flows only).
8. Go to **Credentials → Create Credentials → OAuth client ID**.
9. App type: **Web application**.
10. Authorized redirect URI:
    ``http://localhost:5180/api/v1/integrations/gsc/oauth/callback``.
11. Save the **client_id** + **client_secret** and set them as env
    vars:

    ```
    GSC_OAUTH_CLIENT_ID=...
    GSC_OAUTH_CLIENT_SECRET=...
    ```

Then in the content-stack UI:

- Open Integrations → Google Search Console → **Connect GSC**.
- The daemon redirects you to Google's consent screen.
- Confirm and you're sent back to a "you can close this tab" page.
- The token bundle is now encrypted in ``integration_credentials`` and exposed
  to agents only as an opaque auth credential ref.
  The ``oauth_refresh`` worker (``make oauth-refresh`` for ad-hoc;
  scheduled in M8) refreshes access tokens before they expire.

A 401 from the search-analytics endpoint surfaces "re-auth needed";
clicking **Connect GSC** again picks up where we left off.

---

## Runtime LLM keys

Used by: the operator runtime, outside content-stack. Procedure writing
is agent-led: Codex, Claude Code, or another MCP client is the writer
and SEO operator, and it uses that runtime's own model credentials.
Do not store prose-generation OpenAI/Anthropic keys in content-stack
just so the daemon can spawn unattended writer sessions.

The only OpenAI key content-stack itself needs is the vendor integration
key for image generation below.

---

## OpenAI Images

Used by: ``image-generator``.

1. Open <https://platform.openai.com/api-keys>.
2. Create a new key — restrict it to "Restricted" with only
   ``image.generation`` enabled if your account supports scopes.
3. Paste into Integrations → OpenAI Images.

This row is **separate** from the LLM key used by your external agent
(PLAN.md L1057-L1063), so you can budget images independently from prose.

Default path: the image-generator skill uses the current GPT Image API
(``gpt-image-1.5`` by default). GPT Image responses return base64 image
data, so the daemon wrapper persists the bytes under
``CONTENT_STACK_DATA_DIR/generated-assets`` and returns local
``/generated-assets/...`` URLs for ``article_assets.url``. Do not use
DALL-E as the default path; OpenAI's docs now mark the DALL-E image
models as deprecated.

Cost: treat the wrapper's image estimates as a budget guardrail, not final
billing. The wrapper records the vendor response and the operator should
reconcile against OpenAI's current pricing page.

Env var equivalent:

```
OPENAI_API_KEY=sk-...
```

---

## WordPress

Used by: WordPress credential probes and the deferred ``wordpress-publish``
publisher spec. Procedure 4 does not currently publish to WordPress; internal-site
publishing does not require this.

1. In WordPress, open **Users → Profile → Application Passwords**.
2. Create a dedicated application password for a least-privileged
   publishing user. Prefer ``editor`` or ``author``; do not use an
   administrator account for automation.
3. In Integrations → WordPress, store the payload as either JSON
   ``{"username":"...", "application_password":"..."}`` or compact
   ``username:application-password``.
4. Set ``config_json.wp_url`` to the site root, e.g.
   ``https://example.com``.

The wrapper probes ``GET /wp-json/wp/v2/users/me?context=edit`` using
Basic Auth with the application password, then post creation/update uses
the documented ``/wp-json/wp/v2/posts`` endpoints.

---

## Ghost

Used by: Ghost credential probes and the deferred ``ghost-publish`` publisher
spec. Procedure 4 does not currently publish to Ghost; internal-site publishing
does not require this.

1. In Ghost Admin, create a **Custom Integration**.
2. Copy the Admin API key in ``id:secret`` form.
3. In Integrations → Ghost, store the key as either raw ``id:secret`` or
   JSON ``{"admin_api_key":"id:secret"}``.
4. Set ``config_json.ghost_url`` to the Ghost Admin domain root, e.g.
   ``https://example.com``.
5. Optionally set ``config_json.api_version``; default is ``v5.0``.

The wrapper signs a short-lived HS256 JWT with ``aud="/admin/"`` and
sends it as ``Authorization: Ghost <token>`` with ``Accept-Version``.
The probe hits ``GET /ghost/api/admin/users/?limit=1&include=roles``;
post creation uses ``POST /ghost/api/admin/posts/?source=html``.

---

## Reddit

Used by: ``keyword-discovery`` (PRAW-style search).

1. Open <https://www.reddit.com/prefs/apps>.
2. Click **create another app...** at the bottom.
3. Pick **script**.
4. Set the redirect URI to anything (we use application-only auth so
   the redirect is unused).
5. Copy the **client_id** (under the app name) + **client_secret**.
6. Choose a unique **user_agent** string per Reddit's API rules
   (e.g. ``content-stack/0.1 by your-username``).
7. Paste all three into Integrations → Reddit. The wrapper persists
   them as a JSON bundle inside the encrypted payload.

Env var equivalent:

```
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
```

---

## Google PAA

Used by: ``keyword-discovery``.

No credential needed. The Google PAA wrapper delegates to Firecrawl
under the hood. If you set a direct budget for the wrapper, use kind
``google-paa``; older ``paa`` budget rows are normalized to ``google-paa``
by the REST routes.

---

## Jina Reader

Used by: ``serp-analyzer`` markdown fallback.

1. Optional: sign up at <https://jina.ai/reader> for an API key (free
   tier exists; paid raises limits).
2. Without a key the wrapper hits the public ``r.jina.ai`` endpoint at
   reduced rate. Most use cases work without one.

Env var equivalent:

```
JINA_API_KEY=...
```

---

## Ahrefs

Used by: ``keyword-discovery``, ``one-site-shortcut`` — both have
DataForSEO fallbacks.

Ahrefs API v3 is optional for our first internal tests. Ahrefs' current
docs describe API v3 access and API-unit limits by paid plan, with higher
limits and additional-unit purchases on Enterprise. For solo/SMB
operators, DataForSEO covers the same keyword/SERP surface area we need
first.

If you have a paid Ahrefs plan with API v3 access:

1. Go to <https://ahrefs.com/api>.
2. Generate a new token.
3. Paste into Integrations → Ahrefs.

If you don't have a plan: skip this integration. ``test_credentials``
returns ``IntegrationDownError`` with a hint pointing back to this section,
and the keyword-discovery skill falls back to DataForSEO automatically.
