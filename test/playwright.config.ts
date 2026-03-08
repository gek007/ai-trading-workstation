import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright E2E Test Configuration for FinAlly
 *
 * Environment variables:
 * - BASE_URL: Default http://localhost:8000
 * - LLM_MOCK: Set to 'true' for deterministic tests
 * - MARKET_SIM_SEED: Set to '42' for reproducible prices
 */
export default defineConfig({
  testDir: './tests',
  fullyParallel: false, // Run tests sequentially for state isolation
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1, // Single worker to avoid port conflicts
  reporter: [
    ['html'],
    ['list'],
    ['json', { outputFile: 'test-results/results.json' }]
  ],

  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:8000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 10000,
    navigationTimeout: 30000,
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  // Run local dev server before starting tests
  webServer: {
    command: 'cd ../backend && uv run start_server.py',
    url: 'http://localhost:8000',
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },

  // Test timeout
  timeout: 60000,
});
