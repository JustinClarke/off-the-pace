# Ingestion Design

Why the Bronze layer is built the way it is. The [README](README.md) tells you
*how* to run ingestion; this document explains the decisions behind it and the
resilience model that keeps an hours-long backfill from dying on the first bad
weather file.

## The pipeline at a glance

```
                 ┌─────────────────────────────────────────────────────────┐
                 │                     src/ingest.py                         │
                 │                                                           │
  FastF1 API ──► │  load session ──► DQ gate ──► partitioned Parquet write   │ ──► data/bronze/
 (with retry +   │      │              │              │                      │     <dataset>/
  on-disk cache) │      │              │              └─► manifest row       │     season=YYYY/
                 │      │              │                  (status, rows,      │     race=<slug>/
                 │      │              │                   fingerprint)       │
                 │      └─ per-dataset try/except ─┘                          │
                 └─────────────────────────────────────────────────────────┘
                                          │
                                          ▼
                              data/bronze/manifests/run_<id>.parquet
                                          │
                                          ▼
                          make manifest-report  (status + schema drift)
                                          │
                                          ▼
                                  transform/  (dbt — all business logic)
```

## Design decisions

### Bronze is dumb; logic lives in dbt
Ingestion does exactly one thing: pull raw FastF1 data and land it as Parquet,
renaming columns to snake_case but never *computing* anything. No features, no
derived metrics, no joins. Every business rule lives downstream in dbt where it
is version-controlled, tested, and re-runnable without re-pulling from the API.
The payoff: a transform bug never costs a re-ingestion, and the raw layer stays
a faithful, auditable copy of the source.

### Append-only, idempotent writes
A session's Parquet is written once and skipped on subsequent runs unless
`--force` is passed (`ingest_race` / `ingest_qualifying` check `target.exists()`).
This makes a backfill safe to re-run after a crash: completed races are skipped
in milliseconds, only the gaps are pulled. The FastF1 on-disk cache
(`data/cache/`) makes even a `--force` re-pull cheap.

### Hive partitioning by season and race
Output is laid out as `<dataset>/season=YYYY/race=<slug>/`. DuckDB and dbt prune
partitions from the path, so a query scoped to one race never scans the ~550M-row
telemetry table. Partitioning by the two dimensions every downstream query filters
on is the single highest-leverage layout choice for read performance.

### Warn-don't-fail on qualifying, gate on races
Data-quality severity is tiered (see below). Race laps are the spine of every
model, so a schema failure there *blocks the write*. Qualifying is supplementary,
and red-flagged/short sessions are common, so its checks warn but never reject.
The principle: gate the data you can't afford to get wrong; observe the rest.

## Resilience model

The senior touches that make a multi-hour backfill survivable:

| Mechanism | Where | What it buys |
|-----------|-------|--------------|
| **Per-dataset try/except** | `_write_weather`, `_write_telemetry`, `_write_results`, … each wrapped | One corrupt weather file can't abort a race; one bad race can't abort the season. Failures are logged and ingestion continues. |
| **Exponential backoff retry** | `_with_retry` (1s → 2s → 4s → 8s) | Transient FastF1/network blips recover automatically instead of failing the run. |
| **DQ severity tiers** | `_run_quality_checks` | Schema failure on a race → skip the write and record `error`. Low row count / high nulls → warn only. The gate protects the spine without rejecting legitimately short sessions. |
| **Idempotency via skip-unless-`--force`** | `ingest_race` / `ingest_qualifying` | Re-running after a crash resumes from the gap, not from zero. |
| **Run manifest as audit log** | `_make_manifest_row` → `run_<id>.parquet` | Every attempt — ok, skip, or error — is recorded with row count, DQ flag, and a schema fingerprint. The run is queryable after the fact. |
| **Schema fingerprinting** | `_schema_fingerprint` (SHA-1 of sorted columns) | FastF1's schema drifts between seasons. The fingerprint makes that drift *detectable* (`make manifest-report`) instead of silently flowing into the warehouse. |

## Observability

The manifest is only valuable if something reads it. `make manifest-report`
(`manifest_report.py`) loads every `run_*.parquet` and reports:

1. **Last-run status** per `(season, round, session)` — the most recent
   ok/skip/error outcome, with errored sessions called out.
2. **Schema drift** — any change in a dataset's schema fingerprint between runs,
   flagged with the timestamp it changed.

It exits non-zero when anything errored or drifted, so it doubles as a CI gate.
For long backfills, `scripts/monitor_ingest.py` (stdlib-only) tails the live log
and exits early on `[DQ FAIL]` or process death.

## See also

- [README.md](README.md) — how to run ingestion, scope your data, and verify it.
- [SCHEMA.md](SCHEMA.md) — exact column definitions for every Bronze dataset.
