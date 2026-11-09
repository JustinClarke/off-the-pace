# Data gaps: workarounds and how much each one matters (2026-10-27)

**Status: analysis only. Nothing is resolved by this memo.** W6 (marshal sectors) and DD-WC3 (live feed / licence) stay open. Counts and exclusions only: no loss, coefficient, curve or scale was computed, and no archived DA-03 number is used.

Baseline: the WC-01 pass table built by `transform/tasks/wake_calibration/build_pass_table.py` (sha256 016c3bd6..., the 2026-10-27d build): **2,927,753 passes, 2,188,484 kept, 1,071,162 measured, 14,253 `yellow_sector`**. Rebuilding it with the unpatched builder reproduced every reason exactly (0 changes).

Scripts and outputs (scratch, not in the repo): `/private/tmp/claude-501/-Users-justin-github-off-the-pace/893bb34f-15dd-4fc3-a095-752d56d99b20/scratchpad/wc_workaround/` (`scripts/variant_build.py`, `compare_variants.py`, `yellow_locate.py`, `derive_corners.py`, `derived_build.py`, plus `sector_sensitivity.csv`, `sector_sensitivity_by_race.csv`, `yellow_inference_by_circuit.csv`, `sector_count_vs_multiviewer_2018_2020.csv`, `corner_validation2.csv`, `derived_corner_compare.csv`). Bronze was only read. `data/dev.duckdb` and `ci.duckdb` were not opened.

## Summary

| Gap | Passes affected (verified) | Share of 2,927,753 | Personal prototype | Paid release |
|---|---|---|---|---|
| 1. Marshal sectors approximated (even spacing) | 1,447-6,475 reasons change for boundary errors up to half a sector; 24,399-27,167 if boundaries are wrong by 1/6-1/3 of a lap | 0.05-0.22% (realistic); 0.83-0.93% (gross) | Can ignore for the core counts. Fix before showing per-sector yellow labels in the replay | Must fix (needs a licensed marshal-sector map) |
| 2a. 2018 AUS + BHR (no telemetry) | 0 passes; 1,937 of 189,418 bronze driver-laps missing | 1.02% of driver-laps; 8.67% of 2018 driver-laps | Ignore; label 2018 as 19 races | Not recoverable from any source checked |
| 2b. 2020 Sakhir + Tuscany (no corners) | 26,110 passes recoverable with telemetry-derived corners (13,406 + 12,704) | +0.89% of total; +10.9% of 2020 | Optional: recover with derived corners, flag them | Needs a corner source you are allowed to use, or derived corners |
| 2c. 2022 São Paulo (borrowed 2021 corners) | 18,313 passes (11,912 kept, 5,444 measured) | 0.63% of all; 4.89% of 2022 | Keep; the fallback is safe here | Same, if the corner source is licensed |
| 3. No 2026 in bronze | Every 2026 race: 0 passes until ingested | Whole season | WC-07 runs on 2018-2025; 2026 needs OpenF1 or FastF1 (personal use) | Needs a commercial timing licence |
| 4. Licences (all sources) | All 2,927,753 passes come from F1 timing data via FastF1 | 100% | Personal non-commercial use: acceptable as now | Re-source everything before charging |

## 1. Yellow-flag rule without marshal sectors

**Sensitivity (verified, 13 full or partial rebuilds).** Each variant changes only the corner-to-sector mapping; everything else is the WC-01 builder.

| Variant | Reasons changed | Kept → yellow | Yellow → kept | Yellow passes still yellow (of 14,253) | Measured change | Races changed |
|---|---|---|---|---|---|---|
| shift +1/6 sector width | 2,215 | 709 | 597 | 13,128 | -124 | 68 |
| shift -1/6 sector | 1,661 | 568 | 375 | 13,493 | -52 | 60 |
| shift +1/3 sector | 4,282 | 1,377 | 1,355 | 12,097 | -49 | 96 |
| shift -1/3 sector | 3,285 | 1,041 | 977 | 12,724 | -31 | 84 |
| shift 1/2 sector | 6,475 | 2,145 | 1,868 | 11,010 | -223 | 114 |
| shift +1/6 lap | 26,609 | 8,885 | 7,885 | 895 | -740 | 126 |
| shift -1/6 lap | 24,399 | 7,353 | 7,872 | 1,015 | +215 | 125 |
| shift +1/3 lap | 26,749 | 8,559 | 8,258 | 537 | -224 | 126 |
| shift -1/3 lap | 27,167 | 8,824 | 8,329 | 448 | -234 | 126 |
| sectors split over the 3 timing sectors (from laps Sector1/2SessionTime) | 1,447 | 551 | 477 | 13,577 | -85 | 58 |
| wider rule: k-1, k, k+1 (even spacing) | 5,306 | 3,402 | 0 | 14,253 | -1,754 | 106 |
| sector count from MultiViewer (2018-2020 only, 945,264 passes) | 1,977 | 498 | 875 | 5,040 of 6,261 | +183 | 19 |

