# CO-26 — Add relationships tests

**Status:** SPEC (nothing run). **Group:** 1 data settled · **Depends on:** none · **Blocker:** none. Raised 2026-10-22 from the transform audit.

**Sources:** `transform/models/staging/schema.yml`, `transform/models/intermediate/schema.yml`, `transform/models/marts/schema.yml`.

## Problem

None of the 1,183 dbt tests is a `relationships` test (grep of `transform/models` for `relationships` finds only README mentions). Foreign keys (race_id, driver_id, constructor, compound) are not checked between layers.

## Method

Add `relationships` tests for the key columns of the marts and the exported models to their dimension or staging parent. Any failure is a finding, recorded, not silenced.

## Definition of done

Tests added; run on ci and on a named dev build; failures listed in the log. Do not commit.
