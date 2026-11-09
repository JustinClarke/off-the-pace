# WC-03 lead session: decision record, 2026-10-28

**Status: DRAFT. Opus-delegated: decided by the Opus lead session under the owner's delegation of 2026-10-28; not the owner's personal signature. Not committed, not hashed.** Nothing here changes the registered method (pre-registration SHA-256 `518c3348…`, amendments A1-A4). Where a decision would change it, it is written as a proposed amendment (A5, `WC-03-amendment-A5-noise-DRAFT.md`) and is not applied.

**What had been seen when each decision was made.** No fit, gate (G1-G7 on real data), score, curve, class count or loss value. data/dev.duckdb was not opened, hashed or copied (its modification time was read with `stat`: Oct 26 12:12, unchanged since the WC-01 notes). The bronze files were not hashed (that is G3 check 4). The decisions below are numbered in the order they were written, and each was written before the counts it governs were run.

---

## L1. The pass-table artefact was the wrong build (written before any count)

- **Found.** `_artifacts/WC-01-pass-table/` holds the **first** WC-01 build (pass "a": SHA-256 `7c841ec8…` to `42d2f635…`, builder `d6615439…`). It has 34 columns, no `segment_basis`, and still carries `flat_kink` and the whole-lap yellow rule. The registered table (§2a; WC-02 PROVENANCE; WC-01 PROVENANCE fourth section) is pass "d" (`d343a5be…` to `bd4c2e4a…`, races `de680b39…`), built by `016c3bd6…`, which is the committed builder (97e0760 and HEAD).
- **Decision.** Copy the surviving WC-02 scratch rebuild (`wc01re/full`), which matches pass "d" byte for byte on all eight seasons and `races.csv`, into `_artifacts/WC-01-pass-table-d/`, with SHA256SUMS. Leave the old folder in place with `SUPERSEDED.txt` for the owner to delete. This is not a rebuild and changes no input of the registered run: the run rebuilds into scratch with the committed builder anyway (§2a, G2).
- **Why.** Every count in this session must be on the registered build; pass "a" would misstate every exclusion count.

## L2. Counting rules for the noise inventory (outcome-blind; written before any count)

- Counts on real data use **structural columns only**: season, race, race_id, driver, lap, stint, compound, corner_id, corner_number, corner_class, segment_basis, gap_s, gap_n, clear_ahead, behind_1s, tag, reason, clean, ref_status, ref_n, leader, leader_lap, leader_track_limits, marshal_sector, layout_changed, circuit_info_season, circuit_match; and from bronze laps, Team, Deleted, PitInTime/PitOutTime, LapNumber.
- **Never read or aggregated:** `seg_time_s`, `ref_time_s`, `delta_time_s`, `min_speed_kph`, `apex_kph`, `brake_offset_m`, lap times. These carry the outcome.
- **Not run on real data:** `estimator.prepare_passes` (it classifies passes into held up / dirty air, which A2 forbids before the hashes are recorded), `pass_class`, `fit_passes` (it applies the ±2 s loss trim, which reads the outcome), G2's byte comparison, any G3 check.
- "Fit-eligible, before the loss trim" = §6 fit set without the `|delta_time_s| ≤ 2.0` clause: fit seasons, braking corner, reason NULL, not `no_car_ahead`, `ref_status = measured`, not yielding, `0 ≤ gap_s < 3.0`. It is counted per corner class and gap bin, with distinct races per cell. This is **not** G7: G7 is on the trimmed set, in the point fit and in each of 1,000 draws, and is not computed.

## L3. Readings for §11 (pit-stop comparison group, adjusted jump, predicted drop)

§11 leaves these open; each is fixed here before any event is built on real data. All are report-only (Table 2) and never enter the verdict.

1. **Comparison pair.** A (follower F, car ahead A, lap P) in the same race as the event where: on laps P−2 and P−1, F has A ahead at every braking corner, F is on A's lap at each of them (`lap = leader_lap`, the §11 "same lap numbers"), and the mean gap is in a band; neither F nor A has a pit in or out on P−2 to P+2; F has an outside reference (laps P−6..P−3 and P+3..P+6, same rule as the event); and the jump is defined on at least one corner. The comparison jump is computed with the event's own function (`_pit_jump`) at P.
2. **Cell.** Same race, same gap band, |P − L| ≤ 5. Bands are [0, 0.5), [0.5, 1.0), [1.0, 1.5). An event whose mean gap is below 0 has no band and is dropped as `no_band`. An event with no comparison pair in its cell is dropped as `no_comparison` (§11).
3. **The event itself is never its own comparison**: the car ahead pits at L, so any pair with A = the pitting car and |P − L| ≤ 2 fails "A has no pit on P−2..P+2".
4. **Predicted drop** uses the same corners and rows as the event's jump (corners with a reference and a timed pass on both sides): mean of curve(class, gap) over those rows on L−2, L−1 minus the mean over them on L+1, L+2. The curve is applied as §6 says (`no_car_ahead` gives 0, gap ≥ 3 gives 0, gap < 0 gives the first bin). A row with a car ahead but no gap cannot be priced; the event is then dropped as `no_prediction`.
5. **Bootstrap.** The adjusted jump's interval is race-level (A1: §11 unchanged). Event races (all seasons the figure covers) are resampled with replacement to their count, B = 1,000, with numpy `default_rng([20261027, 11])`, a stream separate from the curve plan so that the plan's draws are unchanged. In draw i the predicted drop uses curve draw i from the main plan (A1: "where the ratio needs curve draws, they come from the same plan"). Ratio in draw i = weighted mean predicted ÷ weighted mean adjusted jump. 95 % percentile intervals.
6. **Minimum.** Fewer than 200 distinct stops after every drop: counts only, marked "not testable" (§11).
7. **Pit laps.** From bronze laps: `pit_in` = PitInTime not null, `pit_out` = PitOutTime not null, per (season, race_id, driver, lap). This is the same source the builder uses for `pit_lap`.

