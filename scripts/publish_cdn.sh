#!/usr/bin/env bash
#
# Publish the exported app data + model artefacts to the GCS CDN bucket that the
# live React app reads from (see app/src/data/manifest.ts → DATA_CDN_BASE).
#
# The app fetches EVERYTHING manifest, parquet, ONNX from this bucket, even
# in local dev. `make app-data` only writes to app/public/data/ on disk; nothing
# reaches the running app until those files are synced here.
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
#   scripts/publish_cdn.sh              # export must have run first (make app-data)
#   scripts/publish_cdn.sh --dry-run    # show what would change, upload nothing
#   CDN_BUCKET=gs://other-bucket scripts/publish_cdn.sh
#
# Requires: gcloud CLI authenticated with write access to the bucket.

set -euo pipefail

CDN_BUCKET="${CDN_BUCKET:-gs://off-the-pace-cdn}"
DATA_CACHE_CONTROL="${DATA_CACHE_CONTROL:-public, max-age=300}"
MANIFEST_CACHE_CONTROL="${MANIFEST_CACHE_CONTROL:-no-cache, max-age=0}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$ROOT/app/public/data"
MODELS_DIR="$ROOT/app/public/models"

DRY_RUN=""
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN="--dry-run"
  echo "── DRY RUN: no objects will be written ──"
fi

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
echo "  bucket:   $CDN_BUCKET"
echo "  account:  $ACCT"
echo "  source:   $DATA_DIR"
echo

# ── 1. Sync data subdirs (no delete; preserves bucket-only objects e.g. ml/) ────
# Manifest is uploaded separately, last, so exclude it from the dir sync.
for sub in dimensions facts intermediates; do
  if [[ -d "$DATA_DIR/$sub" ]]; then
    echo "── syncing data/$sub ──"
    gcloud storage rsync -r $DRY_RUN \
      "$DATA_DIR/$sub" "$CDN_BUCKET/data/$sub"
  fi
done

# ── 2. Sync ONNX model artefacts if present ─────────────────────────────────────
# The app loads models from ${DATA_CDN_BASE}/models (see app/src/ml/manifest.ts →
# MODELS_BASE), i.e. the bucket-root models/ prefix, NOT under data/.
if [[ -d "$MODELS_DIR" ]]; then
  echo "── syncing models/ ──"
  gcloud storage rsync -r $DRY_RUN \
    "$MODELS_DIR" "$CDN_BUCKET/models"
fi

# ── 3. Apply cache-control to data parquet (short max-age, no hour-long staleness)
if [[ -z "$DRY_RUN" ]]; then
  echo "── setting cache-control on data parquet → '$DATA_CACHE_CONTROL' ──"
  gcloud storage objects update \
    "$CDN_BUCKET/data/dimensions/**" \
    "$CDN_BUCKET/data/facts/**" \
    "$CDN_BUCKET/data/intermediates/**" \
    --cache-control="$DATA_CACHE_CONTROL" --quiet >/dev/null
fi

# ── 4. Upload manifest LAST, no-cache (version pointer must never be stale) ──────
echo "── uploading _manifest.json (last, no-cache) ──"
if [[ -z "$DRY_RUN" ]]; then
  gcloud storage cp \
    "$DATA_DIR/_manifest.json" "$CDN_BUCKET/data/_manifest.json" \
    --cache-control="$MANIFEST_CACHE_CONTROL" --quiet
  VERSION="$(gcloud storage cat "$CDN_BUCKET/data/_manifest.json" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["version"])')"
  echo
  echo "  ✅  Published. Live manifest version: $VERSION"
  echo "      Hard-refresh the app (Cmd+Shift+R) to bypass any cached copy."
else
  echo "  (dry-run) would upload $DATA_DIR/_manifest.json"
fi
