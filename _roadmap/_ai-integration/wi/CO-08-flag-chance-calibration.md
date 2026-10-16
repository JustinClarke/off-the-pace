# CO-08 — Chance to make the flag: calibrated, final stints only

**Status:** BUILDING (on the board; owner go-ahead 2026-10-15). The laps-to-flag cap is built. The chance line is built but FAILS the calibration acceptance on 2025, so it is not shown.
**Group:** D carry-over · **Depends on:** the stint-life promotion decision (which model version feeds it) and the laps-to-flag display (option 1) · **Blocker:** none until those land.

**Sources:** `ml/src/survival.py` (AFT predictions), `ml/src/evaluate.py` (scoring), `ml/src/predict.py` (predictions parquet), `scripts/export_app_data.py`, `app/src/features/degradation-simulator/` (display), `docs/app/` (the page that explains the gauge).

---

## What exists today

- The stint-life model predicts how long a set of tyres can last. On a final stint it answers "how long could these tyres last", not "will they reach the flag". The gauge therefore overstates the stint (see the options memo, 2026-10-15).
- The fixed stint-life model (starting value corrected) predicts the tyre life distribution well enough to beat the baseline. Its predicted chances are too cautious in the middle range: it says 18% where 31% happen, 40% where 68%, and 60% where 84%.
- On 2025 it separates final from non-final stints well (AUC 0.961, Brier 0.090, against 0.245 for always guessing the base rate).

## Goal

On a final stint only, show one number: the chance these tyres last to the flag, `P(tyre life >= laps to flag)`. The number must be calibrated: when it says 60%, about 60% of such stints should reach the flag.

## Method

1. **Define the event.** For each final-stint lap, `laps_to_flag` = race's last lap minus current lap. `reached_flag` = the stint's real end is at or after the flag. Use the same censoring rule the gate already uses, so the event matches the scored data.
2. **Raw chance.** From the fitted AFT distribution, compute `P(T >= laps_to_flag)`. Compute it on out-of-fold predictions (fit on each training fold, predict its held-out season) so no row is scored by a model that saw it.
3. **Recalibrate.** Fit a monotone map (isotonic regression, or Platt scaling if isotonic is unstable on few seasons) from raw chance to observed frequency, on the out-of-fold predictions for 2018–2024 only. Save it as a small JSON lookup (breakpoints and values). 2025 is never used to fit it.
4. **Evaluate on 2025.** Brier score, reliability bins (10 bins), expected calibration error, and the same bins as the options memo so the before and after line up.
5. **Export.** Add `flag_chance` (calibrated) and `flag_chance_raw` to the predictions parquet, final-stint rows only; null elsewhere. The app applies the lookup in the browser, using the same JSON, and a parity test checks it.
6. **Display.** Show the number on the final-stint gauge, beside the capped laps-to-flag from option 1. Label it "chance to reach the flag on these tyres" and say it is a model estimate with its own band.

## Acceptance

- 2025 reliability: each of the 10 bins within 5 percentage points of its observed rate, for bins with at least 100 rows. If fewer bins qualify, say so and do not claim calibration for the rest.
- Brier on 2025 better than the raw chance, and better than always guessing the base rate.
- Browser lookup matches the Python lookup on the sample rows (max difference below the repo's ONNX tolerance).
- The chance is null for every non-final stint.

## Output

A reliability table before and after (raw and calibrated), the Brier and ECE numbers, the lookup JSON with its sha256, and the parity result.

## Risks and limits

- Only one season (2025) is a clean test; the calibration can be checked on 2018–2024 out-of-fold but not on a true holdout until 2026.
- Red-flag-shortened races: "laps to flag" uses the race's actual last lap, so these are slightly optimistic. Report how many rows are affected.
- If the stint-life model changes (for example the fixed version is promoted), the lookup must be refitted. The JSON carries the model version it was fitted on, and the export refuses to run on a mismatch.
- Isotonic can overfit with few seasons. Platt is the fallback, and the choice is recorded in the output.

## Result so far (2026-10-15)

- **Cap (step 6, display part):** built and ready. Shows min(median, laps to flag) on final stints.
- **Choices made where the draft conflicts with itself:**
  - Fit and score on every lap with a known outcome (reached the flag = 1, pit-ended = 0, retirements left out). Final-stint-only fitting would be near-trivial (97.4% reached the flag in 2025).
  - Show the chance only on final stints.
  - Laps to flag = scheduled laps (`race_scheduled_laps` seed) minus current lap. 10 of 173 races were stopped short (2,927 rows, 850 in 2025), so those are slightly optimistic.
  - Platt chosen over isotonic inside the training seasons (Brier 0.0990 vs 0.0993).
- **2025 result:** Brier raw 0.0900, calibrated 0.0823, base-rate guess 0.2454. ECE raw 0.076, calibrated 0.049. Only 4 of 10 bins within 5 points (worst 23 points off).
- **Cause:** drift. Where the model says about 50%, the share reaching the flag was 46% (2020), 65% (2021), 54% (2022), 63% (2023), 74% (2024), 77% (2025). A single fixed map averages that out.
- **Artefacts (scratch only):** `flag_chance_lookup.json` (sha256 456aacc8…1f35, paired with fixed booster v15bs, sha 7537a407…), `predictions_v15bs.parquet`. Code: `ml/src/flag_chance.py`, `app/src/ml/flagChance.ts` and tests. Nothing promoted or committed.

## Fix plan for the drift (not yet run)

1. **Recent-season weighting.** Refit the Platt map on 2020–2024 out-of-fold with weights rising for recent seasons (for example 1, 2, 4, 8, 16 for 2020–2024). Decide the weights before looking at 2025.
2. **Last-N-seasons fit.** Refit on the last 2 or 3 out-of-fold seasons only (2022–2024, or 2023–2024).
3. **Test.** Score each option on 2025 with the same 10 bins and the same acceptance rule. Keep the first option that passes; if neither passes, ship the cap alone.
4. **Caveat.** A pass on 2025 is one clean test, and the choice must not be tuned on 2025 again. The first true out-of-sample check is 2026 data, which does not exist yet. Record that the chance line, if shown, is provisional until then.
5. **Dependency.** Refit on whichever stint-life version is promoted, and regenerate the parity fixture.

## Definition of done

Lookup fitted on 2018–2024 out-of-fold only, evaluated on 2025 with the acceptance bins above, exported with the predictions and the parity test passing. Tests re-run by the orchestrator. Do not commit.
