import { expect, test } from '@playwright/test'

import {
  createProject,
  resetProjects,
  trackConsoleErrors,
} from '../helpers'

test.describe('console errors — zero across full nav', () => {
  test.beforeEach(async () => {
    await resetProjects()
  })

  test('navigates every M5.A view + a placeholder; no console.error', async ({ page }) => {
    const errors = trackConsoleErrors(page)
    const project = await createProject({
      name: 'Console Project',
      slug: 'console-project',
      domain: 'console.example.com',
    })
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
      `/projects/${project.id}/runs`,
    ]
    for (const path of paths) {
      await page.goto(path)
      await page.waitForLoadState('networkidle', { timeout: 10_000 })
    }
    expect(errors.errors, errors.errors.join('\n')).toEqual([])
  })
})
