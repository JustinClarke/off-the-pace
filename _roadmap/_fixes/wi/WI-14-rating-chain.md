# WI-14 — Rating-chain truth pass: sign conventions and a symmetric statistic

**Group:** 06 publication · **Depends on:** each item consumes the one before it (F40 → F44 → F45);
F28 and F50 are independent sign-convention bugs on different pages, fix in any order.
**Blocker:** a ruling — P20-vs-P20 or median-vs-median for the equal-car rating (F40; board
decision `FD5`).

**Executed as two board items**, so the unblocked half doesn't wait on the ruling: `WI-14a` = F50,
F28, F46 (F46's fixes — the rank key and the self-scenario text — read `fct_ghost_race_finish`, not
the F40 rating, so they ride with the independent group) and `WI-14b` = F40 → F44 → F45 (the
chain `FD5` gates).

**Findings folded in:** F28 (Med-High, fan), F40 (Medium, fan), F44 (Medium→High for this page,
fan), F45 (Low-Med, fan), F46 (Low, fan, split severity), **F50** (new, High, fan).

**Reverification:** all CONFIRMED-AS-STATED. This cluster is where the reverification pass found its
single most consequential new item — **F50**, an independent sign inversion on a page none of the
three audit rounds caught, despite round 1 explicitly saying it read that page.

---

## F50 (new) — Synthetic Teammate's own sign inversion (read this one first)

Full write-up: `../reference/new-findings.md`. `int_synthetic_teammate.sql:131-133` defines
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

## FD5 Design Round — 2026-09-28

