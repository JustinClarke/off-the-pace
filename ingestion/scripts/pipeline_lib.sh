# Shared helpers for ingestion/scripts/*.sh. Sourced, not run directly.
#
# Env the caller can set:
#   PYTHON          interpreter (default ./.venv/bin/python)
#   DRY_RUN=1       print each command instead of running it
#   MAX_ATTEMPTS    attempts per pass before giving up (default 6)
#   RETRY_SLEEP_S   seconds between failed attempts (default 300)

PY="${PYTHON:-./.venv/bin/python}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-6}"
RETRY_SLEEP_S="${RETRY_SLEEP_S:-300}"
DRY_RUN="${DRY_RUN:-0}"
BRONZE=data/bronze
INGEST=ingestion/src/ingest.py
JOLPICA=ingestion/src/jolpica_client.py
LOCK=ingestion/src/bronze_lock.py
VERIFY=ingestion/verify_bronze.py

log() { printf '=== %s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }

# Run a command, or only print it when DRY_RUN=1.
step() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry run] %s\n' "$*"
    return 0
  fi
  "$@"
}

KNOWN_GAPS=ingestion/known_gaps.txt
LOG_DIR=data/logs

# Sessions that ingest.py reports as blocking in a log: "FAILED YEAR RdN T slug"
# and "[THIN] T  YEAR RdN slug". Printed as "YEAR T slug", one per line.
blocking_sessions() {
  {
    grep -oE 'FAILED [0-9]{4} Rd[0-9]+ [RQ] [a-z_]+' "$1" | awk '{print $2, $4, $5}'
    grep -oE '\[THIN\] +[RQ] +[0-9]{4} Rd[0-9]+ [a-z_]+' "$1" | awk '{print $3, $2, $5}'
  } | sort -u
}

# Blocking sessions in a log that are NOT in known_gaps.txt.
unresolved_sessions() {
  local known
  known=$(grep -vE '^[[:space:]]*(#|$)' "$KNOWN_GAPS" | awk '{print $1, $2, $3}' | sort -u)
  blocking_sessions "$1" | grep -vxF -f <(printf '%s\n' "$known") || true
}

# Retry a whole pass. Each retry resumes, because finished sessions are skipped.
# A pass also counts as done when every blocking session is a known gap.
run_pass() {
  local label="$1"; shift
  local attempt=1
  mkdir -p "$LOG_DIR"
  local logf="$LOG_DIR/$(echo "$label" | tr ' ()+/' '_____').log"
  while (( attempt <= MAX_ATTEMPTS )); do
    log "$label: attempt $attempt/$MAX_ATTEMPTS (log: $logf)"
    step "$PY" "$INGEST" "$@" 2>&1 | tee "$logf"
    local rc=${PIPESTATUS[0]}
    if (( rc == 0 )); then
      log "$label: ok"
      return 0
    fi
    if [[ "$DRY_RUN" != "1" ]] && [[ -n "$(blocking_sessions "$logf")" ]]; then
      local open
      open=$(unresolved_sessions "$logf")
      if [[ -z "$open" ]]; then
        log "$label: ok, with known gaps only: $(blocking_sessions "$logf" | tr '\n' ';')"
        return 0
      fi
      log "$label: unresolved sessions (not in known_gaps.txt): $(echo "$open" | tr '\n' ';')"
    fi
    log "$label: attempt $attempt exited non-zero"
    (( attempt++ ))
    if (( attempt <= MAX_ATTEMPTS )) && [[ "$DRY_RUN" != "1" ]]; then
      sleep "$RETRY_SLEEP_S"
    fi
  done
  log "$label: FAILED after $MAX_ATTEMPTS attempts"
  return 1
}

# Jolpica (standings, pit stops, results): public API, no key, retried the same way.
run_jolpica() {
  local label="$1"; shift
  local attempt=1
  while (( attempt <= MAX_ATTEMPTS )); do
    log "$label: attempt $attempt/$MAX_ATTEMPTS"
    if step "$PY" "$JOLPICA" "$@"; then
      log "$label: ok"
      return 0
    fi
    (( attempt++ ))
    if (( attempt <= MAX_ATTEMPTS )) && [[ "$DRY_RUN" != "1" ]]; then
      sleep "$RETRY_SLEEP_S"
    fi
  done
  log "$label: FAILED after $MAX_ATTEMPTS attempts"
  return 1
}

# Unlock Bronze if a previous run locked it, so this run can write.
unlock_bronze() {
  if [[ -f "$BRONZE/MANIFEST.json" ]]; then
    log "unlocking $BRONZE"
    step "$PY" "$LOCK" unlock "$BRONZE" || return 1
  fi
}

# Write the manifest, set the immutable flag (macOS), then verify the result.
lock_and_verify() {
  # Completeness first: anything missing that is not a known or source-confirmed gap
  # stops the run before the lock, so Bronze is never locked with silent holes.
  log "checking completeness (verify_bronze)"
  step "$PY" "$VERIFY" || {
    log "completeness check found new problems: not locking. Fix them or add them to ingestion/known_gaps.txt, then re-run make ingest-full"
    return 1
  }
  # Record the known gaps inside Bronze, so the lock covers them.
  log "recording known gaps in $BRONZE/KNOWN_GAPS.txt"
  step cp "$KNOWN_GAPS" "$BRONZE/KNOWN_GAPS.txt" || return 1
  log "locking $BRONZE"
  step "$PY" "$LOCK" lock "$BRONZE" || return 1
  log "verifying $BRONZE"
  step "$PY" "$LOCK" verify "$BRONZE" || return 1
}
