#!/usr/bin/env bash
#
# Publish the exported app data + model artefacts to the GCS CDN bucket that the
# live React app reads from (see app/src/data/manifest.ts → DATA_CDN_BASE).
#
# The app fetches EVERYTHING manifest, parquet, ONNX from this bucket, even
# in local dev. `make app-data` only writes to app/public/data/ on disk; nothing
# reaches the running app until those files are synced here.
#
# Staging vs prod:
#   --env prod     (default) publishes to the bucket root: <bucket>/data, <bucket>/models
#   --env staging            publishes under a staging/ prefix: <bucket>/staging/data, …
# Preview builds point VITE_DATA_BASE at the staging prefix, so a bad export can be smoke-
# tested in staging and never reaches prod until promote_cdn.sh copies it across.
#
# Safety properties:
#   • No deletes. We sync without --delete-unmatched-destination-objects so the
#     bucket's data/ml/ (degradation predictions) and any other objects we don't
#     export locally are preserved.
#   • Manifest goes last, with no-cache, so the version pointer never references
#     parquet that hasn't finished uploading.
#   • Data parquet gets a short max-age (default 300s) so a schema change can't
#     be masked by hour-long edge caching (the failure mode we hit on 2026-06-11).
#
# Usage:
#   scripts/publish_cdn.sh                       # prod; export must have run (make app-data)
#   scripts/publish_cdn.sh --env staging         # publish to the staging prefix
#   scripts/publish_cdn.sh --dry-run             # show what would change, upload nothing
#   CDN_BUCKET=gs://other-bucket scripts/publish_cdn.sh
#
# Requires: gcloud CLI authenticated with write access to the bucket.

set -euo pipefail

CDN_BUCKET="${CDN_BUCKET:-gs://off-the-pace-cdn}"
DATA_CACHE_CONTROL="${DATA_CACHE_CONTROL:-public, max-age=300}"
MANIFEST_CACHE_CONTROL="${MANIFEST_CACHE_CONTROL:-no-cache, max-age=0}"

# ── Args ─────────────────────────────────────────────────────────────────────────
ENV="prod"
DRY_RUN=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env) ENV="${2:?--env needs prod|staging}"; shift 2 ;;
    --dry-run) DRY_RUN="--dry-run"; shift ;;
    *) echo "❌  unknown arg: $1" >&2; exit 2 ;;
  esac
done

case "$ENV" in
  prod)    PREFIX="" ;;
  staging) PREFIX="staging/" ;;
  *) echo "❌  --env must be prod or staging (got '$ENV')" >&2; exit 2 ;;
esac

[[ -n "$DRY_RUN" ]] && echo "── DRY RUN: no objects will be written ──"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$ROOT/app/public/data"
MODELS_DIR="$ROOT/app/public/models"
DATA_DEST="$CDN_BUCKET/${PREFIX}data"
MODELS_DEST="$CDN_BUCKET/${PREFIX}models"

# ── Preflight ──────────────────────────────────────────────────────────────────
if ! command -v gcloud >/dev/null 2>&1; then
  echo "❌  gcloud CLI not found. Install: https://cloud.google.com/sdk/docs/install" >&2
  exit 1
fi

if [[ ! -f "$DATA_DIR/_manifest.json" ]]; then
  echo "❌  $DATA_DIR/_manifest.json not found. Run 'make app-data' first." >&2
  exit 1
fi

if ! gcloud storage ls "$CDN_BUCKET" >/dev/null 2>&1; then
  echo "❌  Cannot access $CDN_BUCKET. Check 'gcloud auth login' and bucket permissions." >&2
  exit 1
fi

ACCT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null || echo '?')"
echo "  env:      $ENV"
echo "  bucket:   $CDN_BUCKET"
echo "  dest:     $DATA_DEST"
echo "  account:  $ACCT"
echo "  source:   $DATA_DIR"
echo

# ── 1. Sync data subdirs (no delete; preserves dest-only objects e.g. ml/) ──────
# Manifest is uploaded separately, last, so exclude it from the dir sync.
for sub in dimensions facts intermediates marts; do
  if [[ -d "$DATA_DIR/$sub" ]]; then
    echo "── syncing data/$sub ──"
    gcloud storage rsync -r $DRY_RUN \
      "$DATA_DIR/$sub" "$DATA_DEST/$sub"
  fi
done

# ── 2. Sync ONNX model artefacts if present ─────────────────────────────────────
# The app loads models from ${DATA_CDN_BASE}/models (see app/src/ml/manifest.ts →
# MODELS_BASE), i.e. the <env> models/ prefix, NOT under data/.
if [[ -d "$MODELS_DIR" ]]; then
  echo "── syncing models/ ──"
  gcloud storage rsync -r $DRY_RUN \
    "$MODELS_DIR" "$MODELS_DEST"
fi

# ── 3. Apply cache-control to data parquet (short max-age, no hour-long staleness)
if [[ -z "$DRY_RUN" ]]; then
  echo "── setting cache-control on data parquet → '$DATA_CACHE_CONTROL' ──"
  gcloud storage objects update \
    "$DATA_DEST/dimensions/**" \
    "$DATA_DEST/facts/**" \
    "$DATA_DEST/intermediates/**" \
    "$DATA_DEST/marts/**" \
    --cache-control="$DATA_CACHE_CONTROL" --quiet >/dev/null
fi

# ── 4. Upload manifest LAST, no-cache (version pointer must never be stale) ──────
echo "── uploading _manifest.json (last, no-cache) ──"
if [[ -z "$DRY_RUN" ]]; then
  gcloud storage cp \
    "$DATA_DIR/_manifest.json" "$DATA_DEST/_manifest.json" \
    --cache-control="$MANIFEST_CACHE_CONTROL" --quiet
  VERSION="$(gcloud storage cat "$DATA_DEST/_manifest.json" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["version"])')"
  echo
  echo "  ✅  Published to $ENV. Live manifest version: $VERSION"
  if [[ "$ENV" == "staging" ]]; then
    echo "      Smoke it:  scripts/smoke_cdn.sh --env staging"
    echo "      Promote:   scripts/promote_cdn.sh"
  else
    echo "      Hard-refresh the app (Cmd+Shift+R) to bypass any cached copy."
  fi
else
  echo "  (dry-run) would upload $DATA_DIR/_manifest.json → $DATA_DEST/_manifest.json"
fi
