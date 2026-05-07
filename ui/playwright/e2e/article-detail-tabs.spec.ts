import { expect, test } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

import {
  BREAKPOINTS,
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

const TABS = [
  'brief',
  'outline',
  'draft',
  'edited',
  'assets',
  'sources',
  'schema',
  'publishes',
  'eeat',
  'versions',
  'interlinks',
  'drift',
] as const

test.describe('article-detail tabs — render at every breakpoint', () => {
  test.beforeAll(async () => {
    await resetProjects()
  })

  for (const bp of BREAKPOINTS) {
    test(`every tab @ ${bp.name}px renders + axe + zero console errors`, async ({ page }) => {
      test.setTimeout(120_000)
      await page.setViewportSize({ width: bp.width, height: bp.height })
      const errors = trackConsoleErrors(page)
      await resetProjects()
      const project = await createProject({
        name: `Detail ${bp.name}`,
        slug: `detail-${bp.name}`,
        domain: `detail-${bp.name}.example.com`,
      })
      const article = await createArticle(project.id, {
        title: `Detail @ ${bp.name}`,
        slug: `detail-${bp.name}-slug`,
      })

      for (const tab of TABS) {
        await page.goto(`/projects/${project.id}/articles/${article.id}/${tab}`)
        await page.waitForLoadState('networkidle', { timeout: 15_000 })
        await page.screenshot({
          path: `./playwright/screenshots/article-detail-${tab}-${bp.name}.png`,
          fullPage: true,
        })
        const results = await new AxeBuilder({ page }).analyze()
        expect(
          results.violations,
          `axe violations on /${tab} @ ${bp.name}: ${JSON.stringify(results.violations, null, 2)}`,
        ).toEqual([])
      }
      errors.assertNone()
    })
  }
})
