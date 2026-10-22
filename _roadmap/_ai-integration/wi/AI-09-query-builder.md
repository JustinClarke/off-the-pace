# AI-09 — Query builder: structured requests, bounded SQL, fixed result shape

**Group:** 2 assistant build · **Depends on:** `AI-01`, `CO-16` (the exported sector table must close before any view on it is whitelisted) · **Blocker:** none (AD2, AD3 ruled 2026-10-22).

**Sources:** `app/src/data/duckdb/queryLab.ts`, `app/src/data/duckdb/client.ts`, `app/src/data/manifest.ts`.

---

## Why a builder, not SQL

The model never writes SQL. It fills in a small request; the browser checks every field against a whitelist and builds the query. This keeps every query read-only and bounded, and it means every result can carry its sample size (AD3).

## Method

1. **Request shape** (the only thing the model can send):
   - `view`: one name from the whitelist of curated views (about 8: the stints, corners, driver-season skill, laps and results views). The 28.6M-row telemetry table and the raw flag tables are not exposed.
   - `filters`: column, operator, value. Lap-level views must filter by season.
   - `group_by`: at most two columns.
   - `aggregate`: one of count, avg, median, min, max, sum, on a whitelisted column.
2. **Validation in the browser**, before any SQL: unknown view, column or operator is rejected with a reason the model can read.
3. **SQL** is built from the validated request only, and runs through the existing `runLabQuery`.
4. **Result shape**, always the same: `view`, `filters_applied`, `grain`, `n` per row, `row_count`, `rows_shown` (25 or fewer), `rows_dropped`, values rounded to 3 decimals, a fixed sort order, and the label `computed_not_card`.
5. **Limits:** 3-second timeout; no more than 25 rows returned; read-only.
6. **No data:** `{status: "no_data", reason}`, never an empty table.
7. **Schema on demand:** a describe call returns one view's columns (about 300 tokens). The full schema is never in the prompt.

## Acceptance

- 0 SQL strings come from the model (checked by code path, not by prompt).
- A 200-call fuzz test over invalid fields and operators: every rejection is a structured error; no result breaks the result shape.
- Every returned row has `n`.

## Definition of done

Tests pass, the fuzz test runs in CI, and the headless command answers 10 sample questions through the builder. Do not commit.
