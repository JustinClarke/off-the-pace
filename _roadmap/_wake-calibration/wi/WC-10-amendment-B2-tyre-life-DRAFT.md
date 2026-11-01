# WC-10 discovery registration, amendment B2: rows with missing tyre_life leave step 1, are counted, and the θ layout is computed after the drop

**Status: DRAFT, unsigned, not committed, not hashed.** The three rulings below were accepted by the owner on 2026-10-30 (DD-WC23, "yes to both"; the recommendation taken was layout AFTER the drop). They are written down here by the Opus session. This file is not the owner's signature. It stays a draft until the owner commits it alone and its SHA-256 is recorded on DD-WC23 in `status/build-log.json`. It amends `wi/WC-10-discovery-preregistration-DRAFT.md` (signed 2026-10-30 under DD-WC20, SHA-256 `4d679bf6c94b12cf186776467478400c1feef89930be87d3fe36be49f1e8d248`, commit `6fd0330`), as already amended by `wi/WC-10-amendment-B1-open-choices-DRAFT.md` (commit `b89e54c`, SHA-256 `c9566233bb25dcf078a8cc336682b289ec2d7494cfe6fb7189662d3c56b7b500`). **Neither the registration nor B1 is edited.** Where this file differs from them, this file governs once it is committed and hashed.

**When it was made, stated plainly.** Drafted 2026-10-30, after the WC-10e code was committed (`1a9ef80`) and after a first SG1-SG7 attempt was stopped. **No outcome has been read.** No WC-10 run ledger exists (`_evidence/WC-10-discovery-<date>/` has not been created). RUN START has not been written, and no outcome column has been decoded: not `seg_time_s`, `min_speed_kph`, the sidecar speeds or bronze `LapTime`, and not `seg_start_t` or `seg_end_t` (B1 B-i). Nothing has been fitted on real data, and `data/dev.duckdb` was not opened. The problem was found from **structure columns only**, with a fake outcome (random normals, and a placeholder lap time of 0.0) used solely to exercise the solver on a scratch copy of the logic. This is a pre-result amendment in the sense of §0: at the moment it is committed, the run ledger (§16) shows no outcome-derived number written.

**Why it is needed.** In two 2022 races, some rows that §5 counts as eligible have no `tyre_life`. The tyre term in step 1 (§6d) multiplies by `tyre_life`, so those rows put NaN into the solver. Step 1 then never converges. §6b says what that means: "failure to converge is a run error and a post-hoc amendment case". With the real `seg_time_s`, design A would stop at RUN START in all three corner classes, and the lap arm would stop too. After `OUTCOME DECODED`, that stop is an ordinary Python exception, not an infrastructure cause, so the run could not be restarted without a post-hoc amendment (§0a). It has to be settled now. Changing the solver or its tolerance does not fix it (section B), and §5 does not exclude these rows. So this is an amendment, not just a code fix.

**Nothing else changes.** No threshold, tolerance, floor, trim, window, bin, minimum count, B, seed, season split, circuit or race list, or go/no-go rule changes. The convergence rule of §6b (1e-10, at most 10,000 sweeps) stays as it is. **This file is committed before the code fix is committed, before SG1-SG7 are re-run, and before RUN START.**

---

## A. The owner's rulings

### Ruling 1. tyre_life is required for a row to enter step 1, in design A and in the lap arm

**Registered text.** §5, Eligible pass: "Pass-table row, season ∈ {2022, 2023}, `segment_basis = brake_onset`, `reason` NULL (…), `tag` not `yielding`/`lapped+yielding`, `stint` not NULL, `compound` not NULL." §6b: "y_j = α[G] + φ[r, c, l] + g_k(tyre_life_j; r, compound) + γ_k · behind_1s_j + ε_j", fitted by alternating projections, "converged when the largest absolute change of any coefficient in one sweep is below 1e-10 …, at most 10,000 sweeps; failure to converge is a run error and a post-hoc amendment case." §6d: "`g_k(t; r, m) = θ1[r, m, k]·t + θ2[r, m, k]·t²`, with t = `tyre_life`". §9a: "Step 1 on free laps: `LapTime = α[race, driver, stint] + φ[race, lap] + g(tyre_life; race, compound) + ε`, with g as in §6d".