- A shift of 1/6 or 1/3 of a **lap** is several sectors at 14-21 sectors per circuit. It leaves only 448-1,015 of the 14,253 yellow passes in place, so the rule is essentially random if sectors are that far off. Shifts of a **fraction of one sector** are the realistic error and move 0.05-0.22% of passes.
- **Ceiling.** Only 98,309 passes (3.36%) are on a lap with any yellow and are not already excluded by an earlier reason. No mapping can move more than that.
- **The sector count is also approximate.** The builder takes the count as the highest race_control Sector seen for the slug. Against MultiViewer's counts for 2018-2020 (archived DA-01 count table, not a DA-03 result), it matches 34 of 59 races. It is lower in 18 races (70th Anniversary 4 vs 16, Emilia Romagna 14 vs 19, Bahrain 16 vs 18) and higher in 7.
- **Timing-sector anchoring** is the cheapest improvement that uses only data we hold. It moves 1,447 passes. Whether it is closer to the truth is unverified, because it assumes marshal sectors nest inside timing sectors.

**Inferring boundaries from where yellows are issued (verified, heuristic).** Bronze has 1,338 sector-yellow messages over 2018-2025, with no car number on any of them. A message was attributed when exactly one car was below 60 km/h or OffTrack, on a non-pit lap, between 15 s before and 2 s after it. That located 313 messages (23%). For 632 messages no car qualified, and for 364 several did.
- At the located points, the even-spacing sector equals the yellow sector k for 92, is k+1 for 77 (both caught by the current k / k+1 rule) and is k-1 for 61 (missed). It is 2 or more sectors away for 83. The current rule covers 169 of 313 (54%); the k-1..k+1 rule covers 230 (73%). The heuristic is noisy, so these are rough.
- **Not enough data.** The median circuit has 34.5 yellow messages and 6.5 located. No circuit brackets all its boundaries; the best is Silverstone with 10 of 17 and Austria with 9 of 16. To bound every boundary at least once you need a located point on both sides of each one, which is at least 2 × n points (about 40 for 20 sectors). At a 23% hit rate that is about 170 or more messages per circuit. The busiest circuit, Baku, has 119. Use the inference as a check, not as a map.

**Recommendation.** Personal prototype: keep even spacing, and switch to timing-sector anchoring if it is wanted (a small code change, no new data). Report `yellow_sector` as approximate. Do not show `marshal_sector` as a fact in the WC-07 replay. The k-1 buffer costs 3,402 kept passes (0.16% of kept) and catches the k-1 misses. That is an owner choice. For a paid release, a licensed marshal-sector map is required.

## 2. Missing races

- **2018 Australia and Bahrain.** Built passes are 0. Bronze holds 940 + 997 driver-laps for them (race control and laps only). That is 8.67% of 2018 driver-laps and 1.02% of all. The archive note says no source has these streams, F1's included. **Drop them.** 2018 then has 19 races. Totals do not change, because they were never in the table.
- **2020 Sakhir and Tuscany.** Their circuit_info is empty and no adjacent season exists. The borrowed-corner fallback cannot apply: the fallback is same slug ±1 season, and Sakhir (outer loop) must not borrow Bahrain GP corners. **Workaround (verified):** derive corners from the race's own telemetry, using curvature peaks on a median clean lap.
  - Checked on 67 race-seasons that have circuit_info (2019, 2023 and 2025): 1,107 corners derived against 1,123 official. Recall is 77% within 40 m and 93% within 80 m; precision is 77% and 93%.
  - Built on five circuit_info races, the derived corner counts were 15 vs 15 (Bahrain 2020), 9 vs 11 (Monza), 17 vs 19 (Monaco), 15 vs 16 (Hungary) and 23 vs 18 (Silverstone 2024). Kept passes changed by -18% (Monza) to +28% (Silverstone); Bahrain changed by -0.4%. So derived corners change per-race counts a lot, and the per-corner match is only fair.
  - Applied to the two missing races, it gives Sakhir 13,406 passes (9 corners, 9,247 kept, 3,157 measured) and Tuscany 12,704 (17 corners, 8,427 kept, 4,093 measured). That is +10.9% for 2020.
  - Corner ids are not official numbers, so these races should carry a "derived corners" layout note and be treated as their own layout. Both are already first races at their circuit for the layout flag.
