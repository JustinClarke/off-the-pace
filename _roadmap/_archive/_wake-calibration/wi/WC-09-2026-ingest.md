# WC-09 - Ingest the 2026 season into bronze

**Status: not started, not registered.** No dependency. Blocks nothing in the archived replay (WC-07 covers 2018-2025). Design: [`WC-design-note.md`](WC-design-note.md).

**Why.** Checked 2026-10-27: bronze has no 2026 season in any dataset (laps, telemetry, track_status, race_control, weather, circuit_info, results, schedule, jolpica reference); every dataset stops at season=2025.

**Goal.** Run the existing ingestion for the 2026 races held so far, from the archived FastF1 timing (not the paid OpenF1 live feed; that is DD-WC3).

**Notes.**
- 2026 removes DRS; the DRS code in telemetry changes meaning or disappears. The method must be refit for 2026 (design note), so 2026 passes are counted, not pooled with 2018-2025.
- While circuit_info is re-run, the marshal-sector positions could be written too (`ingestion/src/ingest.py` `_write_circuit_info` writes corners only). That would make the WC-01 sector-yellow rule exact. **Deferred by the owner 2026-10-27 (not rejected)**: bronze for past seasons is not rewritten; W6 stays open. Writing marshal sectors for the new 2026 folders only would be append-only, but it is not part of this item unless the owner asks.

**Done when.** The 2026 race folders exist in bronze with a manifest; the WC-01 builder runs on them on a scratch copy and its counts are recorded. No fit.
