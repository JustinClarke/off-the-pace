# WC-10d adversarial review 2: `WC-10-discovery-preregistration-DRAFT.md` (revision of 2026-10-29)

Reviewer: independent opus-5 agent (did not write the draft or REVIEW-1). 2026-10-29.
Read: the draft in full, REVIEW-1, the plan, BUILD-ORDER rules 1-8, build-log WC-10d/e items, DD-WC20 and the history tail, `data_gate.py`, `sidecar.py` (hash only), `build_pass_table.py` (`race_calendar`, reasons, pit flags), `estimator.py` (`racecraft`, `braking_corner_order`, `prepare_passes`), `run_wc03.py` (`g3_checks`), `counts/` (PROVENANCE, r02/r03 release logic, c2) and `counts_d/` (d01-d04 and outputs), `_evidence/WC-04-2026-10-29/`, WC-02 check 2 **headers only**.

Nothing was fitted. No outcome column was read (pass table and sidecar structural columns only; `prev_lap_*` from the sidecar; WC-02 CSVs: header lines only). `data/dev.duckdb` not touched. No git command run. My scripts are in session scratch (`.../scratchpad/r2/r2_counts.py`, `r2_lap.py`, `r2_s3.py`, `r2_app.py`, `g.py`); they are review scratch, not evidence, and every number they give that the draft should carry is quoted below so the drafter can re-derive it into `counts_d/` (rule 8).

## Verdict: **SIGN AFTER FIXES**

REVIEW-1's B2 (partly), B3 and B4 are fixed. Its S1-S8 are fixed or adequately handled. **B1 is not fixed**: the new S3 statistic is the old zero-by-construction slope, reweighted (R2-B1). SG3 as planted cannot be passed by a correct S3 (R2-B2). The S2 rework still has three defects that change the go/no-go line: the "symmetric" baseline does not cancel linear drift (R2-B3), the count floor makes the fast, aero and lap-arm checks unable to fail (R2-B4), and the one-sided vs bracketed comparison mixes drift with a large composition difference (R2-B5). All five fixes are text edits with exact wording given below. No re-review of the whole document is needed after them; a short check that the edits went in as written is enough.

---

## 1. REVIEW-1 items: are they fixed?

| Item | Status | Where / note |
|---|---|---|
| B1 S3 by construction | **NOT FIXED** | §11 S3 is algebraically the old slope (R2-B1). The count B1 asked for is in (§3 item 8: 150,844 / 172,413, verified). |
| B2 S2 tolerance | **Partly** | Compare one-sided vs bracketed, T = 25 % of bracketed, 90 % equivalence, local ±5 bracket: done. Baseline does not cancel drift (R2-B3); count rule makes checks unfailable (R2-B4); composition confound (R2-B5). |
| B3 class shares error with τ | **Fixed** (with residuals) | §6h cross-fit removes the shared corner-c free passes. Residual sharing via lap-level driver shocks and ĝ remains; SG6 should plant it (S-R2-6). |
| B4 bootstrap lists | **Fixed** | Appendix A equals `race_calendar` over kept passes exactly (24 rows, NFC, bytewise order; script `r2_app.py`). 2022_18 (Japan, wet) is correctly absent. |
| S1 restart loophole | **Fixed**, needs tightening | `OUTCOME DECODED` added. "Infrastructure cause" is a judgement; make it mechanical (S-R2-5). Stale "SG1-SG5". |
| S2 F1 unguarded | **Fixed on paper only** | The lap arm's S2 has about 20 bracketed near-band laps: it can never return anything but INCONCLUSIVE (R2-B4). |
| S3 score lap | **Fixed** | §13 item 7. |
| S4 X6 inputs | **Fixed, but definition mismatch** | The registered X6 text does not match the r03 script that produced 87 (S-R2-4). |
| S5 thin cells | **Fixed**, one ambiguity | Pooling "over compounds" collides with the reference θ1 = 0 (S-R2-3). 47 / 329 verified. |
| S6 open choices | **Fixed** | All nine are fixed in §6/§8. New small ones listed in S-R2-7. |
| S7 scratch numbers | **Fixed** | `counts_d/` with PROVENANCE; hashes match. `d01_out.txt` ends in a traceback (its last query, "groups", fails on a reserved word); no draft number depends on it. Say so in PROVENANCE. |
| S8 seen list | **Fixed, and can now be closed** | Item 9's two "possibly seen" entries are verified as not loss values (§3 below). |
| N1-N6 | Done except N5 | N5: §8a still quotes 22 % / 60 % without saying it is the review's "≥ 2 close and ≥ 2 free" definition, 2022-25. |

