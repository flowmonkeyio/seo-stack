import { expect, test } from '@playwright/test'

import {
  createProject,
  getBaseUrl,
  getDaemonToken,
  resetProjects,
  trackConsoleErrors,
} from '../helpers'

async function createTopic(
  projectId: number,
  body: { title: string; primary_kw?: string; intent?: string; status?: string; source?: string },
) {
  const token = getDaemonToken()
  const base = getBaseUrl()
  const res = await fetch(`${base}/api/v1/projects/${projectId}/topics`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'content-type': 'application/json' },
    body: JSON.stringify({
      title: body.title,
      primary_kw: body.primary_kw ?? '',
      intent: body.intent ?? 'informational',
      status: body.status ?? 'queued',
      source: body.source ?? 'manual',
    }),
  })
  if (!res.ok) throw new Error(`create topic: ${res.status}`)
  return ((await res.json()) as { data: { id: number } }).data
}

test.describe('topics view — create + bulk approve + filters', () => {
  test.beforeEach(async () => {
    await resetProjects()
  })

  test('creates a topic via UI, filters by status, bulk approves selected rows', async ({
    page,
  }) => {
    const errors = trackConsoleErrors(page)
    const project = await createProject({
      name: 'Topic Project',
      slug: 'topic-project',
      domain: 'topic.example.com',
    })

    await page.goto(`/projects/${project.id}/topics`)
    await expect(page.getByRole('heading', { name: 'Topics' })).toBeVisible()
    await expect(page.getByText('No topics yet')).toBeVisible()

    // Create a topic via the modal.
    await page.getByRole('button', { name: 'Create topic' }).first().click()
    const dialog = page.getByRole('dialog', { name: 'New topic' })
    await expect(dialog).toBeVisible()
    await dialog.getByLabel('Title').fill('How to evaluate a sportsbook')
    await dialog.getByLabel('Primary keyword').fill('best sportsbook')
    await dialog.getByRole('button', { name: 'Create topic' }).click()
    await expect(
      page.getByRole('cell', { name: 'How to evaluate a sportsbook' }),
    ).toBeVisible()

    // Seed two more rows directly via REST so we have three queued topics.
    await createTopic(project.id, { title: 'Best odds boost' })
    await createTopic(project.id, { title: 'Top free bets in May' })

    // Reload to refetch the list.
    await page.reload()
    await expect(page.getByRole('cell', { name: 'Best odds boost' })).toBeVisible()

    // Switch to the "Queued" pill — should still show all three.
    await page.getByRole('tab', { name: 'Queued' }).click()
    await expect(
      page.getByRole('cell', { name: 'Top free bets in May' }),
    ).toBeVisible()

    // Select all three via the row checkboxes (DataTable selection).
    const checkboxes = page.getByRole('checkbox', { name: /Select row/ })
    await checkboxes.nth(0).click()
    await checkboxes.nth(1).click()
    await checkboxes.nth(2).click()

    // Bulk-approve banner should appear.
    await expect(page.getByText(/3 selected/)).toBeVisible()
    await page.getByRole('button', { name: 'Approve selected' }).click()

    // Switch to "Approved" pill — three rows now match.
    await page.getByRole('tab', { name: 'Approved' }).click()
    await expect(
      page.getByRole('cell', { name: 'How to evaluate a sportsbook' }),
    ).toBeVisible()
    await expect(page.getByRole('cell', { name: 'Best odds boost' })).toBeVisible()
    await expect(
      page.getByRole('cell', { name: 'Top free bets in May' }),
    ).toBeVisible()

    errors.assertNone()
  })
})
