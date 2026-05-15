# app/ React + DuckDB-Wasm Frontend

**Complete and deployed.** The browser-side analytics app that surfaces F1 race data with zero compute server. DuckDB-Wasm runs SQL in WebAssembly; queries against the gold Parquet files complete in sub-10ms. Deployed to Firebase Hosting with 35 passing tests.

## Architecture

```
Firebase Storage (off-the-pace-cdn) → data/*.parquet + models/*.onnx
        ↓
data/duckdb/client.ts   (DuckDB-Wasm singleton; query() runs SQL in-browser)
data/manifest.ts        (resolves Parquet paths via DATA_CDN_BASE)
data/hooks/             (useQuery, useRaces, useDrivers, useDatabaseStatus)
        ↓
routes/**/*.tsx         (40 route components across 8 pillars)
        ↓
ui/layout/AppShell      (Sidebar + TopBar + FilterBar wrapper)
ui/feedback/            (Spinner, Skeleton, ErrorBoundary, DataBoundary)
```

No compute server. The browser downloads Parquet, loads it into DuckDB-Wasm, and queries it
locally. `make app-build` bundles everything; the output in `dist/` is a static site.

## Subtree map

| Directory | Role |
|---|---|
| `src/data/duckdb/` | DuckDB-Wasm client, status atom, Parquet registration, type definitions |
| `src/data/hooks/` | React Query hooks: `useQuery`, `useRaces`, `useDrivers`, `useDatabaseStatus` |
| `src/data/` (root) | `manifest.ts` (Parquet path resolver), `constants.ts` |
| `src/lib/` | Pure utilities: `format/` (time, number, name), `colors.ts`, `stats.ts`, `url.ts`, `csv.ts` |
| `src/nav/` | `pillars.ts` (9 pillar definitions), `routes.ts` (route registry with featureId links), `seo.ts` |
| `src/state/` | `FilterContext.tsx` (season/driver/race filter), `ThemeContext.tsx`, `preferences.ts` |
| `src/ui/layout/` | `AppShell`, `Sidebar`, `TopBar`, `FilterBar`, `EngineStatus` |
| `src/ui/feedback/` | `Spinner`, `Skeleton`, `ErrorBoundary`, `DataBoundary`, `EmptyState` |
| `src/routes/` | 40 page components see stub legend below |
| `design/` | Design mocks and race-page layout sketches |

## Root config files

| File | What it does |
|---|---|
| `vite.config.ts` | Vite bundler config: aliases, WASM MIME type, dev server |
| `vitest.config.ts` | Vitest test config: jsdom environment, setup file |
| `tailwind.config.ts` | Tailwind CSS config: content paths, theme tokens |
| `postcss.config.js` | PostCSS pipeline (Tailwind, Autoprefixer) |
| `eslint.config.js` | ESLint rules: React hooks, TypeScript |
| `tsconfig.json` | Root TypeScript project references |
| `tsconfig.app.json` | App source TS config (strict, bundler moduleResolution) |
| `tsconfig.node.json` | Node-side TS config (vite.config.ts, vitest.config.ts) |
| `index.html` | HTML entrypoint loads `src/main.tsx` via Vite |
| `package.json` | Dependencies and scripts |

## Content pillars

Route components are organised into 13 pillars. Some are fully implemented, others are placeholder stubs:

| Pillar | Path | Status |
|---|---|---|
| Races | `/races` | coming soon |
| Ghost Car | `/ghost-car` | coming soon |
| Lap Decomposition | `/lap-decomposition` | coming soon |
| Tyre Strategy | `/tyre-strategy` | coming soon |
| Aero & Conditions | `/aero` | coming soon |
| Race Craft | `/race-craft` | coming soon |
| Drivers | `/drivers` | live |
| Constructors | `/constructors` | coming soon |
| Energy & Telemetry | `/energy` | coming soon |
| The Machine | `/ml` | live |
| Query Lab | `/query` | live |
| Data Quality | `/data-quality` | coming soon |

## Status legend

| Status | Meaning |
|---|---|
| live | Fully implemented and available |
| coming soon | Route exists as a placeholder; implementation pending |

## Generated / gitignored

- `dist/` Vite build output; gitignored; regenerate with `make app-build`
- `node_modules/` npm deps; gitignored; restore with `pnpm install`

## Development

```bash
cd app
pnpm install         # restore deps
pnpm dev             # dev server at http://localhost:5174
pnpm build           # type-check + production build to dist/
pnpm test            # Vitest unit tests
pnpm lint            # ESLint
```

---

← Previous in tour: [ml/](../ml/README.md) · **Next in tour: [docs/](../docs/README.md) →**
