import { expect, test } from '@playwright/test'

import {
  createProject,
  getBaseUrl,
  getDaemonToken,
  resetProjects,
  trackConsoleErrors,
} from '../helpers'

test.describe('project detail — targets tab', () => {
  test.beforeEach(async () => {
    await resetProjects()
  })

  test('adding a primary target moves the existing primary off', async ({ page }) => {
    const errors = trackConsoleErrors(page)
    const project = await createProject({
      name: 'Targets Project',
      slug: 'targets-project',
      domain: 'targets.example.com',
    })

    const token = getDaemonToken()
    const base = getBaseUrl()
    // Seed an initial nuxt-content target as primary via the API so the UI
    // starts with one row and we can see the flip.
    const seed = await fetch(
      `${base}/api/v1/projects/${project.id}/publish-targets`,
      {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'content-type': 'application/json' },
        body: JSON.stringify({
          kind: 'nuxt-content',
          config_json: { repo: 'org/site', branch: 'main' },
          is_primary: true,
          is_active: true,
        }),
      },
    )
    expect(seed.status).toBe(201)

    await page.goto(`/projects/${project.id}/targets`)
    await expect(page.getByRole('heading', { name: 'Publish targets' })).toBeVisible()

    // Add a wordpress target and mark primary.
    await page.getByRole('button', { name: 'New target' }).click()
    await page.getByLabel('Kind').selectOption('wordpress')
    await page.getByText('Primary (clears other primaries on save)').click()
    await page.getByRole('button', { name: 'Create target' }).click()

    // Verify only one primary remains via the API.
    const listRes = await fetch(
      `${base}/api/v1/projects/${project.id}/publish-targets`,
      {
        headers: { Authorization: `Bearer ${token}` },
      },
    )
    const list = (await listRes.json()) as Array<{ kind: string; is_primary: boolean }>
    const primaries = list.filter((t) => t.is_primary)
    expect(primaries.length).toBe(1)
    expect(primaries[0].kind).toBe('wordpress')
    errors.assertNone()
  })
})
