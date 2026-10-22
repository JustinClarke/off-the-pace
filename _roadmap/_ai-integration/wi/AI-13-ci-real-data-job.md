# AI-13 — CI cannot test real data

**Status:** SPEC (nothing run), low priority. **Group:** 3 delivery and launch · **Depends on:** none · **Blocker:** none. Raised 2026-10-22 from the transform audit.

**Sources:** `.github/workflows/dbt-ci.yml`, `transform/tests/fixtures/`, `.github/workflows/pipeline.yml`.

## Problem

dbt CI builds on a fixture of about 2.5k rows (three small races). Tests whose thresholds assume full data cannot fail or fire honestly there (for example the frozen-label test warns on 2 rows on CI only). The real-data gates live in `pipeline.yml`, which runs only when `PIPELINE_ENABLED` is set (watch W18).

## Method

Choose one (opus): a real-data test job (self-hosted runner, read-only on a reviewed build), or thresholds written so they hold at fixture scale. Record the choice and why.

## Definition of done

The chosen check runs and its result is recorded. Do not commit.
