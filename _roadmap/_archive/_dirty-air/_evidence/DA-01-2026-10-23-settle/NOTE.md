# DA-01 settle: open items after DD5 (2026-10-23)

**All numbers are PROVISIONAL.** data/dev.duckdb is stale until CO-17 rebuilds it (watch W1). Nothing here reads a stale dev table: item 1 reuses DA-01 results built from the staging views, and item 2 reads the staging views `stg_telemetry_position` and `stg_pits` plus bronze. Re-run both after CO-17. Earlier evidence: `../DA-01-2026-10-23/`. Provenance: PROVENANCE.txt.

| Item | Verdict | Key numbers |
|---|---|---|
| 1. Gate A under DD5 (lapped car ahead is invalid only within 3 s) | **PASS in every season** | 97.0% overall. By season: 95.5 / 95.5 / 96.9 / 95.7 / 97.6 / 98.3 / 97.4 / 98.5% (2018-2025). The lowest is 2018 at 95.50%. |
| 2. 2018 marshal sectors (10 races served the 2019 layout) | **2019 layout is consistent with the yellows. Whether a 2018 layout would fit better cannot be settled.** | Slow car 0 to +3 sectors downstream of the yellow sector: 68.4% in the test races, 81.4% and 72.1% in the controls. Single-car incidents: 70% (test) vs 80% (controls), Fisher p = 0.30. |
| 3. FastF1 livetiming 401 | **Still reproduces** | One GET at 2026-10-23T09:51:36Z returned HTTP 401. |

## 1. Gate A re-verdict under DD5

**Source.** The existing result `../DA-01-2026-10-23/results/05_valid_share_by_season.csv`, column `d_lapped_within_3s_invalid`, already applies the DD5 rule per season, so no query was re-run. A sample is valid when its crossing-order car ahead is:

