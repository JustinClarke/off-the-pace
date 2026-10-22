# CO-16 — Sector dirty-air tax: spread the lap tax by time

**Group:** 1 data settled · **Depends on:** none · **Blocker:** none. `CD7` ruled A (2026-10-22).

**Sources:** `transform/models/intermediate/int_sector_residual_decomposed.sql`, `transform/models/intermediate/int_dirty_air_tax_component.sql`, `transform/tests/assert_sector_aggregates_to_lap.sql`, `scripts/export_app_data.py`.

---

## Problem

The lap dirty-air tax is priced on the previous lap's share (`dirty_air_share_lag1`, theta_air 0.331). The sector model gates its share of that tax on the current lap's `dirty_air_share_lap`. On a lap that follows a dirty lap but runs clean itself, the sectors carry 0 and the lap carries 0.331 s. `assert_sector_aggregates_to_lap` fails on 10,698 dev laps and 152 ci laps, each by exactly 0.331 s, and is held at warn. The sector table is exported to the app (`export_app_data.py:98`), so the query builder (AI-09) could expose it.

## Method

1. Sector dirty-air tax = `dirty_air_tax_s × sector_time_s / lap_time_s`, with no gate. It is NULL where the lap tax is NULL (FD6).
2. Update the model header: this term now carries no sector-specific information. Pricing below lap grain is CD7 option C, a future project (watch W11).
3. In the test, also fail a lap whose sector sum is NULL while its lap total is not, or the other way round. Before this change, 1,482 dev laps were skipped silently.
4. Promote the test to `error` once it returns 0 rows.

A proposed diff exists, **not applied**. Treat it as a draft. The method above is what counts.

- **Copy (use this):** [`_evidence/co-16-2026-10-22/cd7_option_a.diff`](../_evidence/co-16-2026-10-22/cd7_option_a.diff), with [`PROVENANCE.txt`](../_evidence/co-16-2026-10-22/PROVENANCE.txt). It touches `int_sector_residual_decomposed.sql` and `assert_sector_aggregates_to_lap.sql`. sha256 `567d239c…45e4ba4`.
- **Original (session scratch, may be gone; if it still exists the copy is redundant):** `/private/tmp/claude-501/-Users-justin-github-off-the-pace/e7074a22-d03f-4724-882d-5fb7a35a514d/scratchpad/cd7_option_a.diff`.

## Acceptance

- `assert_sector_aggregates_to_lap` returns 0 rows on dev and ci, at severity error.
- Lap-grain tables are unchanged, row for row (no label moves). theta_air stays 0.331.
- `assert_sector_residual_identity` still passes.

## Definition of done

Model and test changed in the working tree. Both sector tests pass on dev and ci. A lap-grain diff shows no change. Do not commit.
