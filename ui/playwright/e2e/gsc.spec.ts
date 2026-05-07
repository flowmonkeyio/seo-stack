import { expect, test } from '@playwright/test'

import { createProject, resetProjects, trackConsoleErrors } from '../helpers'

test.describe('gsc view — three tabs + redirect modal', () => {
  test.beforeEach(async () => {
    await resetProjects()
  })

  test('switches between Raw / Daily Rollup / Redirects', async ({ page }) => {
    const errors = trackConsoleErrors(page)
    const project = await createProject({
      name: 'GSC Project',
      slug: 'gsc-project',
      domain: 'gsc.example.com',
    })

    await page.goto(`/projects/${project.id}/gsc`)
    await expect(page.getByRole('heading', { name: 'GSC Metrics' })).toBeVisible()

    await expect(page.getByRole('tab', { name: 'Raw' })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'Daily Rollup' })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'Redirects' })).toBeVisible()

    await page.getByRole('tab', { name: 'Daily Rollup' }).click()
    await expect(page.getByRole('table', { name: 'Daily GSC rollup' })).toBeVisible()

    await page.getByRole('tab', { name: 'Redirects' }).click()
    await expect(page.getByRole('button', { name: 'New Redirect' })).toBeVisible()

    errors.assertNone()
  })

  test('opens the rollup modal and cancels cleanly', async ({ page }) => {
    const errors = trackConsoleErrors(page)
    const project = await createProject({
      name: 'Rollup Project',
      slug: 'rollup-project',
      domain: 'rollup.example.com',
    })

    await page.goto(`/projects/${project.id}/gsc`)
    await page.getByRole('button', { name: 'Run rollup now' }).click()
    const dialog = page.getByRole('dialog', { name: 'Run GSC rollup' })
    await expect(dialog).toBeVisible()
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).not.toBeVisible()

    errors.assertNone()
  })
})
