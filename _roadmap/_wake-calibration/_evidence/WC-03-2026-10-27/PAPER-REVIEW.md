# WC-03 pre-registration draft: paper review (2026-10-27)

Review of `_roadmap/_wake-calibration/wi/WC-03-preregistration-DRAFT.md` (unsigned draft).

**Paper review only.** Nothing was fitted, scored, gated or simulated, and no loss, curve or coefficient was computed. `data/dev.duckdb`, `data/ci.duckdb` and `data/bronze` were not touched. Nothing was committed. The only file written is this note. The only numbers quoted below come from files already in the repo: the WC-01 count files, the code comments in the dbt models, and the build logs.

**Read:** the draft (in full); WC-02 `BEST-MOVE-NEXT.md`, `SALVAGE-timing.md`, `RECONCILE-1124.md`; `transform/tasks/wake_calibration/build_pass_table.py` (constants, pass events, layout, gaps, flags, outcomes, references); `transform/models/intermediate/int_dirty_air_tax_component.sql`, `int_lap_air_state.sql` (definition lines), `int_field_pace_curve.sql` (header and eligibility); `_roadmap/_fixes/_evidence/wi-12-2026-09-27/d1_build_panels_wi12.py` (header, SQL, I/O); `_roadmap/_fixes/THETA_AIR_LABEL_VALUE_PROCEDURE.md`; `transform/dbt_project.yml` (theta vars); work items WC-03, WC-04, WC-09; WC-01 `counts_by_season.csv`, `passes_by_corner_class.csv`, `PROVENANCE.txt` (command lines); git log of the upstream models since 2026-09-27; and the build-log entries that mention the theta gate and the 2026-10-21 dirty-air scoping.

**Paper verdict: works end to end *with fixes*.** Every fix below can be made as wording before signing. Without them, two things go wrong. The run is likely to stop at G3, and a "replace" verdict would not show that the corner curve is right.

---

## Part 1. Red-team findings

Likelihood means how likely the problem is to actually bite on the real run: **High** (expected), **Medium** (plausible), **Low** (edge case). Findings are ordered by how much damage they can do.

### F1. The contest compares this lap's traffic with last lap's traffic, and the owner already knows which one wins (§2d, §7, §8b, §0 rule)

**What goes wrong.** The flat penalty is priced from the *previous* lap's dirty-air bit (`dirty_air_share_lag1`). It was lagged on purpose, so that "the causal arrow runs prior-lap-position → current-lap-cost" (`int_dirty_air_tax_component.sql` header). The measured cost is built from *this* lap's approach gaps (§7). So the contest does not compare two traffic models on equal terms. It compares a lagged signal with a same-lap signal.

The repo already shows that a same-lap signal wins by itself. The ai-integration build log has a scoping note from 2026-10-21, run read-only on the warehouse with 2018-2025 data, so 2025 is included. It says: "the current-lap bit fits better than the lag (0.473 vs 0.331 alone; 0.407 now / 0.130 lag jointly …), and continuous share_lap_within_1s fits better still (0.881). Better fit is not identification: shared local shocks (yellows, lapped cars) remain a threat."

So W1 can pass simply because the measured cost is same-lap and continuous, even if the corner curve has the wrong shape or level. Shared shocks make this worse. A mis-mapped yellow (marshal sectors are only approximate, builder lines 30-35), or a lapped car slowing both cars, closes the gap and slows the follower on the same lap. That reads as "traffic cost" in the contest and in the fit.

There is also a disclosure problem. The draft says no result has been seen and states that the contest "slightly favours the flat penalty" (§2d, §14). The 10-21 result is prior knowledge of which way this contest's design leans, taken from data that includes the held-out season. It is not a DA-03 number, but it is the kind of prior look a pre-registration must declare.

**Likelihood: High** that it moves the result; **Certain** that it needs disclosing.

