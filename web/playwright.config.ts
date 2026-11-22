import { defineConfig, devices } from '@playwright/test';

const externalBaseUrl = process.env.PLAYWRIGHT_BASE_URL;
const localPort = Number(process.env.PLAYWRIGHT_PORT || 3100);
const mockPort = Number(process.env.MOCK_ORCHESTRATOR_PORT || 18080);

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: externalBaseUrl || `http://127.0.0.1:${localPort}`,
    trace: 'on-first-retry',
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }
      : undefined,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: externalBaseUrl
    ? undefined
    : [
        {
          command: 'node tests/e2e/mock-orchestrator.mjs',
          url: `http://127.0.0.1:${mockPort}/healthz`,
          reuseExistingServer: !process.env.CI,
          timeout: 15_000,
          env: {
            MOCK_ORCHESTRATOR_PORT: String(mockPort),
          },
        },
        {
          command: `pnpm exec next dev --port ${localPort}`,
          url: `http://127.0.0.1:${localPort}`,
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
          env: {
            LOCAL_DEV_ORCHESTRATOR_URL: `http://127.0.0.1:${mockPort}`,
          },
        },
      ],
});
