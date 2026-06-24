import { defineConfig, devices } from '@playwright/test'

// End-to-end smoke suite. Drives the production bundle in a
// real browser to prove the three heavy client-side subsystems boot and produce output: DuckDB-wasm
// init + a real parquet query, an in-browser ONNX inference, and the additive-identity UI.
//
// Two run modes:
//   • Default (CI app gate / `make app-e2e`): no E2E_BASE_URL, so Playwright builds-then-serves the
//     prod bundle via `vite preview` on :4173 (cross-origin-isolated see vite.config.ts `preview`),
//     which fetches data + models from the live GCS CDN. Self-contained; needs no warehouse.
//   • Against a deploy: set E2E_BASE_URL=https://… (e.g. a Firebase preview channel) to skip the
//     local server and smoke the real deploy exactly the "run against a preview deploy" the audit asks for.
//
// Chromium only: DuckDB-wasm + onnxruntime-web rely on cross-origin isolation + wasm threads; Chromium
// is the reference engine the app targets and what prod is verified against.
const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:4173'

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.e2e.ts',
  // Generous: a cold run pays DuckDB-wasm instantiation + cross-origin parquet fetches + ONNX warmup.
  timeout: 90_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  // wasm threads are resource-hungry; one worker in CI avoids contention flaking the suite.
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI
    ? [['list'], ['html', { open: 'never' }]]
    : [['list']],
  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  // Serve the prod bundle locally unless pointed at a live deploy. Requires a prior `pnpm build`
  // (the make target / CI build the app first); reuses an already-running preview when developing.
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: 'pnpm exec vite preview --port 4173 --strictPort',
        url: 'http://localhost:4173',
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
})
