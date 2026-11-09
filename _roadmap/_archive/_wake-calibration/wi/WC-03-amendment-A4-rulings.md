# WC-03 pre-registration, amendment A4: empty gap bins (G7), the A1 clarifications, the step-3 label, and the contest readings the code needs

**Status: DRAFT. Not committed, not hashed. Decisions recorded 2026-10-28 by the Opus session as an Opus decision delegated by the owner; not the owner's personal signature.** The owner, through the coordinator, said yes to these rulings on 2026-10-28; this file is still a draft until the owner commits it alone and its SHA-256 is recorded on WC-03 in `status/build-log.json`. It amends `wi/WC-03-preregistration-DRAFT.md` (signed 2026-10-28, SHA-256 `518c3348a619ebf6a964486bbe6313dcdc86c64ae05ca3daed8db202d9653a63`, commit `839e0f4`) and is read beside amendments A1, A2 and A3. The registered text and A1-A3 are **not edited**. Where this file and the registered text or A1 differ, this file governs once it is committed and hashed.

**When it was made, stated plainly.** Drafted 2026-10-28, after the synthetic G1 (i) failure that led to A1, and after A1-A3 were committed (5aee6b2, e310510, 83134a3). **No real-data result has been seen:** nothing has been fitted, scored, classified or gated on the pass table, the warehouse or the bronze files; G2 and G3 have not been run; `data/dev.duckdb` was not opened. It is a pre-result amendment in the sense of §0. Like A1 it was not written blind to the synthetic results; no ruling here depends on a real-data number.

**Nothing else changes.** No threshold, margin, season split, bin, trim value, minimum, B, seed or verdict rule changes. Each ruling below either closes a gap the registration leaves open or confirms a reading the code already uses.

---

## Ruling 1. A gap bin with no fit pass (A1 item 2): G7

**Question (A1 item 2).** When a gap bin has no fit pass in a corner class, in the point fit or in a bootstrap draw, the bin's fixed effect is not identified. Should that be a setup check G7 in §12a, a new first-row condition in §9, or both? And what happens to P2?

