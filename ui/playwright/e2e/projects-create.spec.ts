import { expect, test } from '@playwright/test'

import { resetProjects, trackConsoleErrors } from '../helpers'

test.describe('projects view — create flow', () => {
  test.beforeEach(async () => {
    await resetProjects()
  })

  test('opens the modal, submits a valid project, and lands on detail', async ({ page }) => {
    const errors = trackConsoleErrors(page)
    await page.goto('/projects')

    await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible()

    // Use the empty-state CTA when present, otherwise the header button.
    const ctaCount = await page.getByRole('button', { name: 'Create project' }).count()
    if (ctaCount > 0) {
      await page.getByRole('button', { name: 'Create project' }).first().click()
    } else {
      await page.getByRole('button', { name: 'New project' }).first().click()
    }

    const dialog = page.getByRole('dialog', { name: 'New project' })
    await expect(dialog).toBeVisible()

    await dialog.getByLabel('Name').fill('Test Site')
    await dialog.getByLabel('Slug').fill('test-site')
    await dialog.getByLabel('Domain').fill('test-site.example.com')
    await dialog.getByLabel('Niche').fill('demo')
    await dialog.getByLabel('Locale').fill('en-US')

    await dialog.getByRole('button', { name: 'Create project' }).click()

    await expect(page).toHaveURL(/\/projects\/\d+\/overview/)
    await expect(page.getByRole('heading', { name: 'Test Site' })).toBeVisible()

    errors.assertNone()
  })
})
