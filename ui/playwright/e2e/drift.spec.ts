import { expect, test } from '@playwright/test'

import { createProject, resetProjects, trackConsoleErrors } from '../helpers'

test.describe('drift view — empty state + threshold slider + M6 deferral notice', () => {
  test.beforeEach(async () => {
    await resetProjects()
  })

  test('renders heading + threshold slider + M6 explainer', async ({ page }) => {
    const errors = trackConsoleErrors(page)
    const project = await createProject({
      name: 'Drift Project',
      slug: 'drift-project',
      domain: 'drift.example.com',
    })

    await page.goto(`/projects/${project.id}/drift`)
    await expect(page.getByRole('heading', { name: 'Drift Watch' })).toBeVisible()
    await expect(page.getByText('No drift baselines yet')).toBeVisible()
    await expect(page.getByLabel('Drift threshold')).toBeVisible()
    await expect(page.getByText('drift comparison engine ships in M6', { exact: false })).toBeVisible()

    // Slider can be moved.
    const slider = page.getByLabel('Drift threshold')
    await slider.fill('0.5')

    errors.assertNone()
  })
})
