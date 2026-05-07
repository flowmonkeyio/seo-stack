import { expect, test } from '@playwright/test'

import {
  createProject,
  getBaseUrl,
  getDaemonToken,
  resetProjects,
  trackConsoleErrors,
} from '../helpers'

async function createArticle(
  projectId: number,
  body: { title: string; slug: string },
): Promise<{ id: number; step_etag: string }> {
  const token = getDaemonToken()
  const base = getBaseUrl()
  const res = await fetch(`${base}/api/v1/projects/${projectId}/articles`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'content-type': 'application/json' },
    body: JSON.stringify({
      title: body.title,
      slug: body.slug,
      eeat_criteria_version: 1,
    }),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`create article: ${res.status} ${text}`)
  }
  const env = (await res.json()) as { data: { id: number; step_etag: string } }
  return env.data
}

test.describe('article-detail walk — procedure-4 happy path through the UI', () => {
  test.beforeEach(async () => {
    await resetProjects()
  })

  test('walks an article from briefing → published via every typed verb', async ({
    page,
  }) => {
    test.setTimeout(120_000)
    const errors = trackConsoleErrors(page)
    const project = await createProject({
      name: 'Walk Project',
      slug: 'walk-project',
      domain: 'walk.example.com',
    })
    const article = await createArticle(project.id, {
      title: 'Walk: full procedure-4',
      slug: 'walk-procedure-4',
    })

    // The typed verbs `mark_eeat_passed` and `mark_published` write
    // `articles.owner_run_id` which is FK-constrained to `runs.id`. The
    // REST surface intentionally does not expose `POST /runs` (run lifecycle
    // is MCP-only — content_stack/api/runs.py L113-L118), so the spec
    // intercepts those two endpoints at the network layer and returns a
    // canonical advanced article. The UI behaviour under test is the
    // button → request → status-badge update; the server-side FK is
    // covered by the M3 Python tests (409/409 passing).
    await page.route(
      `**/api/v1/articles/${article.id}/eeat-pass`,
      async (route) => {
        const reqBody = JSON.parse(route.request().postData() ?? '{}')
        const frozenEtag = `etag-after-eeat-${Date.now()}`
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            data: {
              id: article.id,
              project_id: project.id,
              topic_id: null,
              author_id: null,
              reviewer_author_id: null,
              canonical_target_id: null,
              owner_run_id: reqBody.run_id ?? 0,
              slug: 'walk-procedure-4',
              title: 'Walk: full procedure-4',
              status: 'eeat_passed',
              brief_json: null,
              outline_md: null,
              draft_md: null,
              edited_md: null,
              voice_id_used: null,
              eeat_criteria_version_used: 1,
              last_refreshed_at: null,
              last_evaluated_for_refresh_at: null,
              last_link_audit_at: null,
              version: 1,
              current_step: null,
              last_completed_step: 'mark_eeat_passed',
              step_started_at: null,
              step_etag: frozenEtag,
              lock_token: null,
              created_at: '2026-05-01T00:00:00Z',
              updated_at: new Date().toISOString(),
            },
            project_id: project.id,
          }),
        })
      },
    )
    await page.route(
      `**/api/v1/articles/${article.id}/publish`,
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            data: {
              id: article.id,
              project_id: project.id,
              topic_id: null,
              author_id: null,
              reviewer_author_id: null,
              canonical_target_id: null,
              owner_run_id: 0,
              slug: 'walk-procedure-4',
              title: 'Walk: full procedure-4',
              status: 'published',
              brief_json: null,
              outline_md: null,
              draft_md: null,
              edited_md: null,
              voice_id_used: null,
              eeat_criteria_version_used: 1,
              last_refreshed_at: null,
              last_evaluated_for_refresh_at: null,
              last_link_audit_at: null,
              version: 1,
              current_step: null,
              last_completed_step: 'mark_published',
              step_started_at: null,
              step_etag: 'etag-after-publish',
              lock_token: null,
              created_at: '2026-05-01T00:00:00Z',
              updated_at: new Date().toISOString(),
            },
            project_id: project.id,
          }),
        })
      },
    )

    // Step 1: open the article detail. Status = briefing.
    await page.goto(`/projects/${project.id}/articles/${article.id}/brief`)
    await expect(page.locator('[data-status="briefing"]').first()).toBeVisible()

    // Step 2: edit the brief JSON via the "Edit" → save flow.
    // Use the brief tabpanel's Edit button (not the action-bar "Edit brief").
    await page
      .getByRole('tabpanel', { name: 'Brief' })
      .getByRole('button', { name: 'Edit', exact: true })
      .click()
    const briefTextarea = page.getByLabel('Brief JSON editor')
    await briefTextarea.fill(
      JSON.stringify(
        {
          primary_kw: 'best sportsbook',
          target_word_count: 1800,
          intent: 'informational',
          audience: 'punters',
        },
        null,
        2,
      ),
    )
    await page.getByRole('button', { name: 'Save brief' }).click()
    // Wait for status to flip to "outlined" (set_brief advances the state).
    await expect(page.locator('[data-status="outlined"]').first()).toBeVisible({ timeout: 10_000 })

    // Step 3: navigate to outline tab + save outline.
    await page.getByRole('tab', { name: 'Outline' }).click()
    await expect(page).toHaveURL(/\/outline$/)
    const outlineEditor = page.getByLabel('Article outline markdown editor')
    await outlineEditor.fill('# Outline\n\n## Section 1\n## Section 2\n')
    await page.locator('button.bg-blue-600', { hasText: 'Save' }).first().click()
    await expect(page.locator('[data-status="outlined"]').first()).toBeVisible()

    // Step 4: navigate to draft. Save once, then mark drafted.
    await page.getByRole('tab', { name: 'Draft' }).click()
    await expect(page).toHaveURL(/\/draft$/)
    const draftEditor = page.getByLabel('Article draft markdown editor')
    await draftEditor.fill('# Draft\n\nFirst section body.\n')
    await page.locator('button.bg-blue-600', { hasText: 'Save' }).first().click()
    // Mark drafted button advances outlined → drafted.
    await page.getByRole('button', { name: 'Mark drafted' }).first().click()
    await expect(page.locator('[data-status="drafted"]').first()).toBeVisible({ timeout: 10_000 })

    // Step 5: edited body + save → status becomes "edited".
    await page.getByRole('tab', { name: 'Edited' }).click()
    await expect(page).toHaveURL(/\/edited$/)
    const editedEditor = page.getByLabel('Article edited markdown editor')
    await editedEditor.fill('# Edited body\n\nFinal polished prose.\n')
    await page.locator('button.bg-blue-600', { hasText: 'Save' }).first().click()
    await expect(page.locator('[data-status="edited"]').first()).toBeVisible({ timeout: 10_000 })

    // Step 6: action bar offers "Mark EEAT passed (manual)" — click it.
    await page.getByRole('button', { name: /Mark EEAT passed/ }).click()
    await expect(page.locator('[data-status="eeat_passed"]').first()).toBeVisible({
      timeout: 10_000,
    })

    // Step 7: action bar offers "Publish" — click it.
    await page.getByRole('button', { name: 'Publish' }).click()
    await expect(page.locator('[data-status="published"]').first()).toBeVisible({
      timeout: 10_000,
    })

    // Step 8: published article exposes "Mark refresh due" + "New version".
    await expect(page.getByRole('button', { name: 'Mark refresh due' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'New version' })).toBeVisible()

    errors.assertNone()
  })
})
