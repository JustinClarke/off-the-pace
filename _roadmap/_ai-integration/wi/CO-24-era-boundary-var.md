# CO-24 — Hard-coded era boundary shadows var('era_boundary')

**Status:** SPEC (nothing run). **Group:** 1 data settled · **Depends on:** none · **Blocker:** none. Raised 2026-10-22 from the transform audit.

**Sources:** `transform/models/marts/mart_degradation_history_envelope.sql`, `transform/models/intermediate/int_driver_circuit_era_affinity.sql`, `transform/dbt_project.yml`.

## Problem

`dbt_project.yml` sets `era_boundary: 2022`. Both models set `{% set era_boundary = 2022 %}` (about line 44 and line 60), so changing the var does not reach them.

## Method

Replace each local set with `var('era_boundary')`. Values are unchanged today (both 2022), so output must not move.

## Definition of done

Both models read the var; a rebuild of the two models shows no row change. Do not commit.
