# WC-10d adversarial review 1: `WC-10-discovery-preregistration-DRAFT.md`

**PARTIAL, review paused** (2026-10-29, at the coordinator's request; the owner continues in a new session).

Reviewer: independent opus-5 agent. It did not write the draft. Read: the draft in full, the plan and its review note, BUILD-ORDER rules 1-8, build-log WC-10b-f `done_when` and DD-WC2/14-21, `data_gate.py`, the `run_wc03.py` globs, `build_pass_table.race_calendar`, and the WC-10a/b/c evidence. Nothing was fitted. No outcome column was read. `data/dev.duckdb` was not touched. No git command was run.

**Provisional verdict: SIGN AFTER FIXES.** Do not sign until B1-B4 are fixed and the unvisited areas (end of file) have been reviewed.

## Verified (read-only)

- The pass-table digest is `188dac5e…` over 8 files, and the sidecar digest is `8595ce93…` over 8 files. Both were recomputed with `data_gate.digest_lines` and both match §0b and §16.
- The scoped bronze set is 517 files: laps 173, telemetry 171 and weather 173 under `season=*/race=*/*.parquet`. Quali laps sit under `session=Q/` and are correctly left out.
- The full set (1,214 files, `aed1c27d…`) includes `schedule/season=*/schedule.parquet`, so the claim in §2 holds.
- `sidecar.py` sha256 is `8d2047b9…`, which matches the WC-10b PROVENANCE.
- `data_gate.py` sha256 is `34da633d…`. It is not recorded anywhere yet.
- The DD-WC2 text and the DD-WC18 second line in §15 are word for word.
- The scratch scripts d01/d02 exist in the session scratch folder. I did not re-run them.

## BLOCKER

**B1. S3 may pass by construction (§11 S3).**
- *Problem:* the draft notes that b_drift is exactly 0 over all free passes, because tyre_life equals lap plus a constant within a group, and α and φ span that. S3 therefore only measures the slope in groups that contain a following pass, *relative to* groups that do not. It follows that b_subset = −(w_complement / w_subset) · b_complement. If most free passes sit in groups that also hold a supported following pass (likely: most stints see some traffic at 0-3 s), b_subset is close to 0 whatever the drivers' own drift.
- *Failure scenario:* every follower drifts at +0.01 s per lap (SG3's plant). The groups without a following pass are few, so b_subset is about 0. S3 passes, and the near band carries 7 laps × 0.01 = 0.07 s of bias.
- *Fix:* (a) Before signing, count the share of 2022-23 free passes that sit in groups with at least one supported following pass, and put that count in §3 item 8. (b) Replace S3 with a statistic that is not tied by the constraint: for example, the slope of free-pass residuals on (tyre_life − the group's mean following-pass tyre_life) among groups with following passes, or a leave-group-out φ/g refit. (c) Make SG3 pass/fail: S3 must fail in at least 80 % of simulations at the planted +0.01 s per lap.

**B2. S2's tolerance scales with the quantity it is guarding, so it lets a large one-sided bias through (§11 S2, §8a).**
- *Problem 1, the tolerance:* T = max(0.5·|β̂_full|, floor). D = full − bracketed. About 21 % of near-band passes are bracketed (fast 1,309 of 5,837; medium 3,215 of 15,362; slow 2,958 of 14,435). Suppose the one-sided passes are biased by b. Then D = 0.79b and full = β + 0.79b, and AGREE holds for any b ≤ 1.27β. The headline can be inflated by up to about 100 % and still pass.
- *Problem 1, the asymmetry:* the same rule catches a downward bias already at b ≈ −0.42β. It is lenient toward inflation and strict toward shrinkage.
- *Problem 2, the bracketed set:* bracketed passes use the same group α̂ (from every free pass, with no distance limit). A linear driver drift δ still enters as δ·(t_i − t̄_free) and is not cancelled. A pass at lap 5 with free passes at laps 4, 28, 29 and 30 counts as "bracketed".
- *Problem 3, the verdict rule:* AGREE is decided on the point estimate, so a noisy (wide) D agrees more easily.
- *Fix:*
  - Compare one-sided with bracketed directly: D′ = β_one − β_brk, with T = max(0.25·|β̂_brk|, floor).
  - Compute the bracketed estimate with a symmetric local baseline: the mean of the nearest free pass before and the nearest free pass after, each within ≤ 5 laps. That cancels linear drift.
  - Make AGREE an equivalence test: the 90 % interval of D′ must lie inside [−T, T].
  - Register the new bracketed counts, which are structural.

**B3. The pass class shares the follower's prediction error with τ (§6h, §6e class curves, S2-aero, S_aero).**
- *Problem:* Δ̂ = ŷ0(L) − ŷ0(F), and τ = y − ŷ0(F). If ŷ0(F) is too fast by error e, τ rises by |e| and Δ̂ rises by |e|, so the pass is more likely to be classed held up. Held-up β is pushed up and dirty-air β down.
- *Size:* with n_F = 2 and σ about 0.06 s, e has SD of about 0.04 s, which is the size of the effect.
- *Why it reaches the aero contrast:* time and minimum-speed errors are correlated (WC-02 check 3, about −0.6), and the error variance differs by class through σ̂_k and n_F. The fast − slow contrast can therefore be created or masked mechanically.
- *Fix:* cross-fit. Compute the class from a step-1 fit on free passes of odd laps, and τ from even laps, or the reverse. Alternatively, compute the class from driver-stint α averaged over all corners of the class, which is about 10× less noisy. Add an SG case with zero planted aero effect: the dirty-air fast − slow contrast must contain 0 in at least 90 % of simulations.

**B4. The bootstrap's race and circuit lists are not enumerated. This is the WC-03 A4/A5 trap (§10, §0b).**
- *Problem:* "the sorted circuit list" and "that circuit's sorted race list" never name their source list. The candidates are: races with kept braking passes (43), bronze laps races (2022 Japan is in bronze but all wet), races with a supported following pass, or races left after trims. The last two depend on outcomes or support. The lap arm reads bronze laps, which hold more races. WC-03 lost its run over exactly this kind of ambiguity (A4 ruling 4b, A5).
- *Fix:* put the 43 `race_id`s and their 24 circuit keys in an appendix as a fixed literal list, and state that the plan draws over this list for every arm, including the lap arm and the diagnostics. Add a test that the run refuses if `race_calendar` yields a different mapping.

## SHOULD-FIX

**S1. The restart rule has a code-change loophole after RUN START (§0a).**
- *Problem:* a crash after outcomes are decoded in memory but before anything is written is "restartable under the same conditions". But a code bug cannot be fixed without changing code. §0 counts any amendment made while the ledger shows nothing written as "pre-result", so an agent could change estimator code after outcome-dependent behaviour (which branch crashed, how many iterations ran, a NaN) without it ever counting as post-hoc.
- *Fix:*
  - Add a ledger line, `OUTCOME DECODED`, at the first decode.
  - After that line, a restart is allowed only with byte-identical code, for infrastructure causes (OOM, kill, disk).
  - Any code change after that line is a post-hoc amendment.
  - Tracebacks and logs before the first write must print no values.
  - SG1-SG5 must pass on the committed code before RUN START.

**S2. The fallback F1 is unguarded (§11, §9a).** It needs only the lower end of Near_lap > 0. The lap arm has the same one-sided and drift exposure as design A, but it has no bracketed check and no drift check. If design A fails S2 or S3 because of drift, the fallback still passes on that same drift. *Fix:* apply the S2 rule (as fixed in B2) to the lap arm's bracketed companion. Otherwise, label the FALLBACK line "drift unchecked".

**S3. Contradictory definitions of a scored lap and of racecraft (§9a vs §13 item 7).** §9a defines a scored lap as having no racecraft pass. §13 prices racecraft corners on "every scored lap" and defines a following lap to include racecraft. *Fix:* define a separate "score lap" for §13: every braking corner eligible or racecraft, `LapTime` not required.

**S4. The inputs for X6 are missing from §2.** The identity-matched release set needs pit-entry laps. §2 reads only `Driver`, `LapNumber`, `LapTime` and `Team` from bronze laps. *Fix:* name the pit columns and their source, as r02 used them, in §2 (for example `PitInTime`).

**S5. Thin compound cells turn g into a driver-specific slope (§6d).** A non-reference compound at a race with free passes from 1-2 drivers gets θ1 and θ2 fitted to those drivers' own late-stint free passes. That is a personal quadratic, extrapolated to their early close passes, which contradicts D4. Rank deficiency is also possible. *Fix:* require free passes from ≥ 3 distinct drivers per (r, m, k), or else pool θ over m at that race. Report the count of cells.

**S6. Choices are left open: the agent decides after decoding (practicality, question 4).**
- σ̂_k: with or without a degrees-of-freedom correction for α and φ (singleton φ cells deflate σ̂, which inflates held up).
- n_W: counted before or after the free-pass trim.
- Support, bracketing and the reference compound: fixed per outcome, or from the time-outcome set (the trims are per outcome).
- Ties for the reference compound.
- Trims for coast and throttle in X5 (none are defined).
- How S_aero handles the 0-0.3 s bin and racecraft.
- The previous-lap pass when it is excluded (`prev_lap_reason` not null).
- The meaning of "tolerance 1e-10": max-abs or relative.
- Whether racecraft counts in the stint close share.

*Fix:* fix each one in §6 and §8.

**S7. Registered numbers rest on session scratch (§3 item 8, D6).** "580", "8.1 %", "14.1 %" and the bracketed counts come from `/private/tmp/...` scripts. Rule 8 intent: copy d01/d02 and their outputs into `_evidence/WC-10-2026-10-29/counts/` with a PROVENANCE file before signing.

**S8. Seen-list gaps (§3).**
- The DA-03 dirty-air method (the shipped tax, plausibly fitted on 2022-25 by gap) is not declared as known to exist, even without numbers.
- The WC-02 release-event results (530 events "with readings on both sides", per plan §3 C) are not declared. They may be loss values by traffic state, including 2024-25. This is not yet verified.
- The 16 coast values > 30 s were counted over 2018-25, including the sealed seasons.
- The WC-03 run's G3.1-G3.3 printed values (a pooled slope, 0.4777) are not checked.
- The §3 statement that "nothing by gap" has been seen should be qualified accordingly.

## NOTE

- **N1:** the quantile "maximum" exists by construction: 2 % of scored following laps get it whatever the effect size. With a pooled curve, S is mostly exposure (the count of near corners). "Maximum" will therefore mostly land on stuck, `extrapolated` stints. State this beside DD-WC17.
- **N2:** trains. The class rule compares free-air predictions. A car behind a held-up car ahead is classed dirty air. Consider a "train" tag (car ahead itself < 1 s behind its own car ahead) as a diagnostic.
- **N3:** `data_gate.sha256sums_mismatches` filters `pass_table_` lines. Check 3 needs a `sidecar_` variant, and checks 3 and 4 are not pass/fail in `main` yet (§16 says so).
- **N4:** the file name differs from WC-10d's `done_when` (the draft says so).
- **N5:** §8a quotes the 22 % / 60 % shares under the review's "≥ 2 close and ≥ 2 free" rule, while D5 uses "≥ 2 free". Say which definition each figure uses.
- **N6:** θ_carry's C_l rises with lap within a stint, so it is confounded with driver-specific wear. This is acceptable, since tyre is expected to show "—".

## Not reviewed (resume here)

1. Independent recount of the §3 item 8 numbers. Planned but not run: 421,764 passes; 43 races / 24 circuits; supported close 52,164; bracketed 11,110; φ windows 124,041 / 8,957 / 5,371 / 12,131. Also the counts B1 needs (the free-pass share in groups with following passes), S5 (thin compound cells) and N2 (trains).
2. φ drop rule (question 1): whether dropped passes concentrate in particular races or circuits (per-race φ-unsupported share), and so whether they distort the cluster bootstrap.
3. Catching, DRS and release mitigations in depth (§8d, X4, X6), and whether X6's 87 events match `c2_release_by_season.csv`.
4. Tyre damage carried from the wake raising α, and pushing after release: a proposed "post-release washout" variant (drop free passes within 3 laps after a following spell from step 1). Not yet written up.
5. SG1-SG5 adequacy (§17): whether the planted designs exercise B1-B3, and whether ±10 % bias at 200 × 200 is achievable and meaningful.
6. Seal enforceability (§4) beyond S8: the 2024-25 sidecar outcomes are computed and on disk, and the guard covers only WC-10e code.
7. A line-by-line check of the §0b table against the body for every row (rows 1-12 checked; the coverage floor, cut points and synthetic rows were not).
8. The WC-04 run evidence: what G3.1-G3.3 printed.
