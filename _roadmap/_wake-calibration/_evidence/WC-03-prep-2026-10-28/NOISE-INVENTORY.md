# WC-03 noise inventory (2026-10-28, Opus lead session, delegated; DRAFT)

**What this is.** A list of the known noise sources in the pass table and the bronze inputs: how each is handled today, whether that handling is right, and what would change. Every count comes from the registered pass table (pass "d", `_artifacts/WC-01-pass-table-d/`, hash-verified) or from committed evidence. The counts read **structural columns only** (decision record L2): no segment time, loss, reference time or speed was read, no pass was classified, no gate was run, and nothing was fitted. Sources: `noise_summary.csv`, `following_by_season.csv`, `fit_eligible_pre_trim_by_bin.csv`, `fit_population_flags.csv` and `coverage_per_team.csv` in this folder, plus the WC-01 and WC-02 evidence.

"Fit population" below means the main-era (2022-2024) passes eligible for the §6 curve fit **before** the ±2 s loss trim: **77,575 passes from 66 races**. The older era (2018-2020) has 72,799 passes from 53 races.

| # | Noise source | Size | Handled today | Right? | Change proposed |
|---|---|---|---|---|---|
| 1 | Neutralised laps (SC, VSC, red) | 204,894 passes excluded | `neutralised` | Yes | None |
| 2 | Sector yellows | 14,253 excluded | `yellow_sector`, sector k and k+1, whole lap (DD-WC4/5/7) | Yes, within the marshal-sector limit (#3) | None |
| 3 | Marshal sectors approximated by even spacing (bronze has no sector positions) | About 7,700 kept passes sit one sector outside the k/k+1 band on a yellow lap (pass-b measure: 55,842 released under k/k+1 against 48,180 under a k−1..k+2 band), 0.35 % of kept | Even spacing; re-ingest deferred (DD-WC8) | Acceptable: small, and flat-now shares the exposure (§14) | None for this run. Re-ingest of marshal sectors stays the real fix (DD-WC8). |
| 4 | Restarts (2 laps after SC, VSC, red) | 110,387 excluded | `restart`; VSC endings count as restarts | Conservative: loses data, adds no bias | None |
| 5 | Pit laps, own or the car ahead's | 127,377 + 104,345 excluded | `pit_lap`, `pit_lap_leader` | Yes | None |
| 6 | Wet laps | 157,490 excluded. Four whole races have **no fit pass**: 2022 Japan, 2024 São Paulo (main); 2019 Germany, 2020 Turkey (older) | `wet` | The exclusion is right. **The run's handling of these races is not** (#14) | Draft amendment **A5** |
| 7 | Track-limits laps (own) | 20,312 excluded; none recorded in 2018 and few in 2019 (282) | `track_limits` | Yes; uneven by season, older era only | None |
| 8 | Car ahead on a track-limits lap | 872 fit passes (1.1 %) | Flag only (owner ruling, WC-01 c(b)) | Acceptable at this size | None |
| 9 | Off-track samples | 0 after higher reasons | `off_track` never fires; excursions are caught only through deleted laps | Known limit (WC-01 item 14) | None |
| 10 | Car ahead is a lapped car | 11,431 fit passes (14.7 %; older 23.4 %) | Kept (C2) | Registered; real traffic, often "held up" | None. Visible in the held-up / dirty-air split. |
| 11 | Car ahead is a lap up (the follower has just been lapped) | 5,042 fit passes (6.5 %; older 9.8 %) | Kept unless yielding; racecraft catches the pass itself (leader change within 3 corners) | Acceptable: physically a real wake | None |
| 12 | Blue flags (yielding) | 27,204 following braking passes | Out of the fit; their laps out of the contest (C2) | Yes | None |
| 13 | Gap noise (~0.05 s; WC-02) | Bin 0 (0-0.3 s) holds 2,258 fit passes (2.9 %). Every following pass has all 26 gap samples. | Disclosed; flattens the closest bin (§14) | Yes; the curve is non-increasing, so smear shows up as a flatter bin 0 | None |
| 14 | **Races in the fit seasons with no fit pass, or with laps but no pass table** | Main: 2 of 68 built races. Older: 2 of 55 built races, plus 4 races with bronze laps but no pass table (2018 Australia and Bahrain: no telemetry; 2020 Sakhir and Tuscany: no corner positions) | **Not handled**: the plan is built from the races that contribute fit passes; A4 4b stops the run if θ_now's panel races differ, and that happens after G3 is written | **No.** It would end the one registered run with no verdict | **A5 (draft)**: the union fit-race list. The CLI now refuses before reading the warehouse while A5 is undecided. |
| 15 | 2024 Las Vegas: inconsistent timing feed (WC-02) | 15,264 passes; 825 fit passes (1.06 %) | Kept (DD-WC11); a §12b sensitivity run without it | Yes | None; the sensitivity run is now built |
| 16 | The 34 races flagged by the first timing check | 11,761 fit passes (15.2 %) | Kept: the flag was a line-locator artefact (WC-02 salvage, 168 of 169 races within 0.1 s) | Yes | None |
| 17 | Layout-flagged races (corner set from another layout or season) | 6 main races, 6,137 fit passes (7.9 %); none in the older fit | Flag only (DD-WC6) | Acceptable, but the largest flag share in the fit | Optional: a report-only §12b run without layout-flagged races. Needs its own draft amendment; **not drafted**, owner's call. |
| 18 | Lap 1 and each driver's last lap (the builder needs L−1 and L+1) | 3,325 laps from lap 2 not buildable: 3,315 last laps, 10 mid-race gaps; 464 in 2025 | A3: `lap_1`, `last_lap`, `no_pass_rows` counted at §8a step 1 | Yes | None |
| 19 | 2018 and 2020 gaps | 4 races skipped; 1,857 laps in 2018 with no telemetry (`no_pass_rows`) | Older era only; reported, never the verdict | Yes, except #14 | A5 covers the run side |
| 20 | Stint or compound unknown | 5,237 kept passes with no stint (no reference possible); 8,801 with compound `UNKNOWN` (referenced within the same stint, so the tyre set is the same) | Builder rule | Yes | None |
| 21 | **Measured-reference coverage** ("49 %") | 49 % of **kept** passes have a measured reference, but only **22.2 % of following braking passes** do (216,280 of 973,408). By season: 2022 20.9 %, 2023 18.2 %, 2024 22.2 %, **2025 17.0 %**. Main cause: 466,442 kept passes have a car within 1 s behind, so they cannot donate a reference. | The curve is fitted only where a reference exists; the contest scores every lap; W2 on train laps; §8d states the limit | The handling is right. The **headline is misleading**: the relevant figure is 22 %, not 49 % | None to the method. Report 22 % (and 17 % for 2025) beside the curve. Per-team shares are in `coverage_per_team.csv`. |
| 22 | Neighbouring corners overlap (47 % of braking segments) | — | §7 "first stretch owns it" in lap totals; cluster bootstrap in the fit | Yes | None |
| 23 | Baseline drift inside the ±4-lap window | — | §12b ±2 and ±6 runs | Yes | None; now built |

## Integrity pre-flight (L7)

All pass on the real pass table:
- the race calendar covers all 169 races;
- one season and one circuit per race;
- (race, driver, lap, corner) rows are unique;
- the estimator's reference-donor identity holds on all 1,071,162 measured rows.

The only failure is #14.

## Thinnest fit cells (main era, before the trim; not G7)

Fast corners, 0-0.3 s: 321 passes, 51 races, 53 corners. Every main-era class and bin cell has at least 321 passes from at least 51 races. This is not G7: G7 is on the trimmed set and on each of the 1,000 draws, and it was not computed.

## What is not verified here

- Whether the yardstick panel actually holds laps of the races in #14. That needs the panel, which is G3 check 2, so it was not run. A5 makes the answer irrelevant.
- Anything about loss, curve shape or the contest.
