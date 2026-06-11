#!/usr/bin/env bash
#
# Post-publish / post-deploy smoke of the CDN data plane. Pure HTTP against the public
# bucket needs no gcloud, so it runs anywhere,
# including inside deploy.yml between the staging publish and the prod promotion.
#
# Checks:
#   1. <base>/data/_manifest.json  → 200, parses, has a version + ≥1 table.
#   2. a sample parquet referenced by the manifest → 200 (catches the 2026-06-11 class:
#      manifest points at parquet that 404s).
#   3. (optional) the live site root → 200, when --site is given.
#
# Usage:
#   scripts/smoke_cdn.sh                         # prod CDN
#   scripts/smoke_cdn.sh --env staging           # staging prefix
#   scripts/smoke_cdn.sh --site https://off-the-pace.web.app
#   scripts/smoke_cdn.sh --expect-version <hash> # also assert the live version matches

set -euo pipefail

CDN_BASE="${CDN_BASE:-https://storage.googleapis.com/off-the-pace-cdn}"
ENV="prod"
SITE=""
EXPECT_VERSION=""
MAX_AGE_HOURS=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env) ENV="${2:?}"; shift 2 ;;
    --site) SITE="${2:?}"; shift 2 ;;
    --expect-version) EXPECT_VERSION="${2:?}"; shift 2 ;;
    --max-age-hours) MAX_AGE_HOURS="${2:?}"; shift 2 ;;
    --base) CDN_BASE="${2:?}"; shift 2 ;;
    *) echo "❌  unknown arg: $1" >&2; exit 2 ;;
  esac
done

case "$ENV" in
  prod)    BASE="$CDN_BASE" ;;
  staging) BASE="$CDN_BASE/staging" ;;
  *) echo "❌  --env must be prod or staging" >&2; exit 2 ;;
esac

MANIFEST_URL="$BASE/data/_manifest.json"
echo "── smoke: $ENV ── $MANIFEST_URL"

# 1. manifest
HTTP="$(curl -fsS -o /tmp/_smoke_manifest.json -w '%{http_code}' "$MANIFEST_URL")" || {
  echo "❌  manifest fetch failed (HTTP ${HTTP:-000})"; exit 1; }
echo "  ✓ manifest 200"

read -r VERSION NTABLES SAMPLE < <(python3 - "$BASE" <<'PY'
import json, sys
base = sys.argv[1]
m = json.load(open("/tmp/_smoke_manifest.json"))
tables = m.get("tables", [])
sample = ""
for t in tables:
    p = t.get("path", "")
    if not t.get("partitioned") and p.endswith(".parquet"):
        sample = p; break
    if t.get("partitioned") and t.get("partitions"):
        sample = t["partitions"][0].get("path", ""); break
print(m.get("version", ""), len(tables), sample)
PY
)
[[ -n "$VERSION" ]] || { echo "❌  manifest has no version"; exit 1; }
[[ "$NTABLES" -gt 0 ]] || { echo "❌  manifest lists 0 tables"; exit 1; }
echo "  ✓ version=$VERSION  tables=$NTABLES"

# Data-freshness SLO signal (non-fatal): warn if the manifest is older than the threshold.
# Seasonal data legitimately ages, so this never fails the check it surfaces a breach to
# review rather than paging. The age is always printed when a threshold is given.
if [[ -n "$MAX_AGE_HOURS" ]]; then
  AGE_H="$(python3 -c '
import json, sys
from datetime import datetime, timezone
m = json.load(open("/tmp/_smoke_manifest.json"))
g = m.get("generatedAt")
if not g:
    print("nan"); sys.exit()
dt = datetime.fromisoformat(g.replace("Z", "+00:00"))
print(f"{(datetime.now(timezone.utc) - dt).total_seconds() / 3600:.1f}")
')"
  if [[ "$AGE_H" != "nan" ]] && awk "BEGIN{exit !($AGE_H > $MAX_AGE_HOURS)}"; then
    echo "  ⚠ data freshness: ${AGE_H}h old > ${MAX_AGE_HOURS}h SLO (review; not failing)"
  else
    echo "  ✓ data freshness: ${AGE_H}h old (≤ ${MAX_AGE_HOURS}h)"
  fi
fi

if [[ -n "$EXPECT_VERSION" && "$VERSION" != "$EXPECT_VERSION" ]]; then
  echo "❌  live version $VERSION != expected $EXPECT_VERSION"; exit 1
fi

# 2. sample parquet manifest paths are absolute from the CDN base (e.g. /data/…/x.parquet),
#    exactly as the app builds them (`${DATA_CDN_BASE}${table.path}`), so do NOT re-add /data.
if [[ -n "$SAMPLE" ]]; then
  PARQUET_URL="$BASE$SAMPLE"
  PHTTP="$(curl -fsS -I -o /dev/null -w '%{http_code}' "$PARQUET_URL")" || {
    echo "❌  sample parquet $PARQUET_URL → HTTP ${PHTTP:-000}"; exit 1; }
  echo "  ✓ sample parquet 200 ($SAMPLE)"
else
  echo "  ⚠ no parquet table found in manifest to sample"
fi

# 3. optional live site
if [[ -n "$SITE" ]]; then
  SHTTP="$(curl -fsS -o /dev/null -w '%{http_code}' "$SITE")" || {
    echo "❌  site $SITE → HTTP ${SHTTP:-000}"; exit 1; }
  echo "  ✓ site 200 ($SITE)"
fi

echo "  ✅  smoke passed ($ENV)"