**The gap.** §5 asks only for a non-null `stint` and `compound`. It does not ask for `tyre_life`. But step 1 cannot be computed on a row without it, and the registration does not say what happens to such a row.

**Ruling: required.** A row with `tyre_life` missing does not enter step 1. This holds for design A (every outcome, every class) and for the lap arm (§9a). It also leaves everything counted from the step-1 free set, as ruling 1 of B1 does for racecraft: the ≥ 2 support floor (§6a), the lap arm's ≥ 3 free-lap support (§9a), the φ driver counts n_W (§6c), the thin-cell driver count and the reference compound (§6d), the bracket (§8a), N_F and N_L (§6h) and the S3 population (§11). A following row with `tyre_life` missing cannot be predicted (ŷ0 needs g(t)), so it leaves every average too.

**Reason, in plain English.** The model's tyre term needs the tyre's age. A row without it cannot be fitted and cannot be predicted. Leaving it in stops the whole fit (section B). Filling in an age would invent data. Dropping the row and counting it is how the registration already treats a pass it cannot use.

### Ruling 2. Each dropped row is counted under its own reason, `tyre_life_missing`

**The gap.** As committed, the code has no count for these rows. In the lap arm, the 78 following laps with `tyre_life` missing (69 in 2022_11, 9 in 2022_7) get a NaN τ and fall out through `np.isfinite(tau)` in `lap_arm.fit_lap_arm` without being counted anywhere. They vanish silently.

**Ruling: a named reason, counted.** Every row left out because `tyre_life` is missing is counted under the drop reason **`tyre_life_missing`**, in the outputs and in the run ledger. That covers:
- design A free passes left out of step 1, per class and outcome;
- lap-arm free laps left out of step 1;
- lap-arm following laps, the 78 above included;
- design A following passes whose prediction is missing because `tyre_life` is missing (section C, item 4).

No row with `tyre_life` missing may leave a set without being counted.

**Reason, in plain English.** A drop that is not counted cannot be checked. Every other exclusion in the registration is counted. These should be too, so a reader can see how much of 2022_7 and 2022_11 is missing.

**Builder note, for the owner to confirm before commit (not ruled).** A row can meet two drop reasons, for example a free pass that is both racecraft and missing `tyre_life`. The rulings do not say which reason counts it. This draft proposes that `tyre_life_missing` is checked **after** the reasons that exist now, in the order the code already uses (racecraft, support, φ, outcome null, and so on). The existing counts then do not change, and `tyre_life_missing` counts only rows that nothing else had already removed. The owner may rule another order before committing this file.

### Ruling 3. The θ layout (§6d) is computed after the drop

**Registered text.** §6d: "For each (r, k), the compound with the most free passes is the reference … **Thin cells:** a (race, compound, class) cell is estimated only if its free passes come from ≥ 3 distinct drivers. Otherwise a thin compound takes the reference compound's curve". §6a: "The support flag, the bracket flag, the φ windows, the reference compound and the pass class are computed once from the `seg_time_s` free-pass trim and reused for every outcome."

**The gap.** The reference compound and the thin-cell test count free passes and distinct drivers. They can be counted before or after the rows with `tyre_life` missing are removed, and the answer can differ.

**Ruling: after the drop.** The reference compound, the thin-cell test and the parameter count are computed on the free set that actually enters step 1, with the `tyre_life_missing` rows already removed. That holds for design A (per class, from the `seg_time_s` free-pass trim, §6a) and for the lap arm.

**Reason, in plain English.** The layout should describe the data that are actually fitted. A layout built on rows that are then dropped could keep an "estimated" cell whose drivers are no longer there.