**Fix (wording to adopt).**
> §8b, add a fourth candidate: "**flat-now**: 0.331 × the lap's own dirty-air bit (`dirty_air_share_lap`), clamped 0-5 s. It is the flat penalty moved to the same lap as the measured cost."
> §9, add to W1: "W1 also requires the point estimate of `1 − MSE_measured / MSE_flat-now` on all scored 2025 laps to be at least 0. A measured cost that beats the lagged flat penalty but not the same-lap flat penalty has shown that same-lap timing helps, not that the corner curve is right. Verdict in that case: keep the flat penalty and show the measured figure beside it."
> §14, add: "**Prior knowledge declared.** A read-only scoping on 2026-10-21 (ai-integration build log) found on 2018-2025, including 2025, that a same-lap dirty-air bit fits lap residuals better than the lagged bit (0.473 vs 0.331), and a continuous same-lap share better still. The measured cost is same-lap. The flat-now candidate exists to separate the effect of timing from the effect of the curve." Then delete "The contest therefore slightly favours the flat penalty" from §2d, or rewrite it as "Fitting 0.331 on data including 2025 favours the flat penalty; scoring same-lap against lagged traffic favours the measured cost; the flat-now candidate controls the second."

If the owner does not want a fourth candidate, a weaker alternative is a binding sensitivity run: "The measured cost recomputed from lap L−1's gaps (lagged like the flat penalty) is scored the same way, and its R is printed in the scorecard's first lines."

### F2. G3 will very likely stop the run: the yardstick panel has moved since 0.331 was fitted, and the rebuild script points at the warehouse (§2d, §12a G3)

**What goes wrong.**
1. The 0.331 was fitted on the 2026-09-27 panel. Since then, the models that feed the yardstick have been changed and two label bumps have landed:
   - v15 (CO-04, 2026-10-15): the FD6 unmeasured-air laps were dropped from the field base; the smoother no longer reaches across neutralisations; restart-adjacent laps get their own base; `int_lap_air_state` was rewritten (0faac10 touches `int_field_pace_curve`, `int_compound_cliff_predicted`, `int_lap_air_state`, `int_dirty_air_tax_component`).
   - v16 (CO-17, 2026-10-24): the CO-09 tyre-run key and the CO-15 wear hold. The `dbt_project.yml` note says these moved the label, while "theta_air unchanged at 0.331" refers only to the declared value.

   `THETA_AIR_LABEL_VALUE_PROCEDURE.md` names FD6 and compound refits as triggers for re-running d1/d2. I could not find a record of d1/d2 being re-run after 2026-10-15. On the panel as it is now, `d1`'s own Gate 1 (the pooled-slope fingerprint 0.5033413666 to 1e-9) is very likely to fail. The F2 slope landing on 0.331 to 3 decimal places is uncertain. G3 then says "Otherwise stop".
2. The lagged bit is not the same variable in the two places the draft uses it. `d1` builds the lag as `LAG(COALESCE(share, 0.0))` (pre-FD6). The shipped model now leaves the lag NULL after an unmeasured lap (FD6). §2d takes the flat penalty from the shipped `dirty_air_tax_s` but the yardstick from `d1`. §8a then says "`dirty_air_share_lag1` not missing", but the shipped output column is called `dirty_air_intensity_lag1`, and in `d1` the lag is never missing.
3. `d1_build_panels_wi12.py` hard-codes `DB_NOW = REPO / "data/dev.duckdb"` (read-only, but it is the warehouse, not a scratch copy). It writes `panel_wi12_lap_wi01.parquet` into the committed WI-12 evidence folder (`HERE`), and only the corner panel goes to `WI12_SCRATCH`. It also builds the `as06b_0925` arm from `dev_unfixed.duckdb`. Run as written, it breaks §2d ("never the warehouse itself") and changes committed evidence.

**Likelihood: High** for item 1; **Certain** for items 2 and 3 unless reworded.

