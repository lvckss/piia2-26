import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/peritaje',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  expect: { timeout: 5000 },
  use: { baseURL: 'http://127.0.0.1:5183', headless: true, trace: 'retain-on-failure' },
  webServer: {
    command: 'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5183 --strictPort',
    url: 'http://127.0.0.1:5183',
    reuseExistingServer: !process.env.CI,
  },
})
