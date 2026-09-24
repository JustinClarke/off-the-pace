# WI-14 — Rating-chain truth pass: sign conventions and a symmetric statistic

**Group:** 06 publication · **Depends on:** each item consumes the one before it (F40 → F44 → F45);
F28 and F50 are independent sign-convention bugs on different pages, fix in any order.
**Blocker:** a ruling — P20-vs-P20 or median-vs-median for the equal-car rating (F40).

**Findings folded in:** F28 (Med-High, fan), F40 (Medium, fan), F44 (Medium→High for this page,
fan), F45 (Low-Med, fan), F46 (Low, fan, split severity), **F50** (new, High, fan).

**Reverification:** all CONFIRMED-AS-STATED. This cluster is where the reverification pass found its
single most consequential new item — **F50**, an independent sign inversion on a page none of the
three audit rounds caught, despite round 1 explicitly saying it read that page.

---

## F50 (new) — Synthetic Teammate's own sign inversion (read this one first)

Full write-up: `NEW-FINDINGS.md`. `int_synthetic_teammate.sql:131-133` defines
`driver_skill_proxy_s = teammate_pace_adjusted_s − ego_wc_lap_time_s` — **positive = ego faster**,
confirmed against the file's own header and matching `fct_driver_skill_features.sql:14`'s
convention. But `synthetic-teammate/methodology.tsx:14`, `page.tsx:36,69`, and `transform.ts:21` all
apply the **opposite** convention — negative is displayed as "the driver is faster," colored green,
and labeled `verdict: 'ahead'`. Confirmed live: of 166 eligible driver-seasons, 65 "ahead" + 60
"behind" verdicts are backwards. This is distinct from F16 (display-only, arbitrary label) and F28
(a different page, different root cause) — it inverts the **primary verdict** of nearly every row.

## F28 — Quali vs Race mixes two sign conventions

`quali-vs-race-skill/queries.ts:34-36` computes `delta_s = quali_skill_session_avg_s (field-relative,
negative=faster) − driver_skill_proxy_mean_s (teammate-relative, positive=faster)` —
`fct_driver_skill_features.sql:12-15` documents the opposite conventions explicitly in its own header.
`methodology.tsx:20` claims one convention for both. Reverification measured the practical damage:
Spearman agreement against a sign-consistent comparator is **near zero for four of eight seasons**
(2019, 2020, 2021, 2025), and the delta's sign differs for 17-23 of ~20 drivers per season — the
page's headline claim is close to arbitrary in most seasons, not just technically mislabeled.
**Fix:** the warehouse already computes the correct field-relative delta
(`int_qualifying_decomposed.quali_vs_race_skill_delta_s`) — swap the query to read it, and aggregate
at driver-race grain instead of push-lap-weighted.

## F40 — the equal-car rating compares a ceiling with a median

`int_driver_race_skill_loro.sql:218`: `driver_skill_loro_s = P20(own) − mean(teammates' medians)`.
Independently re-derived the exact decomposition: a spread term (P20(own) − median(own), mean
**−0.916s**) plus a teammate term (median(own) − median(teammate), mean **0.000**) — the entire
−0.92s level is the spread term, and the rating correlates 0.43 with it, so a driver whose laps
scatter more is rated faster, independent of actual pace. A teammate-relative rating should sum to
~0 across a pair; it doesn't — mean pair sum **−1.83s**, and **1,252 of 1,579 (79%)** two-driver
cars show *both* teammates rated faster than each other. This feeds `int_driver_season_ratings`,
`int_driver_circuit_affinity` (F44), and the Era Translator/Timeline pages.

**Ruling needed:** compare like with like — either P20-vs-P20 (keep the "kill cruise drag" ceiling
logic the header describes, applied symmetrically) or median-vs-median (simpler, loses the
ceiling logic). Recommend **P20-vs-P20**, since it's the smaller conceptual change (the header
already argues for using a ceiling, just not consistently) and preserves the stated intent.

## F44 — Driver Circuit Affinity paints every cell green

