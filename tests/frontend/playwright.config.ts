import path from 'node:path'
import fs from 'node:fs'
const { defineConfig } = require('@playwright/test')
const project = path.resolve(__dirname, '../..')
const runtime = process.env.SPORTS_E2E_RUNTIME_DIR || path.resolve(__dirname, '../.runtime/e2e')
fs.mkdirSync(runtime, { recursive: true })

export default defineConfig({
  testDir: './e2e',
  outputDir: path.join(runtime, 'test-results'),
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
      cwd: project,
      env: {
        DATABASE_URL: `sqlite:///${path.join(runtime, 'test.db').replaceAll('\\', '/')}`,
        EXPORT_DIR: path.join(runtime, 'exports'),
        AUTO_SEED: 'true',
        CORS_ORIGINS: 'http://127.0.0.1:5174',
      },
      url: 'http://127.0.0.1:8001/health',
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5174',
      cwd: path.join(project, 'frontend'),
      env: { VITE_API_BASE_URL: 'http://127.0.0.1:8001/api/v1' },
      url: 'http://127.0.0.1:5174/login',
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
})
