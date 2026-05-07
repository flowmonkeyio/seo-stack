import { expect, test } from '@playwright/test'

import { createProject, resetProjects, trackConsoleErrors } from '../helpers'

test.describe('clusters view — create + tree display', () => {
  test.beforeEach(async () => {
    await resetProjects()
  })

  test('creates a pillar then a spoke under it; tree renders both', async ({ page }) => {
    const errors = trackConsoleErrors(page)
    const project = await createProject({
      name: 'Cluster Project',
      slug: 'cluster-project',
      domain: 'cluster.example.com',
    })
    await page.goto(`/projects/${project.id}/clusters`)
    await expect(page.getByRole('heading', { name: 'Clusters' })).toBeVisible()

    // Empty state shows the CTA.
    await expect(page.getByText('No clusters yet')).toBeVisible()
    await page.getByRole('button', { name: 'Create cluster' }).first().click()

    const dialog = page.getByRole('dialog', { name: 'New cluster' })
    await expect(dialog).toBeVisible()
    await dialog.getByLabel('Name').fill('How-to guides')
    // Type defaults to pillar; parent stays null.
    await dialog.getByRole('button', { name: 'Create cluster' }).click()

    // Pillar lands as a row + a side-panel heading. Lock to the row button.
    await expect(
      page.getByRole('button', { name: /How-to guides\s+pillar/ }),
    ).toBeVisible()

    // Add a spoke under it via the row's "+ child" button.
    const childBtn = page.getByRole('button', { name: 'Add child cluster under How-to guides' })
    await childBtn.click()
    const dialog2 = page.getByRole('dialog', { name: 'New cluster' })
    await expect(dialog2).toBeVisible()
    await dialog2.getByLabel('Name').fill('Sportsbook how-to')
    // Type pre-populated to "spoke", parent_id = pillar.id.
    await dialog2.getByRole('button', { name: 'Create cluster' }).click()

    // Spoke is rendered as a row.
    await expect(
      page.getByRole('button', { name: /Sportsbook how-to\s+spoke/ }),
    ).toBeVisible()

    errors.assertNone()
  })
})
