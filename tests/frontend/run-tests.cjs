const path = require('node:path')
const { spawnSync } = require('node:child_process')

const frontend = path.resolve(__dirname, '../../frontend')
const modules = path.join(frontend, 'node_modules')
const mode = process.argv[2]
if (!['unit', 'e2e'].includes(mode)) throw new Error('Expected unit or e2e')
const cli = mode === 'unit'
  ? path.join(modules, 'vitest/vitest.mjs')
  : path.join(modules, '@playwright/test/cli.js')
const config = path.join(__dirname, mode === 'unit' ? 'vitest.config.ts' : 'playwright.config.ts')
const result = spawnSync(process.execPath, [cli, mode === 'unit' ? 'run' : 'test', '--config', config, ...process.argv.slice(3)], {
  cwd: frontend,
  env: { ...process.env, NODE_PATH: [modules, process.env.NODE_PATH].filter(Boolean).join(path.delimiter) },
  stdio: 'inherit',
})
if (result.error) throw result.error
process.exit(result.status ?? 1)
