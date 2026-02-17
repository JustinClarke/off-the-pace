# App Deployment & Data CDN

## Overview

```
https://off-the-pace.web.app              ← Firebase Hosting (app)
https://storage.googleapis.com/off-the-pace-cdn/  ← Firebase Storage (data CDN)
```

The Vite app is deployed to Firebase Hosting. Parquet marts and ONNX model artefacts
are served from a public Firebase Storage bucket so the hosting deployment stays lean.

**Firebase project:** `off-the-pace`
**Storage bucket:** `off-the-pace-cdn`

---

## Why Firebase Storage for data?

- Full CORS control via `gsutil cors set` — sets `Access-Control-Allow-Origin: *` on
  all objects, which GitHub Pages cannot do
- `Cross-Origin-Resource-Policy` is not required on Storage responses because COEP
  `require-corp` only blocks responses that lack CORP when fetched as "no-cors" mode;
  DuckDB-Wasm fetches parquet via `fetch()` in CORS mode (explicit cross-origin), so
  the `Access-Control-Allow-Origin: *` header is sufficient
- Google CDN backed, globally fast

---

## What stays same-origin (Firebase Hosting)

`Cross-Origin-Embedder-Policy: require-corp` is set on all app responses. Any asset
loaded without CORS headers is blocked. The following binaries must therefore be
self-hosted and are copied at build time by `scripts/copy-runtime-assets.mjs`:

| Directory | Contents |
|---|---|
| `public/duckdb/` | `duckdb-eh.wasm` + `duckdb-browser-eh.worker.js` |
| `public/ort/` | ONNX Runtime Web WASM + MJS files |

**DuckDB EH bundle only** — MVP and COI are excluded. COI uses shared memory which
causes the Parquet extension to fail with "mismatch in shared state of memory". MVP is
unused. Do not add them back without re-testing Parquet reads end-to-end.

---

## CDN base URL

Defined once in [`src/data/manifest.ts`](../src/data/manifest.ts):

```ts
export const DATA_CDN_BASE = 'https://storage.googleapis.com/off-the-pace-cdn'
```

All data and model paths flow through this constant:

| Consumer | Resolves to |
|---|---|
| `loadManifest()` | `DATA_CDN_BASE/data/_manifest.json` |
| `getTablePath()` / `getRaceFilePath()` | Full Storage URL to Parquet files |
| `MODELS_BASE` (`src/ml/manifest.ts`) | `DATA_CDN_BASE/models` |
| `MODEL_CARD_URL` (model-metrics) | `MODELS_BASE/model_card.json` |

---

## Deploy protocol

### Rules

- **Run local CI before every commit** — all three checks must pass before pushing to GitHub.
- **Deploy to Firebase manually after pushing** — no automated CI deploy; you control when it goes live.
- **Data/model uploads to Storage are independent** — they are build artefacts, not source code. Upload any time with `gsutil`, no commit needed.
- **Always build before deploying** — Firebase serves whatever is in `app/dist/`, it does not trigger a build.

### Local CI (run before every commit)

```bash
cd app && pnpm install --frozen-lockfile && pnpm run build && pnpm test
```

All three must pass. If any fail, fix before committing.

### Deploy to Firebase (after pushing to GitHub)

```bash
cd app && pnpm run build && cd ..
firebase deploy --only hosting --project off-the-pace
```

### Update data/models in Storage

After regenerating data or retraining models — no commit required:

```bash
# Parquet marts
gsutil -m cp -r app/dist/data gs://off-the-pace-cdn/

# ONNX models + manifests
gsutil -m cp -r app/dist/models gs://off-the-pace-cdn/
```

Uploads are live immediately — Storage has no staging/release concept.

### Rollback the app

```bash
firebase hosting:releases:rollback --project off-the-pace
```

Instantly re-activates the previous Hosting release with no rebuild needed.

---

## firebase.json

COEP/COOP headers on all routes, immutable cache on `duckdb/` and `ort/`, SPA rewrite
catches everything else. No `/data` or `/models` rules needed (they live in Storage).
