# Neutral laps (SC / VSC): what the data supports — 2026-10-24

Read-only analysis. No model, label, app, ML or board file changed. Source: bronze parquet only
(`data/bronze/laps/*/*/*.parquet`, race depth, and `data/bronze/track_status/`), read with the repo
`.venv` duckdb 1.5.6. `data/dev.duckdb` was not used (stale until CO-17). Scripts are in session
scratch (`.../scratchpad/neutral/{base,loss2,pits,gaps,restart}.py`) and may be gone; the definitions
below are enough to rebuild them.

## 1. How track status is encoded

- **Lap level (`stg_laps.track_status`, bronze `TrackStatus`)** is the *flag state*, not an on/off
  bit: a string of every status code in force during the lap, in order (e.g. `41` = SC then clear,
  `671` = VSC, VSC ending, clear). Codes: 1 clear, 2 yellow, 4 SC, 5 red, 6 VSC, 7 VSC ending.
  `stg_laps` tests digit presence: `is_safety_car_lap` = contains 4, `is_vsc_lap` = contains 6/7,
  `is_red_flag_lap` = contains 5. `is_valid_lap` drops any lap containing 4/5/6/7. All neutral laps
  are also `IsAccurate = false` in bronze.
- **Event level (`stg_track_status`)** is one row per status change with `status_duration_s`.
- So a lap flag cannot separate "a whole lap behind the SC" from "SC came out in the last sector".
  Below, **full** = the lap's string is only 4 (SC) or only 6/7 (VSC); the rest are **partial**.

## 2. Counts per season

173 races (2018–2025). "Race-laps" = (race, lap) where any car's lap carries the code.
"Onsets" = deployments in the event log.

| Season | Races | Races SC | Races VSC | Races red | Races any | SC race-laps | VSC race-laps | SC onsets | VSC onsets | Red onsets | SC driver-laps (full) | VSC driver-laps (full) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2018 | 21 | 13 | 12 | 0 | 19 | 79 | 54 | 15 | 15 | 0 | 1,270 (731) | 578 (76) |
| 2019 | 21 | 9 | 7 | 0 | 14 | 81 | 27 | 16 | 9 | 0 | 1,229 (687) | 307 (22) |
| 2020 | 17 | 12 | 6 | 3 | 13 | 115 | 23 | 20 | 7 | 4 | 1,611 (957) | 222 (12) |
| 2021 | 22 | 13 | 7 | 6 | 16 | 64 | 37 | 15 | 12 | 8 | 1,040 (487) | 438 (82) |
| 2022 | 22 | 16 | 15 | 3 | 20 | 104 | 68 | 21 | 22 | 4 | 1,629 (917) | 799 (113) |
| 2023 | 22 | 13 | 10 | 4 | 14 | 66 | 24 | 18 | 10 | 7 | 1,126 (469) | 346 (22) |
| 2024 | 24 | 9 | 8 | 3 | 14 | 63 | 23 | 14 | 9 | 3 | 1,022 (526) | 291 (43) |
| 2025 | 24 | 13 | 9 | 0 | 18 | 93 | 43 | 18 | 13 | 1 | 1,566 (929) | 554 (93) |
| **All** | **173** | **98** | **74** | **19** | **128** | **665** | **299** | **137** | **97** | **27** | **10,493 (5,703)** | **3,535 (463)** |

- Neutral driver-laps are 4.9–9.9% of laps per season. 128 of 173 races (74%) have at least one
  neutral lap. Race counts by lap flag and by event log agree (SC 98, VSC 74).
- **VSC laps are mostly partial**: only 463 of 3,535 VSC driver-laps are fully under VSC. VSC
  periods are short.
- 206 contiguous neutral windows by race-lap; 129 contain SC (matches the race-control page's 129).
- Pit stops (in-lap + out-lap pair), by any neutral code on either lap: green 4,068; SC 1,011;
  VSC 257; red 365. VSC stops per season 20–56, in 4–12 races.

## 3. Time loss per neutral lap vs the same car's green laps

Reference = median of the same driver's clean green laps (status `1`, not pit, accurate, not
deleted, lap > 1) within ±5 laps, needing ≥3. Lap time falls back to the session-time difference
when `LapTime` is NULL (21% of SC laps have no `LapTime`; 2,386 of 2,444 recover this way;
where both exist they agree exactly). Usable: SC 5,859 of 7,602 non-pit laps, VSC 2,438 of 2,632.
Long SCs and SCs near the flag lose the reference most often, so they are under-represented.

