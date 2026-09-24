# WI-05 — Season-onboarding completeness gate (bronze QA + seed/fit coverage)

**Group:** 12 season coverage · **Depends on:** nothing, but should land **before** `WI-02`'s seed
refit (the seed's fits consume the stint boundaries this fixes). · **Blocker:** none.

**Findings folded in:** F6, F8, F21, F24, F25, F26, F32, F33 (all Medium or unranked→Medium), **F52**
(new, Low-Medium).

**Reverification:** all CONFIRMED-AS-STATED, all correctly bronze-scoped where the audit says so (two
independent readers checked the charter's own out-of-scope rule against F18/F24/F25 specifically and
confirmed no cross-check exists between `stg_laps` and `stg_race_control`/`stg_pits` that could have
caught these in the transform layer).

---

## F8 — the 2018 Italian GP silently disappears

`race_to_track.csv` has no `2018_14` row (confirmed: the file jumps 2018_13 → 2018_15). The **INNER**
JOINs at `int_lap_fuel_state.sql:62` and `int_compound_cliff_predicted.sql:90` drop the whole event —
927 laps, 833 valid, ~0.5% of the warehouse. A prior engineer already knew about this
(`fit_compound_cliff.py:111`: "2018_14 is a known, unrelated seed gap," defended against there with a
COALESCE) but that awareness never propagated to the two INNER JOIN sites, and neither model
documents the drop. **The original report has no explicit "Fix:" line for F8** — supplied below.

**Fix:** add the missing `2018_14` row to `race_to_track.csv`, or switch both joins to LEFT JOIN with
an explicit, documented NULL-handling decision (not a silent drop).

## F24, F25 — bronze stint numbering (out of scope for a transform fix; document + guard)

**F24:** three races (2018_3 China, 2022_11 Austria, 2025_6 Miami) have bronze `TimingAppData` stint
numbers that ignore the car's actual pit stops — confirmed against `stg_pits`, itself validated
100%-matched to Jolpica for 2019/2021-2025. 660 eligible rows (317 with a 5-lap label) sit on a stint
that contradicts the pit record. Two of the three races show *systemic* multi-lap corruption (a
driver's tyre age running 11+ laps stale), not a boundary-precision nit.

**F25:** in 17 of 21 2018 races, lap 1's `Stint` is NULL in bronze, so `lap_in_stint` and
`age_in_stint` read one lap low for the entire first stint — 24.5% of 2018's rows, confirmed via an
independent grid-group cross-check (the Q2-tyre-carryover rule gives an exact −1 offset in both the
Q2-starter and non-Q2-starter populations, which is not circular with the primary measurement).

Both are bronze-origin (FastF1 `TimingAppData`), correctly out of scope for a transform-layer root
-cause fix per the charter. The fix is **detection and repair in staging**, not upstream.

## F26 — rain flag contradicts the tyres the field actually ran

False positives: 2019 Monaco shows 83.5% of laps "raining" with 0% of the field on inter/wet tyres
(52% humidity — genuinely wet races run 83-90%). Unflagged wet races: both 2020/2021 Turkish GPs run
~100% inter/wet with 0% rain flag.

**Fix assessment — the report's proposed fix has a real gap.** "Derive wet conditions from tyre use"
is directionally right but partly circular: tyre choice is a strategy decision (teams sometimes gamble
on the wrong compound), not a pure wetness sensor. The report's own diagnostic data already contains a
better answer it doesn't use: the false-positive "raining" laps sit at 52% humidity vs. 83-90% for
genuinely wet races, and `humidity_pct` is already in `stg_weather`. **Recommend combining
`humidity_pct` (a non-circular physical signal) with tyre share as a second independent check**,
rather than tyre share alone.

## F6, F32, F52 — fuel, together

**F6:** `int_lap_fuel_state.sql:36-41` derives `race_lap_count` from `MAX(lap_number)` over **valid**
laps only, so any race where invalid (neutralized/red-flag) laps trail the field understates the
race's real length — confirmed in 12 of 172 races (2022_16 by 6 laps, 2023_3 by 5, etc.). Every lap
of those races prices fuel shifted by `gap × rate`.

**F32:** the same file's `initial_fuel_kg = race_lap_count × fuel_consumption_rate_kg_per_lap` has
**no cap of any kind**. 134 of 171 races exceed the FIA regulatory max (105kg 2018 / 110kg 2019+),
median 117.8kg, max 147.9kg (Sakhir 2020, 87 laps of a 3.5km outer loop at a rate calibrated for a
different, lower-rate short layout — not literally "the full-layout rate" as the original report's
parenthetical suggests, but still producing far more fuel than a ~300km race needs).

**F52 (new):** these two compound on the *same* neutralized races — F6's short lap count feeds
directly into F32's uncapped formula. Fix them together (see `../reference/new-findings.md` for detail): a single
`scheduled_laps` column on `dim_events`, sourced from `data/bronze/schedule/`, fixes both at once —
`race_lap_count` should read from it directly (not `MAX(lap_number)` over any lap subset), and the
consumption rate should be anchored to `regulatory_max_kg / scheduled_laps`.

## F21 — offline parquet fits are two seasons stale

`data/fits/constructor_car_fe.parquet` (fitted 2026-07-07) and `degradation_isotonic.parquet`
(2026-06-15) both carry `data_window: "2018_to_2024"` — neither was refitted after 12a-1 (2025
ingest, landed 2026-09-22). `driver_skill_field_s` is NULL on all 459 2025 driver-races;
`int_driver_circuit_era_affinity` filters that out, so 2025 rookies (ANT, BOR, HAD) never appear in
era-affinity pages. `check_freshness.py:27-30` only checks two *seeds* by fit-date age, and doesn't
reach either parquet fit or check data-window coverage against `MAX(race_year)` — confirmed by
direct read of `MANAGED_SEEDS`, which names neither parquet file.

## F33 — 2018 qualifying accuracy gate

`stg_laps_qualifying.sql:148`'s `AND is_accurate` term has no season carve-out. Confirmed live:
accurate share of timed non-pit quali laps is 0.736 for 2018 vs. 0.9976-1.000 for 2019-2025. This
produces 8.0% vs. ≤2.0% NULL-quali-feature rows for 2018 — larger in relative terms than several
other findings in this cluster despite being the simplest to fix.

## Method

1. **F8:** add the missing seed row or switch to a documented LEFT JOIN.
2. **F24/F25:** rebuild stint boundaries from `stg_pits` (plus red-flag lap changes) and cross-check
   against bronze `TimingAppData`; where they disagree beyond a tolerance, NULL the tyre columns for
   that race rather than serving a boundary that contradicts the pit record. For F25 specifically:
   assign lap 1 to the driver's first real stint when it's the only unassigned lap, and offset
   `TyreLife` by +1 on those stints.
3. **F26:** add `humidity_pct` as a second signal alongside tyre share; flag disagreement between the
   Rainfall column and the combined tyre+humidity signal rather than trusting either alone.
4. **F6/F32/F52:** add `scheduled_laps` to `dim_events` (sourced from `data/bronze/schedule/`); derive
   both `race_lap_count` and the fuel consumption rate from it. *(Corrected as built: neither premise
   holds -- `dim_events` is a 6-row manual incident log, not one row per race, and the bronze schedule
   has no lap count. The column lives in a per-race seed sourced from F1 live timing; see "As built".)*
5. **F21:** extend `check_freshness.py`'s coverage to both parquet fits, checked by `data_window`
   against `MAX(race_year)` in the mart, not by fit-date age.
6. **F33:** drop `is_accurate` from the qualifying validity gate, or require it only where the season
   actually populates it (2019+).

## Acceptance

- No race silently disappears from any mart via an undocumented INNER JOIN.
- Stint boundaries are cross-checked against `stg_pits` for every race, with quarantine (not silent
  serving) where they disagree.
- The rain/wet signal combines at least two independent measurements, not tyre choice alone.
- `race_lap_count` and fuel consumption both derive from a real scheduled-distance column, not from
  `MAX(lap_number)` over a filtered lap subset.
- `check_freshness.py` covers both offline parquet fits, checked by data-window coverage.
- The qualifying validity gate doesn't zero out 2018 on a sync-flag technicality.

## Tests to add

T4 (F8), T19, T20 (F24, F25), T21 (F26), T6, T24 (F6, F32 — combine per F52's note), T25 (F33), plus
extending `check_freshness.py`'s managed set (F21).

## Definition of done

`verify_findings.py`'s F6, F8, F21, F24, F25, F26, F32, F33 checks flip to CLEARED; `WI-02`'s seed
refit can proceed on stint boundaries known to match the pit record for the affected races.

## As built (2026-09-24) -- deviations from this spec

State is in `../status/build-log.json`; this section only corrects the spec where the build disproved
or refined it.

- **F6/F32/F52 -- where `scheduled_laps` lives and comes from.** `dim_events` is one row per
  manually logged incident (6 rows, 2021 only), and `data/bronze/schedule/` carries no lap count, so
  step 4's column could not go there. It is a per-race seed, `transform/seeds/race_scheduled_laps.csv`,
  generated by `ingestion/scripts/fetch_scheduled_laps.py` from the F1 live-timing LapCount stream
  (`TotalLaps`, "intended number of total laps", via `fastf1.api.lap_count`). `scheduled_laps` is the
  first value, announced before the start; `total_laps_final` (kept for audit) differs on 8 races
  where race control changed the distance (e.g. 2024_21 71 -> 69, 2021_12 44 -> 39). The regulatory
  limit is a var + macro (`fuel_regulatory_max_kg_by_season`: 105 kg 2018, 110 kg from 2019), so every
  race now starts at the limit and burns it evenly over `scheduled_laps`.
- **`verify_findings.py`'s F6/F32 query was re-pointed.** It reconstructed the start load from
  `dim_circuits.fuel_consumption_rate_kg_per_lap`, a per-slug constant the fixed model no longer uses
  (no single per-slug rate can equal limit / scheduled laps across seasons and layouts). The query now
  reads the rate `int_lap_fuel_state` actually burned at; the arithmetic is unchanged. `_db.py`'s path
  bug (F53, WI-07) was not touched -- the board was run from a scratch copy with only that path patched.
- **F24 -- quarantine granularity and thresholds.** Race-level as specified, plus driver-race level
  for isolated corruption in otherwise clean races. A race is quarantined at >= 5 bronze stint changes
  with no in-lap in the 3 laps before (or whose in-lap an earlier change already claimed), or when >= 30%
  (and >= 3) of its racing stops have no stint change after them; the numbers are dbt vars. Quarantined:
  races 2018_3, 2022_7, 2022_11, 2025_6 and 14 driver-races (2018_4 RAI, 2018_5 HAR/SIR, 2018_13 VER,
  2018_15 ERI/SIR/VAN, 2018_18 LEC/STR, 2020_1 GRO/LAT, 2020_3 GRO/MAG, 2023_8 TSU). **2022_7 (Monaco
  2022) is new**: 19 of its 35 racing stops have no bronze stint change; the audit's metric (stint
  changes without a stop) missed it because the failure there is the other direction.
  Quarantine serves the pit record's stint ordinal and NULL compound / tyre age.
- **F25 -- slightly wider than "the only unassigned lap".** Fills a leading gap of up to 2 laps (one car
  a race in 2018 misses lap 2 too; its first assigned TyreLife matches the 1-lap cars' pattern, so the
  offset is the gap length). Where the car pitted inside the gap (2018 lap-1 stops), the laps up to the
  in-lap become the stint before bronze's first, with NULL tyres and no offset.
- **F26 -- the combination rule.** A two-of-three vote (bronze Rainfall, humidity >= 70%, field
  inter/wet share >= 0.5) replaces `rainfall_flag` in `stg_weather`, so every consumer gets it;
  `rain_signal_disagreement` flags where bronze Rainfall disagrees with the vote.
- **F21 -- the refit.** Step 5 only extends `check_freshness.py`, but the definition of done needs the
  F21 check CLEARED, which needs both parquet fits refitted on 2018-2025; done (`make car-fe-fit`,
  `make deg-iso-fit` equivalents).
- **F8 -- seed re-key.** The compound seed carried 2018_14's three cells under the pseudo-key `2018_14`
  (the fitter's fallback while race_to_track lacked the row); they were re-keyed to
  `italian_grand_prix`, else the race would have re-entered with no seed cells.
- **Tests.** T6 and T24 are one test (`assert_fuel_load_matches_scheduled_distance`, per F52). T19
  replaces `assert_stint_boundaries_correct` and keeps its age-rises invariant. T25 is a dbt test
  (`assert_quali_valid_share_consistent_across_seasons`), not an extension of
  `snapshot_data_profile.py`: it is a cross-season invariant, and that script's `--check` is red on an
  outdated baseline (F11). `assert_constructor_coefficient_signs` now skips seasons whose dry panel
  holds < 2 constructors: with the corrected wet flag the CI fixtures' 2024 season (2024 São Paulo, run
  entirely on inters/wets) has none, and a lone constructor is centred to exactly 0.
- **Known interaction, not fixed here: F39 (WI-02a).** Quarantine NULLs tyre age on 4,035 valid laps,
  and DuckDB's `LEAST(NULL, 10)` prices each at the 10 s wear cap until WI-02a's NULL guard lands
  (F39's count 383 -> 4,107). Those rows are not training-eligible, but their residuals (~7 s low) feed
  fan-page aggregates for the quarantined races / driver-races.
