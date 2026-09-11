import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  fullyParallel: false,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:5174',
    channel: 'msedge',
    headless: true,
    viewport: { width: 1440, height: 900 },
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: 'python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001',
      cwd: '..',
      env: {
        DATABASE_URL: 'sqlite:///./data/CODEX_TEST_playwright.db',
        AUTO_SEED: 'true',
        CORS_ORIGINS: 'http://127.0.0.1:5174',
      },
      url: 'http://127.0.0.1:8001/health',
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5174',
      cwd: '.',
      env: { VITE_API_BASE_URL: 'http://127.0.0.1:8001/api/v1' },
      url: 'http://127.0.0.1:5174/login',
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
})