**Options.**
- (a) **G7 in §12a only.** §9's first row already reads "Any check in 12a fails … → no verdict", so a G7 failure is no verdict without editing §9.
- (b) **A §9 row only**, no new gate. The failure would not appear in Table 1's G-rows, and the scorecard would need a separate line for it.
- (c) **Both** (A1's proposed wording). Says the same thing twice; two places to keep in step.

**Choice: (a), G7 in §12a; §9 is not edited.** G7 covers both curves that feed a verdict:

> - **G7 curve identified (amendment A4):** (1) in every corner class, every gap bin of the **main curve** has at least one fit pass in the point fit and in each of the 1,000 draws; and (2) in the **fast** and **slow** corner classes, every gap bin of the **dirty-air class curve** has at least one fit pass in the point fit and in each of the 1,000 draws. If not: no verdict, and the scorecard's first line says which curve, which corner class, which bins, and in how many draws. No bin is merged, no prior is used, and no draw is skipped or redrawn (B stays 1,000).

**Reasons.** One mechanism: §9 already turns any §12a failure into no verdict, and Table 1 already lists G1-G6 with pass/fail, so G7 sits where a reader looks. A second statement in §9 adds nothing and could drift.

**P2 consequence (stated so it is not decided silently).** P2 (§10) needs the dirty-air curve's 0.5-1.0 s mean in the fast and the slow class, with an interval over the draws. The REML fit estimates all 8 bins jointly, so an empty bin anywhere in that class leaves the class curve unestimated. Without this ruling an empty bin there would make P2 incomputable, so W3 could be neither passed nor failed. G7 part (2) moves that case to a setup failure: **no verdict**, never "W3 fails". The held-up class curve and the medium-class dirty-air curve feed no verdict input. For them an empty bin still means "not estimable" (reported, "—" with the reason), and the run goes on.

Code: `contest.g7_curve_identified`, `contest.verdict` (synthetic tests `test_a4_g7_*`).

## Ruling 2. The A1 clarifications

**2a. G1 (i) coverage is read per bin.** Options: per bin (each of the 8 bins ≥ 0.90 on its own), or pooled (share of all 8 × 200 bin-intervals ≥ 0.90). **Choice: per bin.** Reason: it is the stricter reading. A pooled share can pass with one bin badly under-covered, and every bin enters P1 or the contest. The A1 numbers (registered model 0.910-0.945) pass under either reading, so the choice does not rescue anything.

**2b. The §6 corner random effect is nested in the circuit (`circuit|corner_id`).** Options: nested, or crossed (one group per `corner_id` label across all circuits). **Choice: nested.** Reason: the builder's `corner_id` is the circuit's own corner number with a letter suffix (`build_pass_table.corner_table`: `corner_number` + letter). Corner "4" at Monaco and corner "4" at Monza are different corners, so a crossed effect would pool unrelated corners under one label and has no physical meaning. The closed-form REML likelihood in `estimator._reml_parts` also assumes nesting. A circuit with a different layout is already a separate circuit key (`SEPARATE_LAYOUT_SLUGS`, §6).

**2c. The G1 (i) simulation design.** **Choice: confirm the design A1 reports as the G1 (i) design, and require both arms to pass.** The two arms are (1) the registered model: circuit SD 0.05 s, corner SD 0.05 s, race shock SD 0.03 s, noise SD 0.15 s, 68 races on 23 circuits, 8 corners per circuit, 30 passes per (race, corner), true curve 0.30 … 0.01 s; and (2) race shocks only, with the same noise and layout. The other option was to fix only arm (1). Reason for keeping both: arm (1) is the model §6 registers. Arm (2) checks that the circuit-then-race resample does not fail when there is no circuit effect; it is conservative there (0.975-0.995). Disclosure: this design was in use when the race-level bootstrap failed. It was not changed afterwards, and it was not tuned to make A1 pass.

## Ruling 3. §8a step 3 (the ±5 s trim) gets a registered label

**Options.** `residual_beyond_5s`, `baseline_outlier`, or `trim_5s`. **Choice: `residual_beyond_5s`.** Reason: it names the quantity and the fixed threshold, in the style of A3's `stint_under_2_laps`.

**Exact new text, §8a Formal, step 3**, replace with:

> 3. On the set from step 2, regress `partial_residual_s` (no traffic term) on `stint_id` and `age_bin` indicators once (ordinary least squares, every lap weight 1); drop laps with |residual| > 5 s (strictly greater). Each dropped lap is counted under `residual_beyond_5s` (amendment A4). The regression is run once on the real held-out sample and is not repeated inside bootstrap draws.

§8a step 5 as amended by A3 now lists, at step 3, the reason `residual_beyond_5s`. The older-car check applies the same step to 2021.

Code: `contest.STEP3_REASON`, `contest.step3_trim_reason` (synthetic tests `test_a4_step3_*`).

## Ruling 4. Readings the contest code needs (the registration leaves them open)

None of these changes a threshold. Each is fixed now, before any result.

**4a. Frequency weights for repeated races in a draw.** §8c says a race drawn twice "counts twice and its stints count as separate stints". The code gives each race a frequency weight equal to its draw count. Stints keep one id, and the stint-and-tyre-age least squares (θ_now in §2d, rescoring in §8b step 3) is solved with those weights; MSE is the weighted mean. **Reason:** the least-squares solution is unique, and k copies of a stint under k separate ids are symmetric. Each copy therefore gets the same stint level as the weighted fit, and the residuals are the same. The two are the same computation, and the weighted form is about k times cheaper. The equality needs one weight per stint. A race weight gives that, because every stint lies inside one race. The code refuses a weight that varies inside a stint, so a `stint_id` that spans two races stops the run before any score. A synthetic test checks the equality (`test_a4_weighted_equals_separate_copies`).

**4b. θ_now's fit races in a draw.** θ_now is refitted on the drawn fit races (A1: race multiplicities over all circuit copies; a circuit copy has no meaning for θ_now). The yardstick panel's 2022-2024 races must be the same set as the curve's fit races. If a race is in one set and not the other, the run stops with an error before any score. **Reason:** §2d and §8c say θ_now and the curve are refitted "on the same drawn fit races". A race with panel laps but no fit passes has no place in the plan, so it could not be drawn.

**4c. A scored lap whose braking corners are all `no_car_ahead`.** The §5 clean-reference rule ("at least half of its braking-corner passes, excluding `no_car_ahead`, have `ref_status = measured`") has an empty denominator for such a lap. **Choice:** the lap is in the **clean-reference half**. **Reason:** the lap was in clear air throughout. In the no-reference half it could never be a train lap anyway, because its median gap is counted as 3 s.

**4d. Which interval end and which point.** W1 uses the 2.5th percentile of the B draw values of `R_flat` and `R_now` on all scored laps. W2 uses the point estimate (point curve, point θ_now, all scored laps) and the 2.5th percentile on train laps. P1 (a) and (b) use the point main curve. P1 (c) uses the 2.5th percentile of the draw values of near − far. P2 passes unless the 97.5th percentile of the draw values of (fast − slow) is below 0 ("wholly below zero"). If a W1, W2, P1 or P2 statistic is undefined in any draw (for example, a set has no laps in that draw), its interval is not taken over fewer than B draws. The result is no verdict, with the reason, as for G7.

**4e. The verdict table is read top to bottom, exactly as §9:** a setup failure (G1-G7, a G5 minimum, or an undefined statistic under 4d) gives no verdict; then W1, W2 and W3 all pass gives replace; then W1 and W3 pass with W2 failing gives keep and show; then W1 failing gives keep and stop; then W3 failing gives keep and stop. Code: `contest.verdict`.

**4f. Unavailable values.** Any figure that cannot be computed (a not-estimable class curve, an undefined cell, a set below its minimum) is printed as "—" with the reason, never 0. The WC-03/WC-04 scorecard contains no modelled value (WC-05's tier). If one is ever added, it carries the DD-WC2 disclaimer word for word.

---

## Decision record

**Decided 2026-10-28 by the Opus session, as an Opus decision delegated by the owner (owner's yes relayed by the coordinator, 2026-10-28); not the owner's personal signature.**

- Ruling 1: option (a), G7 in §12a, covering the main curve (all classes) and the dirty-air class curve (fast and slow); §9 not edited; an empty bin there gives no verdict, never a W3 fail.
- Ruling 2: per-bin coverage; corner nested in circuit; the two-arm G1 (i) design as reported in A1, both arms must pass.
- Ruling 3: §8a step 3 label `residual_beyond_5s`, with the exact text above.
- Ruling 4: readings 4a-4f as written.
- No threshold, margin, B, seed, season split or verdict rule changes.

## After the decision is recorded

1. The owner commits this file alone.
2. `shasum -a 256 _roadmap/_wake-calibration/wi/WC-03-amendment-A4-rulings.md` on the committed text; record the digest and commit on WC-03 in `status/build-log.json`, beside those of A1, A2 and A3.
3. Nothing is fitted, scored or gated on real data before step 2 (BUILD-ORDER rule 4). The real-run CLI (`run_wc03.py`) refuses to start until all four amendment digests are recorded and match the committed files.
