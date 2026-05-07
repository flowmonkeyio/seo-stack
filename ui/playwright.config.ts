// Playwright config for content-stack UI E2E tests.
//
// Wires:
//   - global setup that spawns the daemon on port 5181 and waits for /health
//   - global teardown that kills the daemon
//   - default 1280x800 viewport (responsive.spec.ts overrides per-test)
//   - JSON + HTML reporters for CI

import { defineConfig, devices } from '@playwright/test'

const PORT = Number(process.env.CS_E2E_PORT ?? 5181)
const BASE_URL = `http://127.0.0.1:${PORT}`

export default defineConfig({
  testDir: './playwright/e2e',
  outputDir: './playwright/.pw-results',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false, // single shared daemon
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [['list'], ['html', { outputFolder: './playwright/.pw-html-report', open: 'never' }]],
  globalSetup: './playwright/global-setup.ts',
  globalTeardown: './playwright/global-teardown.ts',
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    viewport: { width: 1280, height: 800 },
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
