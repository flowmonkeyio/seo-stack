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
): Promise<{ id: number }> {
  const token = getDaemonToken()
  const base = getBaseUrl()
  const res = await fetch(`${base}/api/v1/projects/${projectId}/articles`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'content-type': 'application/json' },
    body: JSON.stringify({ title: body.title, slug: body.slug, eeat_criteria_version: 1 }),
  })
  if (!res.ok) throw new Error(`create article: ${res.status}`)
  return ((await res.json()) as { data: { id: number } }).data
}

test.describe('article-detail EEAT veto banner', () => {
  test.beforeEach(async () => {
    await resetProjects()
  })

  // The REST surface intentionally does not expose `POST /runs` (RunRepository
  // is MCP-only — see content_stack/api/runs.py). To exercise the veto-banner
  // UI without seeding a real `runs` row, we intercept the article eeat
  // endpoint at the Playwright network layer and return a fixture report
  // with `vetoes_failed=['T04']`. The backend behaviour itself is covered
  // by the M3 Python repo tests; this test asserts that the UI surfaces the
  // banner + the BLOCK verdict + the core badge correctly when the wire
  // shape signals a veto failure.
  test('veto-fail report surfaces "Cannot ship" banner + BLOCK verdict', async ({ page }) => {
    const errors = trackConsoleErrors(page)
    const project = await createProject({
      name: 'Veto Project',
      slug: 'veto-project',
      domain: 'veto.example.com',
    })
    const article = await createArticle(project.id, {
      title: 'Veto-fail walk',
      slug: 'veto-fail',
    })

    // Network-level intercept of the article-eeat endpoint. Returns a
    // report with one core criterion (id=1) that failed.
    const fixture = {
      score: {
        dimension_scores: {
          C: 60,
          O: 80,
          R: 50,
          E: 70,
          Exp: 90,
          Ept: 80,
          A: 70,
          T: 70,
        },
        system_scores: { GEO: 65, SEO: 78 },
        coverage: {
          C: true,
          O: true,
          R: true,
          E: true,
          Exp: true,
          Ept: true,
          A: true,
          T: true,
        },
        vetoes_failed: ['T04'],
        total_evaluations: 12,
      },
      evaluations: [
        {
          id: 1,
          article_id: article.id,
          criterion_id: 1, // overlaid onto whichever id the seeded T04 row uses
          run_id: 999,
          verdict: 'fail',
          notes: 'seeded for veto-banner test',
          evaluated_at: new Date().toISOString(),
        },
      ],
    }

    // Look up the seeded T04 criterion id so the row's "core" badge resolves.
    const token = getDaemonToken()
    const base = getBaseUrl()
    const cRes = await fetch(`${base}/api/v1/projects/${project.id}/eeat`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    const criteria = (await cRes.json()) as Array<{ id: number; code: string; tier: string }>
    const t04 = criteria.find((c) => c.code === 'T04')
    if (t04) fixture.evaluations[0].criterion_id = t04.id

    await page.route(`**/api/v1/articles/${article.id}/eeat*`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(fixture),
      })
    })

    await page.goto(`/projects/${project.id}/articles/${article.id}/eeat`)
    await expect(page.locator('[data-testid="cs-eeat-veto-banner"]')).toBeVisible()
    await expect(page.locator('[data-testid="cs-eeat-verdict"]')).toContainText('BLOCK')
    // Core badge appears next to the failed criterion (T04 is tier='core').
    await expect(page.locator('[data-testid="cs-eeat-core-badge"]').first()).toBeVisible()

    errors.assertNone()
  })
})
