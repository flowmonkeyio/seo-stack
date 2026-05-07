import { expect, test } from '@playwright/test'

import { createProject, resetProjects, trackConsoleErrors } from '../helpers'

test.describe('project detail — voice tab', () => {
  test.beforeEach(async () => {
    await resetProjects()
  })

  test('adds a voice profile through the form', async ({ page }) => {
    const errors = trackConsoleErrors(page)
    const project = await createProject({
      name: 'Voice Project',
      slug: 'voice-project',
      domain: 'voice.example.com',
    })
    await page.goto(`/projects/${project.id}/voice`)
    await expect(page.getByRole('heading', { name: 'Voice profiles' })).toBeVisible()
    await page.getByRole('button', { name: 'New voice' }).click()
    await page.getByLabel('Name').fill('Friendly')
    await page.getByLabel('Markdown editor').fill('# Friendly voice\n\nWarm and direct.')
    await page.getByRole('button', { name: 'Create voice' }).click()
    await expect(page.getByRole('cell', { name: 'Friendly' })).toBeVisible()
    errors.assertNone()
  })
})
