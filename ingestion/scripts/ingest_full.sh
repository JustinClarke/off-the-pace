#!/usr/bin/env bash
# Full Bronze pull, 2018-2026: every race and qualifying session with telemetry,
# plus Jolpica standings and pit stops. Unattended and safe to re-run.
#
#   1. unlock data/bronze if a previous run locked it
#   2. FastF1 races + qualifying, full telemetry (retried on rate limits), with
#      --fill-missing: a session already on disk is reloaded (FastF1 cache first)
#      only if one of its datasets is absent, and only the absent ones are written
#      (e.g. session_info, qualifying race control/telemetry). Nothing is forced.
#   3. Jolpica standings and pit stops, 2018-2026
#   4. lock data/bronze, then verify it against the manifest
#
# Finished, complete sessions are skipped on re-run, so re-running only pulls or
# fills what is missing.
# Exit 0 only if every step succeeded and the lock verified.
#
# Usage (repo root):   make ingest-full
# Preview only:        make ingest-full DRY_RUN=1
# No credentials are needed: FastF1 and Jolpica are public.

set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
# shellcheck source=ingestion/scripts/pipeline_lib.sh
source ingestion/scripts/pipeline_lib.sh

START=2018
END=2026

unlock_bronze || exit 1

run_pass "pass 1 (R+Q, telemetry, fill missing)" \
  --start-season "$START" --end-season "$END" --session both --telemetry-full --fill-missing || exit 1

run_jolpica "jolpica ($START-$END)" --start-season "$START" --end-season "$END" || exit 1

lock_and_verify || exit 1

log "DONE: full Bronze $START-$END ingested, locked and verified"
