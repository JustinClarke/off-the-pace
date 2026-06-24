#!/usr/bin/env bash
#
# Promote the staging CDN revision to prod.
# Run this only AFTER scripts/smoke_cdn.sh --env staging passes, so a bad export can never
# reach prod un-smoked.
#
# Sequence (mirrors publish_cdn.sh's safety order):
#   1. Smoke staging (unless --skip-smoke) refuse to promote a broken staging revision.
#   2. Archive the current prod manifest → data/manifest-archive/ so rollback_cdn.sh can
#      restore the prior version pointer in one command.
#   3. Copy staging/data → data and staging/models → models (parquet/ONNX first).
#   4. Flip the prod manifest LAST (no-cache) the atomic cutover.
#
# Note on durable rollback: parquet objects are overwritten in place, so the manifest-archive
# restores the *pointer* but not prior parquet *bytes*. Enable GCS object versioning on the
# bucket (recommended; see .github/DEPLOYMENT.md → Rollback) for true content rollback.
#
# Usage:  scripts/promote_cdn.sh [--skip-smoke] [--dry-run]

set -euo pipefail

CDN_BUCKET="${CDN_BUCKET:-gs://off-the-pace-cdn}"
DATA_CACHE_CONTROL="${DATA_CACHE_CONTROL:-public, max-age=300}"
MANIFEST_CACHE_CONTROL="${MANIFEST_CACHE_CONTROL:-no-cache, max-age=0}"
CDN_BASE="${CDN_BASE:-https://storage.googleapis.com/off-the-pace-cdn}"

SKIP_SMOKE=""
DRY_RUN=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-smoke) SKIP_SMOKE=1; shift ;;
    --dry-run) DRY_RUN="--dry-run"; shift ;;
    *) echo "❌  unknown arg: $1" >&2; exit 2 ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGING_DATA="$CDN_BUCKET/staging/data"
STAGING_MODELS="$CDN_BUCKET/staging/models"
PROD_DATA="$CDN_BUCKET/data"
PROD_MODELS="$CDN_BUCKET/models"

command -v gcloud >/dev/null 2>&1 || { echo "❌  gcloud not found" >&2; exit 1; }
gcloud storage ls "$STAGING_DATA/_manifest.json" >/dev/null 2>&1 || {
  echo "❌  no staging manifest at $STAGING_DATA/_manifest.json publish staging first." >&2; exit 1; }

# 1. Smoke staging
if [[ -z "$SKIP_SMOKE" ]]; then
  echo "── smoke staging before promote ──"
  CDN_BASE="$CDN_BASE" "$ROOT/scripts/smoke_cdn.sh" --env staging
fi

STAGING_VERSION="$(gcloud storage cat "$STAGING_DATA/_manifest.json" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["version"])')"
echo "  promoting staging version: $STAGING_VERSION"

# 2. Archive the current prod manifest (if any)
if gcloud storage ls "$PROD_DATA/_manifest.json" >/dev/null 2>&1; then
  STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
  PREV_VERSION="$(gcloud storage cat "$PROD_DATA/_manifest.json" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["version"])' 2>/dev/null || echo unknown)"
  ARCHIVE="$PROD_DATA/manifest-archive/_manifest.${STAMP}.${PREV_VERSION}.json"
  echo "── archiving current prod manifest ($PREV_VERSION) → $ARCHIVE ──"
  [[ -z "$DRY_RUN" ]] && gcloud storage cp "$PROD_DATA/_manifest.json" "$ARCHIVE" --quiet \
    || echo "  (dry-run) would archive prod manifest"
fi

# 3. Copy staging data + models → prod (no delete; parquet/ONNX before the manifest flip)
for sub in dimensions facts intermediates marts; do
  if gcloud storage ls "$STAGING_DATA/$sub" >/dev/null 2>&1; then
    echo "── promote data/$sub ──"
    gcloud storage rsync -r $DRY_RUN "$STAGING_DATA/$sub" "$PROD_DATA/$sub"
  fi
done
if gcloud storage ls "$STAGING_MODELS" >/dev/null 2>&1; then
  echo "── promote models/ ──"
  gcloud storage rsync -r $DRY_RUN "$STAGING_MODELS" "$PROD_MODELS"
fi

if [[ -z "$DRY_RUN" ]]; then
  gcloud storage objects update \
    "$PROD_DATA/dimensions/**" "$PROD_DATA/facts/**" \
    "$PROD_DATA/intermediates/**" "$PROD_DATA/marts/**" \
    --cache-control="$DATA_CACHE_CONTROL" --quiet >/dev/null 2>&1 || true
fi

# 4. Flip the prod manifest LAST
echo "── flipping prod manifest → $STAGING_VERSION (last, no-cache) ──"
if [[ -z "$DRY_RUN" ]]; then
  gcloud storage cp "$STAGING_DATA/_manifest.json" "$PROD_DATA/_manifest.json" \
    --cache-control="$MANIFEST_CACHE_CONTROL" --quiet
  echo "  ✅  Promoted. Prod manifest version: $STAGING_VERSION"
else
  echo "  (dry-run) would flip prod manifest to $STAGING_VERSION"
fi