**Fix (wording to adopt).**
> §2d: "Before signing, the THETA_AIR_LABEL_VALUE procedure is run on the current label (a read-only check, no label change), and its outcome is recorded in this section: either 'd1 Gate 1 and the W40 gate pass on the <date> panel, n = <N>' or 'the panel moved; the label bump is done first and this registration is re-signed'. WC-03 does not start on a panel whose F2 fit is not the declared theta to 3 dp."
> §2d: "The yardstick panel is built by a wrapper that takes the scratch `dev.duckdb` path as an argument and writes only into the scratch folder; it runs only the wi01 arm. `d1_build_panels_wi12.py` itself is not run."
> §2d / §8a: "The flat penalty for a lap is the shipped `dirty_air_tax_s`, joined by `lap_id`. A lap is scored only when `dirty_air_tax_s` is not NULL (FD6: after an unmeasured lap the tax is unknown). The panel's own `d_lag1` is used only for G3."

### F3. The "trains" check cannot see whether trains are priced at the right level (§8b step 3, §9 W2, §14 "Selection")

**What goes wrong.** Step 3 takes out each stint's own level before scoring. So any cost that is constant across a stint vanishes from both candidates, and only changes within a stint are scored. Two consequences follow.
- In a stint spent in a train, the flat bit is 1 on almost every lap, so after the stint level is removed **the flat penalty and "no traffic term" are the same candidate**. W2 then compares the measured cost's lap-to-lap wiggle against nothing. It does not compare the train's level.
- The worry the draft is built around (BEST-MOVE-NEXT §d: the curve is learned from drivers with a clean reference and then understates what trains cost) is a *level* error, and step 3 removes level errors. That matters because the label applies the cost as a level: every lap's tax is subtracted from that driver's skill residual. WC-01 counts show 32-36 % of stints in 2022-2025 have no measured pass at all (`share_stints_no_measured_pass`: 0.32, 0.36, 0.32, 0.36). §14 says "Scoring the whole field and requiring W2 is the guard". It is a much weaker guard than that sentence claims.

The no-reference half is also not only trains. It contains every lap where a car sat within 1 s *behind* (such laps cannot donate references; builder `references()`), including a train leader in clean air whose cost is 0 under both candidates. That dilutes W2 towards R = 0.

**Likelihood: High** that W2 gives no information about levels in trains. The direction of any error it misses is unknown.

**Fix (wording to adopt).**
> §14, replace the selection bullet: "**Selection.** The curve is fitted only where a clean reference exists. The contest removes each stint's own level, so it tests only how traffic cost *changes within a stint*. It cannot show whether the measured cost prices a whole stint spent in a train at the right level; neither could the fit that produced 0.331. W2 guards against the measured cost making within-stint predictions worse in trains; it does not validate the train level."
> §5 / §9 W2: "W2 is scored on the **train laps**: no-reference-half laps whose flat bit is 1 or whose median braking-corner gap is under 1.5 s. It is also reported on the stints that contain laps of both halves (mixed stints), which are the only stints where the level in traffic is compared with the same driver's level out of it."
> §15: "The scorecard states, under the verdict: 'This contest checks changes in traffic within a stint, not the level of a whole stint in a train.'"

### F4. "Replace" does not say what replaces what, for which seasons and which laps (§1, §3, §9)

**What goes wrong.** The label covers 2018-2025 (and will cover 2026). The verdict curve is fitted on 2022-2024 ground-effect cars. The older-car curve and its 2021 contest "cannot rescue or sink" the verdict (§3). So "Replace" either puts the 2022-2024 curve onto 2018-2021 laps, which was never tested, or puts the older curve there even if its own contest failed. Neither is supported by the data. The same gap exists for laps the measured cost cannot price: laps with an excluded braking corner, laps with no car ahead (see F5c), and 2026. Those laps are not scored, so "replace" says nothing about them, yet a label change touches them.

**Likelihood: High** that the question comes up at once if the verdict is "replace". Low that it changes the verdict itself.

**Fix (wording to adopt).**
> §9, under the table: "**Scope of 'replace'.** Replace applies to 2022-2025 laps that meet §8a's conditions. 2018-2021 laps are replaced only if the older-car contest (2018-2020 fit, 2021 score) also passes W1, W2 and W3. Otherwise they keep the flat penalty. Laps the measured cost cannot price keep the flat penalty. 2026 keeps the flat penalty until a 2026 registration exists. The older-car result still cannot sink the 2022-2025 replacement."

