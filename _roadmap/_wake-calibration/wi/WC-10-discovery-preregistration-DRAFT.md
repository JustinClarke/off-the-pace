# WC-10 discovery pre-registration: traffic levels (pace, aero, tyre) on 2022-2023

**Status: DRAFT, unsigned, not committed, not hashed.** Drafted 2026-10-29 for build item WC-10d. **Revised the same day for REVIEW-1 blockers B1-B4 and should-fix S1-S8** (`wi/WC-10-discovery-preregistration-REVIEW-1.md`), **and again for REVIEW-2** (`wi/WC-10-discovery-preregistration-REVIEW-2.md`, verdict SIGN AFTER FIXES): blockers R2-B1-R2-B5, ruling (a) with SG7, should-fix S-R2-1-S-R2-11 applied. Ruling (b) (`data_gate.py` checks 3-4 pass/fail) is code work outside this file; its new hash is a placeholder below until it lands. Per REVIEW-2 (d), a short check that the edits went in as written is all that remains before signing. The owner signs it (DD-WC20) and commits **this file alone**. Its SHA-256 is recorded on DD-WC20 in `status/build-log.json` before anything is fitted (BUILD-ORDER rule 4). Until that is done, nothing in WC-10e may read an outcome column.

Nothing has been fitted for this document. No segment time, minimum speed, exit speed, coast time, throttle share, lap time, delta or reference value was read to write it. Every number below is either a count of structural columns (gap, flags, classes, tyre life, DRS state, lap numbers), a file hash, or a value that was already seen before today and is declared in §3. `data/dev.duckdb` was not touched. No number from the archived dirty-air method (DA-03) is used anywhere.

Sources read: the WC-10 plan and its 2026-10-29 review note (`wi/WC-10-exploratory-levels-PLAN-DRAFT.md`), the WC-10a-l entries and decisions DD-WC2 and DD-WC14-DD-WC21 in `status/build-log.json`, `status/BUILD-ORDER.md` rules 1-8, the WC-03 pre-registration and amendment A1, the WC-02 results and provenance, the code in `transform/tasks/wake_calibration/` (`build_pass_table.py`, `sidecar.py`, `data_gate.py`, `estimator.py`), and the evidence in `_evidence/WC-10-2026-10-29/` (`counts/`, `sidecar/`, `gate_dryrun.txt`).

**File name.** The WC-10d `done_when` in the build log names `wi/WC-10-discovery-registration-DRAFT.md`. This file was written as `wi/WC-10-discovery-preregistration-DRAFT.md`, as the orchestrator instructed. The owner either renames the file before signing or corrects the `done_when` entry.

---

## Checklist: where each required element is fixed