## L4. Readings for the §12b sensitivity runs

1. **±2 and ±6 windows.** References are rebuilt from the pass table with the builder's own rule (`build_pass_table.references`, same clean definition, `REF_MIN_N = 2`) at a half-window of 2 or 6 laps, through a new optional argument whose default is 4. The default leaves every builder output unchanged, so G2 is unaffected (a test checks that half-window 4 reproduces the stored columns). Then the whole chain is rerun: prepare, fit, class curves, θ_now, scored set (the clean-reference half and train laps depend on the reference), contest, W1-W3, with the same seed and B = 1,000.
2. **Without 2024 Las Vegas.** Its passes are removed from the fit and its laps from the θ_now panel. A4 4b requires the two race lists to match, so both lose it. Everything else is unchanged, including the 2025 scored set.
3. **Reporting.** Each run reports W1, W2 and W3 as figures, never pass or fail. If W1 holds in the main run but not in a sensitivity run, the scorecard says so in its first lines (§12b). A sensitivity run's own setup failure (for example an empty bin) is reported as "—" with the reason.

## L5. Coverage per team

- **Team** = bronze laps `Team` for (season, race_id, driver), taking the most frequent value if a driver has more than one. A driver with no bronze lap row gets "—".
- **Now (count only, pass table):** per team and season, the share of following braking passes with a measured reference. "Following braking passes" = braking corner, reason NULL, not `no_car_ahead`, finite `gap_s < 3.0` (negative included), the §5 set.
- **At the run (report only):** per team, the share of scored 2025 laps in the clean-reference half, and the contest point R_flat and R_now per team, with laps and races. No interval and no minimum is registered for teams, so none is invented; a team with no scored lap shows "—".

## L6. The older-car run in the CLI

- After the main era, `run_wc03.py` runs `run_era(era="older")` on the same prepared passes and panel: fit 2018-2020, held out 2021, its own curve and θ_now, the same B and seed. Its setup checks are G1-G3 (shared), G4 and G6 on 2021, and G5 without the fit-race minimums (§8c sets those for the main era only).
- Output goes to `older_*.csv` and to Table 2 of the scorecard. Its verdict line is printed as "older cars (context, never the verdict)". It cannot change the main verdict.
- The older run starts only after the main SCORECARD.md is written, so a crash in it cannot lose the main result.

## L7. An integrity pre-flight on the real pass table (written before it was run)

- **Why.** The noise counts (L2) showed that only 66 of the 68 main-fit races have a fit-eligible pass: 2022 Japan (`2022_18`) and 2024 São Paulo (`2024_21`) are entirely wet. The run builds its bootstrap plan from the races that contribute fit passes, while θ_now uses every 2022-2024 race in the yardstick panel. If the panel holds any lap of those two races (it drops only laps flagged for rainfall), A4 ruling 4b stops the run with an error. That happens **after** G3 is written to PROVENANCE.txt, which §0 counts as a completed run: no verdict, no rerun. This is written up as draft amendment A5 (`WC-03-amendment-A5-fit-race-list-DRAFT.md`) and is not applied.
- **Decision.** Before the run, check the pipeline's own data-integrity assertions on the real pass table, so any other crash of this kind is found now and not during the one run. The pre-flight prints **only pass/fail and row or race counts**. It runs: calendar coverage (`circuit_of`), one circuit per race, one season per race_id, unique (race, driver, lap, corner) rows, the reference-donor identity in `reference_spread` (an equality assertion between the stored reference and the median of its donors; it prints no time), and the fit-race list per era against the built races.
- **Not run:** `racecraft`, `pass_class`, `prepare_passes` as a whole, `fit_passes`, any curve, the panel, any gate. No time, loss or speed value is printed or saved.

## L8. Readings fixed while building (synthetic only; before any real run)

1. **§11, beyond L3** (`pitstop.py`, written by a forked Opus agent of this session):
   - "No car ahead" in the predicted drop means `clear_ahead` true or `reason_wc03 = no_car_ahead`. §11 uses braking corners whatever their exclusion reason, so a clear-air row on an excluded lap is priced 0, not dropped.
   - The ratio is mean predicted ÷ mean adjusted jump over the kept stops. It is "—" when the mean adjusted jump is 0, at the point or in any draw.
   - Any NaN in a curve draw makes the predicted-drop and ratio intervals "—". The adjusted-jump interval needs no curve and is still given.
2. **Table 2 steps never change the verdict.** Each report-only step runs after the verdict and Table 1 are written to SCORECARD.md. A step that raises is logged in PROVENANCE ("TABLE 2 <step>: not computed (…)") and shown as "—" with the error type. The other steps go on. A W, P or G check is never caught this way.
3. **A4 ruling 4b as written, inside the run.** While A5 is undecided, if the curve's fit races and θ_now's panel races differ for the main era, the run writes "No verdict … Fit-race list … (A4 ruling 4b; see draft amendment A5). Nothing was fitted or scored." and stops before any curve. This is what A4 4b says ("the run stops … before any score"), recorded instead of a traceback. The CLI's pre-flight refusal (before G3) normally prevents reaching it. For the older era the same mismatch skips the older run with "—" and the reason.
4. **Sensitivity runs under A5.** The Las Vegas run removes 2024 Las Vegas from the fit-race list too. The ±2 and ±6 runs use the main run's fit-race list.
5. **The order of the run and the evidence folders.** All outputs go to one `--evidence-dir`. §15's split into `WC-03-<date>/` (curve) and `WC-04-<date>/` (verdict), and the §15 chart, are left as presentation work after the run; neither changes a number.
