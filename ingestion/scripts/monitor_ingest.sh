#!/bin/bash
# Monitor ingestion process for failures and completion
#
# Usage:
#   ./scripts/monitor_ingest.sh <output_file>
#
#   <output_file>: path to the ingestion process output (from Bash run_in_background)
#
# Example:
#   python src/ingest.py --start-season 2018 --end-season 2024 --session R &
#   ./scripts/monitor_ingest.sh /path/to/output.log
#
# Polls the output file every 10 seconds and exits immediately if:
#   - Real failures detected ([DQ FAIL], process errors, OOM, disk full, etc.)
#   - Ingestion completes successfully (=== COMPLETE: message)
#
# Ignores FastF1 DEBUG-level noise (debug tracebacks, etc.)

set -e

if [ $# -eq 0 ]; then
  echo "Usage: $0 <output_file>"
  echo ""
  echo "Example:"
  echo "  python src/ingest.py --start-season 2018 --end-season 2024 --session R &"
  echo "  ./scripts/monitor_ingest.sh /tmp/ingest.output"
  exit 1
fi

OUTPUT_FILE="$1"
LAST_CHECK_FILE="/tmp/ingest_monitor_check_$(basename "$OUTPUT_FILE" | md5)"
POLL_INTERVAL=10

# Initialize last check position
if [ ! -f "$LAST_CHECK_FILE" ]; then
  echo "0" > "$LAST_CHECK_FILE"
fi

echo "Monitoring: $OUTPUT_FILE"
echo "Polling every ${POLL_INTERVAL}s for failures or completion..."
echo ""

# Loop until ingestion completes
while true; do
  # Check if output file exists
  if [ ! -f "$OUTPUT_FILE" ]; then
    echo "[$(date '+%H:%M:%S')] Waiting for ingestion output..."
    sleep "$POLL_INTERVAL"
    continue
  fi

  # Read new lines since last check
  LAST_POS=$(cat "$LAST_CHECK_FILE")
  CURRENT_POS=$(wc -c < "$OUTPUT_FILE")

  # If file grew, check for failures or completion
  if [ "$CURRENT_POS" -gt "$LAST_POS" ]; then
    NEW_LINES=$(tail -c +$((LAST_POS+1)) "$OUTPUT_FILE")

    # Check for real failure patterns (ignore DEBUG noise)
    # Only alert on actual failure statuses and process errors
    if echo "$NEW_LINES" | grep -qE '\[DQ FAIL\]| ERROR | CRITICAL |ProcessRuntimeError|MemoryError|OSError.*disk|killed by|Killed'; then
      echo ""
      echo "❌ FAILURE DETECTED in ingestion:"
      echo "$NEW_LINES" | grep -E '\[DQ FAIL\]| ERROR | CRITICAL |ProcessRuntimeError|MemoryError|OSError.*disk|killed by|Killed'
      echo ""
      echo "Recent context:"
      tail -30 "$OUTPUT_FILE"
      exit 1
    fi

    # Check for successful completion
    if echo "$NEW_LINES" | grep -q "=== COMPLETE:"; then
      echo ""
      echo "✅ Ingestion completed successfully!"
      tail -5 "$OUTPUT_FILE"
      exit 0
    fi

    # Show progress (sample of [OK] and [PULL] lines from this batch)
    PROGRESS=$(echo "$NEW_LINES" | grep -E '\[OK\]|\[PULL\]' | tail -1)
    if [ -n "$PROGRESS" ]; then
      echo "[$(date '+%H:%M:%S')] $PROGRESS"
    fi

    # Update position
    echo "$CURRENT_POS" > "$LAST_CHECK_FILE"
  fi

  sleep "$POLL_INTERVAL"
done