---

## 2. Independent recount (REVIEW-1 "not reviewed" item 1)

Independent code (pandas, not the d01-d04 SQL). Every §3 item 8 number reproduces **exactly**:

- 421,764 eligible passes (compound NULL among them: 0, so the §5 compound filter changes nothing); free 172,413; following 247,203; negative gap 2,148; free/following overlap 0. 43 races, 24 circuits.
- Supported following 23,008 / 65,511 / 61,981 (150,500); supported close 8,405 / 22,484 / 21,275 (52,164).
- Unlimited bracket, close: 1,862 / 4,738 / 4,510 (11,110).
- Local ±5: supported following 3,636 / 11,347 / 10,362 (25,345); near band 518 / 1,444 / 1,336 (3,298) of 5,837 / 15,362 / 14,435; far band 11,248.
- φ windows 124,041 / 8,957 / 5,371 / 12,131; close unsupported 7,373 of 52,164.
- Free-pass leverage 150,844 of 172,413; groups 15,634 of 19,137.
- Thin cells 47 of 329 (40 with one driver).

**New structural counts the draft needs** (2022-23, before trims):

| Count | fast | medium | slow |
|---|---|---|---|
| Near-band local-bracketed, **racecraft out** | 428 | 1,035 | 959 |
| ... and φ-supported | **424** | **1,030** | **952** |
| Near-band one-sided, racecraft out, φ-supported | 4,051 | 10,344 | 9,854 |
| Distinct groups / distinct (group, earlier, later) baselines among the bracketed | 318 / 348 | 802 / 875 | 716 / 818 |
| Near-band bracketed at ±6 / ±8 / ±10, racecraft out | 512 / 638 / 748 | 1,238 / 1,544 / 1,741 | 1,169 / 1,482 / 1,671 |
| Cross-fitted class known (N_F ≥ 2, N_L ≥ 2, leader eligible, own φ ok), of supported close non-racecraft | 4,124 of 7,249 (57 %) | 11,576 of 18,305 (63 %) | 11,131 of 17,441 (64 %) |
| Races where the class has **one** braking corner (cross-fit impossible there) | 15 of 37 | 2 of 43 | 2 of 43 |
| Mean signed tyre-age distance d̄, near / far | −7.4 / −2.8 | −6.6 / −2.4 | −7.6 / −3.2 |

- Asymmetry of the local bracket among the bracketed near band: \|(lap − l_b) − (l_a − lap)\| = 0 for 18.9 %, 1 for 35.2 %, 2 for 28.1 %, 3 for 11.8 %, 4 for 6.0 %.
- Train tag (N2): the car ahead's own gap at the same corner and lap is < 1.0 s for 16,277 of 42,995 supported close non-racecraft passes (38 %).
- Old class rule among the same 42,995: 28,845 (67 %), consistent with the old 66.7 %.
- **Lap arm** (structure only; `LapTime` not read; `no_lap_time` is already a pass-table reason): 23,663 scored laps (every braking corner eligible, no racecraft), free 9,504, following 13,325, supported following 5,401, supported near band **1,087**; bracketed within ±5: **20** near-band laps (474 over all following bins); ±8: 48 (757).

---

## 3. Unvisited areas 2-8

