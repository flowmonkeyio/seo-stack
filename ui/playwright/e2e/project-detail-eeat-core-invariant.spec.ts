import { expect, test } from '@playwright/test'

import {
  createProject,
  getBaseUrl,
  getDaemonToken,
  resetProjects,
  trackConsoleErrors,
} from '../helpers'

test.describe('project detail — EEAT core invariant', () => {
  test.beforeEach(async () => {
    await resetProjects()
  })

  test('core rows are read-only in the UI and the server refuses 409 on mutation', async ({
    page,
  }) => {
    const errors = trackConsoleErrors(page)
    const project = await createProject({
      name: 'EEAT Project',
      slug: 'eeat-project',
      domain: 'eeat.example.com',
    })
    await page.goto(`/projects/${project.id}/eeat`)
    await expect(page.getByRole('heading', { name: 'EEAT criteria' })).toBeVisible()

    // Find a row tagged "core" — at least T04, C01, R10 are seeded as core
    // per PLAN.md D7 / §schema.
    const coreLabel = page.locator('span', { hasText: 'core' }).first()
    await expect(coreLabel).toBeVisible()
    await expect(page.getByRole('button', { name: /edit criterion/i })).toHaveCount(0)

    // Find the criterion id on a core row from the server, then directly
    // try to PATCH active=false. Server must respond 409.
    const token = getDaemonToken()
    const base = getBaseUrl()
    const listRes = await fetch(`${base}/api/v1/projects/${project.id}/eeat`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    const list = (await listRes.json()) as Array<{
      id: number
      tier: string
      active: boolean
    }>
    const target = list.find((c) => c.tier === 'core' && c.active)
    expect(target, 'expected at least one tier=core active criterion').toBeTruthy()
    const patchRes = await fetch(
      `${base}/api/v1/projects/${project.id}/eeat/${target!.id}`,
      {
        method: 'PATCH',
        headers: {
          Authorization: `Bearer ${token}`,
          'content-type': 'application/json',
        },
        body: JSON.stringify({ active: false }),
      },
    )
    expect(patchRes.status).toBe(409)
    errors.assertNone()
  })
})
