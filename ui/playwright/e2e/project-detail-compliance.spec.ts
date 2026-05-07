import { expect, test } from '@playwright/test'

import { createProject, resetProjects, trackConsoleErrors } from '../helpers'

test.describe('project detail — compliance tab', () => {
  test.beforeEach(async () => {
    await resetProjects()
  })

  test('adds a compliance rule + position dropdown surfaces all enum values', async ({ page }) => {
    const errors = trackConsoleErrors(page)
    const project = await createProject({
      name: 'Compliance Project',
      slug: 'compliance-project',
      domain: 'compliance.example.com',
    })
    await page.goto(`/projects/${project.id}/compliance`)
    await expect(page.getByRole('heading', { name: 'Compliance rules' })).toBeVisible()

    await page.getByRole('button', { name: 'New rule' }).click()
    // Scope to the form (the page has a separate "Filter by kind" select).
    const form = page.locator('h3', { hasText: 'New compliance rule' }).locator('..')
    await form.getByLabel('Title').fill('Affiliate disclosure')
    await form.getByLabel('Kind').selectOption('affiliate-disclosure')

    // The position dropdown must contain all 6 enum values.
    const positionSelect = form.getByLabel('Position')
    const expected = [
      'header',
      'after-intro',
      'footer',
      'every-section',
      'sidebar',
      'hidden-meta',
    ]
    for (const value of expected) {
      await expect(positionSelect.locator(`option[value="${value}"]`)).toHaveCount(1)
    }
    await positionSelect.selectOption('after-intro')

    await form.getByLabel('Markdown editor').fill('We may earn affiliate commissions.')
    await form.getByRole('button', { name: 'Create rule' }).click()
    await expect(page.getByRole('cell', { name: 'Affiliate disclosure' })).toBeVisible()
    errors.assertNone()
  })
})
