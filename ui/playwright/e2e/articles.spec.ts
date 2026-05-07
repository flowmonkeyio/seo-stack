import { expect, test } from '@playwright/test'

import { createProject, resetProjects, trackConsoleErrors } from '../helpers'

test.describe('articles view — create + filter + click into detail', () => {
  test.beforeEach(async () => {
    await resetProjects()
  })

  test('creates a fresh article and lands on the brief tab', async ({ page }) => {
    const errors = trackConsoleErrors(page)
    const project = await createProject({
      name: 'Article Project',
      slug: 'article-project',
      domain: 'article.example.com',
    })

    await page.goto(`/projects/${project.id}/articles`)
    await expect(page.getByRole('heading', { name: 'Articles' })).toBeVisible()

    // Click the empty-state CTA.
    await page.getByRole('button', { name: 'Create article' }).first().click()
    const dialog = page.getByRole('dialog', { name: 'New article' })
    await expect(dialog).toBeVisible()
    await dialog.getByLabel('Title').fill('How to evaluate a sportsbook')
    // Slug auto-populates from title; allow it to stand.
    await dialog.getByRole('button', { name: 'Create article' }).click()

    // Lands on detail with the brief tab + status timeline.
    await expect(page).toHaveURL(/\/projects\/\d+\/articles\/\d+\/brief$/)
    await expect(
      page.getByRole('heading', { name: 'How to evaluate a sportsbook' }),
    ).toBeVisible()
    // Status badge "briefing" is visible.
    await expect(page.locator('[data-status="briefing"]')).toBeVisible()
    // Status timeline is rendered.
    await expect(page.getByLabel('Article status timeline')).toBeVisible()

    errors.assertNone()
  })
})
