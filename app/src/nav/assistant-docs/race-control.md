---
title: "When did the race stop being a race?"
sidebarTitle: "Race Control Timeline"
description: "Every safety car, VSC and red flag in a race, on the lap it happened and for as long as it lasted plus an honest account of why there is no per-circuit safety-car probability anywhere on the page."
---

<!--
AI-facing source for the assistant's explain_page summary of docs/app/race-control.mdx.
The human page is longer than the 800-token summary budget, so pageSummaries.mjs reads this
file instead. Every Warning/Note here is copied verbatim from the human page, and every figure
must appear there; assistantTools.test.ts fails on drift. Edit the human page first, then this.
-->

## What it shows

Lap-axis blocks: Safety Car (pit stop costs roughly half of normal), VSC, Red Flag (tyres can often be changed for free).

## Reading the signal correctly

<Warning>
  **There is no per-circuit safety-car probability on this page, and that is the finding, not an omission.**

  The warehouse holds 173 races (2018–2025) at 36 circuits: about 4.8 races per circuit. A one-way variance decomposition of the per-race caution rate by circuit puts the between-circuit share at **0.000** for any caution and 0.015 for safety car (permutation p = 0.37, indistinguishable from zero).

  A per-circuit rate at 4.8 races carries a standard error of **20 points**. Thirty-six circuits of pure noise would spread about **93 points**. The observed spread is **100 points**: ten circuits sit at 100% and one at 0%. Baku City Circuit had a caution in 7 of 7 races; printing "Baku: 100% chance of a caution" would be reporting seven coin flips as a forecast.
</Warning>

Only pooled rates, with Wilson 95% CI. Any caution 128/173 races (74.0%, CI 67.0-80.0); safety car 98/173 (56.6%, CI 49.2-63.8); virtual safety car 74/173 (42.8%, CI 35.6-50.2); red flag 19/173 (11.0%, CI 7.1-16.5). 9.03% of race laps 2018-2025 were under a caution (n = 10,373 race laps). Races with a caution: 90.5% in 2018, 58.3% in 2024, 75.0% in 2025.

### The per-circuit strip, and what it actually is

Raw per-circuit rate: 0.000 to 0.100 onsets per racing lap; noise, never read. Shrunk rate (`any_hazard_per_lap_shrunk`): 0.017 to 0.033 per racing lap. Circuit weight `L / (L + 600)` (L = prior racing laps at that circuit) averages 0.202 over 152 circuit-season rows (2019-2025), max 0.452. Roughly four fifths of the value shown is the all-circuits pooled rate wearing a circuit's name.

### Why 2018 is blank

The hazard is season-lagged, so all 21 rows for 2018 are null: **not measurable**, never a measured zero. Fifteen later debut rows are null raw but carry a shrunk rate.

### How a "window" is counted

Contiguous caution laps merge: 129 safety-car windows from 137 logged onsets (2018-2025), exact in 88 of the 98 races with safety-car laps. Accurate on which laps were neutralised; a slight undercount of how many times race control acted.

## Data source

<Note>
  `fct_lap_residuals` carries the same three column names `is_safety_car_lap`, `is_vsc_lap`, `is_red_flag_lap` and they are `FALSE` on every one of its rows, because that mart is built from green racing laps only. It is not a caution source, and any query filtering on those columns there is performing a no-op.
</Note>