- on the same lap, or
- a lapping car (the sample's own car is the one being lapped), or
- a lapped car with `gap_ahead_s >= 3`.

A sample is invalid when:

- a lapped car is ahead within 3 s, or
- the lapped car ahead has a NULL gap, or
- there is no car ahead at all.

**Inputs.** The `pos_flags` and `xorder` tables behind that query were built in DA-01's own scratch work database from the staging views. They were not built from the stale `int_lap_proximity`.

**Results.** Table: `results/01_gateA_dd5_by_season.csv`.

| Season | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | All |
|---|---|---|---|---|---|---|---|---|---|
| Valid share (3 s rule) | 95.50% | 95.52% | 96.90% | 95.71% | 97.61% | 98.27% | 97.35% | 98.47% | 97.00% |

The per-season split holds: every season clears 90% by at least 5.5 points.

**Not verified.**

- The DD5 share is sample-count weighted. DA-01 computed a dt-weighted share only for the literal reading, where it differed from the count-weighted share by at most 0.0002. It did not compute one for the 3 s rule.
- 2018 has telemetry for 19 of 21 races (none for AUS or BHR). In 2018_3 and 2018_11 the track-status timeline is partial.

## 2. 2018 marshal-sector layout

**Races tested.** AUS 2018 and BHR 2018 have no telemetry, so 8 of the 10 races were testable: AZE, ESP, MON, CAN, FRA, AUT, GBR and GER.

**Method.** Script: `queries/08_ms_layout_fit.py`.

1. Each race's position channel gives a reference polyline.
2. Each marshal-sector marker (MultiViewer `trackPosition`) is projected onto that polyline.
3. For each race-control sector message flagged YELLOW or DOUBLE YELLOW, the UTC `Time` is converted to session time using the lap-1 `LapStartDate` and `LapStartTime`.
4. The slow car is found in the window [t-20 s, t+3 s]: speed below 0.5 of the bin's median speed, on track, and outside the pit window. A car that was at racing speed in the preceding 90 s is preferred.
5. The car's x/y position is mapped to a marker sector, taking each marker as the start of its sector. The x/y position is used because `relative_distance` reads about 1.0 for stopped cars.
6. Messages are skipped when the whole field is slow (SC, VSC or red flag).

**Controls.** The same method runs on two control groups:

- C1: the 11 races in 2018 that were served the 2018 layout.
- C2: the 2019 races at the same 10 circuits, served the 2019 layout. Austria 2019 had no sector yellows, so C2 has 9 races.

**Signed offset.** The offset is the predicted sector minus the race-control sector, taken circularly. Yellows are waved upstream of an incident, so a correct layout should mostly give offsets of 0 to +3.

| Group | Matched msgs | Median offset | Offset 0..+3 | Offset -1..+3 | abs offset >= 5 | Exact | +-1 |
|---|---|---|---|---|---|---|---|
| T: 2018 on 2019 layout (8 races) | 79 of 103 | +1 | 68.4% | 70.9% | 17.7% | 17.7% | 49.4% |
| C1: 2018 on 2018 layout (11 races) | 43 of 58 | +1 | 81.4% | 83.7% | 9.3% | 20.9% | 44.2% |
| C2: 2019 on 2019 layout (9 races) | 43 of 87 | +1 | 72.1% | 81.4% | 7.0% | 14.0% | 55.8% |

Sources: `results/08b_offset_by_group.csv`, `results/08_ms_fit_summary_by_group.csv`, and per race `results/08b_offset_by_race.csv`.

**Test against the pooled controls.** These are ad hoc Fisher exact tests; the commands are in PROVENANCE.txt.

- **Offset 0..+3.** 54/79 against 66/86, p = 0.29.
- **abs offset >= 5.** 14/79 against 7/86, p = 0.10.
- **Single-car incidents only** (one slow car, lap >= 2):
  - Offset 0..+3: 23/33 (70%) against 37/46 (80%), p = 0.30.
  - abs offset >= 5: 3/33 against 3/46, p = 0.69.

The test group's excess of large offsets comes mostly from multi-car or lap-1 messages, where the method picks the wrong car. Examples are GBR 2018 lap 1 (four messages at +5/+6) and FRA 2018 lap 53 (three messages at -5/-6).

**Geometry.** On 2018 telemetry, the 2019 markers sit as close to the track as the controls' markers do:

- Median marker distance to the polyline is 2.1-6.2 m in AZE, ESP, MON, CAN, AUT, GBR and GER. The controls range from 2.4 to 5.7 m.
- FRA is about 12 m in both 2018 and 2019, so that offset belongs to the circuit, not the year.
- In every test race the markers fall around the lap in number order.
- No race-control sector number exceeds the 2019 marker count (DA-01 07e).

Source: `results/08_ms_fit_races.csv`, `results/08_ms_markers.csv`.

**Layout stability.** At all 10 test circuits, the API's marker positions are identical (0.0 shift) across every payload it serves from 2019 to 2025. The served payload years include 2019, 2020, 2021 and 2022. The one exception is Catalunya from 2023, which has 16 sectors and moved markers after the circuit change. Source: `results/08b_layout_stability_T_circuits.csv`.

**Verdict.** The 2019 layout fits the 2018 yellows no worse than correct-year layouts fit their own races, within this method's resolution. Whether a true 2018 layout would fit better cannot be settled, for two reasons:

- No 2018 layout exists to test. The API falls back to 2019, and bronze `circuit_info` holds only corners.
- The method's own floor is wide: 19-28% of correct-year control messages fall outside 0..+3.

**Unverified.**

- **The marker = sector-start convention is assumed.** The "nearest marker" convention fits worse in every group (`08_ms_fit_summary_by_group.csv`).
- **Identical markers across served years may mean MultiViewer reuses one marker set per circuit.** In that case stability is not independent evidence of what the FIA used in 2018.
- **No check was made that none of the 10 circuits changed its marshal posts between 2018 and 2019.**
- **AUS 2018 and BHR 2018 are untested** (no telemetry).
- **The test numbers are small:** 3-17 matched messages per race.

## 3. FastF1 livetiming 401

One request was made:

```
GET https://livetiming.formula1.com/static/2018/2018-11-25_Abu_Dhabi_Grand_Prix/2018-11-25_Race/SessionInfo.json
```

It returned **HTTP 401** at 2026-10-23T09:51:36Z. The 401 still reproduces. No fix was attempted.
