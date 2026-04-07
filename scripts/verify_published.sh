#!/usr/bin/env bash
#
# Post-publish verification gate. Run right after a
# publish to assert the CDN actually serves what was just built and AUTO-ROLLBACK the manifest
# pointer if not. This folds the manual 2026-06-11 debugging (stale bundle / manifest pointing at
# parquet that 404s) into one automated guard.
#
# Checks, in order:
#   1. HTTP smoke (scripts/smoke_cdn.sh): manifest 200, sample parquet 200, optional live site 200,
#      and when a local export is present the live version equals the local one.
#   2. Stats parity: published manifest stats (total_laps/drivers/events) match the local export's.
#   3. Model plane: models/manifest.json has a model_version and every referenced .onnx is 200.
#   4. ONNX serving: app/scripts/synthetic_check.mjs runs a real inference (finite output).
#
# On any failure with --rollback-on-fail, restores the previous manifest via rollback_cdn.sh.
#
# Usage:
#   scripts/verify_published.sh                       # verify prod against the local export
#   scripts/verify_published.sh --env staging
#   scripts/verify_published.sh --site https://off-the-pace.web.app --rollback-on-fail
#   scripts/verify_published.sh --skip-onnx           # HTTP + stats only (no node)

set -euo pipefail

CDN_BASE="${CDN_BASE:-https://storage.googleapis.com/off-the-pace-cdn}"
ENV="prod"
SITE=""
ROLLBACK=""
SKIP_ONNX=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env) ENV="${2:?}"; shift 2 ;;
    --site) SITE="${2:?}"; shift 2 ;;
    --rollback-on-fail) ROLLBACK=1; shift ;;
    --skip-onnx) SKIP_ONNX=1; shift ;;
    *) echo "❌  unknown arg: $1" >&2; exit 2 ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="$CDN_BASE"; [[ "$ENV" == "staging" ]] && BASE="$CDN_BASE/staging"
LOCAL_MANIFEST="$ROOT/app/public/data/_manifest.json"

fail() {
  echo "❌  verification FAILED: $1" >&2
  if [[ -n "$ROLLBACK" ]]; then
    echo "── auto-rollback (--rollback-on-fail) ──" >&2
    "$ROOT/scripts/rollback_cdn.sh" --previous || echo "⚠  rollback itself failed investigate manually" >&2
  fi
  exit 1
}

# Local version to assert the publish landed exactly what we built.
LOCAL_VERSION=""
if [[ -f "$LOCAL_MANIFEST" ]]; then
  LOCAL_VERSION="$(python3 -c 'import json;print(json.load(open("'"$LOCAL_MANIFEST"'"))["version"])' 2>/dev/null || echo "")"
fi

# ── 1. HTTP smoke (+ version match when we know the local version) ───────────────
echo "── 1/4  HTTP smoke ──"
SMOKE_ARGS=(--env "$ENV")
[[ -n "$SITE" ]] && SMOKE_ARGS+=(--site "$SITE")
[[ -n "$LOCAL_VERSION" ]] && SMOKE_ARGS+=(--expect-version "$LOCAL_VERSION")
"$ROOT/scripts/smoke_cdn.sh" "${SMOKE_ARGS[@]}" || fail "HTTP smoke (manifest/parquet/site/version)"

# ── 2. Stats parity vs the local export ─────────────────────────────────────────
if [[ -f "$LOCAL_MANIFEST" ]]; then
  echo "── 2/4  stats parity (published vs local) ──"
  curl -fsS -o /tmp/_verify_pub.json "$BASE/data/_manifest.json" || fail "fetch published manifest"
  python3 - "$LOCAL_MANIFEST" /tmp/_verify_pub.json <<'PY' || fail "stats mismatch (published != local export)"
import json, sys
loc = json.load(open(sys.argv[1])).get("stats", {})
pub = json.load(open(sys.argv[2])).get("stats", {})
keys = ["total_laps", "total_drivers", "total_events", "total_circuits"]
bad = [k for k in keys if k in loc and loc.get(k) != pub.get(k)]
if bad:
    for k in bad:
        print(f"    {k}: local={loc.get(k)} published={pub.get(k)}")
    sys.exit(1)
print(f"    ✓ stats match ({', '.join(f'{k}={loc[k]}' for k in keys if k in loc)})")
PY
else
  echo "── 2/4  stats parity skipped (no local export at $LOCAL_MANIFEST) ──"
fi

# ── 3. Model plane: manifest + every ONNX reachable ─────────────────────────────
echo "── 3/4  model artefacts ──"
curl -fsS -o /tmp/_verify_models.json "$BASE/models/manifest.json" || fail "fetch model manifest"
MODEL_VERSION="$(python3 -c 'import json;print(json.load(open("/tmp/_verify_models.json")).get("model_version",""))')"
[[ -n "$MODEL_VERSION" ]] || fail "model manifest has no model_version"
while IFS= read -r onnx; do
  [[ -z "$onnx" ]] && continue
  code="$(curl -fsS -I -o /dev/null -w '%{http_code}' "$BASE/models/$onnx" || echo 000)"
  [[ "$code" == "200" ]] || fail "onnx $onnx → HTTP $code"
done < <(python3 -c 'import json;[print(m.get("onnx","")) for m in json.load(open("/tmp/_verify_models.json")).get("models",[])]')
echo "    ✓ model_version=$MODEL_VERSION, all ONNX reachable"

# ── 4. ONNX serving liveness (real inference) ───────────────────────────────────
if [[ -z "$SKIP_ONNX" ]] && command -v node >/dev/null 2>&1 && [[ -f "$ROOT/app/scripts/synthetic_check.mjs" ]]; then
  echo "── 4/4  ONNX inference ──"
  SYNTH_ENV="$ENV" CDN_BASE="$CDN_BASE" node "$ROOT/app/scripts/synthetic_check.mjs" || fail "ONNX serving check"
else
  echo "── 4/4  ONNX inference skipped ──"
fi

echo ""
echo "  ✅  Published $ENV verified (version ${LOCAL_VERSION:-?}, model $MODEL_VERSION)."
