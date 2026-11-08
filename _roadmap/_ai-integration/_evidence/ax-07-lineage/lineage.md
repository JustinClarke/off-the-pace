# AX-07 lineage table (closes AXW11 with AX-15a)

Date: 2026-11-08. Machine-readable table: `lineage.json` (one row per source model and used column, with class, rule and evidence; `lineage.test.ts` reads it). The column-level reading is AX-07a's (`../ax-07a-lineage-2026-11-07/lineage.md`, dbt manifest walk plus SQL read), updated for the TX-01 and TX-02 columns that landed after it.

## Rule (HD13, ruled 2026-11-07)

| Lineage class | Card class | Live in v1 |
| :-- | :-- | :-- |
| T: no air-state, tax, isolation, WC or ML path to the value or its row filter | T | yes |
| T-F: `int_lap_air_state` only chooses laps (the rain filter via `int_track_evolution`) | T with caveat `AIR_STATE_FILTER` | yes |
| DA: value contains `dirty_air_tax_s` or the taxed residual, or a filter built on it (Q3 default) | DA | held (HD2 = C) |
| TRAFFIC: an air-state gap or share used as a value (Q5 default) | TRAFFIC | held |
| ML | ML | held |

Owner defaults from the AX-07 log note, applied: Q1 components stacked against the skill bar are held; Q2 the compound seed is transform-only with a caveat; Q3 filters on the taxed residual are DA; Q5 exposure shares and gaps are TRAFFIC.

## What changed since AX-07a

- **Race-mart `ci_low` / `ci_high`: DA -> T-F.** AX-07a found the old CI was `STDDEV(driver_skill_residual_s)/SQRT(n)` (taxed). TX-01 replaced it with the order-statistic CI of the paired-lap median, the same statistic as `rating_s`. Interval kind `ci_order_stat_median`, NULL when `paired_lap_count < 6`.
- **`mart_race_coverage` (TX-02): T.** Counts and presence shares only. It reads `int_lap_air_state` for the share of laps with a non-NULL air state, which is a presence test and not a gap, share or price.
- **Results: `stg_results`, T.** Not `mart_race_driver_summary.laps_completed` (that counts valid timed laps), and not `fct_ghost_race_finish` (its row set is DA).

## Design 2.4 reconciled (provisional class -> lineage)

| Design 2.4 row | Design class | Lineage class (card class) | Status in AX-07 |
| :-- | :-- | :-- | :-- |
| (no page) rating marts: race teammate gap | T\* | T-F (T + AIR_STATE_FILTER) | **live**: `race.teammate_gap` |
| rating marts: interval | lap_noise_band | `ci_order_stat_median` (TX-01) | live |
| (no page) results | T | T (from `stg_results`) | **live**: `race.result` |
| era-ratings-timeline | T\* | T-F (T + AIR_STATE_FILTER) | **live**: `era_rating.season` |
| race-control: caution laps | T | T | **live**: `race.cautions` |
| pit-strategy: observed stops | (not listed) | T | **live**: `driver_race.pit_stops` |
| pit-strategy: optimal lap, opportunity cost | T, held | T [S], held (D9) | held |
| pit-strategy: verdict | T, held | **TRAFFIC [A]**, held | held |
| race-lost | T\* | DA (components held under Q1) | refused (no interval; DA) |
| rating marts: `mean_*_component_s`, `mean_dirty_air_tax_s` | T\* | DA (Q1) / DA price | not carded (AX-15a stubs) |
| driver-workload | T | DA [R] / TRAFFIC | not carded |
| data-quality-audit | T | mixed: usable and anomaly counts DA [R] | not carded in this pass |
| quali-vs-race-skill | T (check) | `quali_skill_s` T [S]; `delta_s`, `race_skill_s` DA | not carded in this pass |
| tyre-recovery-forecast | T (check) | mixed; `recovery_rate_pct` DA | not carded in this pass |
| synthetic-teammate, constructor structural pace, track evolution, circuit affinity | T\* | T-F [S] | not carded in this pass (candidates for a later T pass) |
| corner-phase-skill, field-pace-curve, tyre-cliff profiles | T (check) | T-F / T-F [S] / T [S] | not carded in this pass |

`data_quality.race`, `race_control.pooled_rate`, `tyre_cliff_survival.profile`, `corner_phase.season` and `season.teammate_gap` from AX-07's minimum set are **not built yet**; see PROVENANCE.txt in `../AX-07-2026-11-08/`.
