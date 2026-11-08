# AP-03 owner decisions: recommendation (opus, 2026-11-08)

## Decisions
1. **Season interval: pick (c), the combined construction, with the plain mean kept as the point.** SE = max(independent-error SE, spread SE), CI uses t with k-1 df. If k < 3, show no season interval (SE and CI are NULL). Drop (a): it fails calibration, covering 43-56% where it should cover 95%. Do not use DerSimonian-Laird: it moves the point and is undefined when se = 0.
2. **Party Mode: yes, relabel. Use three labels: `party`, `race` and `no clear gap`.** `balanced` goes, because the same test shows it is almost never supported. party/race require |delta| > 0.15 *and* a CI that excludes 0. The season grain uses the rule from (1) on the per-race deltas. Do not suppress the label.
3. **Races column: keep k (races with an estimate)**, with a header tooltip. Any future card's `n` = `{count: k, unit: 'races'}`. Restrict `panel_observations_n` to the same k races.

## Evidence (scratch laneA/dev.duckdb, read-only; scripts in scratchpad/ap03_scripts/)
**Q1. Race mode, 81 team-season cells, k = 9..23 (no cell has k < 3 today).**
- Median SE: (a) 0.0265, (b) SD/sqrt(k) 0.0815, (c) 0.0815 (c equals b in 81/81 cells), DL 0.078.
- Median 95% half-width: (a) 0.052 s, (c) 0.170 s. The old shipped AVG(se) gave 0.22 s.
- **Leave-one-race-out predictive check (1,602 held-out races).** The held-out race is standardised by sqrt(Var(mean of the other k-1) + tau^2 + se_j^2).
  - Coverage at |z| ≤ 1.96: model (a), tau = 0, **45%** (SD(z) = 3.66); model (c) **93%** (SD(z) = 1.07).
  - Naive check, "does the k-1 CI cover the held-out race": (a) 12%, (c) 39%. This is expected to be low for any CI of a mean, so it is not the test that decides.
- **Split-half check** (the mean of half the races vs the other half, Z = diff / sqrt(SE1^2 + SE2^2), target 95%):
  - odd/even rounds: (a) 56%, (c) 96%;
  - random halves: (a) 43%, (c) 96%.
- **Where the excess scatter comes from.**
  - The race-mode deviation variance is 0.145 against a mean se^2 of 0.0148, a 10x excess.
  - Same-weekend race and quali deviations correlate at r = 0.21 (cov 0.044). So about a third of the excess is real weekend-specific car pace.
  - The rest is either race-only effects or per-race SEs that are understated. The per-race SE is SD/sqrt(n) applied to a *median* and ignores lap autocorrelation.
  - Team-by-circuit deviations barely persist year to year (r = 0.095, n = 1,028), so this is not a stable "circuit affinity".
  - Either way, (a) is not a credible bound for "how fast was this car this season".
- **Quali mode:**
  - Median SE: (a) 0.054, (c) 0.080. (c) equals (b) in 58/81 cells; in the other 23, (a) is larger because quali SEs are noisy.
  - LORO coverage: (a) 77%, (c) 92%. Split-half: (a) 86-90%, (c) 99-100%, so (c) is slightly conservative there.
  - 10 quali rows have se = 0, which makes DL/precision weights undefined (McLaren 2025 gives NaN). (c) is unaffected.
- **DL random effects:** it moves the point (race median 0.008 s, max 0.034 s; quali max 0.82 s) and still needs se > 0. Rejected.
- **Top-two separation per season, race mode (diff z > 1.96):**
  - (a) separates 5/8 seasons (2019, 2020, 2022, 2023, 2025). (c) separates 3/8 (2020, 2023, 2025).
  - A paired test on per-race differences under the (c) rule gives the same 3/8. 2019 (t = 1.75) and 2022 (t = 1.04) drop out.
  - Adjacent-rank pairs separated: (a) 48/73, (c) 25/73.
  - Quali top two: (a) 2/8, (c) 1/8.
  - Under (a), the page would call 2019 Mercedes and 2022 Red Bull clearly ahead on evidence the split-half test says is about 3x overstated.