### F5. Rules the draft uses but does not define. Several of these will break the run as written (§5, §6, §7, §8a)

a. **Lap-total geometry (§7).** Two problems.
   - Step 1 says the segment starts at "apex minus the corner's fixed brake-onset offset, `seg_offset_m`". In the builder, `seg_offset_m` is the *median brake offset*, which is negative (`brake_offset = cum[onset] − cum_apex`, then `min(·, 0)`; flat-out is −100), and the segment start is `cum_apex + seg_offset_m` (`attach_outcomes`). Read literally, "apex minus" puts the start after the apex.
   - The apex's lap distance is not a pass-table column. `cum_apex` is computed but is not in `PASS_COLUMNS`, and circuit_info `Distance` is not carried. The "race's fixed corner geometry" therefore has no stated source. If it is taken from circuit_info, it may come from a neighbouring season (`circuit_info_season`).
   - Also undefined: what happens to a segment that starts before the line or ends after it ("no wrap").
   - **Fix:** "Segment k runs from `apex_k + seg_offset_m` (a negative number) to `apex_k + 100 m`. `apex_k` is the median, over the race's clean passes of corner k, of the apex's lap distance, recomputed by the WC-01 builder's apex finder and written as an extra output column (the builder's existing columns are unchanged, so G2 still holds). Segments are clipped to [0, lap length]; clipped metres are owned by no corner." An equally valid alternative needs no new column: "Overlap is measured per pass in time, from `seg_start_t` and `seg_end_t`: corner k's weight on that lap is `1 − overlap with the previous braking corner's segment on the same lap / (seg_end_t − seg_start_t)`."

b. **A pass with no car ahead (§6 "Applying the curve", §8a).** If the builder finds no other car's apex within 30 s before the follower's (`CAR_AHEAD_MAX_S`), it sets `leader = None` and `gap_s = NaN`, with **no** exclusion reason (`no_gap` fires only when a leader exists). §8a requires every braking corner to have "a gap", so every lap with one such corner drops out, which is most race-leader laps and lone runners. §6 does not say what the curve gives at NaN. That is a selection rule nobody chose.
   - **Fix (§6):** "A pass with no car ahead (`clear_ahead` true, `gap_s` missing) gets 0." **(§8a):** "every braking corner has a pass row with no exclusion reason, and either a gap or no car ahead."

c. **Order of the scored-lap filters (§8a).** The ±5 s trim uses "the residual after the baseline step", but that baseline step (§8b step 3) is fitted "over all scored 2025 laps", which depends on the trim. The rule is circular, and "its stint still has at least 2 scored laps" can loop.
   - **Fix:** "Filters are applied once, in this order, on the original (not resampled) 2025 sample: (1) conditions 1-4; (2) fit the stint + age-group regression on y over that set and drop laps with |residual| > 5 s; (3) drop stints left with fewer than 2 laps. No iteration. The scored set is then fixed and is not recomputed inside bootstrap draws."

d. **Held up (§5).** "Two times the median absolute deviation of the follower's reference passes" cannot be computed from the pass table: it stores `ref_n` and `ref_time_s`, not the spread. With `ref_n = 2` the deviation is half the difference of two numbers. "The car ahead's `seg_time_s` at the same corner and lap" does not say *whose* lap; the car ahead may be on `leader_lap ≠ lap`.
   - **Fix:** "The deviation is recomputed from the same donor passes the builder used (same window, same clean rule), with a floor of 0.01 s. The car ahead's time is its pass row at (`leader`, `leader_lap`, `corner_id`)."

e. **Classes do not cover every pass and can overlap (§5, §6).** If the car ahead's time falls between the follower's reference and reference + 2 deviations, the pass is neither held up nor dirty air. A racecraft pass can also meet the held-up or dirty-air rule. The class curves (and P2) need a precedence.
   - **Fix:** "Classes in priority order: racecraft, held up, dirty air, other. 'Other' goes into the contest curve and into no class curve."