`int_driver_circuit_affinity.sql` shrinks a **level** (`raw_affinity_s = driver_skill_loro_s`,
inheriting F40's −0.92s near-universal bias) toward the driver's own mean (also a level, same bias) —
never subtracting the two. The page then colors `cell.value < 0` green.
`methodology.tsx:14-15` explicitly claims "negative = faster than driver average at that circuit."
Confirmed live: **667 of 667** page cells (n_obs ≥ 2) are negative — every driver's row is fully
green. Relative to each driver's own mean, only 47.8% would be green, and just 1 of 32 drivers would
show an all-green row. **Reverification note: for this specific page, "Medium(fan)" understates it —
the heatmap currently carries zero color information as shipped.** `global_driver_mean_s` is already
computed in the model's own `driver_global` CTE, so exposing `shrunk_affinity_s −
global_driver_mean_s` instead of the raw level is a small addition, not a redesign. Note: fixing F40
alone shrinks this page's level bias but doesn't fix it — a driver who genuinely beats his teammates
everywhere would still paint all green under the current "draw the level" logic, since F44 is a
distinct display bug on top of F40's input bias.

## F45 — the era offset reverses the gap it claims to remove

`int_era_normalized_driver_rating.sql`'s bridge-driver offset (t = −1.5, no significance/robustness
gate before it's applied to every pre-2022 driver-season with n≥3) is confirmed by direct code read
to have no significance check at all. The rating it adjusts is teammate-relative (F40), and a car-era
shift should move both teammates alike — so the un-adjusted field-mean gap across the 2022 boundary
is the right reference. It's **−0.044s** before adjustment and **+0.071s** after — the offset turns a
small gap into a larger one of the *opposite sign*. Magnitude not independently rerun this pass
(would need a DB query beyond budget) but the mechanism (no significance gate) is confirmed
sufficient to explain it.

## F46 — Hidden Performance: a false identity, and a rank key nobody validates

Two distinct defects the original report blends into one "Low(fan)" tag — reverification splits
them:

- **(a) Text, Low.** `methodology.tsx:21-22` claims "self-scenario predicted finish = actual finish,
  any deviation signals a data issue." But `fct_ghost_race_finish.sql` re-ranks the **whole**
  scenario (every driver transplanted into the host car), so even the self-scenario's rank depends on
  all 19 other transplants, not just the focal driver — the stated identity has no basis in the SQL.
  Confirmed: fails on 93.4% of the 2,921 self rows the page shows.
- **(b) Rank key, Medium.** The file's own header names `predicted_mean_residual_pace_s` as "the
  ranking key, for `assert_ghost_self_scenario_rank`" — but `predicted_finish_position` actually
  ranks on `predicted_mean_lap_s` instead (fuel-inclusive), a genuine internal inconsistency in the
  SQL, not an app-layer error. Confirmed: 1,299 displayed page rows move ≥3 places between the two
  keys — a concrete numeric error, not just prose.

## Method

1. **F50 first** (independent, no dependencies) — flip the three sign-convention sites, rewrite the
   methodology sentence, add a fixture-based sign regression test.
2. **F28** (independent) — swap to the warehouse's own correct column, fix the aggregation grain.
3. **F40** — apply the P20-vs-P20 ruling; re-check the "field average" wording on every page that
   shows this rating (at least 4: Era Translator, Era Ratings Timeline, Hidden Performance's season
   rating, Driver Circuit Affinity).
4. **F44** — expose `shrunk_affinity_s − global_driver_mean_s` instead of the raw level; correct
   "shrunk toward neutral" → "shrunk toward the driver's own mean" in the methodology text; correct
   the stale "2018–2024" season range.
5. **F45** — drop the offset (set `era_adjusted_rating = shrunk_residual_s`) unless a properly gated
   (significance/robustness-checked) estimate is built instead.
6. **F46** — swap `predicted_finish_position`'s `ORDER BY` to the declared ranking key
   (`predicted_mean_residual_pace_s`); rewrite the self-scenario identity sentence to describe what
   actually holds (per-lap pace, not finish position).

## Acceptance

- Every sign convention on every page matches its source column's documented meaning, verified by a
  fixture test, not just a manual read.
- The equal-car rating is symmetric across teammate pairs (mean pair sum ≈ 0, not −1.83s).
- Driver Circuit Affinity's color signal actually varies (not ~100% one color).
- The era offset doesn't invert the gap it's meant to remove.
- Hidden Performance ranks on its own declared key, and its text matches what the SQL computes.

## Tests to add

T22a (F28), T30 (F40, antisymmetry), T34 (F44, drawn-as-deviation + sign text), T35 (F45, offset
doesn't invert the gap), T36 (F46, declared rank key), new (F50, sign fixture test).

## Definition of done

`verify_findings.py`'s F28, F40, F44, F45, F46 checks flip to CLEARED; F50's new test is wired in and
would fail against the pre-fix `transform.ts`/`page.tsx`.