**Side effect, stated so it is not hidden.** In 2022_11 the compound `UNKNOWN` moves from **estimated** to **thin**: it takes the reference curve at that race. In the lap arm, `n_params` goes from **151 to 149** (its θ1 and θ2 are no longer estimated). In design A the same cell changes the same way in all three classes on the pre-trim free set: fast 135 → 133, medium 153 → 151, slow 153 → 151. The design A figures are counted **before** the §6f (i) trim, because that trim needs `seg_time_s`. The run-time numbers are recomputed and reported (§13 item 2). No other (race, compound) cell changes status.

---

## A2. Label alignment (no change in behaviour)

**The mismatch.** B1 ruling 5 and section D(2) say `duplicate_race_in_copy = "copy"`. The committed code (`design_a.RULED_CHOICES`, commit `1a9ef80`) says `"separate_copy"`. The behaviour is the one B1 ruled (a race drawn twice within one circuit copy is a separate copy, with σ̂'s degrees of freedom counting its parameters per copy). The pre-fix SG4 run showed reweighting equal to a literal refit to 5e-15 with a duplicate race. Only the label differs.

**Alignment.** The code constant, its accepted value in the preflight and the tests are changed from `"separate_copy"` to **`"copy"`**, to match B1 D(2) word for word. **B1 is committed and hashed, so it is not edited.** B1's text governs the label.

---

## B. Root cause (found before any real read)

1. **Where the NaN goes.** `tyre_life` (t) is NaN on some eligible rows. Step 1 builds the tyre-trend columns Z from t and t² (§6d), so those columns hold NaN.
2. **Why the solver never stops.** `design_a.ap_demean` stops when `np.abs(change).max() < tol`. With a NaN in Z, the change is NaN, `np.abs(NaN).max()` is NaN, and `NaN < tol` is never true. So it runs the full 10,000 sweeps, and `fit_step1` / `fit_lap_arm` raise `EstimatorError`.
3. **Why a solver change does not fix it.** Direct least squares (`np.linalg.lstsq`) also fails on NaN input. A different solver or tolerance meets the same NaN. The fix has to be on the data: the row leaves step 1 (ruling 1).
4. **The rest of the fit is healthy.** Not re-derived here; these come from the 2026-10-30 diagnosis and are quoted as recorded there. In the other 41 races, step 1 converges in ≤ 1,220 sweeps. θ has full rank in every race. Alternating projections match direct `lstsq` to 3e-9. With the NaN-t free laps dropped, 2022_7 and 2022_11 converge as well.
5. **Why SG did not catch it.** In `sg_checks.py` `plant()`, the synthetic outcome uses th1·t + th2·t² (and the SG2/SG3 drift terms), so a NaN t gave a NaN synthetic outcome. `free_set` then dropped the row as a null outcome before step 1. The SG fix gives NaN-t rows a finite synthetic outcome (computed on `np.nan_to_num(t)`) while keeping t itself NaN. The rows then reach step 1, as real outcomes would, and meet ruling 1.

**Evidence.** The diagnosis scripts are in session scratch and are not committed:
`/private/tmp/claude-501/-Users-justin-github-off-the-pace/885ba8d8-f683-485f-bcf1-ec11563a5da3/scratchpad/lap/` (`build.py`, `an.py`, `fix.py`, and the pickle `races.pkl`). They read `wc10_io.load_structure`, which refuses guarded columns. The lap time is a constant placeholder 0.0 and the solver check uses random normals, so no outcome is read. If they are to be kept as evidence, the owner copies them into `_evidence/WC-10-2026-10-29/` (BUILD-ORDER rule 8).

---

## C. Counts (structure columns only)

**What was read.** The 2022-23 pass table and sidecar structure columns through `wc10_io.load_structure`: `season`, `race_id`, `race`, `driver`, `lap`, `stint`, `compound`, `tyre_life`, `corner_id`, `corner_number`, `corner_class`, `segment_basis`, `leader`, `leader_lap`, `gap_s`, `clear_ahead`, `behind_1s`, `tag`, `reason`, plus sidecar `exit_bracket_m`, `throttle_n`, `drs_open_approach`, `prev_lap_gap_s`, `prev_lap_clear_ahead`, `prev_lap_reason`. No outcome column, no `seg_start_t`/`seg_end_t`, no `LapTime`, no 2024-25, no fit, no `data/dev.duckdb`. The lap arm's "scored" flag needs `LapTime` to be present; it was taken as present for every lap (placeholder 0.0), as in `fix.py`. So lap-arm counts may be slightly high where `LapTime` is in fact missing. That number cannot be known before RUN START.

| | 2022_7 (Monaco) | 2022_11 (Spielberg) | Total |
|---|---|---|---|
| 1. Lap arm: scored free laps | 110 | 179 | |
| … with `tyre_life` missing | **12** (all LAT, stint 4, MEDIUM) | **45** (stint 3 of eight drivers: BOT 3, GAS 6, MSC 7, OCO 8, RIC 4, VET 2 on UNKNOWN; HAM 10 MEDIUM; TSU 5 HARD) | **57** |
| 2. Lap arm: following laps with `tyre_life` missing (vanished silently via `isfinite(tau)`) | **9** | **69** | **78** |
| 3. Design A: free passes with `tyre_life` missing (racecraft included) | | | **958** |
| … of which not racecraft (left after B1 ruling 1) | 253 | 578 | 831 (fast 153, medium 380, slow 298) |
| 4. Design A: following passes with `tyre_life` missing (before support, racecraft and φ filters) | 233 | 1,145 | 1,378 (fast 291, medium 661, slow 426) |
| Eligible rows (§5) with `tyre_life` missing | 491 | 1,858 | 2,349 |

**No other race has an eligible row with `tyre_life` missing.** That holds for design A rows and lap-arm laps alike.

**Caveat.** Design A counts are taken **before** the §6f (i) free-pass trim, because that trim needs `seg_time_s`. Free-pass counts at run time can only be the same or smaller. WC-10e recomputes every `tyre_life_missing` count at run time and reports it.

**Item 4, stated so it is not missed.** The handoff that set up this amendment named only the 78 lap-arm following laps as vanishing silently. Design A has the same leak. In `design_a.effects`, a following pass with t missing gets a NaN g and falls out through `np.isfinite(gy)`. It is not counted, because the existing reasons `no_free_pass_this_outcome` and `phi_cell_missing_this_outcome` count only `~a_ok` and `~f_ok`. Ruling 2 as worded ("rows dropped for missing tyre_life … counted in the outputs and ledger") covers these passes. How many of the 1,378 reach that point (supported, not racecraft, φ-supported) depends on the trimmed free set, so it is known only at run time.

**Re-derivation.** On 2026-10-30 every count above was re-derived from structure columns, using the committed code (`1a9ef80`, exported read-only to session scratch). The scripts are `/private/tmp/claude-501/-Users-justin-github-off-the-pace/885ba8d8-f683-485f-bcf1-ec11563a5da3/scratchpad/b2verify/verify.py` and `/private/tmp/claude-501/-Users-justin-github-off-the-pace/885ba8d8-f683-485f-bcf1-ec11563a5da3/scratchpad/b2verify/verify_a.py`. They **match** the handoff figures: 12 of 110 and 45 of 179 (57 free laps); 78 following laps (69 + 9); 958 design A free passes; only 2022_7 and 2022_11; lap-arm `n_params` 151 → 149 with 2022_11 UNKNOWN going from estimated to reference. Rows 3 (split), 4 and the design A layout figures are new and were not in the handoff. The convergence figures in section B item 4 were **not** re-derived, because that would mean running the solver.

---

## D. The earlier SG results are pre-fix and superseded

The SG1-SG7 partials from 2026-10-30 (`_evidence/WC-10-2026-10-29/sg/`: `run1/`, `partial_run1/verdicts_PRE_FIX.json` and the README there) were produced **before** this amendment and before the code fix. In those runs the NaN-t rows never reached step 1 (section B item 5), SG3 and SG6 did not finish, determinism was not shown, and the lap arm did not converge in 2022_7 or 2022_11 under SG5. **They are not evidence for RUN START and are superseded.** SG1-SG7 are re-run in full, twice for determinism, into a fresh evidence folder. That happens only after this file is committed and on the code commit that implements it (§0a: after a pre-result amendment, SG1-SG7 are rerun). The pre-fix folder is marked superseded (watch W15). If any SG check fails, nothing real is read. The plan is amended first and never tuned to pass.

---

## E. Preflight addition: real mode refuses without B1, B2 and an SG pass record

**New rule, added to B1 section D.** Before `run_wc10` in real mode writes RUN START, it also checks:

1. **B1 is committed unchanged.** The SHA-256 of `wi/WC-10-amendment-B1-open-choices-DRAFT.md` equals `c9566233bb25dcf078a8cc336682b289ec2d7494cfe6fb7189662d3c56b7b500`.
2. **B2 is committed unchanged.** The SHA-256 of this file equals the digest recorded on DD-WC23. (It cannot be written here, because a file cannot hold its own hash. The code takes it from the recorded value.)
3. **An SG pass record exists.** It shows that SG1-SG7 and the B-ii equivalence test (SG4) passed, twice and deterministically, on the committed code commit that implements B1 and B2. The run must be that same commit. The format and location of the record are not yet defined. The code fix defines them, and they are stated in its commit.
4. **The B2 code is in place.** Rows with `tyre_life` missing are left out of step 1 in design A and the lap arm, `tyre_life_missing` is counted, and the θ layout is built after the drop. A test with NaN-t rows in the synthetic structure passes. `duplicate_race_in_copy` reads `"copy"`.

If any check fails, RUN START is refused, the ledger records `FAILED_RESTARTABLE` with the reason, and nothing is decoded. This check reads file bytes, code constants and the SG record only, never a column value. PROVENANCE prints the B1 and B2 digests and the SG record's identity. This closes watch W14, together with a test showing that real mode refuses each missing item.

---

## Decision record

**Rulings 1-3 accepted by the owner, 2026-10-30 (DD-WC23). Written down by the Opus session; not the owner's personal signature.**

- Ruling 1: `tyre_life` is required for a row to enter step 1, in design A (every outcome and class) and in the lap arm. A following row with `tyre_life` missing cannot be predicted and leaves every average.
- Ruling 2: every such row is counted under `tyre_life_missing`, in the outputs and the ledger, including the 78 lap-arm following laps (69 in 2022_11, 9 in 2022_7) that previously vanished through `isfinite(tau)`, and the design A following passes that vanished through `isfinite(gy)`. The order in which overlapping reasons are counted is proposed in the builder note (after the existing reasons), for the owner to confirm.
- Ruling 3: the θ layout (§6d) is computed after the drop. Side effect: 2022_11 UNKNOWN goes from estimated to thin (reference curve). Lap-arm `n_params` goes 151 → 149, and design A drops 2 parameters per class on the pre-trim free set.
- Label alignment: code `duplicate_race_in_copy` `"separate_copy"` → `"copy"`, matching B1 D(2). B1 is not edited.
- The pre-fix SG partials are superseded. SG1-SG7 are re-run after this file and the code fix are committed.
- Preflight E added: real mode refuses without the B1 and B2 digests and an SG pass record.
- No threshold, tolerance, floor, trim, window, bin, minimum, B, seed, season split, race list or go/no-go rule changes.

## After the decision is recorded

1. The owner commits this file alone, before the code fix.
2. `git show HEAD:_roadmap/_wake-calibration/wi/WC-10-amendment-B2-tyre-life-DRAFT.md | shasum -a 256`. Record the digest and the commit on DD-WC23 in `status/build-log.json`, and resolve DD-WC23.
3. The code fix goes in a separate commit. It implements rulings 1-3 in design A and the lap arm, the `tyre_life_missing` counts, the layout after the drop, the `"copy"` label and preflight E, with tests for each, including NaN-t rows in the synthetic structure. It also includes the `sg_checks.py` fix from section B item 5.
4. SG1-SG7 are re-run, twice, on that commit, into a fresh evidence folder. The pre-fix folder is marked superseded.
5. Only then may RUN START be written, on the owner's go.

```
Commit:   ______________________
SHA-256:  ______________________
```