f. **Joins (§2, §8).** The draft never says how a pass-table lap is matched to a panel lap (season, `race_id`, driver code, lap number → `lap_id`). It also does not say whose stint is used where: the pass table's `stint` comes from bronze `Stint`, while the panel's `stint_id` uses the warehouse's tyre-run key, which changed under CO-09.
   - **Fix:** "Pass rows join to the panel on (`race_id`, `driver` = `driver_id`, `lap` = `lap_number`). The stint for steps 3-4 is the panel's `stint_id`; the stint for references is the pass table's `stint`. Laps that fail to join are counted and reported."

g. **Bin edges (§0, §6).** It is not stated whether a gap of exactly 0.5 s goes in the 0.3-0.5 bin or the 0.5-0.75 bin.
   - **Fix:** "Bins are [lower, upper)."

h. **"Main curve" (§10, §11) versus "contest curve" (§6).** These seem to be the same thing but are never tied together. §11 also does not say which curve gives the predicted drop.
   - **Fix:** "The main curve is the contest curve of §6."

i. **The 2026 pit-stop check (§13)** has no named curve. Using the 2022-2024 curve would break §13's own rule ("no comparison of a 2022-2024 curve with 2026").
   - **Fix:** "2026 pit-stop check: against the 2026-only exploratory curve."

**Likelihood: High** that a, b and c each stop or skew the run; Medium for d-i.

### F6. Internal contradictions (§12a G5 vs §9; §5 vs WC-03; §14 figures)

- **G5 against the verdict table.** G5 says "If the no-reference half falls short, W2 cannot be tested and the verdict cannot be 'replace'". That implies "keep and show" is still allowed. The table says "a minimum in 12a is not met → **No verdict**". Pick one.
  - **Fix:** "If the no-reference half falls below the minimum, W2 is 'not testable' and the verdict is decided as if W2 failed. If the clean-reference half or the whole field falls below it, there is no verdict."
- **Following gap.** WC-03 defines following as "approach gap under 2.5 s". The draft uses 3.0 s without saying it departs from the work item.
  - **Fix:** add "(departs from WC-03's 2.5 s so that the curve meets the 3 s reference rule; fixed before any result)".
- **Racecraft.** WC-03 says "within 3 segments"; the draft says "within 3 corners before or after on the same or adjoining lap". These are close, but "differs" is undefined when the leader is missing at a neighbouring corner.
  - **Fix:** "A missing leader at a neighbouring corner does not count as a change."
- **§14's coverage figures.** "49 % of kept passes; 43 % in 2025" is the measured share of *all* kept passes, which includes flat-out corners (515,750 kept) and clean passes themselves. The share of *following* braking passes with a reference, which is the real fit population, will be lower.
  - **Fix:** "The share of following braking-corner passes with a measured reference is reported in the scorecard; the 49 % figure includes clean and flat-out passes."
- **WC-04 scorecard item 2** ("the straight tow is a gain") and **item 1** ("match") are dropped or changed in the draft. That is fine, but it should say so.
  - **Fix:** "This registration supersedes WC-04 scorecard items 1 and 2 as follows: …"

**Likelihood: High** that G5 matters if the no-reference half is thin; Low otherwise.

### F7. Checks that cannot really fail (§10 P1, P2; §11)

- **P1 passes on a negative far band.** P1 says the 2-3 s mean must be "at most 25 %" of the 0.5-1.0 s mean. The curve is not forced to zero, so a 2-3 s band below zero passes automatically. A negative far band means following at 2.5 s is *faster* than the clean reference, which is a reference-bias symptom that P1 is meant to catch. The non-increasing constraint already guarantees far ≤ near, so the ratio is the only bite P1 has.
  - **Fix:** "|mean over 2.0-3.0 s| ≤ 0.25 × mean over 0.5-1.0 s".
