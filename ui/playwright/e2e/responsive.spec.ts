import { expect, test } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

import {
  BREAKPOINTS,
  createProject,
  resetProjects,
  trackConsoleErrors,
} from '../helpers'

test.describe('responsive viewports — screenshots + axe + zero console errors', () => {
  test.beforeAll(async () => {
    await resetProjects()
  })

  for (const bp of BREAKPOINTS) {
    test(`projects @ ${bp.name}px`, async ({ page }) => {
      await page.setViewportSize({ width: bp.width, height: bp.height })
      const errors = trackConsoleErrors(page)
      await page.goto('/projects')
      await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible()
      await page.screenshot({
        path: `./playwright/screenshots/projects-${bp.name}.png`,
        fullPage: true,
      })
      const results = await new AxeBuilder({ page }).analyze()
      expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([])
      errors.assertNone()
    })
  }

  for (const bp of BREAKPOINTS) {
    test(`project detail tabs @ ${bp.name}px`, async ({ page }) => {
      await page.setViewportSize({ width: bp.width, height: bp.height })
      const errors = trackConsoleErrors(page)
      await resetProjects()
      const project = await createProject({
        name: `Resp ${bp.name}`,
        slug: `resp-${bp.name}`,
        domain: `resp-${bp.name}.example.com`,
      })

      const tabs = ['overview', 'voice', 'compliance', 'eeat', 'targets', 'integrations']
      for (const tab of tabs) {
        await page.goto(`/projects/${project.id}/${tab}`)
        // Wait for the tab heading to render before screenshot/axe.
        await page.waitForLoadState('networkidle', { timeout: 10_000 })
        await page.screenshot({
          path: `./playwright/screenshots/project-${tab}-${bp.name}.png`,
          fullPage: true,
        })
        const results = await new AxeBuilder({ page }).analyze()
        expect(
          results.violations,
          `axe violations on /${tab} @ ${bp.name}: ${JSON.stringify(results.violations, null, 2)}`,
        ).toEqual([])
      }
      errors.assertNone()
    })
  }

  for (const bp of BREAKPOINTS) {
    test(`M5.B list views @ ${bp.name}px`, async ({ page }) => {
      await page.setViewportSize({ width: bp.width, height: bp.height })
      const errors = trackConsoleErrors(page)
      await resetProjects()
      const project = await createProject({
        name: `M5b ${bp.name}`,
        slug: `m5b-${bp.name}`,
        domain: `m5b-${bp.name}.example.com`,
      })

      // Empty-state pass for clusters/topics/articles (no rows seeded).
      const views = ['clusters', 'topics', 'articles']
      for (const v of views) {
        await page.goto(`/projects/${project.id}/${v}`)
        await page.waitForLoadState('networkidle', { timeout: 10_000 })
        await page.screenshot({
          path: `./playwright/screenshots/project-${v}-${bp.name}.png`,
          fullPage: true,
        })
        const results = await new AxeBuilder({ page }).analyze()
        expect(
          results.violations,
          `axe violations on /${v} @ ${bp.name}: ${JSON.stringify(results.violations, null, 2)}`,
        ).toEqual([])
      }
      errors.assertNone()
    })
  }

  for (const bp of BREAKPOINTS) {
    test(`M5.C list views @ ${bp.name}px`, async ({ page }) => {
      await page.setViewportSize({ width: bp.width, height: bp.height })
      const errors = trackConsoleErrors(page)
      await resetProjects()
      const project = await createProject({
        name: `M5c ${bp.name}`,
        slug: `m5c-${bp.name}`,
        domain: `m5c-${bp.name}.example.com`,
      })

      // Empty-state pass for the M5.C views.
      const views = ['interlinks', 'gsc', 'drift', 'runs', 'procedures']
      for (const v of views) {
        await page.goto(`/projects/${project.id}/${v}`)
        await page.waitForLoadState('networkidle', { timeout: 10_000 })
        await page.screenshot({
          path: `./playwright/screenshots/project-${v}-${bp.name}.png`,
          fullPage: true,
        })
        const results = await new AxeBuilder({ page }).analyze()
        expect(
          results.violations,
          `axe violations on /${v} @ ${bp.name}: ${JSON.stringify(results.violations, null, 2)}`,
        ).toEqual([])
      }
      errors.assertNone()
    })
  }

  for (const bp of BREAKPOINTS) {
    test(`M5.C project-detail sub-tabs @ ${bp.name}px`, async ({ page }) => {
      await page.setViewportSize({ width: bp.width, height: bp.height })
      const errors = trackConsoleErrors(page)
      await resetProjects()
      const project = await createProject({
        name: `M5c-tabs ${bp.name}`,
        slug: `m5c-tabs-${bp.name}`,
        domain: `m5c-tabs-${bp.name}.example.com`,
      })

      // Schedules + Cost & Budget sub-tabs.
      const tabs = ['schedules', 'cost-budget']
      for (const tab of tabs) {
        await page.goto(`/projects/${project.id}/${tab}`)
        await page.waitForLoadState('networkidle', { timeout: 10_000 })
        await page.screenshot({
          path: `./playwright/screenshots/project-${tab}-${bp.name}.png`,
          fullPage: true,
        })
        const results = await new AxeBuilder({ page }).analyze()
        expect(
          results.violations,
          `axe violations on /${tab} @ ${bp.name}: ${JSON.stringify(results.violations, null, 2)}`,
        ).toEqual([])
      }
      errors.assertNone()
    })
  }
})
