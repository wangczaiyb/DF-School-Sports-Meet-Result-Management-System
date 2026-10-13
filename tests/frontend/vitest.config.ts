import path from 'node:path'

const frontend = path.resolve(__dirname, '../../frontend')
export default {
  root: __dirname,
  cacheDir: path.resolve(__dirname, '../.runtime/vite'),
  resolve: {
    alias: { vitest: path.join(frontend, 'node_modules/vitest/dist/index.js') },
  },
  test: {
    include: ['unit/**/*.test.ts'],
  },
}