- **P2 is close to unfailable.** It fails only if fast corners are *significantly* below slow ones. A point estimate of fast < slow still passes. That can be the owner's intent (non-inferiority), but it should be named as such.
  - **Fix:** add "and the point estimate of fast minus slow is at least 0", or keep the rule and add "P2 is a check against a clearly reversed sign only; it does not show that fast corners lose more."
- **The pit-stop ceiling** passes unless the curve's predicted drop is above the 97.5th percentile of the observed jump. The push after a stop inflates that jump (§11 says so), so the check is nearly unfailable. With the outside-window reference and the comparison cell on top, it is also likely to be "not testable": the old set had 512 distinct stops with readings on both sides *before* those two drops. Being reported only is fine. See F9 for how it is presented.

**Likelihood: High** that P2 and the pit check pass whatever the truth; Medium that P1's loophole is used.

### F8. The chance procedure is too narrow and has two loopholes (§8c, §0 rule)

- **24 clusters with percentile intervals.** The draft admits the intervals "may be somewhat too narrow" but does nothing about it. That makes W1 easier to pass than its 95 % label suggests.
  - **Fix (§9 W1):** "and the measured cost has the lower MSE in at least 15 of the 24 held-out races (per-race R > 0)". Alternative: "and the leave-one-race-out minimum of R is above 0".
- **The flat penalty is never re-estimated in a draw.** Only the measured cost carries fitting noise. That is conservative for "replace" and acceptable, but it should be stated.
- **The rerun loophole.** §0 allows a rerun for "a bug that the synthetic tests should have caught". After a completed run has been seen, almost any unwelcome result can be blamed on such a bug.
  - **Fix:** "A rerun after a run that completed and printed a result is allowed only with a new failing synthetic test, committed before the rerun, that reproduces the bug. Both results are reported. The verdict is the rerun's only if the fix is a pre-result-style amendment that changes no threshold, definition or data rule."
- **Compute.** The draft budgets 1,000 draws × (three class REML fits, two class-curve fits, the non-increasing step and the 2025 rescoring), plus G1(i)'s 200 simulations each with intervals, plus five sensitivity runs. Only "one full refit over 10 minutes → 200 draws" is bounded. At 10 minutes a refit, 1,000 draws is about 7 days for the main run alone.
  - **Fix:** "G1(i) uses 200 simulations × 200 draws. Sensitivity runs (§12b) use 200 draws. The main run uses 1,000 draws unless a refit exceeds 2 minutes, in which case 200. The choice is recorded from the synthetic timing before any real score."

**Likelihood: Medium** that the narrow intervals tip W1; High that compute forces an unplanned change unless budgeted.

### F9. The pit-stop check sits in the verdict table of the scorecard (§11, §15)

**What goes wrong.** §15 puts "pit-stop ceiling" in the same table as W1-W3 and G1-G5, with "pass or fail". §11 also uses "Pass". A reader will take it as a verdict input. Because it is nearly unfailable (F7), a "pass" will read as confirming the curve when it shows almost nothing. BEST-MOVE-NEXT §d also warns that it shares the fit's selection bias.

**Likelihood: Medium.**

**Fix (§15):** "The scorecard has two tables. Table 1 (the verdict): W1, W2, W3/P1, W3/P2, G1-G5. Table 2 (context, never a verdict input): pit-stop ceiling, older cars, sensitivity runs. Table 2 uses 'within ceiling / above ceiling / not testable', never 'pass' or 'fail'."

### F10. Smaller points

