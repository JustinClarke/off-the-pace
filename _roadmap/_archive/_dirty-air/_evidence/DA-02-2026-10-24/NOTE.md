# DA-02 Phase 1 tables and descriptives: evidence note (2026-10-24)

**Built on a scratch copy of uncommitted code.** The warehouse is a copy of `data/dev.duckdb` (CO-17 build) rebuilt with the working tree (v17 W10 changes plus the two micro-sector models). See PROVENANCE.txt for the commands, hashes and the re-run check. Re-run on the rebuilt dev after the owner commits. Descriptive only: the DA-03 fit was not run.

Panel: `int_microsector_crossings` and `int_microsector_proximity`, 3,743,701 rows each, 20 micro-sectors per lap (DD8), seconds grain (DD7), 171 races, 2018-2025. The panel is built at micro-sector grain from interpolated boundary crossings, not from a sample-level table (the entry-gap design does not need one; the owner may still want it).

## Verdicts

| Gate / check | Verdict | Numbers |
|---|---|---|
| Continue: loss rises as the gap shrinks | **PASS** (raw curve) | Mean `y_s` (s per micro-sector vs field median): <0.5 s +0.068, 0.5-1 +0.018, 1-1.5 +0.010, 1.5-2 +0.006, 2-3 +0.003, >3 -0.007. Same order in both eras. |
| Stop: no gap gradient | **Not triggered** | As above. |
| Build runs in minutes | **PASS** | Crossings 3.3 s, proximity 16.4 s. Two rebuilds identical (EXCEPT = 0, previous session). |
| Gate A carried from DA-01: >= 90% valid | **PASS** | 95.1-98.3% of timing-valid rows per season (81.3% of all rows). |
| Lap-total identity | **PASS** | Sum of 20 micro-sector times vs lap time: median abs 0.026-0.032 s, no bias, 16 laps of 133,685 over 0.5 s. |
| 20 micro-sectors per lap is enough samples | **PASS** | Position samples per slice p50 14 (2018-19) to 19 (2020), p10 9-13. |

## 1. Validity funnel

`results/01_reason_funnel_by_season.csv`. Valid share of all rows 0.737 (2018) to 0.866 (2024); of timing-valid rows 0.951-0.983. Largest drops: non-green track status (22k-56k per season; any non-'1' circuit status counts, since marshal-sector maps are absent, DD6), the two laps after a restart (18k-37k), lapped car ahead within 3 s (7.5k-20k, DD5). `wide_bracket` (crossing interpolated across more than 1 s) is 0-34 per season before 2022 and 5k-10k after: the jittered 2022+ position cadence.

## 2. Loss versus gap

`results/02_loss_vs_gap_raw.csv`, `02b_loss_vs_gap_raw_by_era.csv`. Rows: valid, `y_s` present. The <0.5 s band is the only one with a positive median (+0.028 s) and a share slower than the field above one half (0.587). Pre-2022 is steeper than post-2022 in every band under 3 s (<0.5 s: +0.091 vs +0.057). Raw means, no fixed effects: not an estimate of the dirty-air effect.

## 3. Samples per slice

`results/03_samples_per_slice.csv`. Slices of 1/20 lap from `stg_telemetry_position`, lap >= 2. Share of slices under 10 samples: 9-11% in 2018-19, under 5% after.

## 4. Lap-total identity

`results/04_lap_total_identity.csv`. Complete laps (20 micro-sector times) joined to `stg_laps.lap_time_s`. p95 abs 0.079-0.110 s.

## 5. Interpolation bracket

`results/05_bracket_by_season.csv`. Median gap between the two position samples around a boundary: 0.30 s (2018-19), 0.22 s (2020-21), 0.28 s (2022+). p99 under 0.31 s before 2022, 0.84-1.00 s after.

## 6. Panel for the fit

`results/06_panel_for_fit.csv`. 3,039,930 valid rows, 171 races, 157,900 laps; car ahead's own `y_s` missing on 1.3%.

## Open

- DA-03 pre-registration (`wi/DA-03-preregistration.md`) is a DRAFT, not committed. No fit until the owner commits it.
- P3 owes a micro-sector to corner-class map; DRS state is not in the panel.
- Blue-flag agreement (`assert_microsector_agrees_with_blue_flags`): clear-behind share blue/other ratio 0.19-0.28 against the 0.85 bar (test, not in results/).