**2. φ drops by race.** The φ-unsupported share of supported following passes has a median of 5.7 % per race. Three races exceed 20 %: 2023_3 Melbourne 24.1 %, 2023_20 São Paulo 21.6 %, 2023_10 Silverstone 20.5 %. Next come 2023_19 18.6 % and 2022_16 17.2 %. The top five races hold 38.6 % of all drops. By circuit: Melbourne 16.3 %, Monza 15.7 %, Silverstone 15.5 %, Mexico City 13.8 %. The drops are concentrated, but not enough to distort a 24-circuit bootstrap: no circuit loses more than a sixth. **No change needed.** Add the per-race table to the §13 support tables (it is already implied by "counted"), and add one sentence to §8c: "φ drops concentrate in a few races (2022-23 structure: three races above 20 %, median 5.7 %)."

**3. X6 vs `c2_release_by_season.csv`.** 39 + 48 = 87 matches c2. **But the r03 definition is not the §8f text** (S-R2-4):
- r03's "following on L" is the lap median braking gap < 1.5 s (with clear ahead set to 30), not "close or following".
- r03's "free on L+2" is free **or mostly free** (median ≥ 3).
- r03's free uses `gap_s > 3`, not ≥ 3.
- The car ahead on L is the modal `leader`.
- `pit_lap_leader` marks the car ahead's **in- or out-lap** (`PitInTime` or `PitOutTime` not null, `build_pass_table` line 587), not its pit entry.
- Reasons are first-match in priority order, so a lap that is also `yellow_sector`, `restart` or `neutralised` never shows `pit_lap_leader`.

The run's recount would not reproduce 87 under the §8f wording.

**4. Post-release washout.** Covered by X14. "Following spell" is undefined (S-R2-7).

**5. SG adequacy.**
- SG1 and SG2 exercise neither B1 nor B3. That is acceptable, because SG3 and SG6 are meant to.
- SG3 as planted is unpassable by a correct S3 (R2-B2).
- SG6 lacks the shared-shock structure that would test the cross-fit's residual (S-R2-6).
- There is no SG that checks S2 has any power to AGREE. One is added in ruling (a).
- ±10 % near-band bias at 200 simulations is achievable: planted near 0.09 s, Monte Carlo SE of the mean over 200 simulations ≈ se/14.
- Run time is a real risk. SG1, SG2, SG6 and SG7 each need 200 × 200 = 40,000 full-chain fits. SG5 (one draw timed) must be run first. A shortfall goes to a pre-result amendment (allowed by §10).

**6. Seal enforceability.**
- The 2024-25 pass table (`seg_time_s`, `min_speed_kph` …) and sidecar outcomes are on disk and readable by any agent with duckdb.
- The loader guard covers WC-10e code only. The gate proves the files are unchanged, not unread.
- The seal is therefore procedural and a read cannot be detected. §4 should say so (S-R2-8).

**7. §0b against the body, every row.** Rows agree with the body except:
- **Unit**: omits "`compound` not NULL" (§5; 0 rows affected).
- **Racecraft**: does not say what rows it is computed on (S-R2-7).
- **Pass class**: lists only one of the four `unknown` causes.
- **Coverage floor**: does not say before or after the coast cap.
- **Cut points / none-barely**: do not say how "—" laps and ties at 0 enter the quantiles, or whether a racecraft-only lap has a "following braking corner".
- **Synthetic**: omits SG2, the SG3 false-alarm requirement (≥ 90 % pass) and SG6's 5-point held-up share.

The S1-S3/F1, bins, bands, trims, φ, gate digests (recomputed: 188dac5e…, 8595ce93…, 80d9623b…; sidecar per-file hashes = its SHA256SUMS) and Appendix A rows all match.

**8. WC-04 evidence (G3.1-G3.3).** `_evidence/WC-04-2026-10-29/PROVENANCE.txt` printed only G3.1 (a pass: the dev.duckdb SHA-256 `7173444b…`) and G3.4 (fail, digest `aaaf711d…`). `run_wc03.g3_checks` returns before G3.2/G3.3 when G3.1 or G3.4 fails, so **no panel row count and no slope was computed**. 0.4777453471 is the registered constant `G3_POOLED_SLOPE` in `run_wc03.py`: a pooled lap-level fingerprint from the WC-03 registration, the same family as §3 items 1-2. Separately, WC-02 check 2's two CSVs hold only counts and presence flags (headers: `candidate_events, stays_out, stays_out_pass_rows_both_sides, stays_out_measured_delta_both_sides`; per-event `n_corners, gap_s_min, rows_*, both_deltas_present, …`). The 530 is a count, not a loss value. **§3 item 9's two "possibly seen" bullets can be moved to "verified: no loss value"**, and the §3 closing statement shortened accordingly.