| Season | SC laps n | SC median loss (IQR) | SC ratio | VSC laps n | VSC median loss (IQR) | VSC ratio |
|---|---|---|---|---|---|---|
| 2018 | 636 | +45.6 s (36.1–51.1) | 1.47 | 396 | +17.0 s (9.5–24.9) | 1.20 |
| 2019 | 826 | +36.1 s (20.8–49.0) | 1.40 | 194 | +12.7 s (5.8–21.4) | 1.13 |
| 2020 | 841 | +36.8 s (24.5–50.5) | 1.46 | 140 | +11.1 s (6.7–15.2) | 1.13 |
| 2021 | 517 | +41.8 s (29.5–55.9) | 1.48 | 362 | +15.1 s (7.7–22.2) | 1.17 |
| 2022 | 1,042 | +39.6 s (26.9–52.4) | 1.44 | 534 | +18.8 s (10.0–26.4) | 1.20 |
| 2023 | 654 | +45.6 s (35.7–55.1) | 1.53 | 205 | +15.0 s (8.4–21.3) | 1.18 |
| 2024 | 547 | +39.9 s (24.1–48.1) | 1.44 | 197 | +16.6 s (8.2–29.8) | 1.21 |
| 2025 | 792 | +40.1 s (27.6–49.4) | 1.46 | 408 | +22.2 s (11.8–28.5) | 1.24 |
| **All** | 5,855 (91 races) | **+40.6 s (27.0–51.0)** | **1.46** | 2,436 (72 races) | **+16.4 s (8.7–24.9)** | **1.19** |

Full laps only: SC full +42.5 s (31.4–52.0), ratio 1.49, 3,280 laps / 86 races. VSC full
+30.8 s (25.8–35.1), ratio 1.35, 326 laps / 36 races.

**Is it consistent enough to be a number?**
- **VSC, full laps: yes, as a ratio.** Per-race median ratio p10–p90 = 1.28–1.41 (14 races with
  ≥10 full VSC laps); within-race IQR of the ratio 0.03. That is what a delta-time rule should
  produce. In seconds it varies with lap length, so quote the ratio.
- **VSC, all laps: no.** The 16 s median is a mix of partial laps; it describes how long VSCs
  happened to last within a lap, not what a VSC lap costs.
- **SC: only as a broad range.** Per-race median ratio p10–p90 = 1.31–1.59 (89 races), seconds
  27.9–59.8 s; within-race IQR of the ratio 0.13; on one full-SC lap the spread across cars is
  sd 0.10 in ratio (about ±4–5 s). The loss depends on where the car is relative to the SC and
  the queue, so a per-car "SC lap cost" is mostly about queue position, not the car.
- Per-season medians move (SC 36–46 s, VSC 11–22 s) with circuit mix and deployment length; the
  season-to-season differences are not a trend anyone should report.

## 4. Pit stops under neutral vs green

Relative pit loss = (in-lap + out-lap) minus the median in+out of cars that did not pit on either
lap, same race, same laps, needing ≥5 such cars. "Under SC/VSC" here = the in-lap ends and the
out-lap starts under that code (last/first character of the status string; assumes the string is
chronological).

- Green stops: median relative loss 22.6 s (IQR 20.1–25.5), 3,875 stops, 172 races.
- Same-race paired difference (neutral median minus green median, same race):

| Condition | Races | Stops | Median saving | IQR of saving | Range | Share of green loss saved |
|---|---|---|---|---|---|---|
| SC at entry and exit | 66 | 413 | 9.6 s | 2.7–18.6 s | −52.4 to +64.7 s | 0.43 |
| VSC at entry and exit | 48 | 211 | 5.0 s | 1.2–9.0 s | −40.4 to +20.6 s | 0.23 |

- **Selection**: only 413 of 960 SC entry-and-exit stops have ≥5 cars staying out to compare
  against. The SC sample leans toward SCs where few cars pitted.
- VSC clean stops per season: 35, 20, 24, 14, 53, 31, 19, 15 (2018–2025). Per race, a VSC saving
  rests on a median of about 4 stops.
- The race-control page says a five-lap SC is "everyone got a cheap pit stop". The data supports
  that for SC (about 43% off a green stop); a VSC stop is about 23% cheaper, and in a quarter of
  races the VSC saving is ≤1.2 s.

## 5. What an SC does to gaps (the real "cost")

For 74 SC windows (cars that did not pit from the lap before to the lap after; windows starting
after lap 2), gap to the leader at the lap before the SC vs at the last SC lap, 558 car-windows:

| Position before | n | Gap before | Gap at end of SC | Gap closed (p10–p90) |
|---|---|---|---|---|
| P2 | 27 | 5.3 s | 0.7 s | 2.8 s (0.1–14.6) |
| P3–5 | 88 | 13.4 s | 1.7 s | 10.7 s (0.5–33.0) |
| P6–10 | 177 | 27.8 s | 3.6 s | 22.1 s (2.7–61.1) |
| P11+ | 237 | 45.7 s | 5.8 s | 35.6 s (7.3–88.2) |