`FD5` was deferred rather than ruled on 2026-09-24 (`build-log.json`: "needs a design and
experiment round before deciding P20-vs-P20 or median-vs-median"). This section records that
round's diagnosis, the options it turned up, probe results, and a recommendation for the ruling.
It does not itself resolve `FD5` — `WI-14b` stays blocked until the follow-up bootstrap experiment
below is run and a decision is made.

### Root cause diagnosis

Both candidates on the table when `FD5` was first opened — P20-vs-P20 and median-vs-median — trace
back to the same identity. Decompose the P20-vs-median rating F40 flagged:

```
P20(own) − median(teammate) = [median(own) − median(teammate)] + [P20(own) − median(own)]
```

The second bracket is a **spread penalty**: it depends only on a driver's own lap-time
distribution, not on the teammate at all, and its mean is **~−0.74s** — the same mechanism F40
independently re-derived as a **−0.916s** spread term (F40 measured `P20(own) − mean(own)`; the
median split here trims slightly less). Because that penalty attaches to *each* driver
individually rather than to the pair, both teammates absorb it — which is exactly F40's paradox:
**1,252 of 1,579 (79%)** two-driver cars show *both* teammates rated faster than each other.

Squaring up the comparison to P20-vs-P20 fixes the first bracket (both sides now sum to ~0), but
it does not remove the second bracket's dependency on lap-time spread — a driver whose laps
scatter more still gets a ceiling boost relative to a teammate whose laps don't, even though both
sides of the comparison are now nominally "P20." Median-vs-median removes the spread dependency
entirely, at the cost of the "kill cruise drag" ceiling logic the model header describes.

### Options considered

| # | Option | Description | Status |
|---|--------|-------------|--------|
| A | P20 vs P20 | `P20(own) − P20(teammate)` | On the table — WI-14's original F40 recommendation; smallest code change |
| B | Median vs median | `median(own) − median(teammate)` | Simple; already computed as `driver_skill_loro_mean_s` |
| C | Lap-by-lap median | Self-join own and teammate laps on `(race, car, lap_number)`, take the median of the per-lap deltas | New; best scores across every probe metric |
| D | Hodges-Lehmann | Robust location estimator over the paired per-lap deltas | Robust fallback; dominated by C on every probe metric |
| E | Tyre-matched laps only | Restrict C's lap-by-lap join to laps on matching compound | Sensitivity check on C, not a standalone candidate |

### Probe results

Probed against `dev.duckdb`, 1,571 car-races.

| Metric | A: P20 vs P20 | B: median vs median | C: lap-by-lap median |
|---|---|---|---|
| Spread correlation (separate laps) | −0.25 | 0.02 | 0.03 |
| Split-half reliability | 0.59 | 0.65 | 0.75 |
| Quali agreement | 0.63 | 0.66 | 0.74 |

A still correlates meaningfully with lap-time spread (−0.25) — confirming the diagnosis above:
squaring up to P20-vs-P20 narrows the dependency but doesn't zero it. B and C are both close to
spread-independent. C leads on both split-half reliability and quali agreement, and not just
against A — it beats B by a clear margin on both.

C needs one self-join on `(race, car, lap_number)` and covers **1,569 of 1,571 (99.9%)**
car-races; the 2 uncovered cases have no overlapping lap numbers between teammates in that race.

### Recommendation

Don't rule from the probe numbers alone — they're a single point estimate per option, not an
interval. Next step: measure **C vs B** with a bootstrap experiment (~0.5 day) — resample
car-races, and compare confidence intervals on split-half reliability and quali agreement.

**Decision rule:** adopt **C** if its CIs show a clear win over B; otherwise adopt **B** (simpler,
no new join, already exists as `driver_skill_loro_mean_s`). **A** is not carried into the
bootstrap round — the probe already shows it fails to close the spread dependency that motivated
F40's ruling in the first place, so it no longer competes with B or C on the metric that matters.

### Side bug found

4,828 laps (3.3% of the probed sample) have no field pace available and are currently set to
**0** wherever the field-pace join misses — a made-up value, not a missing-data marker. Under
every option above (A/B/C/D/E) these should be **NULL** and dropped from the rating computation,
not zero-filled: a zero lap time pulls any P20/median/paired-delta statistic toward "impossibly
fast," contaminating whichever option is chosen. Recommend fixing this ahead of the `FD5` decision
— it affects the B baseline as much as any candidate replacement, and left in place it would bias
the bootstrap comparison above before it's even run.

## WI-14b execution — 2026-09-28 (FD5 ruled: option C)

**Ruling.** The user ruled `FD5` = **C, lap-by-lap median**, directly from the probe table above;
the C-vs-B bootstrap round recommended there was not run. Method step 3 was adapted accordingly
(C instead of P20-vs-P20). Stage after this pass: MEASURED (the orchestrator re-runs the
definition of done).

**What changed.**

- **F40** — `int_driver_race_skill_loro.driver_skill_loro_s` = `MEDIAN(own lap_time_s − teammate
  lap_time_s)` over clean laps both drivers ran, self-joined on `(race_year, race_id,
  constructor_id, lap_number)`. Built from raw lap times, so it never reads
  `int_field_pace_curve` (fuel and field pace are identical for both drivers on one lap number and
  cancel inside the pair) and the zero-fill side bug above cannot reach it. New column
  `paired_lap_count`. The P20 aggregate is gone; `driver_skill_loro_mean_s` (option B) and
  `driver_skill_field_s` are unchanged. Sign convention now documented as "negative = faster than
  the teammate", not "than field", in the model, `int_driver_season_ratings` and `schema.yml`.
- **F44** — `int_driver_circuit_affinity` exposes `global_driver_mean_s` and
  `affinity_vs_driver_mean_s = shrunk_affinity_s − global_driver_mean_s`; `shrunk_affinity_s`
  stays the level (the shrinkage-bounds and CI tests still hold on it). The page draws the
  deviation, sorts rows by `global_driver_mean_s`, and the text says "shrunk toward the driver's own
  mean" and "2018–2025".
- **F45** — `int_era_normalized_driver_rating.era_adjusted_rating = shrunk_residual_s`, SE = the
  season SE. The bridge-driver shift is still computed and published as diagnostic columns only.
- **Pages** (the "field average" re-check, method step 3): Era Translator (text, badges, colour
  bands moved to `transform.ts` as `ratingClass` and re-scaled from ±1.5–3 s to ±0.1–0.3 s, ★
  tooltip, column header), Era Ratings Timeline (title "Driver Rating Timeline", text, axis label,
  the low-anchor warning and its `low_anchor_sample_flag`/`n_bridge_drivers` plumbing removed,
  cohort hints), Driver Circuit Affinity (query, transform, text, tooltip, legend), Hidden
  Performance (one paragraph saying what the Rating column is). `docs/app/{era-translator,
  era-ratings-timeline,driver-circuit-affinity}.mdx`, `docs/app/families/drivers.mdx` and
  `docs/transform/families/skill.mdx` rewritten to match. `docs/reference/**` is generated and was
  not touched (W8).
- `verify_findings.py` F44 now measures the column the page draws (the old measure read the level,
  which F40 alone re-centres, so it would have cleared with the display bug still in place).

**Acceptance, measured on the rebuilt dev warehouse.**

| Criterion | Before | After |
|---|---|---|
| F40 mean pair sum / both-faster cars (two-driver cars) | −1.487 s / 1,196 (WI-01 label) | **0.0 / 0** over 1,569 pairs; max \|pair sum\| 0.0 |
| F40 correlation with own lap-time spread | 0.43 (audit) | 0.024 |
| F44 share of drawn cells green / all-green rows | 0.997 / — | **0.517 / 1 of 32** (648 cells, n_obs ≥ 2) |
| F45 field-mean gap pre − post, before → after | 0.0266 → 0.0511 s (widened) | **−0.0061 → −0.0061 s** |
| Bridge-driver shift (diagnostic, not applied) | −0.1153 s, t = −1.5 (audit) | −0.0177 s, SE 0.0542, t = −0.33, 20 drivers |

`verify_findings.py F40 F44 F45`: all three **CLEARED**. Season ratings (n ≥ 5 races) now span
−0.39…+0.39 s (5th–95th pct), 48% negative; top season VER 2025 (−0.98 s, 22 races), so
`assert_rating_top_season_well_supported` still passes. 137 of 3,275 driver-races have no rating
(no teammate clean lap on a shared lap number); 128 of the 3,138 rated ones rest on 1–4 paired
laps (no minimum was set, as in the probe).

**Tests.**

- **T30** `transform/tests/assert_teammate_rating_antisymmetric.sql` — per-pair \|sum\| ≤ 1e-9,
  mean pair sum within 0.1 s, vacuity guard.
- **T35** `transform/tests/assert_era_offset_shrinks_gap.sql` — an applied offset needs \|t\| ≥ 2
  and must not widen or invert the field-mean gap. Mutation-checked: re-applying the old offset
  formula fails all three rules.
- **Fixture tests (sign conventions).** `transform/models/intermediate/unit_tests_rating_chain.yml`
  (the repo's first dbt unit tests): F40's paired median on a hand-built race (−0.25 / +0.25, clean
  filter pinned, lone driver NULL) — mutation-checked, a flipped sign fails it; F44's deviation on a
  driver who beats his teammate everywhere.
- **T34** `app/src/features/driver-circuit-affinity/{transform.test.ts,methodology.test.tsx}`,
  `app/src/features/era-translator/{transform.test.ts,methodology.test.tsx}`,
  `app/src/features/era-ratings-timeline/{transform.test.ts,methodology.test.tsx}` — drawn values
  are deviations, colour follows sign on the new scale, and the methodology text states what the
  column means. All 18 new app assertions fail against the HEAD sources.
- Runs: `dbt test` on the chain (79 pass, dev), `dbt build` of the chain on the CI fixtures (84
  pass), app vitest 423 pass, `tsc` clean, `app_docs_audit` pass, `ml/tests/test_features.py` 34
  pass. T22a and T36 belong to WI-14a.

**Left open.**

- **App data not re-exported.** The committed `app/public/data` parquet predates this pass: the
  Driver Circuit Affinity query selects `affinity_vs_driver_mean_s`, which it lacks, and the era
  pages' new text describes numbers the old parquet does not hold. `export_app_data.py --table`
  rewrites `_manifest.json` with that one table only, and a full export is fenced by W25, so it
  was not run.
- **Zero-fill side bug** (above) still feeds `driver_skill_field_s` (Ghost Standings via
  `int_driver_circuit_era_affinity`) and `driver_skill_loro_mean_s`. Commented in the model; not
  fixed here.
- **Peripheral labels** still say "era-adjusted": `app/src/nav/seo.ts`, `nav/pillars.ts`,
  `routes/home/tileViz.tsx`, `routes/roadmap.tsx` (Career Twin blurb).
