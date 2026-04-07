# Deployment & Release Runbook

How _Off The Pace_ ships. Implements Phase 2 (Release engineering & CD) of
`SYSTEM_DESIGN_AUDIT.md`: turn the laptop `make app-deploy` into a keyless, staged,
rollback-able pipeline.

## Architecture in one paragraph

The app bundle (`app/dist`) is **pure code** it reads all data/models from the GCS CDN
(`gs://off-the-pace-cdn`) at runtime, keyed by a build-time `VITE_DATA_BASE`. So a **code
deploy runs entirely in CI**. The **data export needs the 6 GB warehouse**, which is not in
CI, so producing + publishing data is an operator/orchestration step (Phase 4) that runs
*before* a release. CI then validates that data in **staging**, promotes it to **prod**, and
deploys the code.

```
 operator / Phase-4 pipeline                 CI (deploy.yml, on release)
 ───────────────────────────                 ───────────────────────────
 make app-data app-models                    smoke staging  ─┐
 make app-publish-staging   ──► gs://…/staging/data           ├─ promote staging→prod (atomic manifest flip)
                                                              ├─ firebase deploy (code)
                                              ◄── prod ───────┘  smoke prod
```

## One-time setup (cloud an admin does this once)

CI authenticates to GCP with **Workload Identity Federation** no long-lived JSON key.

1. **Provision WIF** (creates the pool/provider locked to this repo, a least-privilege deploy
   service account, and the impersonation binding):
   ```bash
   bash scripts/setup_wif.sh
   ```
   It prints two values. Store them as **repository Actions _variables_** (Settings → Secrets
   and variables → Actions → **Variables**, not Secrets they are not sensitive):

   | Variable | Value |
   |---|---|
   | `GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/<num>/locations/global/workloadIdentityPools/github-pool/providers/github-provider` |
   | `GCP_DEPLOY_SERVICE_ACCOUNT` | `gh-deploy@off-the-pace.iam.gserviceaccount.com` |
   | `FIREBASE_PROJECT` | `off-the-pace` (optional; defaults to this) |
   | `PROD_SITE_URL` | e.g. `https://off-the-pace.web.app` (optional; enables the prod site smoke) |

   Until `GCP_WORKLOAD_IDENTITY_PROVIDER` is set, `deploy.yml` and `preview.yml` **skip**
   (their job `if:` guards on it), so releases won't show a red deploy before setup.

2. **Enable GCS object versioning** on the bucket (makes data rollback restore real bytes,
   not just the pointer see Rollback):
   ```bash
   gcloud storage buckets update gs://off-the-pace-cdn --versioning
   ```
   This is codified in Phase 6 (Terraform); the command above is the interim.

## Cutting a release

Versioning is automated by **release-please** (`release-please.yml`), driven by
[Conventional Commits](https://www.conventionalcommits.org/) on `main`.

1. Land work on `main` with conventional commit subjects (`feat:`, `fix:`, `perf:`, …).
2. release-please keeps an open **"chore: release X.Y.Z"** PR with the computed version and a
   generated `CHANGELOG.md`. Review it.
3. **Publish the data first** (operator, from a machine with the warehouse):
   ```bash
   make app-data app-models      # export warehouse → app/public/data, copy ONNX
   make app-publish-staging      # → gs://…/staging/data
   make app-smoke ENV=staging    # sanity-check staging
   ```
4. **Merge the release PR.** That tags the release and publishes a GitHub Release, which
   triggers `deploy.yml`: it smokes staging → builds the app → **promotes staging→prod** →
   `firebase deploy` → smokes prod.

`make app-deploy` (the old all-in-one laptop path) still works for emergencies but bypasses
staging/smoke prefer the pipeline.

## Preview deploys

Every app PR (`preview.yml`) builds against the **staging** data prefix and deploys to a
Firebase preview channel `pr-<n>`, posting the shareable URL as a PR comment (expires 7 days).
Fork PRs are skipped (no WIF access).

## Rollback

Prod's data version pointer is the `version` field in `_manifest.json`. Every promotion
archives the superseded prod manifest to `gs://…/data/manifest-archive/`.

```bash
make app-rollback                       # restore the immediately previous manifest
make app-rollback TO=_manifest.<stamp>.<ver>.json   # restore a specific archived manifest
scripts/rollback_cdn.sh --list          # list archived manifests
```

**What rollback restores:** the version pointer (which tables + which `?v=` cache-bust keys
the app loads). Because publish overwrites parquet objects **in place**, the parquet *bytes*
are only truly recoverable if **object versioning is on** (step 2 above) then restore the
prior generations:
```bash
# inspect generations, then restore the pre-incident one:
gcloud storage ls --all-versions gs://off-the-pace-cdn/data/marts/<table>.parquet
gcloud storage cp gs://…/<table>.parquet#<generation> gs://…/<table>.parquet
```
A **code** rollback is `firebase hosting:rollback` (Firebase keeps prior releases) or
re-deploying a prior tag.

## Workflows at a glance

| Workflow | Trigger | Does |
|---|---|---|
| `release-please.yml` | push to `main` | Maintain release PR + CHANGELOG; tag on merge |
| `deploy.yml` | release published / manual | Smoke staging → promote → firebase deploy → smoke prod |
| `preview.yml` | app PR | Build vs staging data → preview channel + PR comment |

## Local equivalents

```bash
make app-publish-staging   # publish_cdn.sh --env staging
make app-smoke ENV=staging # smoke_cdn.sh --env staging
make app-promote           # promote_cdn.sh  (staging → prod, atomic)
make app-rollback          # rollback_cdn.sh --previous
```
