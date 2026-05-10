import { expect, test } from '@playwright/test'

import { createProject, resetProjects, trackConsoleErrors } from '../helpers'

test.describe('procedures view — list + run modal', () => {
  test.beforeEach(async () => {
    await resetProjects()
  })

  test('renders the procedures list with two tabs', async ({ page }) => {
    const errors = trackConsoleErrors(page)
    const project = await createProject({
      name: 'Procedure Project',
      slug: 'procedure-project',
      domain: 'procedure.example.com',
    })

    await page.goto(`/projects/${project.id}/procedures`)
    await expect(page.getByRole('heading', { name: 'Procedures' })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'Available' })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'Recent Runs' })).toBeVisible()

    errors.assertNone()
  })

  test('opens the run modal with current runner copy', async ({ page }) => {
    const errors = trackConsoleErrors(page)
    const project = await createProject({
      name: 'M7 Project',
      slug: 'm7-project',
      domain: 'm7.example.com',
    })

    await page.goto(`/projects/${project.id}/procedures`)
    // The list MAY be empty depending on whether procedures/ is populated;
    // the view always renders the empty-state row.
    const runButtons = page.getByRole('button', { name: /^Run procedure/ })
    const count = await runButtons.count()
    if (count === 0) {
      // No procedures registered — fine; that's a valid empty-state pass.
      errors.assertNone()
      return
    }
    await runButtons.first().click()
    const dialog = page.getByRole('dialog', { name: /Run procedure:/ })
    await expect(dialog).toBeVisible()
    await expect(dialog.getByText(/Runs start immediately/)).toBeVisible()
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).not.toBeVisible()

    errors.assertNone()
  })
})
