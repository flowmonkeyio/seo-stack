import { expect, test } from '@playwright/test'

import {
  getBaseUrl,
  getDaemonToken,
  resetProjects,
  trackConsoleErrors,
} from '../helpers'

// The daemon does NOT support hard-delete in M5.A — `DELETE` is a soft
// delete that sets `is_active=false` but leaves the row visible to the
// list endpoint. To exercise the empty-state code path we restart the
// daemon by deleting and re-creating the database file… but that's heavy
// for a single assertion. The pragmatic alternative: reset projects, then
// verify the list endpoint actually returns zero rows from the user's
// point of view (the soft-deleted rows still appear, so we look at the
// projects view's emptiness via the data table's empty-state cell rather
// than a header "No projects yet" headline that only fires when the API
// is genuinely empty).

test.describe('projects view — empty state', () => {
  test.beforeEach(async () => {
    await resetProjects()
  })

  test('shows the Projects heading + new-project CTA', async ({ page }) => {
    const errors = trackConsoleErrors(page)
    await page.goto('/projects')
    await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'New project' })).toBeVisible()

    // Either: the daemon's project list is genuinely empty (M5.A clean
    // install) AND the empty-state CTA appears, OR the daemon has rows
    // from prior tests soft-deleted but still listed AND we see the
    // table. Both branches are valid M5.A behaviour. We just verify
    // the page renders without console errors.
    const token = getDaemonToken()
    const base = getBaseUrl()
    const res = await fetch(`${base}/api/v1/projects?limit=1`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(res.ok).toBeTruthy()
    const body = (await res.json()) as { items: unknown[] }
    if (body.items.length === 0) {
      await expect(page.getByText('No projects yet').first()).toBeVisible()
    } else {
      await expect(page.getByRole('table', { name: 'Projects' })).toBeVisible()
    }
    errors.assertNone()
  })
})