| Required element (WC-10d `done_when`, plan §9, review note, orchestrator brief) | Section |
|---|---|
| Purpose and scope: discovery only, 2024-25 sealed, pace first, aero as proxy, tyre expected "—", retrospective only | §1, §4 |
| Season split with confirmation sealed (plan §9) | §4 |
| Design A exact specification: groups, field effect, tyre trend, bins, class rule, braking corners, outcomes, estimator (plan §9) | §6 |
| Outcome columns and sidecar definitions, coast-time cap, thresholds, exit-speed use, coverage (plan §9; WC-10b open points 1-2) | §6g, §7 |
| Review item 1: bracketed-subset estimate as a mandatory companion with a numeric tolerance; "bracketed" vs one-sided defined (WC-10d open point 3) | §8a, §11 S2 |
| Review item 2: close-share tiers, with an "extrapolated" flag at ≥ 80 % | §8b |
| Review item 3: identity-matched release set | §8f, §12 |
| Review item 4: minimum free-car count for the field corner-lap effect, with a fallback | §6c, §8c |
| Review item 5: shrinking vs growing gap split as the primary catching check, lagged refit secondary | §8d, §12 |
| Gap-bin × tyre-age collinearity | §8e |
| Bootstrap draws and seed (plan §9) | §10 |
| Switch rule to the lap-level, pace-only fallback | §11 |
| Diagnostics labelled DIAGNOSTIC, never moving a level; multiple-testing rule | §12 |
| What discovery produces; cut-point rule (DD-WC17, quantiles) | §13 |
| What discovery may not conclude | §14 |
| Labels: modelled, DD-WC2 verbatim, DD-WC18 second line, "—" with a reason | §15 |
| "Replay v1 is retrospective" (plan §9) | §1, §15 |
| Data gate (WC-10c), dry run before RUN START, restart rule, when a run "completes" | §0, §16 |
| Synthetic recovery test before the real run (WC-10e `done_when`) | §17 |
| Seen list (plan §9 items 1-4, WC-10a/b/c evidence, this draft's own counts) | §3 |
| No DA-03 number; WC-10 does not decide the flat penalty (plan §9) | §1, §14 |
| Fixed numbers in one place | §0 |
| Honest limits and risks | §18 |
| Judgement calls, for the owner to overrule | §19 (CHOICE D1-D30) |
| Sign-off | §20 |
| Adversarial review of the identification text by an independent opus-5 reviewer, recorded before signing (WC-10d `done_when`) | Review 1 (partial) and Review 2 (full, SIGN AFTER FIXES) done; both sets of fixes applied. §20a. |

---

## 0. The rule this document exists for

**Every definition, threshold, tolerance, season split and decision rule below is fixed now, before any WC-10 outcome is read. None may change after an outcome has been read.**
- **Plain English:** if a rule turns out to be unworkable before any outcome has been read (for example, a column is missing, or 1,000 draws cannot finish in time), the fix is a pre-result amendment. It is committed alone and hashed before the run. A change made after an outcome has been read is a post-hoc amendment. It is labelled as such, it is committed alone and hashed before any rerun, and it can never replace the first run's outputs: both sets are kept and reported.
- **Formal:** an amendment is pre-result only if, at the moment it is committed, the run ledger (§16) shows no outcome-derived number written.

### 0a. When a run starts, fails or completes (this closes the WC-03 trap)

WC-03 ended because its rule counted a **gate result** as a result. The G3 digest line was written, a path-encoding fault made it fail, and that failure used up the one run before any outcome had been read. This registration does not use that rule.

- **Plain English:**
  - The run first checks that its input files are exactly the registered ones (the data gate, §16). That check reads file bytes and file names only, never a column value.
  - If the gate fails, the run stops. Nothing has been seen, so the failure is **restartable**: fix the cause (a path, a mount, a missing file), keep the same code, data, seed and draws, and start again.
  - Only after the gate passes is RUN START written. Writing RUN START does **not** complete the run.
  - A crash after RUN START and before the first outcome column is decoded is also restartable, under the same conditions.
  - **First decode.** The moment the loader first decodes an outcome column, it writes the ledger line `OUTCOME DECODED`. From that line on, a restart is allowed only with **byte-identical code and inputs**, and only for an infrastructure cause (defined below). Any change to code, constants or inputs after that line is a **post-hoc amendment**, even if nothing was written yet. Logs and tracebacks written before the first outcome-derived number must print no outcome value.
  - **Infrastructure cause (mechanical).** An infrastructure cause is one of: the process ended by a signal (exit status 128 + n, including the OOM killer), or an `OSError` with errno ENOSPC / EIO. Any Python exception is not. The run's entry point catches every exception and writes only its type, file and line to the ledger and stderr, never its message or arguments. Before `OUTCOME DECODED`, code may change only through a pre-result amendment, after which SG1-SG7 are rerun.
  - SG1-SG7 (§17) must pass on the committed code before RUN START.
  - The run **completes** at the first moment an outcome-derived number is written anywhere a person could read it: any file, the run log, stdout or stderr. From that moment it is the one discovery run.
- **Formal:**
  - An *outcome column* is any of: `seg_time_s`, `min_speed_kph`, `delta_time_s`, `ref_time_s`, `apex_kph` (pass table); `exit_speed_kph`, `coast_time_s`, `partial_throttle_share` (sidecar); `LapTime`, `Sector1Time`, `Sector2Time`, `Sector3Time` (bronze laps); the bronze telemetry `speed_kph` and `throttle_pct`.
  - An *outcome-derived number* is any number computed from one or more values of an outcome column, after any transformation: an estimate, interval, residual, trim count, coverage of a trimmed set, test statistic or score. Counts of non-null values (coverage) and the structural counts listed in §3 are **not** outcome-derived.
  - Run states follow `data_gate.run_state(gate_ok, outcome_number_written)`, with this mapping (the `OUTCOME DECODED` line is a ledger event beside the states; the restart rule above uses it):

    | State | Condition | Meaning |
    |---|---|---|
    | `FAILED_RESTARTABLE` | gate failed, nothing outcome-derived written | restart allowed |
    | `RUNNING` | gate passed, nothing outcome-derived written yet | a crash here is restartable |
    | `COMPLETED` | gate passed, an outcome-derived number written | the one run; no restart |
    | `FAILED_NOT_RESTARTABLE` | gate failed after an outcome-derived number was written | cannot happen if the code order below holds; if it does, it is reported, never retried |

  - **Code order, enforced and tested:** (1) data gate → (2) gate result and RUN START written to the ledger → (3) only then may any outcome column be decoded. A test shows that the gate step decodes no parquet column, and that the outcome loader refuses to run unless the ledger holds a passing gate line for this run.
  - The ledger is `_evidence/WC-10-discovery-<date>/PROVENANCE.txt`. Each start is logged with time, reason, gate result, state at exit, and whether an outcome-derived number had been written.
  - **One run.** After `COMPLETED`, discovery is never rerun under this registration. A bug found afterwards is handled only by a post-hoc amendment committed alone and hashed before any rerun. The first run's outputs stay in the evidence and are named in the confirmatory registration's seen list.

### 0b. The fixed numbers in one place

| What | Fixed value | § |
|---|---|---|
| Discovery seasons | 2022, 2023 (43 races on 24 circuits in the pass table's kept braking passes) | §4 |
| Sealed seasons | 2024, 2025: no outcome column decoded by anyone, any code or any agent until DD-WC21 is resolved | §4 |
| Unit | one braking-corner pass: `segment_basis = brake_onset`, `reason` NULL, not yielding, `stint` not NULL, `compound` not NULL (0 rows affected in 2022-23) | §5 |
| Free pass | `clear_ahead` true, or `gap_s ≥ 3.0` | §5 |
| Following pass | `0 ≤ gap_s < 3.0`; close = `0 ≤ gap_s < 1.0` | §5 |
| Racecraft | WC-03 C5 rule (`estimator.racecraft`), computed on **all** 2022-23 pass-table rows (as WC-03 `prepare_passes`): out of every fit, counted | §5 |
| Gap bins (s), [lower, upper) | 0-0.3, 0.3-0.5, 0.5-0.75, 0.75-1.0, 1.0-1.5, 1.5-2.0, 2.0-2.5, 2.5-3.0 (the registered 8) | §6e |
| 0-0.3 s bin | estimated and reported; used in **no** decision; per-lap scores price it at the 0.3-0.5 s value | §6e |
| Near band / far band | near = mean of the 0.5-0.75 and 0.75-1.0 bin estimates; far = mean of the 2.0-2.5 and 2.5-3.0 bin estimates | §6e |
| Group | (`race_id`, `driver`, `stint`, `compound`, `corner_id`) | §6a |
| Structure sets | Support, bracketing, φ windows, the reference compound and the pass class are fixed once, from the `seg_time_s` free-pass trim, and reused for every outcome; ties for the reference compound go to the compound name that sorts first bytewise | §6a, §6d |
| Support | a following pass is used only if its group has ≥ **2** free passes after trims | §6a |
| Field corner-lap effect φ | from free passes of ≥ **3** distinct other drivers at that corner and lap; if fewer, same corner laps l±1; then l±2; else the pass is unsupported (dropped, counted) | §6c |
| Tyre-age trend | quadratic in `tyre_life`, per (race, compound, corner class); the linear term of the race-class reference compound fixed at 0 (absorbed by φ); no driver-specific slope; a (race, compound, class) cell needs free passes from ≥ **3** distinct drivers, else that compound takes the reference compound's curve (θ1 = 0, θ2 of the reference) | §6d |
| Car behind | `behind_1s` indicator, one coefficient per corner class, from free passes | §6b |
| Incident trims | free pass: \|y − group's free-pass median\| > 2.0 s (time) or 40 km/h (speeds); following pass: \|effect\| > 2.0 s or 40 km/h; lap arm: \|effect\| > 5.0 s | §6f |
| Pass class | cross-fitted: the class uses stint offsets from the **other** corners of the same class, so it shares no free pass with τ; held up if the leader's predicted free-air time exceeds the follower's by more than 2 × se; otherwise dirty air; `unknown` if N_F < 2 or N_L < 2 (free passes at the other corners of the class), or the leader's pass is not eligible, or the leader's φ̃ is unsupported (a class with one braking corner at a race gives `unknown` for all its passes there) | §6h |
| Bracketed pass | its group has a free pass 1-5 laps earlier **and** one 1-5 laps later (local bracket); every other supported pass is one-sided; the bracketed effect uses the interpolated local baseline (linear in lap between the nearest earlier and later free pass); one trim, on τ with group α̂, for both sets | §8a |
| Switch S1 (dose-response) | seg time, every corner class: lower 95 % end of near > 0 **and** lower 95 % end of (near − far) > 0 | §11 |
| Switch S2 (one-sided vs bracketed) | D′ = (one-sided near band standardized to the bracketed mix over 15 cells of gap change × stint close-share tier) − bracketed near band; T = max(0.25 × \|bracketed\|, 0.020 s) for pace; max(0.25 × \|bracketed\|, 0.75 km/h) for the aero contrast; AGREE if the 90 % interval of D′ lies inside [−T, T] **and** ≥ 500 bracketed near-band passes enter; DISAGREE if it lies wholly outside and ≥ 100 enter; else INCONCLUSIVE | §11 |
| Switch S3 (drift, exposure-weighted) | \|B_k\| ≤ max(0.25 × \|near\|, 0.010 s), every corner class; B_k = near-pass-weighted plug-in of group drift slopes × tyre-age distance (groups with ≥ 3 free passes spanning ≥ 8 tyre-age laps) | §11 |
| Fallback F1 | lap arm: lower 95 % end of the 0.5-1.0 s median-gap band > 0, **and** S3 (corner level) passes in medium and slow; the lap arm's own bracketed comparison is a DIAGNOSTIC | §11 |
| S2 power ladder (SG7) | if SG7 fails: window ±8 laps; then pace floor 0.030 s; then S2 leaves the go/no-go table and the line prints "S2 unpowered"; each step a pre-result amendment committed alone | §17 |
| Stuck-stint flag | stint close share ≥ **0.80** → "extrapolated" | §8b |
| Gap-change split | shrinking: gap − previous-lap gap < −0.10 s; growing: > +0.10 s; steady otherwise; previous lap free counts as shrinking | §8d |
| Chance | circuit-then-race cluster bootstrap (as WC-03 A1) over the fixed 24-circuit, 43-race list in **Appendix A** for every arm; **B = 1,000, fixed**; seed **20261029** (numpy `default_rng`); 95 % percentile intervals; diagnostics use draws 1-200 of the same plan; per-lap scores 80 % intervals | §10 |
| Coast time | brake off and throttle < 5 % before own brake onset, back at most 300 m, dropout > 1.0 s → null; values > **10.0 s** set to null (`coast_implausible`), counted | §7 |
| Partial-throttle share | 5 ≤ throttle < 98 %, share of car samples in the segment, ≥ 3 samples | §7 |
| Exit speed | car-row speed at apex + 100 m, linear in distance, null if the bracketing samples are > 50 m apart; secondary aero outcome, never in a level | §7 |
| DRS in approach | any car sample with code 10, 12 or 14 in the 300 m before the segment start | §7 |
| σ̂_k | residual SD of step 1 with a degrees-of-freedom correction (§6b); the connected components of the α-φ graph are counted by the code (at least one per race and corner) | §6b |
| Coverage floor for a sidecar diagnostic | ≥ 0.70 non-null among supported following passes in that corner class, else "—, coverage"; coast coverage is counted **after** the 10 s cap (outcome-derived, written only after RUN START) | §7 |
| Level cut points | 50th / 75th / 90th / 98th percentiles of the per-lap score among 2022-23 following laps, per factor (DD-WC17); quantiles over following laps whose score is not "—"; a lap exactly at a cut takes the lower level | §13 |
| "None/barely" | no following braking corner on the lap (a lap whose only following corners are racecraft counts as following); or score below the 50th percentile; or the lap score's 80 % interval includes 0 | §13 |
| Data gate | scoped bronze (laps, telemetry, weather) 517 files `80d9623bf0c0447bdb3ef642af0250f6eb70c00e254e039ac8bb81ffdd068b3d`; pass table 8 files `188dac5e31279a4d4edf6629a095ac1dfb7511254e5a59d9ad0d619bd734dc24`; sidecar 8 files `8595ce93ca6ff211551bce2546d6635078f0a2cb60dd92ee92f1917cf5ea9d91`; full bronze 1,214 files `aed1c27da1cc00fb80eea470bb0c5c4879ee09556c81ff35bc17ad4aff1690b4`; all NFC paths; gate code `data_gate.py` sha256 `cab8c7479d42bb62d019681ff7ccf5aae15f8217c74c098621c22999bf5f3142` | §16 |
| Synthetic gate before the real run | SG1 and SG2: per-bin 95 % coverage ≥ 0.90 over 200 simulations × 200 draws, near-band bias within ±10 % of the planted value; SG3: S3 fails in ≥ 80 % of drift simulations (drift relative to the field) and passes in ≥ 90 % without drift (false alarm); SG6: aero contrast interval contains 0 in ≥ 90 % of zero-aero simulations and the held-up share is within 5 percentage points across classes; SG7 (S2 power): AGREE in medium and slow in ≥ 80 %, DISAGREE ≤ 5 % in every class, with the fixed fallback ladder | §17 |

---

## 1. Purpose and scope

- **Plain English:**
  - This registration covers one exploratory run on 2022 and 2023 only. Its job is to find out whether a "how much is following costing this driver" level can be estimated at all, and to produce the numbers a later, separate registration needs: the shape of the effect and where the level boundaries fall. It decides nothing for the product.
  - The order of ambition is fixed:
    - **Pace** first: time lost through braking corners.
    - **Aero** second, as a **proxy**: extra minimum-speed loss in fast corners compared with slow ones, in passes where the car ahead is not slower. It reads "aero-like loss", not "downforce lost".
    - **Tyre** last. It is **expected to show "—"** (not identifiable with this data), and discovery only measures how far from identifiable it is.
  - 2024 and 2025 stay sealed (§4). Every result here is in-sample.
  - Replay v1 is **retrospective**: computed after the race and played back lap by lap. Nothing here is a live or causal (trailing-only) level. That is WC-10l, under its own registration.
  - WC-10 does not decide the flat penalty, the label or anything WC-03 left open. No DA-03 number is used.
- **Formal:** the scope is WC-10e (the discovery fit and diagnostics) and the inputs WC-10f reads (per-lap scores and cut points). Era: ground-effect cars only. 2018-2021 and 2026 are out of scope.

---

## 2. Data inputs (exact)

| Input | Path | Columns read | Fingerprint |
|---|---|---|---|
| Pass table (pass d) | `_roadmap/_wake-calibration/_artifacts/WC-03-run/pass-table/pass_table_{2022,2023}.parquet` | `season`, `race_id`, `race`, `driver`, `lap`, `stint`, `compound`, `tyre_life`, `corner_id`, `corner_number`, `corner_class`, `segment_basis`, `seg_start_t`, `seg_end_t`, `seg_time_s`, `min_speed_kph`, `leader`, `leader_lap`, `gap_s`, `clear_ahead`, `behind_1s`, `tag`, `reason` | 8-file digest `188dac5e…` (§16); per-file hashes equal pass-d `SHA256SUMS` |
| Sidecar (WC-10b) | `_roadmap/_wake-calibration/_artifacts/WC-10/sidecar/sidecar_{2022,2023}.parquet` | key (`season`, `race_id`, `driver`, `lap`, `corner_id`), `exit_speed_kph`, `exit_bracket_m`, `coast_time_s`, `partial_throttle_share`, `throttle_n`, `drs_open_approach`, `prev_lap_gap_s`, `prev_lap_clear_ahead`, `prev_lap_reason` | 8-file digest `8595ce93…` (§16); joins 1:1 to the pass table (WC-10b PROVENANCE) |
| Bronze laps | `data/bronze/laps/season={2022,2023}/race=*/*.parquet` | `Driver`, `LapNumber`, `LapTime`, `Team` | inside the scoped digest `80d9623b…` |
| Pit laps (X6) | the pass table's own `reason` values `pit_lap` (own in- or out-lap) and `pit_lap_leader` (the car ahead's in- **or** out-lap: `PitInTime` or `PitOutTime` not null in `build_pass_table`), read on the rows that §5 excludes; reasons are first-match in priority order, so a pit lap that is also `yellow_sector`, `restart` or `neutralised` does not show as a pit lap; no pit column of bronze laps is read | (as pass table) | as pass table |
| Bronze schedule | `data/bronze/schedule/season={2022,2023}/schedule.parquet` (via `build_pass_table.race_calendar`) | circuit key for the bootstrap | inside the full digest `aed1c27d…` |

- `seg_time_s` is the pace outcome. `delta_time_s` and `ref_time_s` (the WC-03 ±4-lap reference) are **not used**: design A builds its own counterfactual (§6).
- **Code to be committed before the run:** `sidecar.py` and `data_gate.py` are working-tree code today (sha256 of `sidecar.py` = `8d2047b9…` in the WC-10b PROVENANCE). `data_gate.py` was reviewed by REVIEW-1 and REVIEW-2 at sha256 `34da633d4095f60104471fc773d84dacdb6b2ed9ba00bc6797df37a4a07057d5`; it is being changed for REVIEW-2 ruling (b) (checks 3 and 4 pass/fail), and the registered version is sha256 `cab8c7479d42bb62d019681ff7ccf5aae15f8217c74c098621c22999bf5f3142` (§16). The run's PROVENANCE names the commit that holds them, and the WC-10e estimator code.

---

## 3. What has already been seen (declared prior knowledge)

This follows WC-03 prereg §2e: everything that was seen before this document is listed, so nothing is presented as blind that is not.

1. **The 2026-10-21 same-lap scoping** (prereg §2e item 1). On 2018-2025 **including 2022-2025**, a lap-level traffic share fitted lap time: current-lap bit 0.473 against lag 0.331 alone; jointly 0.407 now and 0.130 lag; the continuous share within 1 s gave 0.881. **These are lap-level traffic-cost coefficients pooled over seasons that include both the discovery and the sealed seasons.** They show that a lap-level traffic effect fits lap time. This is why the confirmatory tests (WC-10g) are corner-level, fast-vs-slow and level calibration, not "is there any lap-level effect".
2. **The 2026-10-28 reference-fit rerun** (prereg §2e item 2): 0.305 (95 % interval 0.269-0.341) on the 2018-2025 yardstick panel. It is a lap-level coefficient, pooled.
3. **WC-02 check 3** (`_evidence/WC-02-2026-10-27/check3_by_class.csv`, `check3_by_class_season.csv`). For measured-reference passes **2018-2025, including 2022-2023 and 2024-2025**, the per-class Spearman correlation between the segment-time delta and minus the minimum-speed delta was −0.64 (fast), −0.59 (medium) and −0.47 (slow); sign agreement was 76 %, 74 % and 68 %. The files also print a **per-class median minimum-speed delta pooled over all gaps** (for example fast 0.0 km/h, medium −0.5 km/h) and per-season Spearman values. These are statistics of loss values, pooled over every gap, clean and following alike. They hold no information by gap.
4. **The plan's 2022 noise floor: SEEN, outcome values** (plan §9 item 4; `s04_noise_floor_2022.py`, 2022 only; clean passes and all-clean laps only). Within-group SD after a tyre-life trend:

   | Class | Segment time SD (MAD) | Minimum speed SD (MAD) | Passes |
   |---|---|---|---|
   | Fast | 0.060 s (0.026) | 3.02 km/h (1.64) | 8,846 |
   | Medium | 0.063 s (0.031) | 2.44 km/h (1.28) | 28,341 |
   | Slow | 0.064 s (0.034) | 1.86 km/h (0.98) | 26,730 |

   Free-lap time SD was 0.313 s (MAD 0.139), over 3,866 laps and 347 stints. 2022 is a discovery season. **This document uses these values to set the absolute tolerance floors in S2 and S3 (§11).** That use is allowed only because the values are declared here.
5. **The plan's and the review note's outcome-blind counts, reproduced in WC-10a** (`_evidence/WC-10-2026-10-29/counts/`, PROVENANCE MATCH, scripts s01-s03, s05, s06, r01-r03; structural columns only). Main numbers:
   - Identifying close passes 2022-25: 107,451 of 215,970. With ≥ 2 free alone: 113,271.
   - Bracketed 23,687; free only after 64,960; free only before 18,804.
   - corr(close, tyre life) within groups −0.34; nearest free pass a median 7 tyre-age laps away (p90 20; 34 % more than 10).
   - Other free cars per (race, corner, lap): median 5; fewer than 3 for 26 %.
   - Previous-lap gap present for 86.6 %, also close 73.0 %.
   - Stuck tiers 2022-25: ≥ 80 % close holds 40,294 close passes (18.7 %), 13.1 % identifying; 50-80 % holds 65,827, 36 % identifying; the < 50 % tiers are about 71 % identifying. 85,358 close passes have no free pass in their group.
   - 2022-23 identifying close: fast 7,951 / medium 21,063 / slow 20,045 (37 / 43 / 43 races); bracketed 1,674 / 4,128 / 3,995. 2024-25 identifying close: 9,479 / 25,148 / 23,765.
   - DRS 2023: any open on 91.2 % of close laps against 3.2 % of free laps.
   - Release events: 1,635 / 551 free on L+2 / 848 identity-matched / 362 matched and free. By season, matched and free: 2022 39, 2023 48, 2024 65, 2025 47.
   - Trailing ±4 reference at 0.5-1 s: 3.1 %. Car-row spacing: median 0.24 s / 13 m, p90 0.40 s / 25 m.
   - Per team 2025, close: identifying 42-55 %, own-clean 4.5-15.8 %.
   - s01's lap-time and sector coverage columns were dropped to keep the grep clean.
6. **WC-10b sidecar coverage** (`_evidence/WC-10-2026-10-29/sidecar/`). Non-null shares only: exit speed 0.983-1.0, coast 0.764-0.801, partial throttle ≥ 0.999, DRS ≥ 0.999, previous-lap gap 0.953-0.963. A range check reported counts only: **16 rows of `coast_time_s` above 30 s** (all seasons pooled, values not printed); exit speed 0 rows outside [0, 400]; throttle share 0 rows outside [0, 1]. The 16 is an outcome-derived count. It is the only sidecar value-related fact known, and it motivated the cap in §7.
7. **WC-10c gate dry run** (`gate_dryrun.txt`): the digests in §0b and §16, run twice with identical output.
8. **This draft's own structural counts, 2022-2023 only** (copied from session scratch into `_roadmap/_wake-calibration/_evidence/WC-10-2026-10-29/counts_d/`: scripts `d01_support_2022_23.py`, `d02_phi_window.py`, `d03_review_counts.py`, `d04_local_bracket.py` under `scripts/`, outputs under `csv/`; PROVENANCE in that folder). They read only `season`, `race_id`, `race`, `driver`, `lap`, `stint`, `compound`, `tyre_life`, `corner_id`, `corner_class`, `segment_basis`, `leader`, `leader_lap`, `gap_s`, `clear_ahead`, `behind_1s`, `tag`, `reason`, plus sidecar `drs_open_approach` and `prev_lap_gap_s`, plus the bronze schedule (circuit keys). A grep of the scripts finds no outcome-column name outside the docstring. They are scratch (rule 8): WC-10e recomputes every one of them at run time and reports them. The numbers (kept braking, non-yielding, `stint` not NULL; before racecraft, trims and φ drops):
   - 421,764 passes in 43 races on 24 circuits (2022: 21 races, 2023: 22). Free 172,413; following 247,203; negative gap 2,148.
   - Supported following passes (group ≥ 2 free): 150,500 (fast 23,008 / medium 65,511 / slow 61,981). Supported close: 52,164 (8,405 / 22,484 / 21,275), in 37 / 43 / 43 races.
   - Bracketed (**unlimited-distance** definition used by the first draft, kept for reference only): following 47,520; close 11,110 (fast 1,862 / medium 4,738 / slow 4,510); near band (bins 0.5-1.0) fast 1,309, medium 3,215, slow 2,958. **The registered definition is the local ±5-lap bracket** (§8a): supported following 25,345 (fast 3,636 / medium 11,347 / slow 10,362); near band 3,298 of 35,634 (fast 518 of 5,837 / medium 1,444 of 15,362 / slow 1,336 of 14,435); far band 11,248 of 44,904.
   - **Free-pass leverage for the drift check (review B1):** 150,844 of 172,413 free passes (87.5 %) sit in groups with a supported following pass. Thin compound cells (review S5): 47 of 329 (race, compound, class) cells have free passes from < 3 drivers (40 from one), holding 1,539 free and 2,376 following passes.
   - Race and circuit list: 43 races on 24 circuits, fixed in Appendix A.
   - Supported following by bin and class: 0-0.3 s: 737 / 2,168 / 2,222; 0.3-0.5 s: 1,831 / 4,954 / 4,618; 0.5-0.75 s: 3,168 / 8,505 / 7,873; 0.75-1.0 s: 2,669 / 6,857 / 6,562; 1.0-1.5 s: 3,944 / 11,414 / 10,954; 1.5-2.0 s: 4,140 / 11,844 / 11,136; 2.0-2.5 s: 3,430 / 10,487 / 9,998; 2.5-3.0 s: 3,089 / 9,282 / 8,618.
   - Field effect, supported following passes, ≥ 3 distinct other free drivers:
     - at the same corner and lap: 124,041;
     - only with laps l±1: 8,957;
     - only with laps l±2: 5,371;
     - none of these: 12,131 (8.1 %). For close passes, 7,373 of 52,164 (14.1 %).
     - A race-lap φ (all braking corners) would rescue only 580 of the 12,131.
   - Car ahead's prediction available (car ahead's pass kept and its group has ≥ 2 free passes): 34,778 of 52,164 supported close passes (66.7 %). (Old rule; superseded by the cross-fitted rule of §6h, whose share is recounted at run time.)
   - Stuck tiers 2022-23, close passes / supported: ≥ 80 % 18,537 / 1,928; 50-80 % 31,198 / 11,610; 20-50 % 35,630 / 25,390; < 20 % 15,146 / 13,236.
   - Gap change, supported close with a previous-lap gap: 49,878, of which shrinking 25,932, steady 12,615, growing 11,331.
   - DRS open in the approach: 13,582 of 52,164 supported close passes.
   - A free pass of the same group within ±4 laps: 19,860 supported close passes; within ±8: 31,264.
   - **Counts added for REVIEW-2** (independent recount by the REVIEW-2 reviewer, copied into `counts_d/` as `d05_review2_counts.py`, `d06_s3_population.py`, `d07_lap_arm.py`, `d08_appendix_check.py` with outputs `csv/d05_out.txt`-`csv/d08_out.txt`; same structural columns, plus sidecar `prev_lap_clear_ahead` and `prev_lap_reason`; d05 reproduces every number above exactly):
     - Supported near-band passes, racecraft out: 5,254 / 13,248 / 12,657. Locally bracketed (±5) among them: 428 / 1,035 / 959; and also φ-supported: **424 / 1,030 / 952**. One-sided, racecraft out, φ-supported: 4,051 / 10,344 / 9,854.
     - The bracketed near band (racecraft out, φ-supported) sits in 318 / 802 / 716 distinct groups and 348 / 875 / 818 distinct (group, earlier, later) baselines. Off-midpoint distance \|(l − l_b) − (l_a − l)\|: 0 for 18.9 %, 1 for 35.2 %, 2 for 28.1 %, 3 for 11.8 %, 4 for 6.0 %.
     - Near band bracketed, racecraft out, at ±6 / ±8 / ±10 laps: 512 / 1,238 / 1,169; **638 / 1,544 / 1,482**; 748 / 1,741 / 1,671.
     - Composition of the near band (racecraft out, φ-supported), bracketed vs one-sided: arrived from free 33.0 / 28.4 / 26.7 % vs 2.9 / 2.2 / 2.2 %; stint close share < 0.20: 64.8 % vs 20.1 %; 0.50-0.80: 3.0 % vs 24.8 %; ≥ 0.80: 0.0 % vs 4.1 %.
     - S3 population (`d06`; supported near-band passes in groups with ≥ 3 free passes whose free `tyre_life` spans ≥ 8 laps; before racecraft, φ drops and trims): 3,218 / 8,016 / 7,497 near-band passes in 965 / 2,624 / 2,372 groups; mean d −7.96 / −7.34 / −8.27 laps; iid se of B_k with the §3 item 4 SDs 0.0030 / 0.0021 / 0.0023 s (span ≥ 4: 0.0055 / 0.0035 / 0.0032 s).
     - Mean signed tyre-age distance d̄ of supported passes to their group's free-pass mean, near / far: −7.40 / −2.80 (fast), −6.56 / −2.37 (medium), −7.56 / −3.16 (slow).
     - Cross-fitted class known (N_F ≥ 2, N_L ≥ 2, leader eligible, own φ ok), of supported close non-racecraft passes: 4,124 of 7,249 (57 %), 11,576 of 18,305 (63 %), 11,131 of 17,441 (64 %). The old rule among the same 42,995: 28,845 (67 %).
     - (race, class) cells with exactly one braking corner: fast 15 of 37 races, medium 2 of 43, slow 2 of 43.
     - Train tag (car ahead's own `gap_s` at the same corner and lap < 1.0): 16,277 of 42,995 supported close non-racecraft passes (38 %).
     - φ-unsupported share of supported following passes, by race: median 5.7 %; three races above 20 % (2023_3 24.1 %, 2023_20 21.6 %, 2023_10 20.5 %); the top five races hold 38.6 % of drops; by circuit the highest is Melbourne 16.3 %.
     - Lap arm (`d07`; `LapTime` not read): 23,663 lap-arm scored laps; free 9,504; following 13,325; supported following 5,401; supported near band **1,087**; bracketed within ±5: **20** near-band laps (474 following laps over all bins); within ±8: 48 (757).
     - Appendix A equals `race_calendar` over kept passes (24 rows, NFC, bytewise order; `d08`). 2022_18 (Japan, wet) has no kept braking pass.
9. **Known to exist, with no values read for this registration (review S8; closed by REVIEW-2 §3 point 8).**
   - The archived dirty-air method (DA-03), whose shipped tax was plausibly fitted on 2022-25 by gap. Its existence is declared. No DA-03 number is used or was read.
   - **Verified: no loss value.** The WC-02 release-event results (plan §3 C, the 530 events "with readings on both sides"): WC-02 check 2's two CSVs hold only counts and presence flags (headers: `candidate_events, stays_out, stays_out_pass_rows_both_sides, stays_out_measured_delta_both_sides`; per event `n_corners, gap_s_min, rows_*, both_deltas_present, …`). The 530 is a count, not a loss value.
   - The count of 16 `coast_time_s` values above 30 s was taken over 2018-25, including the sealed seasons (item 6).
   - **Verified: no G3.2/G3.3 value exists.** The WC-04 run's PROVENANCE printed only G3.1 (a pass: the `dev.duckdb` SHA-256 `7173444b…`) and G3.4 (fail, digest `aaaf711d…`). `run_wc03.g3_checks` returns before G3.2/G3.3 when G3.1 or G3.4 fails, so no panel row count and no slope was computed. 0.4777453471 is the registered constant `G3_POOLED_SLOPE` in `run_wc03.py`: a pooled lap-level fingerprint from the WC-03 registration, the same family as items 1-2.
10. **The WC-03 run**: it stopped at G3 check 4 (digest `aaaf711d…` against `aed1c27d…`, NFD path names). Nothing was fitted or scored (`_evidence/WC-04-2026-10-29/`). The WC-03 amendment A1 synthetic coverage numbers are known; they come from synthetic data only.
11. **NOISE-INVENTORY** (`_evidence/WC-03-prep-2026-10-28/`): structural counts only. For example, 22.2 % of following braking passes have a measured reference.
12. **Everything WC-10e produces on 2022-2023, by construction**, once it is written.

**Statement on loss values in the discovery seasons.** No WC-10 effect has been read for 2022-2023: no design-A estimate, no corner-level loss by gap bin, no minimum-speed or exit-speed deficit by gap, no sidecar outcome summary. The loss-related values that have been seen and that include 2022-2023 rows are items 1-4 above. They are pooled lap-level coefficients (items 1-2, and the registered WC-03 constant 0.4777453471 of item 9, the same family), pooled rank correlations and a pooled median (item 3), and a clean-pass noise floor (item 4). None of them is broken down by gap. The WC-02 release-event files and the WC-04 G3 prints were checked (item 9) and hold no loss value. The one remaining unknown is the DA-03 method, whose existence is declared and none of whose numbers was read for this document; "nothing by gap" is therefore a claim about what was read for and before this document, with DA-03 named as the exception the owner should keep in mind.

---

## 4. Seasons and the seal

| Seasons | Role |
|---|---|
| 2022, 2023 | Discovery. Every fit, diagnostic, score and cut point in this registration. |
| 2024, 2025 | **Sealed.** Confirmation only (WC-10h), under a separate registration (WC-10g, DD-WC21). |
| 2018-2021, 2026 | Out of scope. |

- **Plain English:** nobody, and no code or agent, reads an outcome column of 2024 or 2025 until the confirmatory registration has been signed, committed alone and hashed. The 2024-25 files are hashed by the data gate (bytes only) and are otherwise never opened by WC-10e or WC-10f. The earlier pooled looks in §3 items 1-3 are already known and declared; the seal applies from now on.
- **Formal:** the loader refuses any `season` outside {2022, 2023} for the pass table, the sidecar and bronze laps (WC-10e test). The run log lists every parquet file opened for column reads, and only 2022-23 paths may appear. The gate's byte-hashing of 2024-25 files is the only exception, and no column is decoded there (`test_data_gate`).
- **The seal is procedural.** The 2024-25 outcome columns are on disk and a read cannot be detected afterwards. Every WC-10 agent brief carries the seal rule. Any read of a 2024-25 outcome column, by anyone, is logged in the build log as a breach and is named in WC-10g's seen list. (The loader guard covers WC-10e code only, and the gate proves the files are unchanged, not unread.)

---

## 5. Pass sets

| Set | Plain English | Formal |
|---|---|---|
| Eligible pass | One driver through one braking corner, on a lap with no exclusion. | Pass-table row, season ∈ {2022, 2023}, `segment_basis = brake_onset`, `reason` NULL (the WC-01 exclusions: lap 1, neutralised, yellow sector, restart, pit laps of either car, wet, track limits, no segment, off track, no gap), `tag` not `yielding`/`lapped+yielding`, `stint` not NULL, `compound` not NULL. |
| Braking corners only | Flat-out corners are not used. They have no braking point, so the corner window is not comparable (WC-03 C1). | `segment_basis = fixed_before_apex` excluded. |
| Free pass | No car within 3 s ahead. | `clear_ahead` true or `gap_s ≥ 3.0`. A car close behind does not stop a pass being free; it is adjusted for (§6b). |
| Following pass | Within 3 s of the car ahead. | `0 ≤ gap_s < 3.0`. |
| Close pass | Within 1 s. | `0 ≤ gap_s < 1.0`. |
| Racecraft | An overtake or a position change is happening nearby. | WC-03 C5, `estimator.racecraft` unchanged: `gap_s < 0`, or the leader differs at any braking corner within 3 before or after (same or adjoining lap). Computed on **all** 2022-23 pass-table rows (eligible or not), as WC-03 `prepare_passes` did. **Out of every fit** and counted (CHOICE D18). In per-lap scores a racecraft corner is priced by its bin, and `gap_s < 0` at the 0.3-0.5 s value. |
| Lapped car ahead | The car ahead is a lapped car within 3 s. | `tag = lapped`: kept, as WC-03 C2. Count reported. |

---

## 6. Design A, exactly

### Plain-English summary

For every following pass, predict what this driver would have done through this corner on this lap **in free air**, from three things:
1. their own free-air passes of the same corner in the same stint and on the same tyre;
2. how the whole field's free-air passes of that corner moved on that lap (fuel burn, rubber, wind);
3. how this compound wears with age at this race.

The pass's traffic effect is what actually happened minus that prediction. The loss at each gap is the average of those effects over all passes in the gap bin.

This is a two-step "predict from free air, then compare" design: the imputation estimator (CHOICE D1). Its key property is that the free-air prediction is built **only from free passes**. Traffic passes never shape their own baseline, and every robustness check (bracketed passes, stuck tiers, DRS, catching) is just a different average of the same per-pass effects.

**The identifying assumption, stated plainly.** Within a stint, without traffic, a driver's time through a corner moves in parallel with the field's free-air time at that corner (with the compound's wear curve), lap by lap. A driver whose own tyres or pace drift differently from the field (saving tyres while stuck, overheating them in the wake, pushing after a release) breaks this assumption. Sections 8 and 11 check it.

### 6a. Groups and support

- **Plain English:** a group is one driver, one stint, one tyre set, one corner. A following pass can be used only if its group also has at least two free passes, so the driver's own free-air level at that corner is known.
- **Formal:** group `G = (race_id, driver, stint, compound, corner_id)`. A following pass is **supported** if its group has ≥ 2 free passes after the free-pass trim (§6f). Unsupported following passes are dropped from every average and counted by class, bin and stint close-share tier. The support flag, the bracket flag, the φ windows, the reference compound and the pass class are computed once from the `seg_time_s` free-pass trim and reused for every outcome. If a speed-outcome step 1 leaves a group with no free pass, its following passes are dropped for that outcome and counted. CHOICE D5: there is no "≥ 2 close" requirement (the review's counting definition), because a group with one close pass identifies that pass as well as any other.

### 6b. Step 1: the free-air model (free passes only)

For free pass j of group G at race r, corner c, lap l, corner class k:

    y_j = α[G] + φ[r, c, l] + g_k(tyre_life_j; r, compound) + γ_k · behind_1s_j + ε_j

- Fitted separately for each **corner class** k ∈ {fast, medium, slow} and each outcome, by least squares with the fixed effects α and φ absorbed (alternating projections; converged when the largest absolute change of any coefficient in one sweep is below 1e-10 in the outcome's own unit, at most 10,000 sweeps; failure to converge is a run error and a post-hoc amendment case). The model is unweighted.
- `behind_1s` is the builder's flag (a car within 1 s behind). γ_k is estimated from free passes only.
- **σ̂_k**: the residual SD of step 1 per corner class, with a degrees-of-freedom correction: σ̂_k² = RSS / (n − p), where n is the number of free passes in the fit and p = (number of α levels) + (number of φ cells) + (number of estimated θ and γ terms) minus the number of connected components of the α-φ graph, counted by the code. (α groups and φ cells are both per corner, so there is at least one component per (race, corner), not one per (race, class).) It is used only in the class rule (§6h).

### 6c. The field corner-lap effect φ, and what happens when it is thin

- **Plain English:** φ is what happened to everyone's free-air time at that corner on that lap. It is trusted only if at least three other drivers were in free air there. If fewer were, the two neighbouring laps are pooled (then four neighbouring laps). If even that has fewer than three other drivers, the pass cannot be predicted and is dropped and counted. In 2022-23 that is 8.1 % of supported following passes, and 14.1 % of supported close ones (§3 item 8).
- **Formal:** φ̂[r, c, l] is estimated in step 1 for every (r, c, l) cell with at least one free pass. For following pass i of driver d at (r, c, l), let n_W = the number of distinct drivers ≠ d with a free pass at corner c on laps l−W..l+W. The prediction uses:
  - W = 0 (φ̂[r, c, l]) if n_0 ≥ 3;
  - else W = 1 if n_1 ≥ 3;
  - else W = 2 if n_2 ≥ 3;
  - else the pass is **φ-unsupported**, dropped and counted.

  n_W is counted on the free passes that survive the free-pass trim of the `seg_time_s` fit. For W ≥ 1, φ̃ is the mean of φ̂[r, c, l'] over l' ∈ [l−W, l+W] that have a free pass, weighted by the number of free passes in each cell. CHOICE D6. A race-lap φ fallback was considered and rejected: on the 2022-23 structure it would rescue only 580 passes (§3 item 8).
- The share of predictions at each W is reported per class and bin.

### 6d. Tyre-age trend

- **Plain English:** the field effect already carries the drift every car shares. The tyre term adds only how one compound wears differently from another at this race, and any bend in the wear curve. No driver gets a personal wear rate. Where a driver's close passes are all early and their free passes all late, a personal rate would be impossible to separate from the traffic effect (review item 1).
- **Formal:** `g_k(t; r, m) = θ1[r, m, k]·t + θ2[r, m, k]·t²`, with t = `tyre_life` and m = compound. For each (r, k), the compound with the most free passes is the reference, and its θ1 is fixed at 0. That linear term is not identified separately from φ, because within a group `tyre_life` and `lap` move together. All θ2 terms and all other θ1 terms are estimated. **Thin cells:** a (race, compound, class) cell is estimated only if its free passes come from ≥ 3 distinct drivers. Otherwise a thin compound takes the reference compound's curve at that race and class (θ1 = 0, θ2 = θ2 of the reference); its level difference is absorbed by α. The count of such cells is reported. In 2022-23 structure that is 47 of 329 cells (40 with one driver), holding 1,539 of 172,413 free passes and 2,376 of 247,203 following passes (`counts_d/csv/d03_out.txt`). If the reference compound itself has free passes from < 3 drivers, every compound at that (race, class) shares one curve (θ1 = 0, one θ2 estimated from all its free passes). CHOICE D4: piecewise-linear knots or driver-specific slopes were considered. Driver slopes do not identify under one-sided support, and knots add parameters per race without a stated benefit.

### 6e. Step 2: per-pass effects, the curve and the bands

- **Plain English:** for each supported following pass, effect = actual minus predicted free-air value. For time, positive means time lost. For minimum and exit speed, the sign is flipped, so positive means speed lost. The curve value at a gap bin is the plain average of the effects in that bin.
- **Formal:** for supported following pass i, ŷ0_i = α̂[G_i] + φ̃_i + ĝ_k(tyre_life_i) + γ̂_k·behind_1s_i.
  - Pace: τ_i = y_i − ŷ0_i, with y = `seg_time_s`.
  - Speeds: τ_i = ŷ0_i − y_i, with y = `min_speed_kph` or `exit_speed_kph`.
  - β[k, b] = the mean of τ_i over passes in class k and bin b, after the trim (§6f). Each pass has weight 1.
  - Bins are the registered 8 (§0b). There is no monotone (non-increasing) constraint: discovery reports the raw shape (CHOICE D13). The 0-0.3 s bin is reported and used in no decision, because of 0.05-0.08 s gap noise (WC-02).
  - Near = (β[k, 0.5-0.75] + β[k, 0.75-1.0]) / 2. Far = (β[k, 2.0-2.5] + β[k, 2.5-3.0]) / 2.
  - **Pace curve** (the one used in pace scores): β for `seg_time_s`, pooled over pass classes (CHOICE D8, the WC-03 C8 analogue). It needs only gap and corner class, so it applies to every lap.
  - **Class curves**: the same averages restricted to `held_up` or `dirty_air` passes, for all three outcomes.
  - **Coast time and partial-throttle share (X5)** use this estimator with their own trims: a free pass is dropped if it is more than 3.0 s (coast) or 0.5 (throttle share) from its group's free-pass median, and a following pass if |τ| exceeds the same limit.
  - The 0-0.3 s bin is priced at the 0.3-0.5 s value for aero as for pace (§13).

### 6f. Incident trims (fixed numbers, set before any fit)

- **Plain English:** passes with an obvious incident (a lock-up, a big moment, a timing fault) are left out, using wide fixed limits that ordinary traffic cannot reach.
- **Formal:**
  - (i) A free pass is dropped from step 1 if |y_j − median of its group's free-pass y| > 2.0 s (`seg_time_s`) or > 40 km/h (`min_speed_kph`, `exit_speed_kph`). The rule is applied once, per outcome, before step 1.
  - (ii) A following pass is dropped from the averages if |τ_i| > 2.0 s or > 40 km/h.
  - (iii) Lap arm: |τ| > 5.0 s (§9).

  Counts are reported per class and bin. CHOICE D9 (the 2.0 s matches WC-03 C3).

### 6g. Outcomes and their roles

| Outcome | Column | Role |
|---|---|---|
| Segment time | pass table `seg_time_s` | **Pace** (primary); the switch rule S1-S3 |
| Minimum speed | pass table `min_speed_kph` | **Aero** (primary): the dirty-air fast − slow contrast |
| Exit speed (apex + 100 m) | sidecar `exit_speed_kph` | Aero, **secondary**: reported beside minimum speed; enters no level and no switch (CHOICE D14) |
| Lap time | bronze `LapTime` | Lap arm and fallback (§9); tyre carry-over (§9b) |
| Coast time, partial-throttle share | sidecar | DIAGNOSTIC only (§12) |

A pass with a null outcome is left out of that outcome's step 1 and step 2 and counted. It is never filled.

### 6h. Held up versus dirty air (pass class), cross-fitted

- **Plain English:** a following pass is **held up** if the car ahead, in free air, would be clearly slower through this corner than this driver would be. Otherwise it is **dirty air**. "Clearly" means more than two standard errors of the difference. The comparison must not use the same free passes that set the pass's own free-air prediction: if it did, a prediction that is too fast would raise the loss τ **and** make the pass look held up at the same time, which would push held-up losses up and dirty-air losses down for no real reason. So the class is built only from how the two drivers' stints ran at the **other corners of the same class** in that race. If either stint has too little free-air running there, the class is **unknown**, and that pass does not count towards aero.
- **Formal:**
  - For follower stint F (`race_id`, `driver`, `stint`, `compound`) and class k at corner c, and for each corner c′ ≠ c of class k in the race with a group (F, c′) holding ≥ 1 free pass, let a[F, c′] = α̂[F, c′] − ᾱ[r, m, c′], where ᾱ[r, m, c′] is the mean of α̂ over all groups at race r, compound m (the stint's compound), corner c′, **excluding both the follower's and the leader's stint**. The stint offset is o[F, c, k] = the mean of a[F, c′] over those c′, weighted by each group's free-pass count. N_F = the total free passes in those groups. The leader's stint is found from the leader's pass row at (`leader`, `leader_lap`, c); o[L, c, k] and N_L are built the same way.
  - Predicted free-air values: ŷ0^cls(F) = ᾱ[r, m_F, c] + o[F, c, k] + φ̃[r, c, l] + ĝ_k(tyre_life_F) + γ̂_k·behind_1s_F, and ŷ0^cls(L) the same for the leader at (l_L, tyre_life_L, behind_1s_L). Here ᾱ[r, m, c] excludes both stints as above.
  - Δ̂_i = ŷ0^cls(L) − ŷ0^cls(F) (time). se_i = σ̂_k · sqrt(1/N_L + 1/N_F).
  - `held_up` if Δ̂_i > 2·se_i; `dirty_air` otherwise.
  - `unknown` if N_F < 2 or N_L < 2, or the leader's pass at (r, L, l_L, c) is not eligible, or the leader's φ̃ at that cell is unsupported (§6c).
  - Classes use the time model's quantities for all three outcomes. Racecraft passes are not classed.
  - τ_i itself is unchanged (§6e) and uses the pass's own corner-c α̂. The class uses no free pass from corner c of either stint's group, so the class and τ share no free-pass error at c. (φ̃ and ĝ are shared, and are common to the leader and follower at the same race.)
  - CHOICE D7: two classes, mirroring WC-03 N3. The variant that leaves out an ambiguous band (0 < Δ̂ ≤ 2·se) is a DIAGNOSTIC (§12). CHOICE D23: the cross-fit, which replaces a corner-c free-air comparison (review B3).
  - The share of supported close passes with a class (not `unknown`) is recomputed and reported at run time. The earlier 66.7 % (§3 item 8) was under the **old** rule (leader's group at corner c with ≥ 2 free passes) and no longer applies. The expected change is a drop in `unknown` for the follower and a rise for stints with free passes at too few other corners of the class.
  - **Check on the class (SG6, §17):** with zero planted aero effect, the dirty-air fast − slow contrast must contain 0 in at least 90 % of simulations.
  - **Single-corner classes.** In 15 of 37 races with fast braking corners, the fast class has only one braking corner, so every fast pass there is `unknown`; fast-class aero rests on 22 races. (Medium and slow: 2 of 43 races each; `counts_d/csv/d05_out.txt`.) In 2022-23 structure the cross-fitted class is known for 57 / 63 / 64 % of supported close non-racecraft passes (§3 item 8).

---

## 7. Sidecar definitions (fixed)

The sidecar is used as built in WC-10b: no rebuild, and its hash is in the gate. The constants in `sidecar.py` are registered as they stand, with one added rule: the coast cap.

| Column | Plain English | Formal (constants in `sidecar.py`) |
|---|---|---|
| `exit_speed_kph` | Speed 100 m after the apex. | Car-row speed at apex + `EXIT_AFTER_APEX_M` = 100 m, linear in distance; null if the bracketing car samples are > `EXIT_MAX_BRACKET_M` = 50 m apart. |
| `coast_time_s` | How long the driver was off both pedals just before braking. | Brake off and throttle < `COAST_THROTTLE_PCT` = 5 %, run back from the driver's own brake onset (last rising brake edge within 300 m before apex), at most `COAST_LOOKBACK_M` = 300 m; null if a gap between car samples > `COAST_MAX_DT_S` = 1.0 s lies inside the run; 0 if none observed. **Added cap (CHOICE D15):** values > **10.0 s** are set to null with reason `coast_implausible` and counted. Reason: the run is capped at 300 m, and covering 300 m in more than 10 s means an average below 108 km/h before a braking point under racing conditions. That points to a data fault, not a lift. The 16 values above 30 s (§3 item 6) are a subset. The alternative considered was a 30 s cap (the WC-10b range bound); it was rejected because 10-30 s is equally implausible. |
| `partial_throttle_share` | Share of the corner spent part-way on the throttle. | Share of car samples in the segment with 5 ≤ throttle < `FULL_THROTTLE_PCT` = 98 %; null below 3 samples. A sample share, not time-weighted. |
| `drs_open_approach` | DRS flap open approaching the corner. | Any car sample with DRS code in {10, 12, 14} in the 300 m before the segment start (the gap window). |
| `prev_lap_gap_s` | Gap at the same corner one lap earlier. | Pass-table `gap_s` of (driver, corner, lap − 1); null if that pass is missing or had no car ahead (`prev_lap_clear_ahead` separates the two); never 0. |

- **Thresholds 5 % and 98 % (CHOICE D15):** kept from WC-10b. The alternatives considered were 1 %/10 % for coasting and 99 % for full throttle. Reasons: the throttle channel reads 99-100 at full (some 104), so 98 leaves a noise margin; 5 % absorbs pedal noise at closed throttle. Changing either would need a sidecar rebuild and a new hash, for no stated gain.
- **Resolution, stated:** about 4 Hz (median 13 m between samples, p90 25 m). Exit speed is interpolated. Coast time resolves to about 0.24 s and is a lower bound. Brake is on/off only.
- **Coverage rule:** coverage (the non-null share) of each sidecar column among supported following passes is reported per class. Coast coverage is counted **after** the 10 s cap; it is therefore outcome-derived and written only after RUN START. A sidecar diagnostic is reported for a class only if coverage there is ≥ 0.70; otherwise it shows "—, coverage < 0.70". Exit speed as a secondary aero outcome follows the same rule.
- **W9 holds until DD-WC20:** no value, mean or distribution of a sidecar outcome is printed before the run completes the gate and writes RUN START.

---

## 8. The identification holes from the review note, and how each is handled

### 8a. One-sided support (review item 1: the biggest hole)

- **The hole:**
  - Only 22 % of identifying close passes (2022-25, the review's definition: ≥ 2 close and ≥ 2 free in the group) have free passes of the same corner both before and after them in the stint. 60 % have free passes only later.
  - For most passes, therefore, the close-vs-free comparison runs through the drift model (φ and g), not through a local comparison.
  - Under the **local** definition below, 2022-23 supported near-band (0.5-1.0 s) passes that are locally bracketed number fast 518, medium 1,444, slow 1,336 of 5,837 / 15,362 / 14,435 (`counts_d/csv/d04_out.txt`; before outcome trims). Fast is below the 500 AGREE floor of S2: it is 424 after racecraft and φ drops (medium 1,030, slow 952; `counts_d/csv/d05_out.txt`).
- **Plain English:** every headline number is reported for the **one-sided** passes and for the **locally bracketed** passes, where the driver had free air at that corner within five laps both before and after. The bracketed estimate leans far less on the drift model, because its baseline is interpolated between a free pass on each side and so cancels any steady (linear) drift. The two are compared **with each other** (§11 S2), not with the full-sample number, after the one-sided passes are reweighted to the bracketed passes' catching and stuck-stint mix. If they differ by more than a fixed tolerance, design A is not trusted. The bracketed estimate is a **mandatory companion**: every table that shows a near-band, far-band or aero-contrast value shows its bracketed value beside it.
- **Formal:**
  - A supported following pass i in group G is **bracketed** if G has a free pass at lap l_b with l_i − 5 ≤ l_b < l_i **and** a free pass at lap l_a with l_i < l_a ≤ l_i + 5, both in the trimmed step-1 set. Every other supported pass is **one-sided** (free passes only on one side within five laps, or none within five laps). The two sets partition the supported passes.
  - The bracketed estimate uses an **interpolated local baseline**: ŷ0^loc_i = φ̃_i + ĝ_k(tyre_life_i) + γ̂_k·behind_1s_i + w_b·r_b + w_a·r_a, with w_b = (l_a − l_i)/(l_a − l_b) and w_a = (l_i − l_b)/(l_a − l_b) (linear interpolation in lap; within a stint `tyre_life` and lap differ by a constant). r_b and r_a use φ̂ at the free pass's own (r, c, lap) cell. A linear drift cancels exactly. Trim (ii) is applied once, to τ with the group α̂ (§6e); a pass dropped there is dropped from β^one and β^brk alike, and τ^loc is not trimmed separately. CHOICE D26.
  - Here r_b and r_a are the step-1 values y − φ̂ − ĝ − γ̂·behind_1s of the nearest earlier free pass (lap l_b) and the nearest later free pass (lap l_a) of the group, within the ±5-lap bracket. τ^loc_i = y_i − ŷ0^loc_i (sign-flipped for speeds as in §6e). In 2022-23 structure 81 % of bracketed near-band passes are 1-4 laps off the midpoint of their bracket (§3 item 8), which is why a plain average of r_b and r_a would not cancel drift.
  - β^brk[k, b] = the mean of τ^loc over bracketed passes in class k and bin b. β^one[k, b] = the mean of τ (§6e, group α̂) over one-sided passes. D′ (§11 S2) is computed with β^one standardized to the bracketed composition, paired within each bootstrap draw.
  - The tolerance, equivalence test and verdict are in §11 S2.
  - Counts of bracketed and one-sided passes per class and bin are reported.

### 8b. Stuck-all-stint stints (review item 2)

- **The hole:**
  - In 2022-25, stints with ≥ 80 % of passes close hold 18.7 % of close passes, and only 13 % of them are identifying. In 2022-23 it is 18,537 close passes, of which 1,928 are supported.
  - The effect is learned from drivers whose gap varied and applied to stuck drivers by assumption.
- **Plain English:** levels on a stint spent almost entirely close behind are shown with an **"extrapolated"** note. Discovery reports the effect separately for each close-share tier, so a tier that behaves differently can be seen.
- **Formal:**
  - Stint close share = the share of the stint's eligible braking passes (`race_id`, `driver`, `stint`, `compound`) that are close (0 ≤ `gap_s` < 1.0). Racecraft passes are eligible: they count in the denominator, and in the numerator if their gap is in [0, 1.0). A pass with a negative gap is not close.
  - Tiers: < 0.20, 0.20-0.50, 0.50-0.80, ≥ 0.80.
  - Every lap in a stint with close share ≥ 0.80 carries the flag `extrapolated` on its pace and aero levels.
  - The near band per tier (seg time and the aero contrast) is reported as a DIAGNOSTIC with intervals, plus the supported share per tier.

### 8c. Thin field effect (review item 4)

- **The hole:** a median of 5 other free cars per (race, corner, lap); 26 % of identifying close passes have fewer than 3.
- **Handling:** the minimum of 3 distinct other free drivers and the ±1 / ±2 lap fallback (§6c). Unsupported passes are dropped and counted. The near band is also reported by the window used (W = 0 against W ≥ 1) as a DIAGNOSTIC.
- **Stated selection:** the dropped passes cluster where few cars are free, most likely early in the race when the field is bunched. The report gives their count by lap-of-race decile, and the φ-unsupported share per race (§13 item 2). φ drops concentrate in a few races (2022-23 structure: three races above 20 %, median 5.7 %; no circuit loses more than a sixth, §3 item 8).

### 8d. Catching bias (review item 5)

- **The hole:** a driver closes up because they are faster, so close passes look fast (loss underestimated); the reverse happens when falling back. The lagged-gap refit is weak, because 73 % of passes with a previous-lap gap were also close on the previous lap.
- **Plain English:** the **primary** catching check splits the effect by whether the gap to the car ahead was shrinking, steady or growing since the previous lap at the same corner. If catching bias matters, the shrinking passes show a smaller loss than the growing ones. The lagged-gap refit is kept as a secondary check. Both are DIAGNOSTIC: they never move a level or the switch.
- **Formal:**
  - Δgap_i = `gap_s` − `prev_lap_gap_s`. Shrinking if Δgap < −0.10 s; growing if > +0.10 s; steady otherwise.
  - If the previous lap was free (`prev_lap_clear_ahead` true, or `prev_lap_gap_s ≥ 3`), the pass counts as shrinking and is also counted separately as "arrived from free".
  - If there is no previous pass (null with `prev_lap_clear_ahead` null), or the previous lap's pass is excluded (`prev_lap_reason` not null), the pass is "unknown".
  - 0.10 s is above the 0.05-0.08 s gap noise (CHOICE D20).
  - The near band (seg time) per split is reported with intervals.
  - A printed **flag** "catching sensitivity large" is raised for a class if |β_near^grow − β_near^shrink| > |β_near|. It is carried into the confirmatory draft and changes nothing here.
  - Δgap covers the previous lap's segment, not this pass's segment, so it is not a function of this pass's outcome. It is still correlated with the driver's relative pace on that lap, which is the point of the split.

### 8e. Gap bin × tyre age collinearity

- **The hole:** within groups, corr(close, tyre_life) = −0.34. Close passes come early in a stint, free ones later. Near bins therefore sit further from their free passes than far bins, so a drift error does not cancel in near − far.
- **Handling:**
  - (1) No driver-specific slope (§6d).
  - (2) The bracketed companion and its comparison with the one-sided passes (§8a, §11 S2).
  - (3) The S3 drift check (§11): each group's own free-pass residual slope on `tyre_life`, multiplied by each near-band pass's tyre-age distance from that group's free passes and averaged over the near-band passes (B_k), which is the implied drift bias on the near band.
  - (4) A DIAGNOSTIC ±4 / ±8-lap local-baseline variant (§12).
  - (5) Reported per bin: the mean signed tyre-age distance d̄_b between each supported pass and its group's free passes, and the share of passes one-sided after / before / bracketed. These are structural numbers, so the extrapolation each bin relies on is visible.

### 8f. Release events (review item 3)

The car-ahead-pits check uses the **identity-matched** set only, registered as the r03 script (`_evidence/WC-10-2026-10-29/counts/`) defined it:
- **Lap state** comes from the median braking gap over the lap's eligible braking passes, with clear ahead set to 30 s. A lap is **following** if that median is < 1.5 s, **free** if every braking pass is free, and **mostly free** if the median is ≥ 3 s (tested in that order; eligible as in §5 without the `compound` filter, racecraft not removed, as r03 did).
- An **event** is a following lap L where:
  - some pass row on L+1 has reason `pit_lap_leader` with `leader` equal to L's modal `leader`;
  - no pass row on L+1 has `pit_lap` (the follower stays out);
  - L+2 (same stint) is free or mostly free.
- `pit_lap_leader` is the car ahead's in- **or** out-lap (`PitInTime` or `PitOutTime` not null), not only its pit entry. Reasons are first-match in priority order, so a pit lap masked by an earlier reason (`yellow_sector`, `restart`, `neutralised`) is missed.
- Free uses `gap_s ≥ 3`, as everywhere else in this registration. r03 used `gap_s > 3`; if the recount changes under ≥ 3, both counts are reported and the ≥ 3 set is used.

In 2022-23 that is 87 events (2022: 39, 2023: 48). The WC-10e run recounts them against `_evidence/WC-10-2026-10-29/counts/` (`c2_release_by_season.csv`) before using them; the recount must reproduce 39 / 48 (under r03's > 3, if ≥ 3 differs). The check is DIAGNOSTIC, sign only (§12).

---

## 9. The lap-level arm (also the fallback), and tyre carry-over

### 9a. Lap arm: net lap pace

- **Plain English:** the same predict-then-compare idea at the level of whole laps. Predict this driver's free-air lap time from their own free laps in the stint, the field's free laps on that lap, and the compound's wear. A following lap's effect is actual minus predicted. Effects are averaged by the lap's median gap. This number is **net of DRS and tow**, because a whole lap includes the straights. It is always fitted. If design A fails the switch rule (§11), it becomes the pace level, and aero and tyre show "—".
- **Formal:**
  - Scored lap (lap arm): every braking corner of the race on that lap has an eligible pass (§5), there is no yielding and no racecraft pass, and bronze `LapTime` is present. (Per-lap scores in §13 use a different, wider set: the **score lap**.)
  - Median gap: the median over braking corners of `gap_s`, with free corners set to 3.0 s.
  - Free lap: every braking corner free.
  - Following lap: median gap in [0, 3.0).
  - Step 1 on free laps: `LapTime = α[race, driver, stint] + φ[race, lap] + g(tyre_life; race, compound) + ε`, with g as in §6d (the per-class index dropped) and φ under the §6c rule over distinct other free drivers on that lap (W = 0, 1, 2, else unsupported).
  - Support: the driver-stint has ≥ 3 free laps.
  - τ = LapTime − ŷ0; trim |τ| > 5.0 s. β_lap[b] = mean τ by the 8 median-gap bins. Near_lap = mean of the 0.5-0.75 and 0.75-1.0 bins.
  - **Lap-arm bracketed companion (DIAGNOSTIC).** A following lap is *bracketed* if the driver-stint has a free lap 1-5 laps earlier and one 1-5 laps later; the bracketed effect uses the interpolated baseline of §8a (w_b·r_b + w_a·r_a over the nearest earlier and nearest later free lap's residual). The one-sided and bracketed Near_lap and their difference are reported with intervals, as a DIAGNOSTIC only: in 2022-23 structure only 20 near-band laps are bracketed within ±5 laps (474 following laps over all bins, 1,087 supported near-band laps; `counts_d/csv/d07_out.txt`), so no verdict could ever be reached. F1's drift guard is corner-level S3 instead (§11). CHOICE D21, D30.

### 9b. Tyre carry-over θ_carry (expected "—")

- **Plain English:** does a driver stay slower on **free** laps after a spell close behind, more so the longer the spell? This is the only tyre signal the data has (no temperature or sliding data). It is confounded by tyre saving while stuck, pushing after a release, and off-cycle pit stops, and is expected not to be identifiable. Discovery measures it and its checks. The tyre level is shown only if the confirmatory C5 gate passes.
- **Formal:**
  - Close lap: a scored lap with median gap < 1.0 s. Episode: a maximal run of consecutive close laps in a stint.
  - C_l = the number of close laps earlier in the stint.
  - On free laps of driver-stints with ≥ 3 free laps:

        LapTime = α[race, driver, stint] + φ[race, lap] + g(tyre_life; race, compound) + θ_carry·C_l + Σ_{j=1..3} π_j·1{l is j laps before the stint's next episode} + ε

    fitted jointly by least squares (θ is a coefficient here, not an average).
  - Reported:
    - θ_carry with its interval;
    - the pre-trend π_1..π_3 (should be 0);
    - θ by episode-length tier: C_l split into close laps from episodes of 1-2, 3-4 and ≥ 5 laps; the plan expects growth with length.
  - Nothing here decides a tyre level. That is confirmatory C5.

---

## 10. Chance: the bootstrap

- **Plain English:** to see how much of each number could be luck, the data are reshuffled 1,000 times. Each reshuffle first draws circuits with replacement, then that circuit's races with replacement, and reruns the whole chain: step 1, the class rule, the effects, the averages and the checks. The interval is the middle 95 % of the 1,000 results.
  - Circuits are drawn first because the same corner appears in 2022 and 2023, and its effect probably differs by layout. WC-03 amendment A1 showed, on synthetic data, that resampling races alone gives intervals that are too narrow when circuit-level variation exists.
  - There are 24 circuits and 43 races in discovery, so the intervals rest on about 24 clusters, and that is stated with every table.
- **Formal:**
  - Circuit key: `build_pass_table.race_calendar` (`CIRCUIT_ALIASES`, `SEPARATE_LAYOUT_SLUGS`).
  - **The lists are fixed literals in Appendix A:** 24 circuit keys and 43 `race_id`s. They are the races with at least one kept braking pass (§5) in 2022-23, counted from structural columns only. The draw plan is made over these lists for **every** arm (corner level, lap arm, tyre carry-over and diagnostics). A race in the list with too little data for an arm stays in the plan and simply contributes nothing; no race is added or removed by support, trims or outcomes. The run refuses to start if `race_calendar` yields a different mapping from Appendix A (a test).
  - Plan per draw, from one `numpy.random.default_rng(20261029)`: first `integers(0, 24, 24)` over the circuit list of Appendix A (sorted bytewise on the NFC UTF-8 key); then, for each drawn circuit in draw order, `integers(0, m, m)` over that circuit's race list (sorted bytewise on `race_id`).
  - A circuit drawn twice enters as two distinct circuits. Its races, groups, φ cells and pass classes are separate copies. A race drawn twice within one copy counts twice.
  - **B = 1,000, fixed.** The point estimate is the full-sample fit, not the bootstrap mean.
  - Intervals: 95 % percentile (2.5th-97.5th). Per-lap scores: 80 % percentile (10th-90th) from the same draws.
  - **Diagnostics** (§12) use draws 1-200 of the same plan (CHOICE D3) to save run time. They are labelled as such.
  - No fallback count. If the synthetic timing (§17) shows 1,000 draws cannot finish, the fix is a pre-result amendment.
  - CHOICE D2 (circuit-then-race; the alternative is race-level) and D3 (the seed is new: 20261029, the drafting date; WC-03's 20261027 is not reused, so no draw plan is shared with WC-03's code paths).

---

## 11. The switch rule: design A, the fallback, or neither

The rule is computed once, on the full run, and printed as the **go/no-go line**, the first line of the discovery summary.

**S1: the dose-response is visible (pace, seg time).**
- **Plain English:** in every corner class, the loss 0.5-1.0 s behind is clearly above zero and clearly above the loss 2-3 s behind.
- **Formal:** for each k ∈ {fast, medium, slow}: the lower 95 % end of β_near > 0 **and** the lower 95 % end of (β_near − β_far) > 0 (CHOICE D12).

**S2: one-sided and bracketed passes agree (pace; and, separately, the aero contrast).**
- **Plain English:** estimate the near-band loss twice: from the passes whose free-air baseline sits on only one side (these lean on the drift model), and from the passes with a free pass on each side within five laps, which use an interpolated local baseline between the two (this cancels a steady drift). Bracketed passes are mostly brief encounters (the driver arrived from free air and left again), so before comparing, the one-sided passes are reweighted to the bracketed passes' mix of catching state and stuck-stint tier. If the two agree to within a fixed tolerance, with the uncertainty included, the drift model is not distorting the one-sided passes. If the data cannot show that, the answer is "inconclusive", not "agree". The tolerance is a quarter of the bracketed estimate, so it does not grow with the bias it is guarding.
- **Formal:**
  - For pace, per class: T = max(0.25·|β̂^brk_near|, **0.020 s**), and D′ is the standardized difference of the next bullet (β^brk from §8a). CHOICE D28.
  - β^one_near is standardized to the bracketed composition: D′ = Σ_s w_s·β^one_near,s − β^brk_near, where s runs over the 15 cells of gap change (§8d: shrinking, arrived from free, steady, growing, unknown) × stint close-share tier (< 0.20, 0.20-0.50, ≥ 0.50), w_s is the share of bracketed near-band passes in cell s, and β^one_near,s is the near band of one-sided passes in cell s. Bracketed passes in a cell with fewer than 20 one-sided near-band passes are dropped from β^brk and counted. The unstandardized D′ is reported beside it.
  - Cell rules (part of CHOICE D28): "shrinking" here excludes "arrived from free" (the two are separate cells; §8d's "counts as shrinking" applies to X3 only). The stint close-share tier is §8b's, with the two top tiers merged at ≥ 0.50. "Near band of cell s" is the mean of the 0.5-0.75 and 0.75-1.0 bin means within the cell; a cell with no one-sided pass in one of the two bins uses the other bin's mean.
  - For the aero contrast A = β_near^{dirty, fast} − β_near^{dirty, slow} (`min_speed_kph`; medium − slow reported alongside), computed on one-sided and on bracketed dirty-air passes: D′_A = A^one − A^brk; T_A = max(0.25·|Â^brk|, **0.75 km/h**). D′_A uses the same 15 cells: each class's one-sided dirty-air near band is standardized to that class's bracketed dirty-air mix before the fast − slow difference.
  - Verdict per comparison (an **equivalence test**):
    - **AGREE** if the 90 % percentile interval of D′ lies inside [−T, T] **and** at least 500 bracketed near-band passes enter β^brk after racecraft, φ drops and trims (for A: the smaller of the fast and slow dirty-air counts);
    - **DISAGREE** if that interval lies wholly outside [−T, T] and at least 100 bracketed passes enter;
    - **INCONCLUSIVE** otherwise.
    - For A, both counts are the smaller of the fast and slow dirty-air bracketed counts.
  - The window (±5 laps) and the floors are fixed. The floors are about one third of the seen per-pass noise SD (0.06 s; 1.9-3.0 km/h; §3 item 4). CHOICE D10, D27. SG7 (§17) checks that S2-pace can reach AGREE under no drift; if it cannot, the fixed ladder of SG7 applies (±8 laps, then a 0.030 s pace floor, then "S2 unpowered"), each step a pre-result amendment (CHOICE D29).
  - **Expected weakness, stated now:** 2022-23 bracketed near-band counts after racecraft and φ drops, before trims: 424 / 1,030 / 952. Fast pace S2 and S2-aero cannot be AGREE; they can still be DISAGREE on a clear gap, and DISAGREE blocks.

**S3: no extrapolation drift in the free-air model (exposure-weighted group drift).**
- **Plain English:** the free-air model is used to predict a pass several laps away from the driver's free passes. If a driver's own pace drifts with tyre age differently from the field, that prediction is off by (the drift) × (how many laps away the pass is). So for each driver-stint-corner with enough free running, measure how its free-air residuals trend with tyre age, multiply that trend by how far each real near-band pass sits from the group's free passes, and average over the near-band passes. That average is the drift bias on the near-band loss, and it must be small against the effect.
- **Why this and not a pooled slope of residuals.** Over all free passes of a (race, corner), the residual slope on `tyre_life` is zero by construction, because the group effect and the corner-lap effect absorb it. That was the first draft's S3, and the second draft's leave-one-out slope was the same slope reweighted (REVIEW-2 R2-B1). Of 2022-23 free passes, **87.5 %** (150,844 of 172,413) sit in groups that also hold a supported following pass (fast 88.8 %, medium 87.3 %, slow 87.3 %; 15,634 of 19,137 groups with a free pass; `counts_d/csv/d03_out.txt`), so even a slope restricted to such groups would pass for any drift. B_k below weights each group by its near-band exposure and distance, which the normal equations do not constrain.
- **Formal:**
  - Population: groups G of class k with ≥ 3 free passes after trims whose free passes span ≥ 8 tyre-age laps (max − min `tyre_life`), and ≥ 1 supported near-band pass that enters β_near (not racecraft, φ-supported, not trimmed).
  - b̂_G = the OLS slope, with intercept, of the step-1 residuals ε̂_j on `tyre_life_j` over G's free passes.
  - d_i = `tyre_life_i` − the mean `tyre_life` of G's free passes.
  - B_k = the mean over those near-band passes of b̂_{G(i)} · d_i. Under a linear drift of the driver relative to the field, τ_i is biased by exactly (that drift) × d_i, so B_k is the plug-in estimate of the drift bias on β_near.
  - Pass if |B_k| ≤ max(0.25·|β̂_near,k|, 0.010 s) in every class (point estimates; the 95 % interval and the share of near-band passes covered are reported).
  - Why not a pooled slope: `tyre_life` lies in the span of the α and φ dummies, so step-1 residuals sum to zero against `tyre_life` within every (race, corner). Any slope weighted by free passes (including a plug-in leave-one-out slope, which is that slope reweighted by (n/(n−1))²) is near zero by construction. B_k weights each group by its near-band exposure and distance, which the normal equations do not constrain.
  - 2022-23 structure (before racecraft, φ drops and trims): the population covers 3,218 / 8,016 / 7,497 of 5,837 / 15,362 / 14,435 supported near-band passes; mean d is −8.0 / −7.3 / −8.3 laps; with the seen per-pass SD (§3 item 4) the iid standard error of B_k is about 0.003 / 0.002 / 0.002 s (0.006 / 0.004 / 0.003 s with a 4-lap span, which is why 8 is used).
  - CHOICE D11 (the tolerance is unchanged) and D24 (the statistic).
  - SG3 (§17) requires S3 to fail in at least 80 % of simulations with a planted +0.01 s per lap driver drift made relative to the field, and to pass in at least 90 % without it.

**F1: the fallback shows a dose-response and is drift-checked.**
- **F1:** lap arm: the lower 95 % end of Near_lap > 0, **and** S3 (corner level) passes in medium and slow. The lap arm's own bracketed comparison (§9a) is a DIAGNOSTIC: in 2022-23 structure only about 20 near-band laps are bracketed within ±5 laps (474 following laps over all bins, 1,087 supported near-band laps). The FALLBACK line carries "lap drift checked through corner-level S3 only".
- CHOICE D30. (The lap arm has no S3 analogue of its own; corner-level S3 is the drift evidence for the driver-stint pace drift that a lap-level fit would share.)

**The go/no-go line:**

| Condition (read top to bottom; first match wins) | Line | What goes to the confirmatory draft (WC-10g) |
|---|---|---|
| S1 passes in every class, S2-pace has no DISAGREE and AGREE in medium and slow, S3 passes in every class | **DESIGN A** | pace from design A (corner level); aero **if** S2-aero is not DISAGREE, else aero "—"; tyre to C5 |
| Otherwise, and F1 passes | **FALLBACK (lap level, pace only)** | pace from the lap arm, labelled "net of DRS/tow"; aero "—"; tyre to C5 |
| Otherwise | **NEITHER** | no pace level; aero "—"; tyre to C5; the owner decides whether WC-10 continues |

- Fast-class S2 INCONCLUSIVE does not block DESIGN A. It is printed on the line as "fast-corner bracketed check inconclusive" and carried into WC-10g as a stated weakness. S2-aero INCONCLUSIVE is treated the same way (aero is proposed, with the weakness printed). Medium or slow INCONCLUSIVE does block DESIGN A, because the table requires AGREE there. A DISAGREE in any class blocks (pace: DESIGN A; aero: aero "—"); with the 100-pass floor, fast and aero can reach DISAGREE.
- **If SG7's ladder ended at step 3** ("S2 unpowered", §17), the S2 conditions are dropped from the first row of the table, S2 is still computed and printed, and the line carries "S2 unpowered".
- The line is computed by code from the registered rule and written as, for example: `GO/NO-GO: DESIGN A | S1 pass,pass,pass | S2 pace INCONCLUSIVE,AGREE,AGREE | S2 aero INCONCLUSIVE | S3 pass,pass,pass`.
- **The line decides only what is proposed for confirmation.** It does not decide what is shown to anyone.

---

## 12. Diagnostics (every one labelled DIAGNOSTIC) and multiple testing

**DIAGNOSTIC.** None of the items below moves a level, a cut point or the go/no-go line. Each prints with the word DIAGNOSTIC in its table title. Each uses draws 1-200 (§10).

| # | Diagnostic | What is reported |
|---|---|---|
| X1 | Drift: local-baseline windows ±4 and ±8 laps | α̂ replaced, per following pass, by the mean of (y − φ̂ − ĝ − γ̂·behind_1s) over the group's free passes within ±W laps (≥ 2 required, else dropped and counted); near band and far band per class; count supported (2022-23 close: 19,860 within ±4, 31,264 within ±8) |
| X2 | Lagged gap (secondary catching check) | β by bins of `prev_lap_gap_s` instead of `gap_s`; same passes where a previous-lap gap exists |
| X3 | Shrinking / steady / growing gap (primary catching check) | §8d; the "catching sensitivity large" flag |
| X4 | DRS-tagged split | near band per class with `drs_open_approach` true vs false (2022-23 supported close: 13,582 open) |
| X5 | Coast time and partial-throttle share by gap | the same estimator (§6) with these as outcomes, per class and bin, plus near − far; read as "a rise equal in slow and fast corners points to saving or being held up, not wake" (confidence note only) |
| X6 | Release events (identity-matched, r03 definition, §8f) | per event: lap-arm effect on L and on L+2 (sign of the change), and the pace score on L; counts by drop reason; 87 events in 2022-23 (39 / 48) |
| X7 | Close-share tiers | §8b |
| X8 | Field-effect window used | near band for passes predicted with W = 0 vs W ≥ 1 (§6c) |
| X9 | Pass class with ambiguous band removed | aero contrast using dirty air with Δ̂ ≤ 0 only |
| X10 | Monotone version | β after pool-adjacent-violators per class (WC-03 C7 style), beside the raw bins |
| X11 | Per team | supported share and near band per team |
| X12 | Exit-speed aero contrast | §6g |
| X13 | Train tag | following passes where the car ahead is itself within 1 s of its own car ahead (its `gap_s` at the same corner and lap < 1.0); near band and aero contrast with and without the tag; a car behind a held-up car ahead is otherwise classed dirty air (§6h) |
| X14 | Post-release washout | step 1 refitted after dropping free passes within 3 laps after a following spell (a maximal run of consecutive laps on which the group's pass is following, 0 ≤ gap < 3, or racecraft); near band beside the registered one |
| X15 | Lap-arm bracketed companion | §9a: one-sided and bracketed Near_lap and their difference with intervals; no verdict (about 20 bracketed near-band laps in 2022-23 structure) |

X1-X15 run on the time-model structure sets (support, bracket, φ windows, reference compound and pass class from the `seg_time_s` trim, §6a), except where a row says otherwise (X14 refits step 1).

**Reading the quantile "maximum".** The top level is the 98th percentile by construction (§13): about 2 % of following laps reach it whatever the effect size. With one pooled curve per class, the score is mostly exposure (how many following corners the lap has, and at what gap), so "maximum" will mostly land on stuck stints and carries the `extrapolated` flag often. It is not a physical limit (DD-WC17).

**Multiple testing.**
- **Plain English:** discovery makes no claims, so it tests nothing for significance. The only rules applied to intervals are S1, S2, S3 and F1, fixed above. Every other interval is a description. With dozens of intervals printed, some will exclude zero by chance, and none of them is read as a finding.
- **Formal:** all intervals are unadjusted 95 % percentile intervals. The summary prints the total number of intervals reported, with the sentence: "Discovery intervals are unadjusted and describe 2022-23 only; no discovery interval is a test." The words "significant", "confirmed" and "proves" do not appear in discovery outputs. Holm's correction belongs to the confirmatory gates (C1, C2, C5 in WC-10g), not here.

---

## 13. What discovery produces

Into `_roadmap/_wake-calibration/_evidence/WC-10-discovery-<date>/`. Parquet goes into `_artifacts/WC-10/discovery/` with SHA256SUMS (rule 8).

1. **SUMMARY.md:**
   - line 1: the go/no-go line (§11);
   - line 2: "Exploratory, discovery data (2022-23), in-sample, not confirmed.";
   - line 3: "Levels are relative to the typical following lap.";
   - then the S1-S3 and F1 tables with thresholds, estimates, intervals and verdicts.
2. **Support tables:** every §3 item 8 count recomputed, plus counts after racecraft, trims and φ drops, per class × bin × W, bracketed / one-sided, close-share tier, pass class (held up / dirty air / unknown), per team, and the φ-unsupported share per race and per circuit. The S2 composition cells (15 per class: counts of bracketed and one-sided near-band passes, w_s, and bracketed passes dropped for a thin cell).
3. **Curves (CSV):** class × bin × outcome × set (all, bracketed, held up, dirty air) with estimate, 95 % interval, passes, races and circuits. Near, far and near − far. The aero contrasts (fast − slow, medium − slow) for minimum and exit speed.
4. **Lap arm:** β_lap by median-gap bin, the bracketed companion (DIAGNOSTIC, X15), F1 (with corner-level S3 as its drift guard).
5. **Tyre:** θ_carry, pre-trend π_1..π_3, θ by episode-length tier, with intervals and counts.
6. **Diagnostics X1-X15**, each titled DIAGNOSTIC.
7. **Per-lap scores** for every scored 2022-23 lap: point estimate, 10th and 90th percentiles over the 1,000 draws, the `extrapolated` flag, and the reason when unavailable:
   - **Score lap.** A lap is scored if every braking corner of the race on that lap is either an eligible pass (§5) or a racecraft pass (§5); `LapTime` is **not** required, and a lap with a yielding tag is not scored. (This is a wider set than §9a's lap-arm "scored lap" which excludes racecraft and requires `LapTime`.) A following lap, for cut points, is a score lap with at least one corner at 0 ≤ gap < 3 or racecraft.
   - **Pace** `S_pace` (s) = Σ_k w_k · β_pace(class_k, bin_k) over the lap's braking corners. w_k are the WC-03 §7 no-double-counting weights from `seg_start_t` / `seg_end_t`. The 0-0.3 s bin is priced at the 0.3-0.5 s value. Racecraft corners are priced by their bin (gap < 0 at the 0.3-0.5 s value). Free corners give 0. In `S_aero`, the 0-0.3 s bin is priced at the 0.3-0.5 s value of the minimum-speed curve; racecraft corners are not classed and give 0 (their count is reported). Straights and flat-out corners are not priced, and the page says so. Under FALLBACK, `S_pace` = β_lap(the lap's median-gap bin), labelled net of DRS/tow.
   - **Aero** `S_aero` (km/h) = Σ over the lap's fast and medium braking corners with pass class `dirty_air` and 0 ≤ gap < 3 of [β_dirty^{min speed}(class_k, bin_k) − β_dirty^{min speed}(slow, bin_k)]. Held-up corners give 0. If more than half of the lap's fast and medium following corners are `unknown`, the result is "—" with reason "car-ahead level unknown" (CHOICE D16).
   - **Tyre:** not scored in discovery (it waits on C5).
8. **Cut points** (computed at WC-10f from these outputs only, by this rule, DD-WC17):
   - For each factor with a score: the 50th, 75th, 90th and 98th percentiles of the point `S` over **following laps** of 2022-23 (a score lap with at least one braking corner at 0 ≤ gap < 3 or racecraft) whose score for that factor is not "—". A lap whose only following corners are racecraft counts as following and is scored by its racecraft pricing. A lap exactly at a cut takes the lower level. Quantiles use numpy's default (linear) method.
   - Seconds are written to 3 decimals, km/h to 2.
   - Levels: **none/barely** below the 50th percentile; **low** 50th-75th; **medium** 75th-90th; **high** 90th-98th; **maximum** ≥ 98th, meaning "about as large as this data has seen", not a physical limit.
   - **None/barely is also definitional:** a lap with no following braking corner; or a lap whose 80 % score interval includes 0 (CHOICE D17).
   - The page text says that levels are relative to the typical following lap.
   - Physical cuts may be revisited at WC-10f, before WC-10g is signed (DD-WC17). If they are, the reason is written down and the quantile cuts stay in the evidence beside them.
9. **PROVENANCE.txt:** this registration's SHA-256 (from DD-WC20's resolution), code commit, interpreter, the gate result lines, the run ledger (§0a), seed, B, every file opened (2022-23 only), and output hashes.

---

## 14. What discovery is NOT allowed to conclude

- That anything **generalises** beyond 2022-23. Every number is in-sample. 2024-25 decides that (WC-10h).
- That following **causes** the effect, or that the aero proxy is **downforce** lost. It reads "aero-like loss". Lifting to avoid the gearbox ahead, or saving front tyres, give the same signature.
- Any **tyre** level. The tyre factor shows "—" until C5 passes in confirmation.
- Any **per-lap measured loss** for a driver. A level is the typical effect for a car in that state. Single-lap noise (0.31 s SD) makes a single lap's own loss unresolvable.
- Anything about **stuck-all-stint** drivers beyond "extrapolated from drivers whose gap varied".
- Anything about the **flat penalty** (0.331), the label, WC-03 or WC-04. No comparison with them is made. No DA-03 number appears.
- That a diagnostic interval excluding 0 is a finding (§12).
- **No discovery number reaches the app, the label or the replay.** WC-10f's one-race table is a static exploratory file headed "exploratory, discovery data, in-sample, not confirmed". Anything shown to users waits on WC-10i (scorecard) and DD-WC19.

---

## 15. Labels

| Shown | Label | Rule |
|---|---|---|
| Car ahead, gap (s, m), DRS open, tyre age, compound | **measured** | from timing and traces |
| Pace and aero levels (and tyre, if ever shown) | **modelled** | always |
| A factor without a level (switch result, failed gate), an excluded lap (with its WC-01 reason), no gap, φ-unsupported, car-ahead level unknown (aero), sidecar coverage < 0.70 | **unavailable** | "—" with the reason; **never 0, never "none"** |

Every modelled level carries **two separate lines**, verbatim:

1. DD-WC2, word for word: "Normalised from other compounds, based on stints from other drivers or the general performance of the tyres after removing other factors."
2. DD-WC18, as a separate line: "Level = typical effect for a car in this situation, not a measurement of this lap"

Also:
- The `extrapolated` flag is shown with the level for stints with a close share ≥ 0.80.
- The lap-arm pace level carries "net of DRS/tow".
- Corner-level pace carries "braking corners only; straights and flat-out corners not priced".
- Replay v1 carries the badge "retrospective".
- Any total prints its modelled share (rule 7).

---

## 16. The data gate

- **Plain English:** before the run reads any value, it confirms that every input file is byte-for-byte the file registered here. File names are compared in one canonical Unicode form (NFC), so the São Paulo path-encoding fault that ended WC-03 cannot recur. A dry run of this gate is done, and its output recorded, before the real run's RUN START. If any check fails, the run stops before reading anything, and it is restartable (§0a).
- **Formal:** `transform/tasks/wake_calibration/data_gate.py` (WC-10c), NFC-normalised relative paths, `<sha256>  <path>` lines sorted bytewise, SHA-256 of the text. All four checks must hold:

| # | Scope | Files | Digest |
|---|---|---|---|
| 1 | Pass table, `_artifacts/WC-03-run/pass-table/pass_table_*.parquet`; per-file hashes also equal that folder's `SHA256SUMS` | 8 | `188dac5e31279a4d4edf6629a095ac1dfb7511254e5a59d9ad0d619bd734dc24` |
| 2 | Bronze laps, telemetry and weather, `data/bronze/{laps,telemetry,weather}/season=*/race=*/*.parquet` (`scoped_bronze_digest`) | 517 | `80d9623bf0c0447bdb3ef642af0250f6eb70c00e254e039ac8bb81ffdd068b3d` |
| 3 | Sidecar, `_artifacts/WC-10/sidecar/sidecar_*.parquet` (same recipe, `digest_lines`); per-file hashes also equal that folder's `SHA256SUMS` | 8 | `8595ce93ca6ff211551bce2546d6635078f0a2cb60dd92ee92f1917cf5ea9d91` |
| 4 | Full WC-03 bronze set (covers schedule, used for the circuit key, and circuit_info) | 1,214 | `aed1c27da1cc00fb80eea470bb0c5c4879ee09556c81ff35bc17ad4aff1690b4` |

- Checks 1, 2 and 4 are as recorded in `gate_dryrun.txt` (2026-10-29, two identical runs). Check 3 was computed for this draft with `data_gate.digest_lines` on 2026-10-29: file bytes only, no column decoded.
- Checks 3 and 4 are additions. In the reviewed `data_gate.py` (sha256 `34da633d4095f60104471fc773d84dacdb6b2ed9ba00bc6797df37a4a07057d5`) they were not pass/fail (check 4 printed as "sanity only"). Per REVIEW-2 ruling (b) they are made pass/fail, with tests, **before signing**; `main` exits 1 if any of checks 1-4 fails. The registered gate code is `data_gate.py` sha256 `cab8c7479d42bb62d019681ff7ccf5aae15f8217c74c098621c22999bf5f3142`, and its dry run is recorded twice in `_evidence/WC-10-2026-10-29/gate_dryrun_v2.txt` (CHOICE D19).
- **Order:** a gate dry run on the real inputs writes its output into the discovery evidence folder before RUN START. Then the run itself repeats the gate, and only on a pass writes RUN START (§0a).
- Gate failure: the state is `FAILED_RESTARTABLE`, the failing check and the found value are logged, and the owner is told. If an input really changed, a pre-result amendment fixes the new digest before a restart. Nothing is read in between.

---

## 17. Checks before the real run (synthetic)

These run on synthetic outcomes laid over the **real 2022-23 structure** (the real groups, laps, gaps, tyre ages, φ support and circuits; synthetic y only). Their numbers are synthetic, are not outcome-derived, and do not complete the run.

- **SG1, recovery under the model.**
  - Plant y = α + φ + g + β_true(class, bin) + circuit-level β variation + race shock + noise, with:
    - noise SD 0.06 s;
    - α SD 0.3 s;
    - φ as a common linear drift −0.003 s/lap plus cell noise SD 0.02 s;
    - g compound-specific quadratics;
    - β_true = 0.12, 0.10, 0.08, 0.06, 0.04, 0.02, 0.01, 0.005 s by bin;
    - circuit β variation SD 0.02 s, race shock SD 0.02 s.

    These values are a synthetic design, not a prior on the effect.
  - Requirements, over 200 simulations × 200 draws with the registered bootstrap: per-bin 95 % coverage ≥ **0.90** in bins 0.3-3.0 s; and the mean near-band estimate within ±10 % of the planted near band, per class.
- **SG2, recovery with one-sided support and tyre drift.** As SG1, with the real one-sided pattern and a planted compound-specific tyre drift. The same two requirements apply.
- **SG3, power of the drift check (pass/fail).** To SG1's y add a driver drift of +0.01 s per tyre-age lap in every group with ≥ 1 supported near-band pass, made relative to the field: from every pass, subtract the mean of the planted term over the free passes in its (race, corner, lap) cell, so that φ cannot absorb it. Report the realized near-band bias (mean simulated β̂_near minus planted). Over 200 simulations S3 must fail in ≥ 80 %. With no drift planted, S3 must pass in ≥ 90 %. S2-pace verdict rates are reported for both.
- **SG6, the class rule under zero aero effect (pass/fail).** Plant a pace effect by gap and **zero** minimum-speed contrast between fast and slow classes, with the SG1 noise and α structure and a correlation of about −0.6 between time and minimum-speed errors. The dirty-air fast − slow contrast interval (§11 A) must contain 0 in at least **90 %** of 200 simulations, and the held-up share must not depend on class by more than 5 percentage points. The plant also carries a driver-lap shock shared by every corner of the lap (SD 0.02 s; correlated −0.6 with the minimum-speed shock) and a driver × corner interaction (SD 0.02 s), so that the lap-level link between the class and τ that the cross-fit does not remove (§6h, §18) is exercised.
- **SG7, S2 power (pass/fail).** Under SG1 (no drift), S2-pace must be AGREE in medium and slow in ≥ 80 % of 200 simulations, and DISAGREE in ≤ 5 % in every class. If SG7 fails:
  1. The window becomes ±8 laps (2022-23 bracketed near band, racecraft out: 638 / 1,544 / 1,482), and SG7 is rerun.
  2. If it fails again, the pace floor becomes 0.030 s, and SG7 is rerun.
  3. If it fails a third time, S2 is reported but leaves the go/no-go table, and the line prints "S2 unpowered".

  Each step is a pre-result amendment committed alone. The ladder is fixed now, so choosing a step involves no judgement after any result. (CHOICE D29.)
- **SG4:** the class rule (cross-fitted, §6h) gives every following pass exactly one of held up / dirty air / unknown / racecraft; a null outcome is never filled; the loader refuses 2024-25; the gate decodes no column; the restart guard allows a restart after a gate failure with nothing outcome-derived written, and refuses one after.
- **SG5:** the timing of one full draw is recorded before the real run. SG5 runs **first**: SG1, SG2, SG6 and SG7 each need 200 × 200 = 40,000 full-chain fits, and a shortfall in run time is fixed by a pre-result amendment (§10).

If SG1, SG2, SG3, SG6 or SG7 fails, nothing real is read. The fix is a pre-result amendment (for SG7, the fixed ladder above).

---

## 18. Honest limits and risks

- **Design A leans on the drift model more than its headline support suggests.** About half of close passes are supported, but only about one in ten supported near-band passes is bracketed within five laps (3,298 of 35,634). For the rest, the comparison runs through φ and g (review item 1). S2 and S3 are the guards. Fast-class S2 and the aero S2 cannot be AGREE (424 fast bracketed near-band passes after racecraft and φ drops, below the 500 floor); they can still DISAGREE.
- S2 compares populations that differ in catching and stuck-stint mix. The standardization covers the observed mix only; a DISAGREE may still reflect selection the cells do not capture.
- **The assumption S3 cannot see:** a driver-specific deviation that starts exactly when traffic ends (pushing after a release, or tyres overheated in the wake and recovering) has no slope within the later free passes. S3 checks a linear extrapolation drift among free passes only. X14 looks at the washout case.
- **The class shares its structure with the effect it labels.** Even cross-fitted, the class rule compares free-air predictions; a car behind a held-up car ahead is classed dirty air (X13 tags these trains; 38 % of supported close non-racecraft passes in 2022-23 structure). Shared lap-level driver shocks still link the class to τ, and so does ĝ; SG6 plants the lap-level shock. In 15 of 37 races the fast class has a single braking corner, so fast-class aero rests on 22 races.
- **Tyre damage from following that persists into free air** makes later free passes slower, raises α̂, and pulls the pace effect toward zero. This is the same quantity the tyre factor tries to measure, and it biases pace downward.
- **Unsupported passes are selected:** passes with no free pass in their group (about 40 % of close passes in 2022-25) and φ-unsupported passes (14 % of supported close in 2022-23) are dropped. They are concentrated in trains and early laps, where loss may be largest. Levels there are extrapolations.
- **Pass class is estimated.** It uses predictions with noise. Under the old rule a third of supported close passes had no car-ahead prediction; under the cross-fitted rule the class is known (structurally) for 57 / 63 / 64 % of supported close non-racecraft passes (§3 item 8), before the run's φ and trim drops. Aero rests on the classed passes only.
- **Aero is a proxy.** Downforce loss, lifting and tyre saving all lower fast-corner minimum speed. X5 helps without resolving it.
- **DRS** gives entry speed after a DRS zone. Corner-level pace carries some of the gain. X4 reports the split. The lap arm is net of DRS/tow.
- **Few clusters:** 24 circuits. Percentile intervals on few clusters may run narrow.
- **4 Hz car data:** exit speed is interpolated across 13-25 m; coast time is a lower bound with 0.24 s resolution.
- **The cut points are relative.** Quantile cuts say how this lap compares with other following laps, not how many tenths were lost.
- **Prior knowledge (§3):** lap-level traffic effects pooled over 2018-2025, a 2022 noise floor and pooled WC-02 rank correlations are known. The tolerance floors were set using the noise floor.
- **Gap noise** of 0.05-0.08 s smears the closest bins. The 0-0.3 s bin is out of every decision.
- **Run time:** whole-chain refits for 1,000 draws × 3 classes × 3 outcomes, plus variants, may be slow, and SG1, SG2, SG6 and SG7 need 40,000 full-chain fits each. SG5 is timed first. A shortfall is fixed only before any real result.
- **The seal is procedural** (§4): a read of a 2024-25 outcome column cannot be detected afterwards.

---

## 19. Judgement calls (CHOICE D1-D30), for the owner to confirm or overrule

| # | Choice | Alternative considered | Reason | § |
|---|---|---|---|---|
| D1 | Two-step imputation: free-air model on free passes only, then actual minus predicted per following pass | One joint fixed-effects regression with gap-bin dummies (the plan's formula) | Traffic passes never shape their own baseline; bracketed, tier and catching checks become averages of the same per-pass effects, with no refits | §6 |
| D2 | Circuit-then-race bootstrap | Race-level | Same corner in both seasons; A1 showed race-level intervals too narrow under circuit variation | §10 |
| D3 | B = 1,000, seed 20261029; diagnostics use draws 1-200 | All diagnostics at 1,000; reuse seed 20261027 | Run time; no shared draw plan with WC-03 | §10 |
| D4 | Quadratic tyre trend per (race, compound, class); no driver slope; a thin compound cell (< 3 drivers) takes the reference compound's curve (θ1 = 0, θ2 of the reference) | Piecewise linear; driver-specific slopes; pooling θ over compounds (collides with the reference θ1 = 0) | Driver slopes do not identify under one-sided support | §6d |
| D5 | Support = ≥ 2 free passes in the group | ≥ 2 free and ≥ 2 close (the review's counting rule) | A single close pass is identified as well as two | §6a |
| D6 | φ: ≥ 3 other free drivers; windows ±1, ±2 laps; else dropped | Race-lap φ fallback | Race-lap rescues only 580 passes in 2022-23 | §6c |
| D7 | Held up if Δ̂ > 2 se, else dirty air (WC-03 N3 analogue) | Three-way with an ambiguous band | Consistency with WC-03; the three-way version is X9 | §6h |
| D8 | Pace curve pooled over pass classes | Class-specific pace curves in scores | Applies to every lap, including unknown class | §6e |
| D9 | Trims 2.0 s / 40 km/h / 5.0 s | Residual-based trims | Fixed, wide, independent of the effect | §6f |
| D10 | S2 floors 0.020 s / 0.75 km/h; three-way verdict (tolerance rule: D25; count rule: D27) | A pure interval-overlap test | Floors ≈ ⅓ of the per-pass noise | §11 |
| D11 | S3: \|B_k\| ≤ max(0.25 × \|near\|, 0.010 s) (statistic: D24) | No drift gate (diagnostic only) | The plan's go/no-go requires drift inside tolerance | §11 |
| D12 | S1 requires every class | Medium and slow only | Aero is a fast − slow contrast and needs the fast class | §11 |
| D13 | Raw bins, no monotone step | WC-03's pool-adjacent-violators | Discovery is about shape; monotone is X10 | §6e |
| D14 | Exit speed secondary, never in a level | Exit speed in S_aero | Interpolated over up to 50 m; tow on exit | §6g |
| D15 | Coast > 10.0 s → null; thresholds 5 % / 98 % kept | 30 s cap; 1 % / 10 % / 99 % | 300 m in > 10 s is implausible; no sidecar rebuild | §7 |
| D16 | S_aero summed over fast and medium dirty-air corners; "—" if more than half unknown | Mean per corner; "—" if any unknown | Scales with exposure; avoids blanking most laps | §13 |
| D17 | None/barely if the lap's 80 % score interval includes 0 | The plan's "bins' interval includes 0" | One rule on the quantity that is levelled | §13 |
| D18 | Racecraft out of the fit (WC-03 C5) | Kept in the following bins | Overtaking is not following | §5 |
| D19 | Gate adds the sidecar digest and the full 1,214-file digest as pass/fail | Scoped plus pass table only | The sidecar and schedule are direct inputs | §16 |
| D20 | Catching split at ±0.10 s; previous lap free counts as shrinking | ±0.05 s; previous free excluded | Above gap noise; catching from free is the purest catching | §8d |
| D21 | Lap arm by imputation, free lap = all braking corners free, ≥ 3 free laps; its bracketed companion is a DIAGNOSTIC (X15) | Joint regression with a median-gap bin; a lap-arm S2 verdict | Same logic as design A; the plan's H used ≥ 3; only about 20 near-band laps are bracketed within ±5 in 2022-23, so a lap-arm S2 could only ever be INCONCLUSIVE | §9a |
| D22 | No rerun after completion except under a hashed post-hoc amendment, both results kept | Free reruns, since discovery is "seen" anyway | Forking paths would feed the cut points and the switch | §0a |
| D23 | Pass class cross-fitted over the other corners of the class | Corner-c free-air comparison (shares the follower's prediction error with τ) | Review B3 | §6h |
| D24 | S3 = exposure-weighted group drift B_k (near-pass-weighted plug-in of group drift slopes × tyre-age distance; groups with ≥ 3 free passes spanning ≥ 8 tyre-age laps) | pooled or leave-one-out slope | both are zero by construction (REVIEW-1 B1, REVIEW-2 R2-B1); the 8-lap span halves the se against 4 laps | §11 |
| D25 | S2 compares one-sided with locally bracketed (±5 laps), T = 25 % of bracketed, equivalence at 90 % | Compare full with bracketed, T = 50 % of full | The old tolerance grew with the bias it guarded and was lenient to inflation | §11 |
| D26 | Bracketed baseline interpolated linearly in lap between the nearest earlier and later free pass; one trim, on τ with group α̂, for both sets | Symmetric ½(r_b + r_a); a separate trim on τ^loc | The symmetric mean cancels drift only at the midpoint (81 % of bracketed near-band passes are off it); one trim keeps β^one and β^brk on the same passes | §8a |
| D27 | S2: AGREE needs ≥ 500 bracketed near-band passes, DISAGREE ≥ 100 | One floor of 500 for every verdict | A single floor made fast, aero and lap-arm S2 unable to fail (REVIEW-2 R2-B4) | §11 |
| D28 | S2's one-sided near band standardized to the bracketed mix over 15 cells (gap change 5 × stint close-share tier 3); cells with < 20 one-sided passes drop their bracketed passes | Unstandardized D′ (reported beside it) | Bracketed passes are mostly brief encounters; unstandardized D′ mixes drift with catching and stuck-stint selection (REVIEW-2 R2-B5) | §11 |
| D29 | SG7 power check with the fixed ladder: ±8 laps, then pace floor 0.030 s, then "S2 unpowered" | Choosing the window or floor after seeing SG7; ±8 from the start | ±5 is safer under curvature; the ladder is fixed now so no step involves judgement (REVIEW-2 ruling a) | §17 |
| D30 | F1's drift guard is corner-level S3 in medium and slow; the FALLBACK line says "lap drift checked through corner-level S3 only" | A lap-arm S2 (unreachable); "drift unchecked" | The lap arm has about 20 bracketed near-band laps; corner-level S3 measures the same driver-stint drift | §11 |

---

## 20. Owner sign-off

### 20a. Before signing

- [ ] The adversarial review of the identification text (§6, §8, §11) by an independent opus-5 reviewer has been done, and its findings and the fixes are recorded here. Review 1 (partial, 2026-10-29): `wi/WC-10-discovery-preregistration-REVIEW-1.md`; blockers B1-B4 and should-fix S1-S8 are addressed (§6h, §8a, §10 and Appendix A, §11, §0a, §17). Review 2 done (`wi/WC-10-discovery-preregistration-REVIEW-2.md`); its edits are applied (R2-B1-R2-B5, SG7 from ruling (a), S-R2-1-S-R2-11; new counts in `counts_d/`, d05-d08). Per its ruling (d), one short check that each replacement text went in as written is enough; no third full review.
- [ ] The file name is resolved (the WC-10d `done_when` says `WC-10-discovery-registration-DRAFT.md`; this file is `WC-10-discovery-preregistration-DRAFT.md`).
- [ ] `data_gate.py` checks 3 and 4 are pass/fail with tests (REVIEW-2 ruling (b)), the dry run is recorded twice in `gate_dryrun_v2.txt`, and the new sha256 is recorded in §0b, §2 and §16 (done 2026-10-29).
- [ ] `sidecar.py`, `data_gate.py` and the NFC fix in `run_wc03.py` are committed (owner).
- [ ] The §3 statement on loss values (pooled values seen; nothing by gap) is accepted as written.

### 20b. Signature

```
Scope and seal:        [ ] Approved as written    [ ] Approved with edits: ______
Design A (§6):         [ ] Approved as written    [ ] Approved with edits: ______
Switch rule (§11):     [ ] Approved as written    [ ] Approved with edits: ______
Choices D1-D30:        [ ] Confirmed as written   [ ] Confirmed with edits: ______
Data gate (§16):       [ ] Four checks            [ ] Checks 1-2 only
Yes to the discovery run on 2022-23:   [ ] yes   [ ] no
Signed (owner):        ______________________
Date:                  ______________________
```

### 20c. After signing (owner's steps; nothing is fitted before step 4)

1. Change the status line at the top to "SIGNED <date>".
2. Commit **this file alone**, with no other file in the commit.
3. Compute its fingerprint as committed: `shasum -a 256 _roadmap/_wake-calibration/wi/WC-10-discovery-preregistration-DRAFT.md`.
4. Record it on **DD-WC20** in `status/build-log.json` as "signed <date>, commit <sha>, SHA-256 <hex>, yes to run". Then run `board.py --check` and `--write-order`.

```
Commit:   ______________________
SHA-256:  ______________________
```

---

## Appendix A. The bootstrap lists (fixed literals)

The 43 races (2022: 21, 2023: 22) with at least one kept braking pass (§5) and their 24 circuit keys, from structural columns only (`counts_d/csv/d03_out.txt`). The draw plan of §10 is made over exactly this list for every arm. Order: circuits sorted bytewise on the NFC UTF-8 key; races within a circuit sorted bytewise on `race_id`. The run refuses to start if `build_pass_table.race_calendar` gives a different mapping.

| # | Circuit key (NFC) | Race ids, sorted bytewise |
|---:|---|---|
| 1 | Austin | 2022_19, 2023_18 |
| 2 | Baku | 2022_8, 2023_4 |
| 3 | Barcelona | 2022_6, 2023_7 |
| 4 | Budapest | 2022_13, 2023_11 |
| 5 | Imola | 2022_4 |
| 6 | Jeddah | 2022_2, 2023_2 |
| 7 | Las Vegas | 2023_21 |
| 8 | Le Castellet | 2022_12 |
| 9 | Lusail | 2023_17 |
| 10 | Marina Bay | 2022_17, 2023_15 |
| 11 | Melbourne | 2022_3, 2023_3 |
| 12 | Mexico City | 2022_20, 2023_19 |
| 13 | Miami | 2022_5, 2023_5 |
| 14 | Monaco | 2022_7, 2023_6 |
| 15 | Montréal | 2022_9, 2023_8 |
| 16 | Monza | 2022_16, 2023_14 |
| 17 | Sakhir | 2022_1, 2023_1 |
| 18 | Silverstone | 2022_10, 2023_10 |
| 19 | Spa-Francorchamps | 2022_14, 2023_12 |
| 20 | Spielberg | 2022_11, 2023_9 |
| 21 | Suzuka | 2023_16 |
| 22 | São Paulo | 2022_21, 2023_20 |
| 23 | Yas Island | 2022_22, 2023_22 |
| 24 | Zandvoort | 2022_15, 2023_13 |