- **Mercedes 2020 race (k = 16):** mean -1.2733; (a) SE 0.0264; SD 0.4015 so (b) = (c) = 0.1004; t_15 = 2.131; CI [-1.4873, -1.0594].

**Q2. Party Mode.**
- **Race grain** (1,602 rows with a delta; 42 have NULL race pace):
  - Point labels: party 647, race 577, balanced 378.
  - 478 party/race rows have a CI covering 0 (283 party, 195 race). This confirms the lane's count.
  - 374 of the 378 "balanced" rows have a CI reaching outside ±0.15 s. "Consistent across quali and race" is therefore claimed without support in 99% of balanced rows.
  - A balanced label that needs the CI inside ±0.15 would leave 4 rows. A separate `balanced` label is effectively dead.
- **Proposed race-grain labels:** party 364, race 382, no clear gap 856.
- **Season grain, shipped SE** (series SEs sqrt(Σse²)/k, combined in quadrature):
  - 6 labelled cells have a CI covering 0. The proposed labels give party 31, race 20, no clear gap 30.
- **Season grain, (c) rule on per-race deltas** (median SE 0.060 → 0.103; t_{k-1}):
  - 11 labelled cells have a CI covering 0. The proposed labels give **party 27, race 20, no clear gap 34**.
  - Examples: 2023 Red Bull 0.351 [-0.713, 1.415] (race → no clear gap); 2022 McLaren -0.166 [-0.676, 0.344].
- **Shipped season delta defect:** it is AVG(q) − AVG(r) over the joined rows. AVG(r) skips the 42 NULL-race rows while AVG(q) keeps them, so the two means cover different races. This shifts the delta by up to 0.071 s (2018 cells). Use AVG(q − r) over races where both are present.
- **Why a third label rather than suppression:**
  - A blank cell reads as "missing data" and collides with the 42 genuinely NULL rows.
  - The CSV and the assistant need an explicit state to quote.
  - "no clear gap" is a true statement whether the gap is small or merely unmeasurable. "balanced" and "not distinguishable" are not both true.
- **NULL delta:** `classify(null)` currently returns `balanced`, which over-claims. Make it `null` and render "—".

**Q3. Races column.**
- 22 race-mode cells change (2018: most teams 21 → 18; Toro Rosso 20 → 17). Quali has no change.
- k is the divisor in both the SE and the t-df, so showing k lets a reader redo the arithmetic. Showing 21 next to a mean of 18 would mislead.
- The 42 NULL rows carry 29 panel observations in total. Include them in `Obs` only for races in k, for consistency.

## Implementation spec (for a sonnet builder; do not commit)
**A. `app/src/features/constructor-structural-pace/queries.ts`, season branch only (the race branch is unchanged).**
- In the agg CTE, per constructor, with p = pace and se = pace_se:
  - `k = COUNT(p)`, `pace_s = AVG(p)`, `s2 = VAR_SAMP(p)`, `msq = SUM(se*se) / COUNT(p)`;
  - `se_s = CASE WHEN COUNT(p) >= 3 THEN SQRT(GREATEST(s2, msq) / COUNT(p)) END`;
  - `panel_observations_n = SUM(panel_observations_n) FILTER (WHERE p IS NOT NULL)`, `races_n = k`.
- Return pace_s, se_s, panel_observations_n and races_n, plus `ci_low/high = NULL` placeholders. The CI is computed in TS, because DuckDB has no t-quantile.
- Identity to cite in the comment: Var(mean) = tau²/k + Σse²/k² with tau² = max(0, s² − mean se²), which equals max(s², mean se²)/k.

**B. `.../constructor-structural-pace/transform.ts`**
- Replace `seasonMeanSe` with `seasonMeanSe(paces, ses)`:
  - drop pairs where either value is null or non-finite;
  - k < 3 → null;
  - otherwise `sqrt(max(var_samp(paces), mean(ses²)) / k)`.
