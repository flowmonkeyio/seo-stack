import { expect, test } from '@playwright/test'

import { createProject, resetProjects, trackConsoleErrors } from '../helpers'

test.describe('interlinks view — empty state + suggest + repair modal', () => {
  test.beforeEach(async () => {
    await resetProjects()
  })

  test('renders empty state, status pills, and the suggest button', async ({ page }) => {
    const errors = trackConsoleErrors(page)
    const project = await createProject({
      name: 'Interlink Project',
      slug: 'interlink-project',
      domain: 'interlink.example.com',
    })

    await page.goto(`/projects/${project.id}/interlinks`)
    await expect(page.getByRole('heading', { name: 'Interlinks' })).toBeVisible()
    await expect(page.getByText('No interlinks yet')).toBeVisible()
    await expect(page.getByRole('tab', { name: 'Suggested' })).toBeVisible()
    await expect(
      page.getByRole('button', { name: 'Suggest interlinks' }).first(),
    ).toBeVisible()

    errors.assertNone()
  })

  test('opens the repair modal and cancels cleanly', async ({ page }) => {
    const errors = trackConsoleErrors(page)
    const project = await createProject({
      name: 'Repair Project',
      slug: 'repair-project',
      domain: 'repair.example.com',
    })

    await page.goto(`/projects/${project.id}/interlinks`)
    await page.getByRole('button', { name: 'Repair' }).click()
    const dialog = page.getByRole('dialog', { name: 'Repair interlinks' })
    await expect(dialog).toBeVisible()
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).not.toBeVisible()

    errors.assertNone()
  })
})