- **2022 São Paulo.** Its own circuit_info is identical to 2023's (0 m apart) and sits 325 m off as a whole frame from the 2022 telemetry. 2021's corners match it 100%, with an internal difference of 11 m after rigid alignment. The fallback is **safe here**. Dropping the race would remove 18,313 passes (0.63% of all, 4.89% of 2022) and change the measured share of kept from 48.95% to 48.96% overall and from 47.26% to 47.34% for 2022. Keep it.
- **What the fallback does to the layout flag.** It sets `layout_changed = True` with the note "corners taken from circuit_info season X (fallback)". That is not structural, so no new layout epoch starts. It also hides any real corner move in the fallback season, because the corners are the donor's by construction. Only the lap-length check (±50 m) could still catch a change. It is safe when the race is the same slug, ±1 season, matches the telemetry at 90% or more, and the lap length is within 50 m (São Paulo -15.9 m, Belgium 2021 +34 m, Bahrain 2024 -2.4 m). Flagged fallback passes total 35,028 (380 + 18,313 + 16,335).

## 3. 2026

Bronze stops at 2025 in every dataset (WC-09). The following is **reasoning, not run**:
- **Pipeline.** With no telemetry, the builder skips every race ("no telemetry parquet"), so 2026 has 0 passes. Laps-only data could give a timing-sector-level traffic count, not a per-corner one. 2026 also changes the meaning of the DRS code (TS-1 depends on it), and the design note already says 2026 must be counted separately, not pooled. A new circuit (for example Madrid) gets its sector count only from its own few yellows, so it will undercount (see section 1).
- **WC-07 replay.** It needs `ReplaySource.traces` with X/Y, distance, speed, brake and Status. It cannot run on 2026 without position and car data.
- **Legal personal-use options.**
  - OpenF1 historic API: free, CC BY-NC-SA 4.0, labelled "Personal use". The 2026 sessions returned 200 on 2026-10-23 (archive note). It has location and car_data at about 3.7 Hz, laps and race_control. It has **no** Status, distance or track_status, so these must be synthesised (distance from X/Y or integrated speed; Status = OnTrack, losing the off_track exclusion; track status rebuilt from race_control). Corners would come from the derived-corner method or MultiViewer.
  - FastF1 with the owner's F1 TV login: formula1.com terms say "personal, non-commercial use only".
  - So yes, a personal replay of 2026 is feasible, but with a weaker off-track exclusion. Fetching was not tested in this run.

## 4. Commercial use: what a replacement must supply

All current sources are blocked or unclear for a paid product: the F1 timing data behind FastF1 and bronze (formula1.com terms: personal, non-commercial, no extraction), OpenF1 and Jolpica (NC-SA), MultiViewer (no terms, "non-commercial, fair use"), FIA PDFs (terms unread), bacinger (MIT, OSM provenance unknown), OSM (ODbL share-alike on derived databases) and TUMFTM (LGPL).

| Gap | A commercial source must supply |
|---|---|
| Marshal sectors | Per-circuit, per-layout-year marshal-sector boundaries (positions or distances) aligned to the timing feed, with a licence that allows derived, published output |
| Missing races / corners | Corner positions per layout year, or the right to derive them from licensed telemetry (derived corners are only as licensable as the telemetry) |
| 2026 and later | Position (about 4 Hz or faster), car data (speed, brake, throttle), laps with sector times, race control with sector numbers, track status, and a historical archive |
| All | Explicit commercial and redistribution rights for derived per-corner aggregates, attribution terms, no share-alike, rate limits, and coverage of 2018-2025 |

No paid vendor is named because none was verified. The likely route is a data licence from Formula One Management (F1's own data licensing) or a vendor it licenses. Check: commercial use, derived-data publication, back-catalogue years, the marshal-sector map, and sub-licensing.

## 5. Overall dependence

- **Core measurement** (approach gap, segment time, reference): independent of marshal sectors except through `yellow_sector` (at most 0.22% of passes under realistic error). Missing races are a coverage gap (about 1-2% of driver-laps), not a bias in what is measured. The licence is the real dependency: 100% of the data.
- **Replay (WC-07):** needs telemetry per race. 2018-2025 is fine except the 4 races. Its per-sector yellow label is the least reliable thing it would show.
- **Can ignore for a personal prototype:** marshal-sector approximation (label it), 2018 AUS/BHR, 2020 Sakhir/Tuscany (or recover them with derived corners), and the São Paulo fallback.
- **Must fix before any paid release:** the data licence for every season, a licensed marshal-sector map, a licensed corner source (or licensed telemetry to derive it), and a licensed 2026+ feed.

## Verified vs reasoning

- **Verified by running code:** the section 1 sensitivity and inference counts; the sector-count comparison; the section 2 counts, the derived-corner validation and builds, and the São Paulo frame check.
- **Reasoning only:** the 2026 pipeline and replay behaviour; that timing sectors nest marshal sectors; all licence conclusions (taken from the 2026-10-23 sources note; no terms were re-read today); the vendor route.