---

## 4. Blockers (exact proposed text)

### R2-B1. S3 is still the zero-by-construction slope (REVIEW-1 B1 not fixed)

*Proof.*
- Let ε̂ be the step-1 residuals and u_j = y_j − φ̂ − ĝ − γ̂·b = α̂_G + ε̂_j.
- Because Σ_{j∈G} ε̂_j = 0, the plug-in leave-one-out residual is e_j = u_j − mean_{−j}(u) = n/(n−1)·ε̂_j, and m_j = n/(n−1)·(t_j − t̄_G).
- So s_k = Σ_G c_G Σ_j ε̂_j t_j / Σ_G c_G SS_G, with c_G = (n_G/(n_G−1))² ∈ (1, 2.25].
- Within a stint, `tyre_life` = lap + a stint constant. It therefore lies in the span of the φ[r,c,l] and α[G] dummies, and Σ ε̂_j t_j = 0 over every (race, corner) block.
- s_k is thus the first draft's slope, reweighted mildly and restricted to the 87.5 % population. Its numerator is about −(the complement's sum).
- REVIEW-1's failure scenario applies unchanged. "Breaks that identity" in §11 is false.

*Replace the Formal block of §11 S3 with:*

> - Population: groups G of class k with ≥ 3 free passes after trims whose free passes span ≥ 8 tyre-age laps (max − min `tyre_life`), and ≥ 1 supported near-band pass that enters β_near (not racecraft, φ-supported, not trimmed).
> - b̂_G = the OLS slope, with intercept, of the step-1 residuals ε̂_j on `tyre_life_j` over G's free passes.
> - d_i = `tyre_life_i` − the mean `tyre_life` of G's free passes.
> - B_k = the mean over those near-band passes of b̂_{G(i)} · d_i. Under a linear drift of the driver relative to the field, τ_i is biased by exactly (that drift) × d_i, so B_k is the plug-in estimate of the drift bias on β_near.
> - Pass if |B_k| ≤ max(0.25·|β̂_near,k|, 0.010 s) in every class (point estimates; the 95 % interval and the share of near-band passes covered are reported).
> - Why not a pooled slope: `tyre_life` lies in the span of the α and φ dummies, so step-1 residuals sum to zero against `tyre_life` within every (race, corner). Any slope weighted by free passes (including a plug-in leave-one-out slope, which is that slope reweighted by (n/(n−1))²) is near zero by construction. B_k weights each group by its near-band exposure and distance, which the normal equations do not constrain.
> - 2022-23 structure (before racecraft, φ drops and trims): the population covers 3,218 / 8,016 / 7,497 of 5,837 / 15,362 / 14,435 supported near-band passes; mean d is −8.0 / −7.3 / −8.3 laps; with the seen per-pass SD (§3 item 4) the iid standard error of B_k is about 0.003 / 0.002 / 0.002 s (0.006 / 0.004 / 0.003 s with a 4-lap span, which is why 8 is used).

Also: §11 S3 Plain English, the "Why this" paragraph, §8e item (3), §0b S3 row ("B_k = near-pass-weighted plug-in of group drift slopes × tyre-age distance"), and CHOICE D24 ("S3 = exposure-weighted group drift B_k | pooled or leave-one-out slope | both are zero by construction").

### R2-B2. SG3's plant is absorbed by φ, so a correct S3 must pass it

Planting +0.01 s per lap in every group with following passes plants it in 87.5 % of free passes. φ (per corner-lap) absorbs about 87.5 % of the trend. The bias it induces on β_near is about 0.125 × 0.01 × 7 ≈ 0.009 s, below the 0.010 s floor. A correct S3 passes, and "fail in ≥ 80 %" then fails SG3 for the wrong reason, forcing a pre-result amendment. *Replace SG3 with:*