- **Lap labels near the start/finish line (§2b risk, §7, §8a).** The salvage found lap start times about 2 s off the sector clock in some races (2023 Netherlands). A pass at the first or last corner could then be counted in the wrong lap's total. **Low.** Fix (§8a): "a pass counts in a lap's total only if `seg_start_t` and `seg_end_t` lie inside that lap's start and end times; otherwise the lap is not scored."
- **Ownership by "first segment" (§7 step 2).** This hands the braking zone of corner k, where wake loss shows up as earlier braking, to corner k−1's post-apex tail. That biases the measured cost low in a way that is not random. It is stated as an assumption, which is acceptable, but a split-evenly sensitivity costs nothing. **Low.**
- **Gaps below 0 get the first bin (§6).** Overtaking passes, which were not fitted, are given the largest cost. This is defensible but unexplained. **Low.** Fix: "(the overtaking pass is priced as the closest following pass; no separate racecraft cost is fitted)".
- **W1's margin has no stated basis.** 0.5 % is fixed in advance and the owner cannot steer it after seeing data, but its meaning depends on how much of 2025 is clean air. Laps where both candidates are 0 dilute R. **Low.** Fix: "The scorecard also reports R on laps where either candidate is non-zero (for context, not the verdict)."
- **The yardstick is not perfectly neutral.** The field-pace base keeps only laps the existing air-state coder calls `free_air`/`tow_zone`, which is the same 1.5 s middle-third coder that defines the flat bit (`int_field_pace_curve.sql`, eligibility). It contains no traffic term, so this is a weak link, but "neutral" overstates it. **Low.** Fix (§2d): "The base is built from laps the flat penalty's own air coder calls clean; that is the only link between the yardstick and the flat penalty."
- **2026 timing (§13).** "Once the data exists, on the 2026 races then held" allows the 2026 checks to be re-run as races accrue. **Low.** Fix: "The 2026 checks run once, when WC-09 lands, on the race list frozen at that time; later runs are labelled updates."
- **The 2026 data source (§13).** WC-09 plans to use archived FastF1 timing, which BEST-MOVE-NEXT says needs an F1 TV login for car data. The draft handles failure correctly ("not run: no data"). Nothing more is needed beyond the fix above.

---

## Part 2. Does the pipeline work end to end? (walked through on paper)

| Step | What happens | Works? |
|---|---|---|
| 0. Sign, commit alone, hash, record on WC-03 | Procedure is clear. | Yes. |
| 1. Write estimator, contest, weights, pit builder; G1 synthetic tests | The tests are well chosen. G1(i) needs interval coverage over 200 simulations, each needing its own bootstrap; there is no budget. | **Yes with fix** (F8 compute). |
| 2. Rebuild the pass table on scratch from 97e0760; G2 byte-for-byte | Builder is deterministic per race; `counts.py` is in the WC-01 evidence folder; bronze is read-only. | Yes, provided bronze has not changed. |
| 3. Scratch warehouse copy; rebuild WI-12 panel; G3 (0.331 to 3 dp, row count) | `d1` reads `data/dev.duckdb` by a hard-coded path and writes into committed evidence. The panel's inputs changed in the v15 and v16 label bumps after 0.331 was fitted. I found no record of d1/d2 re-run since. | **Likely breaks here** (F2). Stop by design, not by crash. |
| 4. Fit the contest curve per class on 2022-2024 (REML + non-increasing step) | Inputs exist (`delta_time_s`, `gap_s`, `corner_class`). "Circuit" for the random effect is not defined (race slug or location; layout changes are flagged only). Workable. | Yes (define circuit). |
| 5. Class curves (held up / dirty air) for P2 | Deviation not in the table; car ahead's lap ambiguous; classes have a gap and overlaps. | **Breaks as written** (F5d, F5e). |
| 6. Lap totals with overlap weights | Apex lap distance not in the table; sign of the offset reversed in the text. | **Breaks as written** (F5a). |
| 7. Choose the 2025 scored laps | Laps with any car-less corner have no gap and drop out silently (mostly the leader); the trim is circular; the join key is undefined. | **Breaks or skews as written** (F5b, F5c, F5f). |
| 8. Score none / flat / measured; stint + age regression; R | Mechanically fine. Same-lap vs lagged, so a W1 pass cannot be read as "the curve is right". | Runs, **result uninterpretable** without F1. |
| 9. Bootstrap 1,000 × (refit + rescore) | Feasible only if one refit is about 2 minutes or less; percentile intervals on 24 clusters run narrow. | **Yes with fix** (F8). |
| 10. P1, P2 | P1 has the negative-band loophole; P2 barely bites. | Runs; weak (F7). |
| 11. Verdict table | G5 contradicts the table; "replace" has no scope. | **Ambiguous** (F4, F6). |
| 12. Pit-stop ceiling | Likely "not testable" after the outside-reference and comparison-cell drops; nearly unfailable if testable. | Runs; little information (F7, F9). |
| 13. Sensitivities, older cars, team coverage | Fine once compute is budgeted. | Yes. |
| 14. 2026 | Correctly guarded as "not run: no data". | Yes. |

