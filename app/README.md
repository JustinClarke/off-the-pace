# app/ React + DuckDB-Wasm Frontend

**Complete and deployed.** The browser-side analytics app that surfaces F1 race data with zero compute server. DuckDB-Wasm runs SQL in WebAssembly; queries against the gold Parquet files complete in sub-10ms. Deployed to Firebase Hosting with 309 tests passing across 35 test files.

## Architecture

```
GCS CDN (gs://off-the-pace-cdn) → data/*.parquet + models/*.onnx
        ↓
data/duckdb/client.ts   (DuckDB-Wasm singleton; query() runs SQL in-browser)
data/manifest.ts        (resolves Parquet paths via DATA_CDN_BASE)
data/hooks/             (useQuery, useRaces, useDrivers, useDatabaseStatus)
        ↓
features/<dir>/         (one analytical feature each, rendered via FeaturePage)
App.tsx                 (hand-maintained path → import() router)
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
| `src/features/` | One directory per analytical feature; each renders through the shared `FeaturePage` template (see **Feature anatomy** below) |
| `src/lib/` | Pure utilities: `format/` (time, number, name), `colors.ts`, `stats.ts`, `url.ts`, `csv.ts` |
| `src/ml/` | ONNX runtime layer: model session queue, feature-vector builders, parity verification |
| `src/nav/` | `pillars.ts` (11 pillar definitions), `routes.ts` (route registry with `featureId` + `shipped` flags), `seo.ts` |
| `src/state/` | `FilterContext.tsx` (season/driver/race filter), `ThemeContext.tsx`, `preferences.ts` |
| `src/ui/layout/` | `AppShell`, `Sidebar`, `TopBar`, `FilterBar`, `EngineStatus`, `FeaturePage` |
| `src/ui/feedback/` | `Spinner`, `Skeleton`, `ErrorBoundary`, `DataBoundary`, `EmptyState` |
| `src/routes/` | Bespoke page components (home, query lab) that don't follow the FeaturePage pattern |
| `src/config.ts` | Site metadata, feature flags, and `CANONICAL_DOCS_BASE` (the docs host every `methodologyHref` is built from) |

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

## Routing: two registries, one router

There are **two** route lists, and they serve different jobs don't confuse them:

- **`src/App.tsx` is the actual router** a hand-maintained `path → import()` map. This is what
  React Router renders. It also carries a few legacy alias paths (`/aerodynamics/*`,
  `/deep-dives/*`) that exist only here.
- **`src/nav/routes.ts` is the navigation/feature registry** it records `pillar`, `featureId`,
  `label`, and `shipped` for each route, and drives the sidebar and `/roadmap`. It is **not** the
  router, and it has drifted from `App.tsx` before (the alias paths above). When you add a feature,
  update both.

`routes.ts` holds **59 route entries** across **11 pillars** (`pillars.ts`). **46** carry a
`featureId`; of those, **30 are shipped** and 16 are `shipped: false` (roadmap stubs surfaced on
`/roadmap`). The 30 shipped `featureId` routes each map 1:1 to a `src/features/<dir>/` module.

## Content pillars

`pillars.ts` defines **11** pillars. Live pillars render shipped features; the three "coming soon"
pillars are nav landing pages whose features are all `shipped: false`.

| Pillar | Path | Status |
|---|---|---|
| Home | `/` | live |
| Ghost Car | `/ghost-car` | live |
| Lap Decomposition | `/lap-decomposition` | live |
| Tyre & Strategy | `/tyre-strategy` | live |
| Aero & Conditions | `/aero` | live |
| Drivers | `/drivers` | live |
| Constructors | `/constructors` | live |
| The Machine (ML) | `/ml` | live |
| Query Lab | `/query` | live |
| Data Quality | `/data-quality` | live |
| Roadmap | `/roadmap` | live |

Three further pillars **Races** (`/races`), **Race Craft** (`/race-craft`), and **Energy &
Telemetry** (`/energy`) exist in `routes.ts` as `shipped: false` landing pages and are surfaced
only on `/roadmap`, not in the sidebar.

| Status | Meaning |
|---|---|
| live | Fully implemented and available |
| coming soon | `shipped: false`; surfaced on `/roadmap` only |

## Feature anatomy

Every analytical feature is a directory under `src/features/<dir>/` with a fixed layout. The
`<dir>` name is the feature's canonical **slug** it is reused verbatim as the docs page filename
(`docs/app/<dir>.mdx`) and inside the feature's `methodologyHref`.

| File | Role |
|---|---|
| `index.ts` | Re-exports the page: `export { default } from './page'` |
| `page.tsx` | The route component; wires data into `<FeaturePage>` and renders the chart |
| `queries.ts` | The DuckDB-Wasm SQL the feature runs |
| `transform.ts` | Pure shaping of query rows into chart/series data |
| `transform.test.ts` | Vitest unit tests for the transform |
| `methodology.tsx` | Exports `methodologyContent` (drawer JSX) **and** `methodologyHref` (docs deep-link) |

`page.tsx` renders the shared **`FeaturePage`** template (`src/ui/layout/FeaturePage.tsx`), whose
prop contract is:

| Prop | Purpose |
|---|---|
| `title` | Feature heading |
| `hook` | One-sentence framing of the question the feature answers |
| `badges` | Audience tabs (`What It Means` / `Why It Matters` / `How It's Calculated`) |
| `methodology` | The drawer body pass `methodologyContent` from `methodology.tsx` |
| `methodologyHref` | Deep-link to the docs page pass `methodologyHref` from `methodology.tsx` |
| `provenance` | Footer metadata (data window, fit date, n, model version, fingerprint) |
| `csvRows` | Rows emitted by the "Export CSV" button |
| `isLoading` / `error` / `isEmpty` | Query state forwarded from the feature's `useQuery` |

**`methodologyHref` is built as `` `${CANONICAL_DOCS_BASE}/app/<dir>` `` and nothing else.** It must
point at the feature's own `/app/<slug>` page (not a raw `/reference/**` model page); the page in
turn names and links the underlying dbt model in its **Data source** section.

**Query Lab (`/query`) is the one bespoke shipped feature** it is a `src/routes/` page, not a
FeaturePage module, and carries no `featureId`. It is documented by a hand-written
`docs/app/query-lab.mdx` and is an explicit exception in the docs gate.

## Documentation

Every shipped feature ships a public docs page alongside its code. The contract is enforced by a
CI gate see [.github/CONTRIBUTING.md](../.github/CONTRIBUTING.md) ("Documenting a new app
feature") and run `make docs-app-audit` to check coverage. In short, when you add or change a
feature, in the same PR:

1. write/update `docs/app/<dir>.mdx` from `docs/snippets/app-page-template.mdx`,
2. add the slug to the `docs.json` "App & Visualizations" group,
3. set `methodologyHref` to `` `${CANONICAL_DOCS_BASE}/app/<dir>` ``,
4. run `make docs-app-audit` and `make docs-facts` green.

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
