#!/usr/bin/env bash
#
# One-command prod rollback: re-publish a prior
# manifest as the live version pointer. promote_cdn.sh archives every superseded prod
# manifest to data/manifest-archive/, so rolling back is restoring one of those.
#
#   scripts/rollback_cdn.sh --list            # show archived prod manifests, newest first
#   scripts/rollback_cdn.sh --to <archive>    # restore that archived manifest as live
#   scripts/rollback_cdn.sh --previous        # restore the most recent archive (one-step undo)
#
# IMPORTANT what this does and does not restore:
#   • Restores the version POINTER (which tables + which ?v= cache-bust keys the app loads).
#   • Does NOT restore parquet BYTES: publish overwrites objects in place. For true content
#     rollback the bucket must have OBJECT VERSIONING enabled, then restore the prior object
#     generations (see .github/DEPLOYMENT.md → Rollback). With versioning off, a pointer
#     rollback is only correct if the prior parquet was never overwritten since.

set -euo pipefail

CDN_BUCKET="${CDN_BUCKET:-gs://off-the-pace-cdn}"
MANIFEST_CACHE_CONTROL="${MANIFEST_CACHE_CONTROL:-no-cache, max-age=0}"
PROD_DATA="$CDN_BUCKET/data"
ARCHIVE_DIR="$PROD_DATA/manifest-archive"

command -v gcloud >/dev/null 2>&1 || { echo "❌  gcloud not found" >&2; exit 1; }

list_archives() {
  gcloud storage ls "$ARCHIVE_DIR/" 2>/dev/null | grep '_manifest\..*\.json$' | sort -r
}

ACTION=""
TARGET=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --list) ACTION="list"; shift ;;
    --previous) ACTION="previous"; shift ;;
    --to) ACTION="to"; TARGET="${2:?--to needs an archive path or name}"; shift 2 ;;
    *) echo "❌  unknown arg: $1" >&2; exit 2 ;;
  esac
done

[[ -n "$ACTION" ]] || { echo "Usage: rollback_cdn.sh --list | --previous | --to <archive>"; exit 2; }

if [[ "$ACTION" == "list" ]]; then
  echo "Archived prod manifests (newest first):"
  list_archives | sed 's/^/  /' || echo "  (none)"
  exit 0
fi

if [[ "$ACTION" == "previous" ]]; then
  TARGET="$(list_archives | head -1)"
  [[ -n "$TARGET" ]] || { echo "❌  no archived manifests to roll back to." >&2; exit 1; }
fi

# Allow passing just the basename; resolve to the full archive path.
if [[ "$TARGET" != gs://* ]]; then
  TARGET="$ARCHIVE_DIR/$TARGET"
fi
gcloud storage ls "$TARGET" >/dev/null 2>&1 || { echo "❌  archive not found: $TARGET" >&2; exit 1; }

VERSION="$(gcloud storage cat "$TARGET" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["version"])' 2>/dev/null || echo unknown)"
echo "── rolling back prod manifest → $TARGET (version $VERSION) ──"
echo "    (pointer only confirm object versioning if parquet bytes changed since)"
gcloud storage cp "$TARGET" "$PROD_DATA/_manifest.json" \
  --cache-control="$MANIFEST_CACHE_CONTROL" --quiet
echo "  ✅  Rolled back. Live prod manifest version: $VERSION"