Every car loses about the same 40 s per SC lap in absolute terms. What differs is how much margin
it gives up or gains. That is a per-race record, not an estimate, and it is the honest version of
"what did the safety car cost each car". P11+ includes lapped cars; 55 of the 129 SC windows drop
out of this cut (pit stops or an early start).

## 6. Restart laps (already handled, confirmed)

Green laps after a neutral window vs the same car's green laps more than 3 laps from any
neutral window (±8 laps):

| Laps after window | After SC: median (IQR) | After VSC only: median (IQR) |
|---|---|---|
| 1 | +1.67 s (0.63–3.00), n 1,559 | −0.20 s, n 1,038 |
| 2 | +0.74 s (0.14–1.61), n 1,819 | −0.13 s, n 968 |
| 3 | +0.28 s | −0.05 s |
| 4 | +0.24 s | −0.03 s |

This matches FD2 (`int_event_corrections`: restart lap and lap after an SC/red restart excluded;
VSC not, because it is unaffected). Laps 3–4 after an SC are still about +0.25 s. That is probably
a bunched field (real dirty air), so it is not a reason to drop more laps. It is a sensitivity
check for DA-03.

## 7. What already exists (so nothing is duplicated)

- **ML**: neutral laps are out of every lap model (`is_valid_lap`); restart laps out (FD2);
  SC/VSC pit ends are censored for stint life (D6, CO-09 `is_stint_life_censored`,
  `stint_end_cause` sc_pit / vsc_pit); `int_sc_hazard_history` is a season-lagged SC/VSC hazard;
  `int_pit_loss_circuit` drops neutral stops from pit loss; `int_pit_strategy_value` discounts pit
  loss by SC chance. CO-04 stops the field-pace smoother at SC/VSC/red boundaries (W43).
- **Dirty air**: `int_lap_air_state` and `int_lap_proximity` zero SC/VSC/red laps; dirty-air-cost
  never charges the lap after a neutral lap; the DA design note (section 1) drops OffTrack, SC,
  VSC, red, local yellow, lap 1 and the 2 laps after a restart.
- **App**: `race-control` (per-race caution timeline from `race_caution_timeline`; pooled SC/VSC
  rates with Wilson intervals; explicit refusal of per-circuit SC chance); `pit-strategy` (Gantt,
  verdicts, SC-discounted pit loss); dirty-air-cost, race-lost, lap-waterfall,
  stint-degradation-timeline all state that neutral laps are excluded. There is no feature for
  SC/VSC pit savings, gap compression, or a neutral-lap explainer.
- `fct_lap_residuals` holds valid laps only, so neutral laps are not in the lap export the
  assistant's query builder (AI-09) and comparison tool (AI-11) read.

## 8. Options assessed

| Option | Value | Cost | Risk | Where |
|---|---|---|---|---|
| (a) Keep out of ML, say nothing | Out of ML is right and done. "Say nothing" is wrong: the assistant will be asked why lap 24 is missing or why a lap chart has a gap | Zero for ML; small for the wording | Silent gaps read as missing data | ML: done. Wording: AI-02 / AI-01 |
| (b1) Neutral time cost as an ML feature or label | Low. The lap models predict tyre-driven pace; SC loss is set by race control and queue position. Already excluded and censored | Retrain plus label version | Leaks race-control noise into a wear model | Do not build |
| (b2) Pit-under-neutral vs green tyre life | Low and confounded. Neutral stops are opportunistic and D6 already censors them; comparing "lives" compares strategy, not tyres | Medium | Selection effect presented as a tyre fact | Do not build; D6 is the answer |
| (b3) Green-lap tyre age (new, not in the brief) | Medium, unproven. 46% of FastF1 stints contain ≥1 SC/VSC lap; 21% have ≥20% of laps neutral, and those laps count as full tyre age with little wear | Feature arm plus CO-18-style retrain; must wait for CD10 | May not beat baseline; FastF1 stint splits inflate the shares (CO-09 re-keys them) | New item, after CO-18 |
| (c1) SC/VSC pit saving, pooled | Good fan value, answers "is a VSC stop as good as an SC stop". Pooled numbers are stable | Small: one export aggregate plus a panel on race-control or pit-strategy | Small per-race samples; selection on SC | New item (race-control / pit-strategy), card via AI-01 |
| (c2) "What the SC did to the gaps", per race | High fan value; a record, not a model | Medium: new lap-grain export with session time for neutral laps | Lapped cars, pit stops in the window, NULL times | New item; extends race-control |
| (c3) Neutral-lap explainer | Medium; makes exclusions in other pages legible. Numbers: full VSC lap ≈1.35× green, SC lap 1.3–1.6× | Small (copy plus 2–3 cards) | Quoting the 16 s all-VSC median | AI-10 explainer, AI-01 cards, AI-02 wording |
| (c4) Stint card with neutral laps marked | Medium; mainly a display fix | Small once (c2)'s export exists | None beyond the export | AI-11 (shade neutral laps in `compare_lap_times`); stint-degradation-timeline |
| (d) Dirty air: exclude or flag neutral laps | Needed, already done in the current models and planned in DA | Zero new; one check | Restart laps 3–4 still +0.25 s | DA-02 tests / DA-03 sensitivity, no new item |
| (e) Eval questions on neutral periods (not in the brief) | Tests the refusals below | Small | None | AI-07 |

