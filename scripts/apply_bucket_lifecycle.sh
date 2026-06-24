#!/usr/bin/env bash
#
# Apply the GCS lifecycle policy + ensure object versioning. The "no-delete" publish
# leaks superseded objects indefinitely; this bounds storage while preserving recent
# generations for rollback.
#
# Versioning is enabled here too because the noncurrent-version lifecycle rule (and durable
# data rollback) are no-ops without it.
#
# Usage:  scripts/apply_bucket_lifecycle.sh [--dry-run]
# Requires: gcloud authenticated with admin on the bucket.

set -euo pipefail

CDN_BUCKET="${CDN_BUCKET:-gs://off-the-pace-cdn}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
POLICY="$ROOT/infra/gcs_lifecycle.json"

command -v gcloud >/dev/null 2>&1 || { echo "❌  gcloud not found" >&2; exit 1; }
[[ -f "$POLICY" ]] || { echo "❌  policy not found: $POLICY" >&2; exit 1; }

if [[ "${1:-}" == "--dry-run" ]]; then
  echo "── DRY RUN ──"
  echo "would: gcloud storage buckets update $CDN_BUCKET --versioning"
  echo "would: gcloud storage buckets update $CDN_BUCKET --lifecycle-file=$POLICY"
  echo ""
  echo "policy:"; cat "$POLICY"
  exit 0
fi

echo "── enabling object versioning on $CDN_BUCKET ──"
gcloud storage buckets update "$CDN_BUCKET" --versioning

echo "── applying lifecycle policy ──"
gcloud storage buckets update "$CDN_BUCKET" --lifecycle-file="$POLICY"

echo "  ✅  Lifecycle applied. Current config:"
gcloud storage buckets describe "$CDN_BUCKET" --format='value(lifecycle_config)' 2>/dev/null || true
