import { expect, test } from '@playwright/test'

import { createProject, resetProjects, trackConsoleErrors } from '../helpers'

test.describe('project detail — overview tab', () => {
  test.beforeEach(async () => {
    await resetProjects()
  })

  test('renders project metadata + recent activity table', async ({ page }) => {
    const errors = trackConsoleErrors(page)
    const project = await createProject({
      name: 'Overview Project',
      slug: 'overview-project',
      domain: 'overview.example.com',
      niche: 'qa',
    })
    await page.goto(`/projects/${project.id}/overview`)

    await expect(page.getByRole('heading', { name: 'Overview' })).toBeVisible()
    await expect(page.getByText('overview-project').first()).toBeVisible()
    await expect(page.getByText('Project identity')).toBeVisible()
    await expect(page.getByText('Overview Project').first()).toBeVisible()
    await expect(page.getByText('Recent activity')).toBeVisible()
    await expect(page.getByText('Locale')).toBeVisible()
    await expect(page.getByText('Niche')).toBeVisible()
    errors.assertNone()
  })
})