**Bottom line.** **Yes with fixes.** The design holds up: a clean held-out season, a rule for adding up laps without double counting, the whole field scored, a one-sided pit check. The ten findings above are wording, not redesign. The two that matter most:
- **F2** decides whether the run gets past G3 at all. It should be settled before signing, with a read-only check of whether the theta procedure still passes on today's label.
- **F1** decides whether a "replace" would mean anything. Today the contest can be won by same-lap timing alone, and the repo already holds a scoping result that says so.

---

## Part 3. The pipeline in plain English (for the owner)

1. **Inputs.** Three things go in.
   - **The corner table.** For every driver, lap and braking corner from 2018 to 2025, it records how far behind the car in front they were just before the corner (in seconds), and how long the corner took them. Where possible, it also records how long the same corner took the same driver on nearby laps in clean air. That is their own "normal".
   - **Today's charge.** A flat 0.331 s for any lap that follows a lap spent close behind another car.
   - **A neutral lap-time yardstick.** Each lap's time with the field's pace, the fuel load and the tyres taken out. It contains no traffic charge.
2. **Clean the data.** Drop corners under safety car, yellow flags, rain, pit laps, track-limits laps, blue flags and off-track moments. Drop flat-out kinks altogether. Drop single corners where a driver lost more than 2 s (incidents).
3. **Measure corner loss.** For each corner where a clean "normal" exists, loss = time taken minus the normal.
4. **Fit the curve.** Using 2022-2024 only, sort following corners into eight gap bands (0-0.3 s up to 2.5-3 s behind) and three corner speeds (slow, medium, fast). Estimate the typical loss in each band, allowing for some circuits and corners simply being different. Then force the curve to never rise as the gap grows. The result is a staircase: lose this much at 0.5 s behind, less at 1.5 s, and so on.
5. **Add it up per lap.** For a 2025 lap, look up each corner's gap on the staircase and add the values, counting stretches where two corners overlap only once. That is the measured traffic cost for the lap.
6. **The contest.** Take each 2025 lap's yardstick time and subtract the traffic charge in three versions: nothing, the flat 0.331, and the measured cost. Remove each stint's own level and the tyre age. Then see which version leaves the smallest leftover error. The score is how much smaller the measured cost's error is than the flat penalty's. Repeat 1,000 times while reshuffling which races count, to see how much of the difference could be luck.
7. **The verdict table.**
   - **Replace** only if all three hold: the measured cost beats the flat penalty by at least 0.5 % even on the unlucky end of the reshuffles (W1); it is no worse for drivers stuck in trains (W2); and the physics makes sense, meaning almost no loss 2-3 s back and fast corners not clearly losing less than slow ones (W3). All set-up checks must also pass.
   - If it wins but fails in trains: **keep the flat penalty and show the new number beside it.**
   - If it does not win, or the physics is wrong: **keep the flat penalty and stop.**
   - If a set-up check fails: **no verdict.**
8. **Reported beside it, not deciding it:**
   - the pit-stop check (when the car in front pits, the follower's sudden gain should be at least what the curve predicts);
   - the same test on the 2018-2021 cars;
   - reruns with different "normal" windows;
   - results per team;
   - 2026, labelled exploratory, once its data can be loaded.
9. **What you get.** A one-page scorecard whose first line is the verdict, followed by every rule, its fixed bar, the result and pass or fail. You read it before anything else uses the number.
