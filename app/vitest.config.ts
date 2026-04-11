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
      // baseline (lines/stmts 15.3%, fns 33.1%, branches 68.6%). The included globs span whole feature
      // dirs pure transform/lib logic is well covered by *.test.ts; React rendering is exercised by
      // the Playwright E2E, not unit tests so this floor guards against *losing* coverage (deleting
      // tests, landing large untested modules) rather than asserting a high quality bar. Raise it when
      // coverage rises; never lower it without cause.
      //
      // The lines/stmts figures dropped from ~33% to ~15% on the vitest 2 -> 3 upgrade: the same
      // 309 tests run, but coverage-v8 3 counts every file matched by `include` (with `all` true by
      // default) in the denominator, including the untested-by-design React page/methodology/query
      // modules that v2 left out. That is the more honest measure (untested modules now drag the
      // number down), so the floor was re-baselined to the new actuals rather than papered over.
      thresholds: {
        statements: 15,
        branches: 68,
        functions: 32,
        lines: 15,
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
