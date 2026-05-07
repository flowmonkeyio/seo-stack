import { expect, test } from '@playwright/test'

import {
  createProject,
  getBaseUrl,
  getDaemonToken,
  resetProjects,
  trackConsoleErrors,
} from '../helpers'

test.describe('console errors — zero across full nav', () => {
  test.beforeEach(async () => {
    await resetProjects()
  })

  test('navigates every M5.A + M5.B view; no console.error', async ({ page }) => {
    test.setTimeout(60_000)
    const errors = trackConsoleErrors(page)
    const project = await createProject({
      name: 'Console Project',
      slug: 'console-project',
      domain: 'console.example.com',
    })

    // Seed an article so the article-detail walk covers all 12 tabs.
    const token = getDaemonToken()
    const base = getBaseUrl()
    const aRes = await fetch(`${base}/api/v1/projects/${project.id}/articles`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'content-type': 'application/json',
      },
      body: JSON.stringify({
        title: 'Console nav article',
        slug: 'console-nav',
        eeat_criteria_version: 1,
      }),
    })
    if (!aRes.ok) throw new Error(`create article: ${aRes.status}`)
    const article = ((await aRes.json()) as { data: { id: number } }).data

    const paths = [
      '/projects',
      `/projects/${project.id}/overview`,
      `/projects/${project.id}/voice`,
      `/projects/${project.id}/compliance`,
      `/projects/${project.id}/eeat`,
      `/projects/${project.id}/targets`,
      `/projects/${project.id}/integrations`,
      `/projects/${project.id}/clusters`,
      `/projects/${project.id}/topics`,
      `/projects/${project.id}/articles`,
      `/projects/${project.id}/articles/${article.id}/brief`,
      `/projects/${project.id}/articles/${article.id}/outline`,
      `/projects/${project.id}/articles/${article.id}/draft`,
      `/projects/${project.id}/articles/${article.id}/edited`,
      `/projects/${project.id}/articles/${article.id}/assets`,
      `/projects/${project.id}/articles/${article.id}/sources`,
      `/projects/${project.id}/articles/${article.id}/schema`,
      `/projects/${project.id}/articles/${article.id}/publishes`,
      `/projects/${project.id}/articles/${article.id}/eeat`,
      `/projects/${project.id}/articles/${article.id}/versions`,
      `/projects/${project.id}/articles/${article.id}/interlinks`,
      `/projects/${project.id}/articles/${article.id}/drift`,
      `/projects/${project.id}/runs`,
    ]
    for (const path of paths) {
      await page.goto(path)
      await page.waitForLoadState('networkidle', { timeout: 10_000 })
    }
    expect(errors.errors, errors.errors.join('\n')).toEqual([])
  })
})
