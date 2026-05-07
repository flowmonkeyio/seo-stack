import { expect, test } from '@playwright/test'

import { createProject, resetProjects, trackConsoleErrors } from '../helpers'

test.describe('schedules sub-tab — empty state + add modal', () => {
  test.beforeEach(async () => {
    await resetProjects()
  })

  test('renders Schedules tab and the empty state', async ({ page }) => {
    const errors = trackConsoleErrors(page)
    const project = await createProject({
      name: 'Schedules Project',
      slug: 'schedules-project',
      domain: 'schedules.example.com',
    })

    await page.goto(`/projects/${project.id}/schedules`)
    await expect(page.getByRole('heading', { name: 'Scheduled jobs' })).toBeVisible()
    await expect(page.getByText('No scheduled jobs yet')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Add schedule' })).toBeVisible()

    errors.assertNone()
  })

  test('opens the add-schedule modal and cancels cleanly', async ({ page }) => {
    const errors = trackConsoleErrors(page)
    const project = await createProject({
      name: 'Schedules Modal Project',
      slug: 'schedules-modal-project',
      domain: 'schedules-modal.example.com',
    })

    await page.goto(`/projects/${project.id}/schedules`)
    await page.getByRole('button', { name: 'Add schedule' }).click()
    const dialog = page.getByRole('dialog', { name: 'Add schedule' })
    await expect(dialog).toBeVisible()
    // Validate that the form fields exist
    await expect(dialog.getByLabel('Kind')).toBeVisible()
    await expect(dialog.getByLabel('Cron expression')).toBeVisible()
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).not.toBeVisible()

    errors.assertNone()
  })
})
