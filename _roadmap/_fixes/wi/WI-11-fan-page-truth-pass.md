# WI-11 — Fan-page truth pass (general)

**Group:** 06 publication · **Depends on:** F27 needs `WI-05`'s wet-flag fix (F26) landed first.
**Blocker:** none otherwise.

**Findings folded in:** F15, F16, F27, F29, F30, F36, F37. (F28, F40, F44-F46, F50 are the
sign-convention/rating chain — see `WI-14`. F31 is pit-strategy — see `WI-13`.)

**Reverification context.** This user's stated product framing (2026-09-20 decision, `_improvements`
project memory) is "win = fan value, not publication" — these pages are the product, not a
footnote. Several severities below are called **understated** on that basis, not just on raw
technical grounds: a page stating something its SQL doesn't compute is a trust problem for the
product whether or not it moves an ML metric.

---

## F15 — Counterfactual "Actual Pts" isn't the official result — **understated, call it Medium(fan)**

`counterfactual-championship/queries.ts:73` builds `actual_points` from FastF1 finishes mapped
through a hardcoded points table; `ChampionshipChart.tsx:40` labels it "Actual Pts";
`methodology.tsx:28` calls it "real-world result." No Jolpica/official source is read anywhere in the
query. Verified: equal to Jolpica's official final standings for 20/20 drivers in 2018, but only
14/20 in 2019, max gap 54 points (2023) — a flagship, complex page, materially wrong in recent
seasons, not a legacy-data footnote. **The original report gives no explicit fix for F15** — a real
gap in the audit's own deliverable.

**Fix:** the durable fix (ingest per-round official standings) is bigger than a text edit; ship the
cheap interim fix first — relabel "Actual Pts" as "Actual Pts (FastF1 result)" and drop "real-world
result" from the methodology text — while the durable fix is scoped separately.

## F16 — `ANY_VALUE` picks an arbitrary label while the aggregate is correct

`synthetic-teammate/queries.ts:28-29` and `mart_corner_skill_driver.sql:234` both use
`ANY_VALUE(teammate_driver_id)`/`ANY_VALUE(constructor_id)` for display, while the underlying
`avg_skill_proxy_s` correctly averages across all teammates. Display-only, agree Low. **Fix:** sound
and minimal — `STRING_AGG(DISTINCT …)` or a count badge instead of a single arbitrary value.

## F27 — Wet-Race Specialist measures skill on zero wet laps — **understated**

`fct_driver_skill_features.sql:140` filters `is_rain_lap = FALSE` into the very aggregate
(`driver_skill_proxy_mean_s`) that `wet-race-specialist/queries.ts:26-29` then slices by
`race_wet_flag`. Confirmed: of 17 wet-flagged races, rain laps reaching the page = **0**.
`methodology.tsx:12` calls it "relative to the field model" when the column is teammate-relative per
its own header. This isn't a partial mismatch — the page's entire premise (wet-condition skill) is a
null result dressed as a finding. **Fix:** depends on `WI-05`'s F26 (rain-flag accuracy) landing
first, and needs a genuinely new query path since `is_rain_lap = FALSE` is baked into the shared
clean-lap filter feeding `fct_driver_skill_features` — not a one-line change.

## F29 — Blind-Test Scoreboard compares the wrong horizon — **understated, most consequential of this batch**

`blind-test-scoreboard/queries.ts:74` joins the model's 5-lap cumulative prediction against
`next_lap_degradation_jump_s` (1-lap, undetrended, legacy target) as "actual." Confirmed directly
against `ml/src/schema.py:283` and `predict.py:94`: the model is trained and scored on
`next_5_lap_cumulative_jump_s`. Result: the page shows 90.8% p10-p90 coverage against the wrong
actual; the true target shows 79.4% — much closer to the intended 80%. **This is the model's own
trust/credibility page — exactly the "argument-settling stats" surface the product framing
prioritizes — and it structurally flatters the model.** Should be Medium-High(fan), not folded into
round 2's unranked low-severity block. **Fix:** sound and minimal per the original report — swap the
actual column for `next_5_lap_cumulative_jump_s` (read from `S.DEGRADATION_TARGET` rather than
hard-coded), plus update the methodology text's "next-lap" wording, which is internally consistent
with the buggy query today and needs to change too.

## F30 — Tyre-Cliff Survival's KM validation is circular

`tyre-cliff-survival/queries.ts:119` defines `cliffed = BOOL_OR(cliff_onset_passed)`, and
`cliff_onset_passed` is itself `age > seed onset` — so "the KM curve crosses 0.5 near the model line"
is guaranteed by construction, not an independent check. Agree Med-Low(fan) — only the *validation
claim* is broken; the KM curve and scatter overlay still show real data. **Fix:** the report's
proposal (event = the label's *observed* first crossing) is directionally right but bigger than a
query tweak — it needs a new observed-jump-crossing detector, not a small edit.

## F36 — Waterfall "observed delta" has a phantom third term

`int_lap_residual_decomposed.sql:309-315` confirms `pace_delta_s = total_explained_s +
driver_skill_residual_s` exactly (an identity, not an approximation) — `track_unexplained_s` is
explicitly informational and outside it (the file's own line 19-20 comment says so). Yet the same
file's header comment at `:306-308` claims a 3-term identity *including* `track_unexplained_s`, and
`lap-waterfall/queries.ts:59-61` / `race-lost/queries.ts:56-58` both implement that false 3-term
sum. **The bug originates in the model's own header comment, not just app-layer misreading.** Small
in magnitude (mean 0.02s/driver-race, max 1.36s) — agree Low. **Fix:** trivial — drop the
`+ track_unexplained_s` term in both query files, and correct the SQL header comment that caused the
app-layer error in the first place.

## F37 — Home page stats are false, and worse than described

`export_app_data.py`'s `build_stats_block` does `SELECT COUNT(*) FROM dim_circuits` (no
raced-venue filter — 44 rows, only 32 are actual venues raced 2018-2025) and counts `*_v1.onnx` files
for "5/5 models beat baseline" with an `or 5` fallback. **Independently verified worse than
described:** checked `ml/models/model_card.json` directly — 4 of 5 models show
`beats_baseline_significant: True`, one `False`. So "5/5" is false against the project's own model
card, not just against the file-counting method the audit describes. This is the single
highest-traffic page (hero stats, first impression) and both numbers are provably false against
in-tree ground truth. **Should be Medium(fan)**, not folded into round 2's unranked low-severity
block. **Fix:** filter `dim_circuits` to raced events; sum `model_card.json`'s
`beats_baseline_significant` flags instead of globbing filenames.

## Method

Each item is independent — work in any order, except F27 waits on `WI-05`/F26.

## Acceptance

Every page's displayed claim (label, headline stat, or methodology sentence) matches what its own
SQL actually computes, verified by reading both side by side.

## Tests to add

T22 (F29/F30 family — page-level contract tests), plus new lightweight assertions per page for F15
(label matches source), F37 (home-page stats match `dim_circuits`'s raced-venue filter and
`model_card.json`'s own flags).

## Definition of done

`verify_findings.py`'s F15, F16, F27, F29, F30, F36, F37 checks flip to CLEARED; each page's
methodology text is re-read against its query one more time after the fix, since these are exactly
the kind of defect that recurs when text and query drift independently.