## 9. Recommendation (priority order)

1. **Wording and refusals for neutral laps.** AI-02 rows: "neutral laps are excluded from pace
   and tyre numbers" (required wording when a lap is missing), plus the forbidden claims in
   section 10. AI-07: 3–4 questions (why is lap N missing, did the SC hand X the win, per-circuit
   VSC saving, SC vs VSC for one driver) with the hedge or refusal expected. Data: available
   (`race_caution_timeline`). Risk: none. Cost: hours, inside existing items.
2. **AI-11 marks neutral laps.** `compare_lap_times` shades SC/VSC/red laps from
   `race_caution_timeline` and says why laps are absent (`fct_lap_residuals` holds valid laps
   only). Data: available. Risk: a chart without it shows unexplained gaps. Cost: under a day,
   inside AI-11.
3. **Pooled SC/VSC pit saving (new item, small).** One season-pooled table: median saving, IQR,
   races, stops, share of green loss, for SC and VSC, plus the green baseline. Shown pooled only,
   with n, on race-control or pit-strategy, and as one AI-01 card. Data: computable from bronze /
   `stg_laps` today; needs an export aggregate. Risk: selection on SC (43% of SC stops usable),
   small VSC samples. Cost: 1–2 days.
4. **Per-race gap story (new item, medium).** For each SC window, every car's gap to the leader
   before and at the end, with pitters marked. Data: available in `stg_laps` (session time per
   lap) but not exported; needs a new lap-grain export that includes neutral laps. Risk: lapped
   cars and pit stops; must say "gap closed", not "time lost". Cost: 3–5 days.
5. **Neutral-lap explainer (AI-10 content).** Short explainer with the two stable numbers (full
   VSC lap ≈1.35× green, IQR across races 1.28–1.41; SC lap ≈1.5× with a 1.3–1.6 range) and the
   gap table. Cost: about a day after 1.
6. **Later, owner's call: green-lap tyre age feature** as a new ML arm after CO-18 and CD10. Not
   now.

Not recommended: (b1), (b2), per-car "seconds lost to the SC", per-circuit SC/VSC savings.

## 10. Misleading claims to avoid

- **"A VSC stop saves X s, an SC stop Y s" at a circuit, in a season, or for a driver.** VSC
  clean stops are 14–53 per season, about 4 per race; per-race IQR 1.2–9.0 s and some races show a
  negative saving. Only the pooled comparison holds (SC 9.6 s vs VSC 5.0 s, 66 vs 48 races).
- **"The SC cost car X 40 s."** Every car loses roughly the same; the meaningful cost is the gap
  closed, which depends on position, not on the car.
- **"A VSC lap costs 16 s."** That median mixes partial laps. A full VSC lap is ≈1.35× green.
- **"The SC won/lost X the race."** That is a counterfactual this data cannot settle.
- **"Tyres pitted under SC last longer/shorter."** Neutral stops are opportunistic and censored
  (D6); any difference is strategy, not tyres.
- **Per-circuit SC chance** (already refused on race-control; keep the refusal in AI-02).
- **Season trends in SC loss or VSC saving** (2019 vs 2025 etc.): circuit mix and deployment
  length, not a trend.

## 11. Gaps (not verified)

- 2018 has 1,317 laps with empty `TrackStatus` (Chinese 573, German 545, Hungarian 96, Australian
  83, Austrian 20), so 2018 lap-level counts are low; race-level counts still agree with the event
  log. 2020 has 23 such laps.
- 2025: the event log has 1 red onset but no lap carries code 5. Not resolved.
- That the status string is chronological is assumed (used for "SC at entry and exit"), not
  checked against the event log.
- Pit saving is in+out time against cars staying out; it does not model queuing, double stacks,
  or positions lost. The SC sample is selected (needs ≥5 cars staying out).
- Gap compression covers 74 of 129 SC windows; P2 has 27 cases only.
- Stint shares use FastF1 stints, not CO-09's re-keyed tyre runs (SC drive-throughs split stints,
  which inflates the neutral share).
- Nothing checked against the CO-17 rebuild or the exported CDN tables; bronze only.
- Yellow-flag laps (code 2: 1,047–1,780 per season) not analysed; they stay in `is_valid_lap`.
- Red-flag laps (426 driver-laps) not analysed for loss; their pit stops (365) are free tyre
  changes and excluded from section 4.