> **SG3, power of the drift check (pass/fail).** To SG1's y add a driver drift of +0.01 s per tyre-age lap in every group with ≥ 1 supported near-band pass, made relative to the field: from every pass, subtract the mean of the planted term over the free passes in its (race, corner, lap) cell, so that φ cannot absorb it. Report the realized near-band bias (mean simulated β̂_near minus planted). Over 200 simulations S3 must fail in ≥ 80 %. With no drift planted, S3 must pass in ≥ 90 %. S2-pace verdict rates are reported for both.

### R2-B3. The "symmetric" local baseline does not cancel linear drift

½(r_b + r_a) equals the drift at the pass only when the pass is at the midpoint. 81 % of bracketed near-band passes are off the midpoint by 1-4 laps. *Replace in §8a Formal:*

> ŷ0^loc_i = φ̃_i + ĝ_k(tyre_life_i) + γ̂_k·behind_1s_i + w_b·r_b + w_a·r_a, with w_b = (l_a − l_i)/(l_a − l_b) and w_a = (l_i − l_b)/(l_a − l_b) (linear interpolation in lap; within a stint `tyre_life` and lap differ by a constant). r_b and r_a use φ̂ at the free pass's own (r, c, lap) cell. A linear drift cancels exactly. Trim (ii) is applied once, to τ with the group α̂ (§6e); a pass dropped there is dropped from β^one and β^brk alike, and τ^loc is not trimmed separately.

Also §0b "Bracketed pass" and §11 S2 Plain English: "interpolated local baseline" in place of "symmetric".

### R2-B4. The count floor makes three checks unable to fail

"< 500 bracketed = INCONCLUSIVE" blocks DISAGREE as well as AGREE.
- After racecraft and φ drops, fast has 424 bracketed near-band passes. Fast pace S2 can therefore never DISAGREE.
- S2-aero (dirty-air, classed; fast ≈ 424 × 0.57 × the dirty share ≈ 150-250) can never DISAGREE, so "aero if S2-aero is not DISAGREE" always proposes aero.
- The lap arm's S2 has about 20 bracketed near-band laps (474 over all bins), so F1's drift guard is always INCONCLUSIVE. That reopens REVIEW-1 S2.

*Replace the §11 S2 verdict bullets with:*

> - **AGREE** if the 90 % percentile interval of D′ lies inside [−T, T] **and** at least 500 bracketed near-band passes enter β^brk after racecraft, φ drops and trims (for A: the smaller of the fast and slow dirty-air counts);
> - **DISAGREE** if that interval lies wholly outside [−T, T] and at least 100 bracketed passes enter;
> - **INCONCLUSIVE** otherwise.

*Replace "Expected weakness" with:* "2022-23 bracketed near-band counts after racecraft and φ drops, before trims: 424 / 1,030 / 952. Fast pace S2 and S2-aero cannot be AGREE; they can still be DISAGREE on a clear gap, and DISAGREE blocks."

*Replace F1 in §11 and §0b with:*

> **F1:** lap arm: the lower 95 % end of Near_lap > 0, **and** S3 (corner level) passes in medium and slow. The lap arm's own bracketed comparison (§9a) is a DIAGNOSTIC: in 2022-23 structure only about 20 near-band laps are bracketed within ±5 laps (474 following laps over all bins, 1,087 supported near-band laps). The FALLBACK line carries "lap drift checked through corner-level S3 only".

Also: §9a "Lap-arm S2" becomes "Lap-arm bracketed companion (DIAGNOSTIC)"; CHOICE D21 reason; §13 item 4.

### R2-B5. One-sided vs bracketed mixes drift with composition

Bracketed passes are mostly brief encounters: the driver arrived from free air and left again within five laps. Near band, racecraft out, φ-supported:

