import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'happy-dom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
    coverage: {
      provider: 'v8',
      include: ['src/features/**', 'src/lib/**', 'src/data/**'],
      exclude: ['**/*.fixture.ts', '**/*.types.ts'],
      // Regression ratchet, set just below the current
      // baseline (lines/stmts 33%, fns 34%, branches 79%). The included globs span whole feature
      // dirs pure transform/lib logic is well covered by *.test.ts; React rendering is exercised by
      // the Playwright E2E, not unit tests so this floor guards against *losing* coverage (deleting
      // tests, landing large untested modules) rather than asserting a high quality bar. Raise it when
      // coverage rises; never lower it without cause.
      thresholds: {
        statements: 32,
        branches: 78,
        functions: 33,
        lines: 32,
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
