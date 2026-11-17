# TX-24 — Track-limits counts from DeletedReason

**Group:** 1b new-data · **Depends on:** TX-15 · **Model / cost:** `sonnet-5`, 0.5-1d

**Evidence:** data-use audit, read-only, 2026-11-16 (relayed to the board session; no evidence file on disk). References re-checked 2026-11-16.
**How to run:** own scratch folder, copy named `dev.duckdb`, 1 thread (rule 5). Never write `data/dev.duckdb`, `data/bronze/` or `data/fits/`. No data-writing make target without the owner. Nothing staged or committed by an agent.
**Class:** measured, transform class (rule 4: live since AX-07). Missing stays NULL with a reason, never 0. A card on this mart is AX-28, not this item.

## Why
Bronze laps carry `Deleted` and `DeletedReason` (audit: 2,010 R and 722 Q laps deleted). `stg_laps.sql:93-99` keeps `is_deleted` and drops the reason.

## Method
Carry `DeletedReason` through `stg_laps` and `stg_laps_qualifying`; parse the turn when the text names one ("Track Limits at Turn X"), else keep the text with turn NULL. Mart: deleted laps per driver, race, session and turn, with the raw reason kept. Plain counts; no rate unless the denominator (laps run) is in the same row.

## Done when
Counts reconcile with the Bronze `Deleted` totals per session, and a test fails if a deleted lap is missing from the mart.

## Sources
`transform/models/staging/stg_laps.sql`, `transform/models/staging/stg_laps_qualifying.sql`, `ingestion/SCHEMA.md`, `transform/models/marts/fct_track_limits.sql` (new).

## 2026-11-16 (fixall session), scratch only, not exported
stg_laps and stg_laps_qualifying now carry deleted_reason. New marts: models/marts/new_data/fct_track_limits.sql (one row per deleted lap, turn parsed) and fct_track_limits_driver_session.sql (counts per driver, race and session with n_laps_run; a season with no deletion data in Bronze gives NULL plus SOURCE_HAS_NO_DELETION_DATA). Test assert_track_limits_reconcile passes: counts match Bronze per session (R 2,010 and Q 722 for 2019-2026; 2018 is 816 driver-sessions, all NULL with the reason). Turn parsed on all but 1 2023 Q and 2 2024 R deletions. Output: /private/tmp/claude-501/-Users-justin-github-off-the-pace/2a4fcfbe-da29-45d9-a8d3-1e4bbaaf446a/scratchpad/fixall/new_marts_check.txt.
