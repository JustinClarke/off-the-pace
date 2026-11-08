# AX-15a: T* (held) kinds, 2026-11-08

Source: AX-15a table, `_evidence/ax-07-lineage/lineage.md` and `lineage.json` (AX-07a verdicts as updated by AX-07).
T* list = AX-15a table rows, plus AX-07a T* verdicts, minus AX-07a T verdicts.

## Differences from the AX-15a doc
- `rating_s`, TX-01 CI, era-ratings-timeline: lineage T-F -> LIVE in AX-07 (`race.teammate_gap`, `era_rating.season`); no stub.
- driver-circuit-affinity, synthetic-teammate, track-evolution, corner-phase-skill: lineage T-F/T, not stubbed (candidates for a live pass; corner_phase.season is built live in AX-07b).
- quali-vs-race: `quali_skill_s` T, `delta_s` / `race_skill_s` DA: not stubbed here (mixed; no table row names it).
- `tyre_cliff_survival.profile`: added as HELD by AX-07b. The page's stint query filters on anomaly_class IN (normal, clean_cliff), a filter built on the taxed residual (Q3 default: DA); the KM curve is also a lower bound (SURVIVAL_LOWER_BOUND). Owner may rule T-F with a second caveat instead.
- `data_quality.race`: added as HELD by AX-07b (usable_laps, pct_usable, anomaly_laps DA by lineage).
- `race_lost.component`: stays the AX-04 kind (class DA, every row refused, build() returns []); the doc lists race-lost under the breakdown row. Not converted to a stub (parity tests of AX-04); owner may ask for it.
- `driver_isolation.stint` is stubbed per (driver, race), not per stint (stint id would be read from the value table).
- Kind names for the table rows are chosen here (AX-21 should link these ids).

## Stub kinds (18)
| kind | grain | class | route | lineage reason |
| :-- | :-- | :-- | :-- | :-- |
| `lap_waterfall.component` | race_driver | DA | /lap-decomposition/waterfall | total_explained_s contains dirty_air_tax_s; skill is the remainder |
| `sector_decomposition.component` | race_driver | DA | /lap-decomposition/sectors | sector dirty air (WC) |
| `ghost_race.standings` | race_driver | DA | /ghost-car/standings | fct_ghost_car_pace / fct_ghost_race_finish carry dirty_air_tax_s |
| `counterfactual_championship.season` | season_constructor | DA | /ghost-car/championship | ghost-car pace includes the tax |
| `hidden_performance.season` | season_constructor | DA | /ghost-car/hidden | ghost-car pace includes the tax |
| `race_driver.skill_components` | race_driver | DA | /lap-decomposition/race-lost | race mart mean_*_component_s are net of the tax |
| `season_driver.skill_benchmark` | season_driver | DA | /drivers/consistency | benchmark driver_skill and dirty_air rows are net of the tax |
| `driver_isolation.race` | race_driver | TRAFFIC | /aero/dirty-air | CO-30: thin cells priced with the flat rule (int_driver_isolation_lap_panel.sql:119-153) |
| `driver_isolation.stint` | race_driver | TRAFFIC | /aero/dirty-air | CO-30; stub is per (driver, race) because a stint id is a value-table key |
| `driver_consistency.season` | season_driver | DA | /drivers/consistency | fct_driver_skill_features is built on the residual |
| `wet_race.specialist` | season_driver | DA | /drivers/wet-race | built on the residual |
| `constructor_structural_pace.season` | season_constructor | DA | /constructors/structural | constructor_component_s, CO-30 |
| `party_mode.season` | season_constructor | DA | /tyre-strategy/party-mode | shares the car term |
| `constructor_circuit_interaction.season` | season_constructor | DA | /constructors/circuits | shares the car term |
| `constructor_team_averages.season` | season_constructor | DA | /constructors/team-averages | shares the car term |
| `dirty_air.price` | race_driver | TRAFFIC | /aero/dirty-air | price_kind: the tax and cumulative tax stay held until AX-16 (rule 9) |
| `tyre_cliff_survival.profile` | race_compound | DA | /tyre-strategy/survival | stint filter anomaly_class IN (normal, clean_cliff) is built on the taxed residual (Q3: DA filter); the Kaplan-Meier curve is also a lower bound |
| `data_quality.race` | race | DA | /data-quality | lineage: usable_laps, pct_usable and anomaly_laps are dirty-air-dependent |
