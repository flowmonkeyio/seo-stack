# API key + OAuth setup

This guide walks through obtaining credentials for every M4 vendor
integration. Every key is stored encrypted at rest in
``integration_credentials`` (AES-256-GCM with a per-row 12-byte nonce
and a project-bound AAD; PLAN.md L1106-L1124).

The "First-run flows" section in PLAN.md L1065-L1088 is the canonical
spec; this doc is the operator-facing how-to.

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

1. Open <https://console.cloud.google.com>.
2. Create a new project (or pick an existing one).
3. Navigate to **APIs & Services → Library** and enable
   **Google Search Console API**.
4. Enable **Web Search Indexing API**.
5. Enable **PageSpeed Insights API**.
6. Go to **OAuth consent screen** → choose "External" if you have a
   personal Google account, "Internal" if you have a Google Workspace
   organisation.
7. Add scopes: ``https://www.googleapis.com/auth/webmasters.readonly``
   and ``https://www.googleapis.com/auth/indexing``.
8. Add yourself as a test user (External flows only).
9. Go to **Credentials → Create Credentials → OAuth client ID**.
10. App type: **Web application**.
11. Authorized redirect URI:
    ``http://localhost:5180/api/v1/integrations/gsc/oauth/callback``.
12. Save the **client_id** + **client_secret** and set them as env
    vars:

    ```
    GSC_OAUTH_CLIENT_ID=...
    GSC_OAUTH_CLIENT_SECRET=...
    ```

Then in the content-stack UI:

- Open Integrations → Google Search Console → **Connect GSC**.
- The daemon redirects you to Google's consent screen.
- Confirm and you're sent back to a "you can close this tab" page.
- The token bundle is now encrypted in ``integration_credentials``.
  The ``oauth_refresh`` worker (``make oauth-refresh`` for ad-hoc;
  scheduled in M8) refreshes access tokens before they expire.

A 401 from the search-analytics endpoint surfaces "re-auth needed";
re-running step 12 (the Connect button) picks up where we left off.

---

## OpenAI Images

Used by: ``image-generator``.

1. Open <https://platform.openai.com/api-keys>.
2. Create a new key — restrict it to "Restricted" with only
   ``image.generation`` enabled if your account supports scopes.
3. Paste into Integrations → OpenAI Images.

This row is **separate** from any runtime LLM key (PLAN.md L1057-L1063)
so you can budget images independently from prose.

Cost: ~$0.04 per ``1024x1024 standard`` image; ~$0.08 for ``1024x1024
hd`` and the wide / tall variants.

Env var equivalent:

```
OPENAI_API_KEY=sk-...
```

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
under the hood — costs flow through Firecrawl's budget cap.

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

## Ahrefs (Enterprise plan only)

Used by: ``keyword-discovery``, ``one-site-shortcut`` — both have
DataForSEO fallbacks.

Ahrefs only issues API tokens to Enterprise plan customers
(~$15k/year minimum at 2025 pricing). For solo/SMB operators
DataForSEO covers the same surface area.

If you have an Enterprise plan:

1. Go to <https://ahrefs.com/api>.
2. Generate a new token.
3. Paste into Integrations → Ahrefs.

If you don't have a plan: skip this integration. ``test_credentials``
returns ``IntegrationDownError`` with a hint pointing back to this
section, and the keyword-discovery skill falls back to DataForSEO
automatically.

---

## codex-plugin-cc (adversarial review)

Used by: ``eeat-gate`` (skill #11; M6).

1. Install the Codex Claude Code plugin separately:
   ``claude plugin install codex-plugin-cc``.
2. Set ``CLAUDE_PLUGIN_ROOT`` to the plugin root (the install script
   does this automatically).
3. In the content-stack UI Integrations tab toggle "codex-plugin-cc"
   on for the project. The toggle persists as
   ``integration_credentials.kind='codex-plugin-cc'`` with
   ``config_json.enabled=true`` (no encrypted payload — the plugin
   itself is the credential surface).

If the plugin is not installed the adversarial-review helper returns
``{verdict: "SKIPPED", reason: "plugin-not-installed"}`` so the EEAT
gate degrades gracefully.