| | Bracketed | One-sided |
|---|---|---|
| Arrived from free (fast / medium / slow) | 33 / 28 / 27 % | 2-3 % |
| Stint close share < 0.20 (all classes) | 65 % | 20 % |
| Stint close share ≥ 0.50 (all classes) | 3 % | 29 % |

Catching bias (§8d) runs through exactly these variables. An unstandardized D′ can therefore DISAGREE with no drift at all, and it can AGREE when drift and selection offset each other. *Add to §11 S2 Formal (and use the same cells for D′_A):*

> β^one_near is standardized to the bracketed composition: D′ = Σ_s w_s·β^one_near,s − β^brk_near, where s runs over the 15 cells of gap change (§8d: shrinking, arrived from free, steady, growing, unknown) × stint close-share tier (< 0.20, 0.20-0.50, ≥ 0.50), w_s is the share of bracketed near-band passes in cell s, and β^one_near,s is the near band of one-sided passes in cell s. Bracketed passes in a cell with fewer than 20 one-sided near-band passes are dropped from β^brk and counted. The unstandardized D′ is reported beside it.

and to §18: "S2 compares populations that differ in catching and stuck-stint mix. The standardization covers the observed mix only; a DISAGREE may still reflect selection the cells do not capture."

---

## 5. Should-fix (exact edits)

- **S-R2-1. Stale references.**
  - §0a "SG1-SG5" becomes "SG1-SG7".
  - §13 item 6 "X1-X12" becomes "X1-X14".
  - §17 last line "SG1, SG2, SG3 or SG6" becomes "SG1, SG2, SG3, SG6 or SG7".
  - §0b synthetic row: add SG2, "SG3 false alarm: S3 passes in ≥ 90 % without drift", "SG6 held-up share within 5 points across classes", "SG7 (S2 power)".
  - §0b unit row: add "`compound` not NULL".
  - §8a "falls below it after trims" becomes "is 424 after racecraft and φ drops".
  - Order the CHOICE table D1…D25.
  - §20a: replace the "Open:" sentence with "Review 2 done (`…-REVIEW-2.md`); its edits are applied."
- **S-R2-2. σ̂ degrees of freedom.** α groups and φ cells are both per corner, so the α-φ graph has at least one component per (race, **corner**), not per (race, class). Write: "minus the number of connected components of the α-φ graph, counted by the code".
- **S-R2-3. Thin cells (§6d).** Replace "pooled over compounds at that race and class (one shared pair)" with: "a thin compound takes the reference compound's curve at that race and class (θ1 = 0, θ2 = θ2 of the reference); its level difference is absorbed by α".
- **S-R2-4. X6 (§8f, §2, §12).** Register r03's definition literally. Lap state comes from the median braking gap over eligible braking passes, with clear ahead set to 30 s. A lap is "following" if that median is < 1.5 s, "free" if every braking pass is free, and "mostly free" if the median is ≥ 3 s. An event is a following lap L where some pass row on L+1 has reason `pit_lap_leader` with `leader` equal to L's modal leader, no pass row on L+1 has `pit_lap`, and L+2 (same stint) is free or mostly free. `pit_lap_leader` is the car ahead's in- **or** out-lap, and reasons are first-match, so a pit lap masked by an earlier reason is missed. The recount must reproduce 39 / 48. Use `gap_s ≥ 3` for free, as everywhere else, and state that r03 used > 3 if the count changes.
- **S-R2-5. Restart rule (§0a).** Use this text:

  > An infrastructure cause is one of: the process ended by a signal (exit status 128 + n, including the OOM killer), or an `OSError` with errno ENOSPC / EIO. Any Python exception is not. The run's entry point catches every exception and writes only its type, file and line to the ledger and stderr, never its message or arguments. Before `OUTCOME DECODED`, code may change only through a pre-result amendment, after which SG1-SG7 are rerun.
