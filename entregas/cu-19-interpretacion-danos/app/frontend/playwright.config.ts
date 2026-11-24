import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/peritaje',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  expect: { timeout: 5000 },
  use: { baseURL: 'http://127.0.0.1:5174', headless: true, trace: 'retain-on-failure' },
  webServer: {
    command: 'bun run dev --host 127.0.0.1 --port 5174',
    url: 'http://127.0.0.1:5174',
    reuseExistingServer: !process.env.CI,
  },
})
