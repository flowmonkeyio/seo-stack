import { expect, test, type Page } from '@playwright/test'

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

const FORBIDDEN_ACTION_RE =
  /^(new|create|add|edit|save|delete|run|publish|approve|reject|apply|dismiss|connect|reconnect|test|mark|set|suggest|repair)\b/i

async function expectNoForbiddenActionButtons(page: Page): Promise<void> {
  const matches = page.getByRole('button', { name: FORBIDDEN_ACTION_RE })
  await expect(matches).toHaveCount(0)
}

test.describe('observer-mode UI contract', () => {
  test.beforeEach(async () => {
    await resetProjects()
  })

  test('navigating the exposed UI only issues safe API reads', async ({ page }) => {
    test.setTimeout(90_000)
    const errors = trackConsoleErrors(page)
    const unsafeRequests: string[] = []
    page.on('request', (request) => {
      const url = new URL(request.url())
      if (!url.pathname.startsWith('/api/') && !url.pathname.startsWith('/mcp')) return
      if (['GET', 'HEAD', 'OPTIONS'].includes(request.method())) return
      unsafeRequests.push(`${request.method()} ${url.pathname}`)
    })

    const project = await createProject({
      name: 'Observer Project',
      slug: 'observer-project',
      domain: 'observer.example.com',
    })
    const article = await createArticle(project.id, {
      title: 'Observer Article',
      slug: 'observer-article',
    })

    const routes = [
      '/projects',
      `/projects/${project.id}/overview`,
      `/projects/${project.id}/voice`,
      `/projects/${project.id}/compliance`,
      `/projects/${project.id}/eeat`,
      `/projects/${project.id}/targets`,
      `/projects/${project.id}/integrations`,
      `/projects/${project.id}/schedules`,
      `/projects/${project.id}/cost-budget`,
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
      `/projects/${project.id}/interlinks`,
      `/projects/${project.id}/gsc`,
      `/projects/${project.id}/drift`,
      `/projects/${project.id}/runs`,
      `/projects/${project.id}/procedures`,
    ]

    for (const route of routes) {
      await page.goto(route)
      await page.waitForLoadState('networkidle', { timeout: 10_000 })
      await expectNoForbiddenActionButtons(page)
    }

    expect(unsafeRequests).toEqual([])
    errors.assertNone()
  })

  test('browser bootstrap token is rejected for mutations', async ({ page }) => {
    await page.goto('/projects')
    const result = await page.evaluate(async () => {
      const tokenResponse = await fetch('/api/v1/auth/ui-token')
      const { token } = (await tokenResponse.json()) as { token: string }
      const writeResponse = await fetch('/api/v1/projects', {
        method: 'POST',
        headers: {
          authorization: `Bearer ${token}`,
          'content-type': 'application/json',
        },
        body: JSON.stringify({
          slug: 'ui-forbidden-write',
          name: 'UI Forbidden Write',
          domain: 'ui-forbidden.example.com',
          locale: 'en-US',
        }),
      })
      return {
        status: writeResponse.status,
        body: await writeResponse.json(),
      }
    })

    expect(result.status).toBe(403)
    expect(result.body.detail).toContain('read-only')
  })
})