- **S-R2-6. SG6.** Add to the plant a driver-lap shock shared by every corner of the lap (SD 0.02 s; correlated −0.6 with the minimum-speed shock) and a driver × corner interaction (SD 0.02 s). Add to §6h: "In 15 of 37 races with fast braking corners, the fast class has only one braking corner, so every fast pass there is `unknown`; fast-class aero rests on 22 races." Add to §18: "shared lap-level driver shocks still link the class to τ".
- **S-R2-7. Small open choices.**
  - Racecraft is computed by `estimator.racecraft` on **all** 2022-23 pass-table rows, as WC-03 `prepare_passes` did.
  - Sidecar coverage for coast is counted **after** the 10 s cap. It is therefore outcome-derived and written only after RUN START.
  - Cut-point quantiles are over following laps with a score other than "—"; a lap exactly at a cut takes the lower level; a lap whose only following corners are racecraft counts as following for cut points and is scored by its racecraft pricing.
  - X14: a "following spell" is a maximal run of consecutive laps on which the group's pass is following (0 ≤ gap < 3) or racecraft.
  - X1-X14 run on the time-model structure sets.
- **S-R2-8. Seal (§4).** Add: "The seal is procedural. The 2024-25 outcome columns are on disk and a read cannot be detected afterwards. Every WC-10 agent brief carries the seal rule. Any read of a 2024-25 outcome column, by anyone, is logged in the build log as a breach and is named in WC-10g's seen list."
- **S-R2-9. §3 item 9.** Replace the WC-02 and G3 bullets with the verified facts in point 8 of section 3 of this review (counts only; G3.2/G3.3 never computed; 0.4777453471 is the registered WC-03 constant). Drop the corresponding hedge in the closing statement. The DA-03 and 16-coast bullets stay.
- **S-R2-10. N5.** §8a: "(2022-25, the review's definition: ≥ 2 close and ≥ 2 free in the group)".
- **S-R2-11. Data gate code identity.** In §2 and §16, record `data_gate.py` sha256 `34da633d4095f60104471fc773d84dacdb6b2ed9ba00bc6797df37a4a07057d5` as reviewed, and replace it with the new hash after ruling (b).

---

## 6. Rulings

**(a) S2 design: workable with changes. Keep the window at ±5 laps and the tolerance at T = max(0.25·|β̂^brk|, 0.020 s) for pace and max(0.25·|Â^brk|, 0.75 km/h) for aero, with the 90 % equivalence test.**
- *Why the numbers stay:*
  - Medium and slow keep about 1,030 and 952 bracketed near-band passes after racecraft and φ drops.
  - Those passes sit in 875 and 818 distinct baselines, so clustering of the baseline noise is mild.
  - With the declared per-pass SD (0.06 s) the per-pass SD of τ^loc is about 0.075 s, giving an iid se(β^brk) of about 0.0025 s and a 90 % half-width of about 0.008-0.012 s after a cluster design effect of 2-4.
  - AGREE is then reachable whenever |D′| ≲ 0.010 s. The table is **not** unreachable for medium and slow.
  - Fast cannot reach 500, and the table already does not require it.
- *Why not ±8 now:* with linear interpolation (R2-B3), ±5 against ±8 matters only for curvature in driver drift, and ±5 is the safer default. ±8 is the pre-registered fallback.
- *Required changes:* R2-B3, R2-B4, R2-B5, plus a power check:

  > **SG7, S2 power (pass/fail).** Under SG1 (no drift), S2-pace must be AGREE in medium and slow in ≥ 80 % of 200 simulations, and DISAGREE in ≤ 5 % in every class. If SG7 fails:
  > 1. The window becomes ±8 laps (2022-23 bracketed near band, racecraft out: 638 / 1,544 / 1,482), and SG7 is rerun.
  > 2. If it fails again, the pace floor becomes 0.030 s, and SG7 is rerun.
  > 3. If it fails a third time, S2 is reported but leaves the go/no-go table, and the line prints "S2 unpowered".
  >
  > Each step is a pre-result amendment committed alone. The ladder is fixed now, so choosing a step involves no judgement after any result.

