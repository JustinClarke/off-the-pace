# CO-05 — W4: review the committed ingestion hardening, fix the stale test

**Group:** D carry-over · **Depends on:** none · **Blocker:** none.

**Sources:** `ingestion/verify_bronze.py`, `ingestion/src/ingest.py`, `ingestion/src/bronze_checks.py`, `ingestion/tests/test_bronze_verification.py`, `ingestion/tests/test_ingest_hardening.py`.

**Audit finding:** 7.

---

## What exists today (checked 2026-10-15)

- Fixes watch rule W4 says the ingestion-hardening work is uncommitted and unread. It was committed in a9fe181 (2026-09-25): `ingest.py`, `bronze_checks.py`, `verify_bronze.py`, `check_season_seeds.py`, and both new test files. `git status` shows no ingestion changes.
- The two test files give 56 passed, 1 failed: `test_markdown_table_keeps_its_season_range`. The test expects 2025 to be left out of the coverage table, but `verify_bronze.py:60` sets `MARKDOWN_SEASONS = range(2018, 2026)` on purpose (2025 was added once fully ingested; the 8-season scope is settled). **The test is stale, not the code.**

## Method

1. Update the test to the 2018–2025 range (for example, assert 2025 is kept and an out-of-range season is dropped).
2. Read a9fe181's ingestion diff for anything that changes what is written to bronze.
3. Leave `ingest-recent` at 2023–24. That is deliberate.
4. Record the review and test output in W4, and clear it.

## Acceptance

- Both test files pass.
- W4 records what was read, what was tested and the outcome.

## Definition of done

Tests green and W4 cleared with its resolution. Do not commit.
