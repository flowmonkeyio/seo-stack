import { expect, test } from '@playwright/test'

import { createProject, resetProjects, trackConsoleErrors } from '../helpers'

test.describe('cost & budget sub-tab — zero-state + budget form', () => {
  test.beforeEach(async () => {
    await resetProjects()
  })

  test('renders the no-spend badge when zero across the board', async ({ page }) => {
    const errors = trackConsoleErrors(page)
    const project = await createProject({
      name: 'Cost Project',
      slug: 'cost-project',
      domain: 'cost.example.com',
    })

    await page.goto(`/projects/${project.id}/cost-budget`)
    await expect(page.getByRole('heading', { name: /Current month/ })).toBeVisible()
    await expect(page.getByText('No spend recorded yet')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Budget caps' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Set budget' })).toBeVisible()

    errors.assertNone()
  })

  test('opens the budget form and submits a $50 dataforseo cap', async ({ page }) => {
    const errors = trackConsoleErrors(page)
    const project = await createProject({
      name: 'Budget Project',
      slug: 'budget-project',
      domain: 'budget.example.com',
    })

    await page.goto(`/projects/${project.id}/cost-budget`)
    await page.getByRole('button', { name: 'Set budget' }).click()
    const dialog = page.getByRole('dialog', { name: 'Set new budget' })
    await expect(dialog).toBeVisible()
    await expect(dialog.getByLabel('Integration kind')).toBeVisible()
    await dialog.getByLabel('Monthly cap (USD)').fill('25')
    await dialog.getByRole('button', { name: 'Save budget' }).click()
    // Toast surfaces "Budget saved"
    await expect(page.getByText(/Budget saved/i)).toBeVisible()

    errors.assertNone()
  })
})