**(b) data_gate.py checks 3 and 4: make them pass/fail BEFORE signing.**
- *Reason:* WC-03 died because a registered digest disagreed with the digest the run-time gate computed. Check 3's digest in §16 was computed ad hoc for the draft, not by the gate that will run.
- Fixing a wrong digest after signing costs a pre-result amendment (commit alone, hash). Fixing it before signing costs an edit.
- *Work:*
  - Give `sha256sums_mismatches` a `prefix` argument (`"pass_table_"` / `"sidecar_"`).
  - Add a check-3 function over `_artifacts/WC-10/sidecar/sidecar_*.parquet` plus its SHA256SUMS (I verified both match today).
  - Make check 4 pass/fail.
  - `main` exits 1 if any of checks 1-4 fails and prints one line per check.
  - Add tests for each check failing (wrong byte, missing file, NFD name).
  - Run the dry run twice into `_evidence/WC-10-2026-10-29/gate_dryrun-2.txt`.
  - Record the new `data_gate.py` sha256 in §16.
- The owner commits the code. The draft only cites the hash.

**(c) Build-log history entry: yes, add one now, as bookkeeping only, before signing.**
- Today's draft revision, `counts_d/` and both reviews are not in the log.
- The 17:00 entry's `next_action` is stale.
- `data_gate.py`'s hash is recorded nowhere.
- Do not change DD-WC20 (still OPEN) or WC-10d's stage. Form, matching the existing schema:

```json
{
  "date": "2026-10-29T<hh:mm>:00+04:00",
  "session": "WC-10d: draft revised for REVIEW-1 (B1-B4, S1-S8); counts_d evidence; independent REVIEW-2. Bookkeeping only; nothing fitted or scored; no outcome column read; data/dev.duckdb not touched; nothing committed, staged or pushed.",
  "landed": [
    "wi/WC-10-discovery-preregistration-DRAFT.md revised (unsigned, uncommitted, unhashed).",
    "_evidence/WC-10-2026-10-29/counts_d/ (d01-d04, outputs, PROVENANCE).",
    "wi/WC-10-discovery-preregistration-REVIEW-2.md: SIGN AFTER FIXES; blockers R2-B1 (S3 still zero by construction), R2-B2 (SG3 plant absorbed by phi), R2-B3 (local baseline not drift-cancelling), R2-B4 (count floor makes fast/aero/lap S2 unfailable), R2-B5 (S2 composition confound); rulings (a)-(d)."
  ],
  "verified": [
    "Section 3 item 8 counts reproduced exactly by independent code; Appendix A equals race_calendar over kept passes; gate digests 188dac5e/8595ce93/80d9623b recomputed; sidecar per-file hashes match SHA256SUMS.",
    "data_gate.py sha256 34da633d4095f60104471fc773d84dacdb6b2ed9ba00bc6797df37a4a07057d5 (reviewed version); sidecar.py 8d2047b9...",
    "WC-04 run computed no G3.2/G3.3 value; WC-02 check 2 CSVs hold counts only."
  ],
  "assumed": ["File name still differs from WC-10d done_when; owner to resolve."],
  "gates_run": ["board.py --check", "board.py --write-order"],
  "next_command": "python3 _roadmap/_wake-calibration/status/board.py --check",
  "next_action": [
    "AGENT (drafter): apply REVIEW-2 edits R2-B1..B5 and S-R2-1..11; copy the new structural counts into counts_d/ with PROVENANCE.",
    "AGENT (sonnet-5 or drafter): data_gate checks 3-4 pass/fail with tests; dry run twice; record the new hash in the draft.",
    "OWNER: commit sidecar.py, data_gate.py, run_wc03.py NFC fix and tests; then sign DD-WC20, commit the registration alone, record its SHA-256."
  ]
}
```

**(d) Verdict: SIGN AFTER FIXES.**
- Required before signing: R2-B1 to R2-B5 with SG7 (ruling a), ruling (b), S-R2-1, S-R2-4, S-R2-5, S-R2-9 and S-R2-11.
- The other should-fix items are cheap and recommended, but none of them changes the go/no-go line.
- After the edits, one short check that each replacement text went in as written and that the new counts are in `counts_d/` is enough. A third full review is not needed.
- The owner also resolves the file name (the draft's §20a box).
