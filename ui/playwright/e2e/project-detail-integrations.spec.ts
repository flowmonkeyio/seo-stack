import { expect, test } from '@playwright/test'

import {
  createProject,
  getBaseUrl,
  getDaemonToken,
  resetProjects,
  trackConsoleErrors,
} from '../helpers'

test.describe('project detail — integrations tab', () => {
  test.beforeEach(async () => {
    await resetProjects()
  })

  test('add integration; click Test; verify a toast appears', async ({ page }) => {
    const errors = trackConsoleErrors(page)
    const project = await createProject({
      name: 'Integrations Project',
      slug: 'integrations-project',
      domain: 'integrations.example.com',
    })

    const token = getDaemonToken()
    const base = getBaseUrl()
    // Seed one credential via API so the UI list isn't empty (the form
    // requires payload material that's painful to drive via Playwright).
    const seed = await fetch(
      `${base}/api/v1/projects/${project.id}/integrations`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'content-type': 'application/json',
        },
        body: JSON.stringify({
          kind: 'firecrawl',
          plaintext_payload: 'fake-key-for-test',
          config_json: {},
          expires_at: null,
        }),
      },
    )
    expect(seed.status).toBe(201)

    await page.goto(`/projects/${project.id}/integrations`)
    await expect(page.getByRole('heading', { name: 'Project integrations' })).toBeVisible()
    await expect(page.getByText('firecrawl')).toBeVisible()
    // Click Test — the wrapper is unimplemented for this fake key, the
    // server will return 502 / surface an error toast. Either way we
    // expect a toast to appear (success OR failure both produce one).
    const testBtn = page.getByRole('button', { name: /^Test/ }).first()
    await testBtn.click()
    // Toast region is role=status, aria-live polite.
    await expect(page.locator('[role="status"]').first()).toBeVisible({ timeout: 15_000 })
    errors.assertNone()
  })
})