- Add `t975(df)`: a lookup for df 1..40 (2:4.303, 8:2.306, 15:2.131, 20:2.086, 22:2.074) that returns 1.96 above 120 and interpolates linearly in between. Alternatively, ship a precomputed table for df 1..120.
- In `transform()`, a season row (`races_n > 1`, or a `grain` param) gets `ci = pace ∓ t975(k−1)·se`, and null when se is null. A race row keeps its stored ±1.96 CI.
- `ConstructorPaceEntry.se_s/ci_*` become `number | null`. `toCsvRows` and the table print "—"/null for these. Add a CSV column `interval_method` with the value `race: ±1.96·se` or `season: ±t(k-1)·max(SD/√k, √Σse²/k)`.
- **Tests:** hand case Mercedes 2020 (SE 0.100383, CI [-1.4873, -1.0594]). A 3-race case where (a) wins (scatter < se). k = 2 → null. se = 0 rows give a finite result.

**C. `.../constructor-structural-pace/methodology.tsx` and `page.tsx`**
- Methodology: replace the "lower bound" paragraph. The season interval treats the season's races as a sample of circuits and weekends. It uses the larger of the race-to-race spread and the per-race estimation error, and gives none below 3 races.
- Update the '95% CI' badge text, which currently says width comes only from laps.
- Races header tooltip: "races with an estimate (k); races under 10 measured laps are excluded".

**D. `app/src/features/party-mode/queries.ts`, season branch.**
- Compute over the joined rows `WHERE r.pace IS NOT NULL AND q.pace IS NOT NULL`:
  - `race_pace_s = AVG(r.p)`, `quali_pace_s = AVG(q.p)`, `delta_s = AVG(q.p − r.p)`, `k = COUNT(*)`;
  - `delta_se_s = CASE WHEN k >= 3 THEN SQRT(GREATEST(VAR_SAMP(q.p − r.p), SUM(q.se² + r.se²)/k) / k) END`;
  - return `races_n = k`.
- The race grain is unchanged: `deltaSe = sqrt(se_q² + se_r²)`, ±1.96.

**E. `.../party-mode/transform.ts`, `page.tsx`, `methodology.tsx`**
- Change the type to `ModeLabel = 'party' | 'race' | 'no_clear_gap'` and use this `classify(delta, lo, hi)`:
  - null delta or null CI → `null`;
  - `delta < −0.15 && hi < 0` → party;
  - `delta > 0.15 && lo > 0` → race;
  - else → no_clear_gap.
- The season CI uses t975(k−1)·delta_se_s from the season query. The race grain stays at 1.96.
- CSV: `mode` takes the new values, plus `delta_ci_covers_zero` (true/false/null) and `races_n` (season). Do not add a point-only label column.
- Badges:
  - Retire "Balanced".
  - New badge "No clear gap": the data do not show a quali–race gap beyond ±0.15 s that is distinguishable from zero. This includes small real gaps and gaps too noisy to call.
  - Party and Race Spec badges get the line "…and the 95% CI excludes 0".
- `MODE_BADGE` gets an entry for no_clear_gap, and null renders "—".
- **Tests:** a −0.30 delta whose CI covers 0 → no_clear_gap; a −0.30 delta with CI [−0.45, −0.15] → party; a 0.05 delta → no_clear_gap; null → null; the season SE where scatter dominates.

**F. Re-run the counts after the build. Expected values:**
- race grain party 364 / race 382 / no clear gap 856 / null 42;
- season grain 27 / 20 / 34;
- structural season median SE 0.0815 (race), 0.080 (quali).
- Then: `pnpm exec vitest run src/features/constructor-structural-pace src/features/party-mode`, `pnpm typecheck`, `pnpm lint`.

## Not verified
- All numbers come from the scratch laneA warehouse, not app/public/data parquet. The shipped parquet may differ slightly.
- I did not check whether the per-race SEs are understated through lap autocorrelation directly. The split between "real weekend variation" and "understated se" is inferred from the race/quali covariance only.
- t vs 1.96 was not separately coverage-tested (t is at most 18% wider at k = 9).
- No structural-pace or party-mode card spec exists yet in `app/src/assistant/cards/`, so the card `n` rule is prospective. `intervalKind` has no t-interval value; `ci_normal_95` is closest. Add `ci_t_95` or accept the label mismatch.
- I did not run the app, tests or typecheck, and edited no repo files.
- I did not check the counterfactual or other pages that may reuse season structural pace (e.g. constructor-team-averages).
