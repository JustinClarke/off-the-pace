#!/usr/bin/env bash
# Incremental update: pulls the new rounds of one season (default: the current year),
# plus Jolpica for that season, then locks and verifies Bronze.
#
# Rounds already on disk are skipped, and rounds still in progress are not loaded,
# so this is safe to run after every race weekend.
#
# Usage (repo root):
#   make ingest-update                 # current season
#   make ingest-update SEASON=2025     # a specific season
#   make ingest-update DRY_RUN=1       # preview only
#
# No credentials are needed: FastF1 and Jolpica are public.

set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
# shellcheck source=ingestion/scripts/pipeline_lib.sh
source ingestion/scripts/pipeline_lib.sh

SEASON="${SEASON:-$(date +%Y)}"
if ! [[ "$SEASON" =~ ^[0-9]{4}$ ]] || (( SEASON < 2018 )); then
  log "SEASON must be a four-digit year from 2018 on, got '$SEASON'"
  exit 2
fi

unlock_bronze || exit 1

run_pass "update $SEASON (R+Q, telemetry)" \
  --start-season "$SEASON" --end-season "$SEASON" --session both --telemetry-full --fill-missing || exit 1

run_jolpica "jolpica $SEASON" --start-season "$SEASON" --end-season "$SEASON" || exit 1

lock_and_verify || exit 1

log "DONE: $SEASON updated, locked and verified"
