# WC-10 discovery registration, amendment B1: the eight open choices, three further rulings, four builder readings, and the RUN START preflight

**Status: DRAFT, unsigned, not committed, not hashed.** The twelve rulings below (rulings 1-5 in section A, rulings 6-12 in section A2) were made by the owner on 2026-10-30 and are written down here by the Opus session; the file is not the owner's signature. It is still a draft until the owner commits it alone and its SHA-256 is recorded on DD-WC20 in `status/build-log.json`, beside the registration's. It amends `wi/WC-10-discovery-preregistration-DRAFT.md` (signed 2026-10-30 under DD-WC20, SHA-256 `4d679bf6c94b12cf186776467478400c1feef89930be87d3fe36be49f1e8d248`, commit `6fd0330`). The registered text is **not edited**. Where this file and the registered text differ, this file governs once it is committed and hashed.

**When it was made, stated plainly.** Drafted 2026-10-30, while the WC-10e code (`design_a.py`, `lap_arm.py`, `wc10_io.py`, `diagnostics.py`, `run_wc10.py`) was being written. **No outcome has been read.** No WC-10 run ledger exists (`_evidence/WC-10-discovery-<date>/` has not been created), RUN START has not been written, no outcome column has been decoded, and SG1-SG7 have not been run. Nothing has been fitted on real data, and `data/dev.duckdb` was not opened. This is a pre-result amendment in the sense of §0: at the moment it is committed, the run ledger (§16) shows no outcome-derived number written. The one count in it (section C) uses structure columns only.

**Why it is needed.** While building WC-10e, the code met five cases the registration leaves open. For each one the code has a switch in `design_a.OPEN_CHOICES`, set to `None`, and it raises `OpenChoiceError` the moment the case first occurs in the data. Under §0a, once `OUTCOME DECODED` is written, any change to code or constants is a post-hoc amendment. These cases occur only after outcomes are decoded (in step 1, the class rule or the bootstrap), so they must be settled now. Otherwise the run would stop with a Python exception after `OUTCOME DECODED`. That is not an infrastructure cause, so the run could not be restarted without a post-hoc amendment.

The diagnostics and per-lap score code (`diagnostics.py`) met three more such cases. They have their own switches in `diagnostics.OPEN_CHOICES`, also set to `None`, with the same `OpenChoiceError`. Section A2 rules them (rulings 6-8). The same section records four readings of the signed text that the owner has settled (rulings 9-12), so that the code and the outputs follow one stated reading. So the run has **eight** open-choice switches in all: five in `design_a.OPEN_CHOICES` and three in `diagnostics.OPEN_CHOICES`.

**Nothing else changes.** No threshold, tolerance, floor, trim, window, bin, minimum count, B, seed, season split, circuit or race list, or go/no-go rule changes. Each ruling below either closes a gap the registration leaves open or confirms a reading the code already uses. **Each of the values in sections A and A2 is committed before SG1-SG7 are run and before RUN START.** SG1-SG7 are run with these values set (§0a: after a pre-result amendment, SG1-SG7 are rerun).

---

## A. The owner's rulings (five open choices)

### Ruling 1. Free passes flagged as racecraft are dropped from step 1

**Registered text.** §0b, Racecraft row: "WC-03 C5 rule (`estimator.racecraft`), computed on **all** 2022-23 pass-table rows (as WC-03 `prepare_passes`): out of every fit, counted". §5, Racecraft row: "**Out of every fit** and counted (CHOICE D18)." But §6a and §6b define step 1 on "free passes" (`clear_ahead` true or `gap_s ≥ 3.0`) and do not name racecraft.

**The gap.** The C5 rule also flags a pass whose leader changes at a nearby braking corner, so a free pass can be racecraft. In 2022-23 structure, 11,950 of 172,413 free passes are (section C). The registration does not say whether those stay in step 1.

**Ruling: dropped.** A racecraft free pass leaves step 1 for every outcome. It also leaves everything that is counted from the step-1 free-pass set: the ≥ 2 support floor (§6a), the bracket (§8a), the φ driver counts n_W (§6c), the thin-cell driver count (§6d), N_F and N_L (§6h), and the S3 population (§11). Each dropped pass is counted by class. `OPEN_CHOICES["racecraft_free_passes"] = "drop"`.

**Reason, in plain English.** "Out of every fit" means every fit, and step 1 is a fit. A pass where positions are changing nearby is not clean free air, even if no car was within 3 s, so it should not set any driver's free-air baseline. The other reading would make "every fit" mean "every step-2 average", which the words do not say.

**Effect, stated so it is not hidden.** Some groups fall below the 2-free-pass floor, and their following passes become unsupported. Section C gives the count.

### Ruling 2. A corner of the class with no comparison group left is skipped

**Registered text.** §6h: "let a[F, c′] = α̂[F, c′] − ᾱ[r, m, c′], where ᾱ[r, m, c′] is the mean of α̂ over all groups at race r, compound m (the stint's compound), corner c′, **excluding both the follower's and the leader's stint**." And: "`unknown` if N_F < 2 or N_L < 2 …".

**The gap.** At some other corner c′, there may be no group left at (r, m, c′) once both stints are excluded. Then ᾱ[r, m, c′] is an empty mean, and a[·, c′] cannot be computed. The registration does not say what happens to that corner.

**Ruling: skip that corner.** A corner c′ whose ᾱ has no group left contributes neither to the stint offset o nor to N_F (or N_L). The offset is built from the remaining corners of the class. If too few free passes remain, the existing rule applies unchanged: N_F < 2 or N_L < 2 gives `unknown`. The number of skipped (pass, corner) pairs is counted per class. `OPEN_CHOICES["alpha_bar_empty_other_corner"] = "skip_corner"`.

**Reason, in plain English.** A corner where nobody else ran that compound gives no comparison, so it carries no information about the stint's pace. Leaving it out is what "the mean over those c′" already does for a corner where the stint has no free pass. Making the whole pass `unknown` instead would throw away the other corners that do have a comparison. The registered N ≥ 2 floor still catches a pass left with too little to go on, so no new threshold is needed.

### Ruling 3. A prediction whose driver level and field effect are not identified together is dropped and counted

**Registered text.** §6b: step 1 is "least squares with the fixed effects α and φ absorbed", and σ̂_k counts "the connected components of the α-φ graph". §6e: "ŷ0_i = α̂[G_i] + φ̃_i + …". §9a: the lap arm uses the same step 1 with α[race, driver, stint] and φ[race, lap].

**The gap.** The α-φ graph can split into several pieces (connected components). α̂ and φ̂ are then fixed only up to a constant within each piece. If a following pass's group α̂ and its φ̃ cell (or cells, for W ≥ 1) lie in different pieces, the sum α̂ + φ̃ depends on how the solver happens to fix those constants. It is not identified by the data. The registration counts the pieces but does not say what happens to such a prediction.

**Ruling: dropped and counted.** Such a pass is dropped from every average (as a φ-unsupported pass is) and counted per class and bin, under its own reason (`disconnected`). This applies to design A (every outcome) **and to the lap arm** (§9a), which uses the same check. `OPEN_CHOICES["disconnected_prediction"] = "drop"`.

**Reason, in plain English.** A number that changes when the solver changes is not an estimate, so it cannot be averaged into a loss. Keeping it would put arbitrary values into β. The registration already drops passes it cannot predict (φ-unsupported, §6c) and counts them, so this follows the same pattern.

### Ruling 4. A bootstrap draw that leaves a statistic undefined propagates

**Registered text.** §10: "**B = 1,000, fixed.** … Intervals: 95 % percentile (2.5th-97.5th)." And: "No fallback count."

**The gap.** In some draw a statistic may be undefined (for example, a gap bin or an S2 cell has no pass in that draw). The registration does not say whether the percentile is taken over the remaining draws.

**Ruling: propagate.** If any of the 1,000 draws leaves a statistic undefined, its interval is undefined. Nothing is skipped, and nothing is redrawn: B stays 1,000. This is the rule WC-03 adopted in amendment A4, ruling 1 (G7: "no draw is skipped or redrawn (B stays 1,000)") and ruling 4d ("its interval is not taken over fewer than B draws"). A verdict that needs an undefined interval does not pass: S1 and F1 fail for that class, and S2 is INCONCLUSIVE. The printed interval is "—" with the reason "undefined in n draws". **The go/no-go line prints the number of undefined draws** for every statistic it uses that has any, so a fail or an INCONCLUSIVE caused by this rule can be told apart from one caused by the data. `OPEN_CHOICES["undefined_draws"] = "propagate"`.

**Reason, in plain English.** Leaving out the draws where a statistic does not exist would leave out exactly the draws where the data are thinnest, so the interval would look narrower than it is. Keeping B at 1,000 and admitting the gap is the honest answer, and it matches WC-03.

**Side effect, stated now (S2 for the fast class and the aero contrast).** S2 can give DISAGREE only on a defined 90 % interval (§11). The fast class and the aero contrast A rest on the thinnest bracketed counts (424 fast bracketed near-band passes before trims, §3 item 8), so they are the likeliest to have an empty cell or bin in some draw. Under this ruling, an undefined interval there gives **INCONCLUSIVE**. Fast-class and aero INCONCLUSIVE do not block DESIGN A (§11); they print as a stated weakness. So this rule can turn what would have been a blocking DISAGREE in fast S2-pace or S2-aero into a non-blocking INCONCLUSIVE. It cannot do the reverse. In medium and slow, INCONCLUSIVE already blocks DESIGN A, so there the rule can only block. The undefined-draw count on the go/no-go line is how a reader sees which case happened.

### Ruling 5. A race drawn twice within one circuit copy is a separate copy

**Registered text.** §10: "A circuit drawn twice enters as two distinct circuits. Its races, groups, φ cells and pass classes are separate copies. A race drawn twice within one copy counts twice."

**The gap.** "Counts twice" does not say whether the race's second draw is a second, separate copy of the race (its own groups, φ cells, θ cells and classes, as for a circuit copy), or the same rows given weight 2. The two give the same β and γ, but they differ in σ̂_k's degrees of freedom (§6b), which feed the class rule (§6h).

**Ruling: a separate copy, exactly like a circuit copy.** A race drawn k times within one circuit copy enters as k distinct races. Its groups, φ cells, θ cells and pass classes are separate copies, and its structure (support, bracket, φ windows, thin cells, classes) is each copy's own data. **σ̂_k's degrees of freedom count the race's parameters k times**: in p = (α levels) + (φ cells) + (θ and γ terms) − (connected components), every α level, φ cell, θ term and component of that race is counted once per copy. n and RSS are counted once per copy too. γ_k, which is pooled over races, is estimated once from all copies. The code value is `OPEN_CHOICES["duplicate_race_in_copy"] = "copy"`.

**Reason, in plain English.** The registration already treats a circuit drawn twice as two separate circuits. A race drawn twice should follow the same rule, so the plan is the same at both levels. Counting the copies' rows twice but their parameters once would make σ̂ smaller than a literal refit of the drawn data gives. That would make more passes `held_up` in draws with a repeated race, for no reason in the data.

**Code consequence, stated so it is not missed.** As drafted, `design_a.draw_stats` implements only the value `"weight"`, whose comment says parameters are "counted once in sigma's degrees of freedom", and it raises for any other value. That does not match this ruling. The code must implement `"copy"` (parameters counted once per copy, duplicate races included) before SG1-SG7 are run. Until it does, the preflight in section D refuses RUN START.

---

## A2. The owner's further rulings (three more open choices, four readings)

Rulings 6-8 set the three switches in `diagnostics.OPEN_CHOICES`. Rulings 9-12 record readings of the signed text. **Like section A, each is committed before SG1-SG7 are run and before RUN START.**

### Ruling 6. X1 trims on the registered τ

**Registered text.** §12, X1 row: "α̂ replaced, per following pass, by the mean of (y − φ̂ − ĝ − γ̂·behind_1s) over the group's free passes within ±W laps (≥ 2 required, else dropped and counted)". §6f (ii): "A following pass is dropped from the averages if |τ_i| > 2.0 s or > 40 km/h." §8a (CHOICE D26): "Trim (ii) is applied once, to τ with the group α̂ (§6e); a pass dropped there is dropped from β^one and β^brk alike, and τ^loc is not trimmed separately."

**The gap.** X1 builds a second τ for each following pass, from a local baseline. It does not say whether trim (ii) is applied to that X1 τ or to the registered τ (with the group α̂).

**Ruling: trim on the registered τ.** A following pass enters X1 only if it entered β: it passed trim (ii) on τ with the group α̂, and it has ≥ 2 free passes within ±W laps. The X1 τ is not trimmed separately. `OPEN_CHOICES["x1_trim"] = "registered_tau"` (in `diagnostics.OPEN_CHOICES`). **Any other value is rejected** (the code raises; it does not fall back to a second branch).

**Reason, in plain English.** §8a already settled this question for the other baseline that replaces α̂, the bracketed one: one trim, on the registered τ, so both estimates are averages over the same passes. X1 is the same kind of check, so it follows the same rule. Then a difference between X1 and the registered near band comes from the baseline, not from a different set of passes.

**Code consequence.** As drafted, `diagnostics.py` treats every value other than `"registered_tau"` as `"own_tau"`. It must reject any value it does not recognise, before SG1-SG7 are run.

### Ruling 7. A tied modal leader is not a release event

**Registered text.** §8f: "An **event** is a following lap L where: some pass row on L+1 has reason `pit_lap_leader` with `leader` equal to L's modal `leader`; …".

**The gap.** On lap L, two leaders can tie for the mode. The registration (and r03, which used duckdb `mode()`) does not say which one is "L's modal leader".

**Ruling: dropped.** A lap L whose modal leader is tied is not an event, for both the ≥ 3 and the > 3 free rule. **The number of tied laps is printed** beside the event counts, so the §8f recount (39 / 48) can be read with it. `OPEN_CHOICES["modal_leader_tie"] = "drop"` (in `diagnostics.OPEN_CHOICES`).

**Reason, in plain English.** If two cars were ahead equally often, we cannot say which one was "the car ahead" that pitted, so the lap is not a clean release. Counting it whenever either car pits would let the tie make an event more likely than a lap with one clear leader. Printing the count shows how many laps this removes.

### Ruling 8. Under FALLBACK, a negative median gap is priced at the 0.3-0.5 s bin, and so is the 0-0.3 s bin

**Registered text.** §13 item 7: "Under FALLBACK, `S_pace` = β_lap(the lap's median-gap bin), labelled net of DRS/tow." In the design A sentence of the same item: "The 0-0.3 s bin is priced at the 0.3-0.5 s value. Racecraft corners are priced by their bin (gap < 0 at the 0.3-0.5 s value)." §9a: "Following lap: median gap in [0, 3.0)."

**The gap.** A score lap can hold racecraft corners with `gap_s` < 0 (§13 item 7 admits racecraft corners to score laps), so its median gap can be negative. A negative median has no bin. Also, §13 states the 0-0.3 s → 0.3-0.5 s pricing only in the design A sentence; the FALLBACK sentence does not repeat it.

**Ruling: price both at the 0.3-0.5 s bin.** Under FALLBACK:
- A score lap with a **negative median gap** gets `S_pace` = β_lap[0.3-0.5 s]. `OPEN_CHOICES["fallback_negative_median"] = "bin_0.3-0.5"` (in `diagnostics.OPEN_CHOICES`). The number of such laps is reported.
- A score lap whose median gap is in the **0-0.3 s bin** gets `S_pace` = β_lap[0.3-0.5 s], as in design A. This is the rule the code already applies (`diagnostics.py`, `_pace_values`, about line 848); it is recorded here so the code follows signed text, not a builder's choice.

**Reason, in plain English.** This matches how the registration already prices racecraft in design A: a negative gap is treated as the 0.3-0.5 s bin. The 0-0.3 s bin is too noisy to use on its own (§6e), so the same 0.3-0.5 s value stands in for it under either design. Pricing a negative-median lap this way is a mild extrapolation, because the lap arm is fitted only on laps with median gap ≥ 0 (§9a), and the reader should know that. The other option ("—") would blank laps where the driver was plainly in close traffic.

### Ruling 9. Discovery parquet goes to `_artifacts/WC-10/discovery/` (a reading)

**Registered text.** §13: "Into `_roadmap/_wake-calibration/_evidence/WC-10-discovery-<date>/`. Parquet goes into `_artifacts/WC-10/discovery/` with SHA256SUMS (rule 8)."

**The gap.** The WC-10e build brief (repeated in the `run_wc10.py` docstring) says `_artifacts/WC-10-discovery/`. The two paths differ.

**Ruling: the signed text governs.** Parquet outputs go to `_roadmap/_wake-calibration/_artifacts/WC-10/discovery/`, with a `SHA256SUMS` there. The ledger, SUMMARY.md, CSVs and PROVENANCE.txt go to the evidence folder, as §13 says. This is a reading of the signed text, not a change. It supersedes the brief's `_artifacts/WC-10-discovery/`, and the code is changed to match before SG1-SG7 are run.

**Reason, in plain English.** The signed registration outranks a build brief. It also puts discovery beside the other WC-10 artifacts (`_artifacts/WC-10/sidecar/`), one folder per work item.

### Ruling 10. Summary line 2 is kept word for word, "confirmed" included

**Registered text.** §13 item 1: "line 2: \"Exploratory, discovery data (2022-23), in-sample, not confirmed.\"". §14: WC-10f's table is "headed \"exploratory, discovery data, in-sample, not confirmed\"". §12: "The words \"significant\", \"confirmed\" and \"proves\" do not appear in discovery outputs."

**The gap.** Read literally, §12 bans the word that §13 item 1 requires on line 2.

**Ruling: line 2 is printed exactly as §13 item 1 gives it.** The specific required line beats the general ban: §12's ban is there to stop a claim that something is confirmed, and line 2 says the opposite. **Any banned-word check (in code, a test or SG) must exempt this exact line, byte for byte, and nothing else.** "confirmed" anywhere else in a discovery output still fails the check, and so does a changed line 2.

**Reason, in plain English.** The registration wrote that line on purpose, to warn the reader. Dropping or rewording it to dodge a word filter would remove the warning the filter exists to protect.

### Ruling 11. S_aero uses the literal formula, with no w_k weights

**Registered text.** §13 item 7: "**Aero** `S_aero` (km/h) = Σ over the lap's fast and medium braking corners with pass class `dirty_air` and 0 ≤ gap < 3 of [β_dirty^{min speed}(class_k, bin_k) − β_dirty^{min speed}(slow, bin_k)]. … (CHOICE D16)." By contrast, `S_pace` is "Σ_k w_k · β_pace(class_k, bin_k)".

**The gap.** `S_pace` carries the WC-03 §7 no-double-counting weights w_k; `S_aero` does not. A reader could take the omission as a slip.

**Ruling: the literal formula.** `S_aero` is the unweighted sum, exactly as written, with no w_k. The code already does this (`diagnostics._aero_values`).

**Reason, in plain English.** The weights exist so seconds are not counted twice where segments overlap in time. A minimum speed is a reading at one corner, not a share of lap time, so there is nothing to double-count. D16 chose a sum over corners so the score grows with exposure, and that is what the formula says.

### Ruling 12. A lap whose median gap is missing under FALLBACK is not priced (a reading)

**Registered text.** §13 item 7: "Under FALLBACK, `S_pace` = β_lap(the lap's median-gap bin), labelled net of DRS/tow." §13 item 8 and BUILD-ORDER rule 7: an unavailable value is shown as "—", never 0.

**The gap.** A score lap can have a median gap that is missing (NaN), for example when no corner of the lap has a measured gap. The text gives a bin only to a measured median gap, including a negative one (ruling 8). A missing median has no bin.

**Ruling: not priced.** Under FALLBACK, a lap whose median gap is NaN is not priced. `S_pace` stays undefined and is shown as "—" with a reason. It is never 0, and it is never priced at the 0.3-0.5 s bin. This is a reading of the signed text, recorded for transparency. It is implemented in `diagnostics.py`, and it is committed before SG1-SG7 are run and before RUN START.

**Reason, in plain English.** Unavailable is "—", never 0 (BUILD-ORDER rule 7). Section 13 items 7-8 give a bin only to a measured median gap, negative ones included under ruling 8. A lap with no measured gap has nothing to price, and filling it in at the 0.3-0.5 s value would invent a gap the data does not show.

---

## B. Builder readings, confirmed and recorded for transparency

These are readings the WC-10e builder took where the registration is silent or leaves a detail open. Each is recorded as confirmed. None changes a threshold.

**B-i. `seg_start_t` and `seg_end_t` are treated as outcome columns.** §0a's list of outcome columns does not name them. But `seg_end_t − seg_start_t` is the segment time, so reading them would reveal `seg_time_s`. `wc10_io.OUTCOME_EQUIVALENT_COLUMNS` puts them under the same guard: they are not decoded before RUN START, and their first decode writes `OUTCOME DECODED`. §13 item 7 still uses them after RUN START, for the no-double-counting weights w_k of the per-lap scores. This makes the guard stricter, never looser.

**B-ii. The bootstrap reweights races instead of refitting each draw from scratch.** §10 says each draw "reruns the whole chain". Every quantity in the chain is computed inside one race, except γ_k (pooled per corner class). So the builder computes each draw from per-race pieces with race weights, plus γ_k by a weighted Frisch-Waugh-Lovell step. That is an algebraic identity with refitting the replicated data, up to the §6b convergence tolerance, not an approximation. **This reading is valid only with a test showing it equals a literal refit** of the drawn data on synthetic data. The test must cover a circuit drawn twice and a race drawn twice within one copy (counted as in ruling 5, σ̂_k's degrees of freedom included). It must cover every statistic the go/no-go line uses: β, the class labels, S2's D′ and S3's B_k. The test's output is kept as **SG4 evidence** in the discovery evidence folder. If the test fails or is missing, RUN START is refused.

**B-iii. `| F1 pass/fail` is added to the go/no-go line.** The §11 example line ends at S3. The builder appends ` | F1 pass` or ` | F1 fail`, so all four switch results the table uses are on line 1. Example: `GO/NO-GO: DESIGN A | S1 pass,pass,pass | S2 pace INCONCLUSIVE,AGREE,AGREE | S2 aero INCONCLUSIVE | S3 pass,pass,pass | F1 pass`. Ruling 4 adds the undefined-draw counts after it. The verdict rule itself is unchanged.

**B-iv. The gap-change order follows the d05 counting script.** §8d lists the gap-change cases without an order. A pass can meet two of them: the previous lap was free (`prev_lap_clear_ahead` true, or `prev_lap_gap_s ≥ 3`), but its pass was excluded (`prev_lap_reason` not null). The builder checks in the order `counts_d/scripts/d05_review2_counts.py` used, which produced the §3 item 8 composition counts the registration quotes: (1) **unknown** (previous pass excluded, or missing and not free); (2) arrived from free; (3) shrinking (< −0.10 s); (4) growing (> +0.10 s); (5) steady. **A previous lap that is free but excluded is therefore unknown.** Reason: an excluded lap (pit, yellow, neutralised) does not show catching from free air.

---

## C. Count: groups that fall below the 2-free-pass floor under ruling 1 (structure columns only)

**What was read.** The 2022-23 pass table (pass d), columns `season`, `race_id`, `race`, `driver`, `lap`, `stint`, `compound`, `tyre_life`, `corner_id`, `corner_number`, `corner_class`, `segment_basis`, `leader`, `leader_lap`, `gap_s`, `clear_ahead`, `behind_1s`, `tag`, `reason`. No outcome column, no `seg_start_t`/`seg_end_t`, no sidecar column, nothing fitted. Racecraft is `estimator.racecraft` on all rows (§5). Eligible passes and groups are as in §5 and §6a. The script reproduces d05's supported near-band count with racecraft out (5,254 / 13,248 / 12,657) exactly, as a check.

**Caveat.** These counts are taken **before** the §6f (i) free-pass trim, because that trim needs `seg_time_s`. The trim can only remove more free passes, so the true counts at run time are the same or larger. WC-10e recomputes them at run time and reports them (§13 item 2).

| | All | Fast | Medium | Slow |
|---|---|---|---|---|
| Free passes flagged racecraft (dropped by ruling 1) | 11,950 of 172,413 | | | |
| Groups with ≥ 2 free passes before, < 2 after the drop | **543** | | | |
| … of which hold at least one following pass | **532** | 70 | 236 | 226 |
| Supported following passes, before → after | 150,500 → 144,123 (−6,377) | −851 | −2,766 | −2,760 |
| … lost, not racecraft (would have entered an average) | 5,365 | 762 | 2,313 | 2,290 |
| … lost, close (< 1.0 s), not racecraft | 2,169 | 306 | 956 | 907 |
| … lost, near band (0.5-1.0 s), not racecraft | 1,393 | 191 | 592 | 610 |

So, before the outcome trim, **543 groups** (532 holding a following pass) fall below the floor once racecraft free passes are dropped. That moves 5,365 non-racecraft following passes, 1,393 of them in the near band, from supported to unsupported. These passes are dropped and counted (§6a). Ruling 1 also changes the φ driver counts, the bracket and N_F/N_L; those effects are not counted here and are recomputed at run time.

The script is `b1_racecraft_floor.py`, run on 2026-10-30 from session scratch. A grep of it finds no outcome-column name. If it is to be kept as evidence, the owner copies it into `_evidence/WC-10-2026-10-29/counts_d/scripts/` (BUILD-ORDER rule 8).

### Support impact (every registered count floor, structure columns only)

Full tables: `_evidence/WC-10-2026-10-29/b1_support_impact.md`. Counts are before the §6f trims, so each is an upper bound; fast / medium / slow. **No floor that was met before the drop becomes not met, and none that was not met becomes met.** No threshold changes.

- **S2-pace** bracketed near-band count entering β^brk: 420 / 1,025 / 947 → **387 / 924 / 822**. The 500 AGREE floor stays met in medium and slow and stays missed in fast (non-blocking, as §11 already says). The 100 DISAGREE floor stays met everywhere. The 15-cell rule is unchanged: the same single thin cell per class.
- **S2-aero** upper bound (class-knowable bracketed, min of fast and slow): 306 → **282**. AGREE was and stays impossible. DISAGREE now needs at least 35.5 % of those fast passes to be dirty air (32.7 % before), else forced INCONCLUSIVE (non-blocking). **At risk.**
- **S1** near band entering β: 4,475 / 11,374 / 10,806 → 4,263 / 10,808 / 10,207. **Met.** **S3** population: 2,467 / 5,916 / 5,604 → 2,308 / 5,523 / 5,170 near-band passes. **Met.** **F1**: the lap arm already excludes racecraft laps, so it is unchanged. **Met.** **Data gate**: counts no passes. **Unaffected.**
- Class knowable (supported close, not racecraft): 56 / 63 / 63 % → 53 / 61 / 62 %. φ-unsupported supported following: 12,131 → 12,367. Thin θ cells: 47 → 47 (thin or empty).
- **Worst honest outcome:** power, not floors. 10-13 % fewer bracketed passes in medium and slow make an INCONCLUSIVE S2-pace there (which blocks DESIGN A, then FALLBACK or NEITHER) somewhat more likely. SG7, rerun on the post-amendment structure, measures how much.

---

## D. Preflight clause: RUN START is refused while any open choice is unset

**New rule (added to §0a's code order, before step (2)).** Before the run writes RUN START, it checks:

1. **None of the eight open-choice values is `None`**: the five in `design_a.OPEN_CHOICES` (section A) and the three in `diagnostics.OPEN_CHOICES` (section A2, rulings 6-8). If any one is unset, RUN START is refused, the ledger records `FAILED_RESTARTABLE` with the names of the unset choices, and nothing is decoded.
2. Each value equals the value ruled here: `racecraft_free_passes = "drop"`, `alpha_bar_empty_other_corner = "skip_corner"`, `disconnected_prediction = "drop"`, `undefined_draws = "propagate"`, `duplicate_race_in_copy = "copy"`, `x1_trim = "registered_tau"`, `modal_leader_tie = "drop"`, `fallback_negative_median = "bin_0.3-0.5"`. A value the code does not implement is a refusal, not a fallback.
3. This file is committed, unchanged, and its SHA-256 is recorded on DD-WC20, as the registration's is.
4. The B-ii equivalence test and SG1-SG7 have passed on the committed code with these values set. **SG1-SG7 are run only after this amendment is committed**, on the code commit that sets the eight values (§0a: after a pre-result amendment, SG1-SG7 are rerun).

This check reads code constants and file bytes only, never a column value. A refusal here is restartable, like a gate failure (§0a). The run's PROVENANCE prints the eight values and this file's SHA-256.

**Reason, in plain English.** The point of the switches is that the code never decides for the owner. A switch left at `None` would surface as an exception after `OUTCOME DECODED`, when a restart is no longer clean. Checking before RUN START turns that into a refusal that costs nothing.

---

## Decision record

**Rulings 1-12 made by the owner, 2026-10-30. Written down by the Opus session; not the owner's personal signature.**

- Ruling 1: racecraft-flagged free passes are dropped from step 1 (`drop`).
- Ruling 2: a corner of the class with no comparison group left is skipped; N_F < 2 or N_L < 2 still gives `unknown` (`skip_corner`).
- Ruling 3: a prediction whose α and φ are not identified together is dropped and counted, in design A and the lap arm (`drop`).
- Ruling 4: undefined draws propagate (interval undefined, nothing skipped or redrawn, as WC-03 A4 G7); the go/no-go line prints the undefined-draw counts; fast and aero S2 may become INCONCLUSIVE (`propagate`).
- Ruling 5: a race drawn twice within one copy is a separate copy; σ̂'s degrees of freedom count its parameters twice (`copy`).
- Ruling 6: X1 trims on the registered τ (group α̂), as §8a D26 does for the bracketed baseline; unknown values are rejected (`registered_tau`).
- Ruling 7: a lap L with a tied modal leader is not a release event; the tie count is printed (`drop`).
- Ruling 8: under FALLBACK, a negative median gap and the 0-0.3 s bin are both priced at the 0.3-0.5 s bin of β_lap (`bin_0.3-0.5`).
- Ruling 9 (reading): discovery parquet goes to `_artifacts/WC-10/discovery/` with SHA256SUMS, as §13 says; supersedes the brief's `_artifacts/WC-10-discovery/`.
- Ruling 10 (reading): summary line 2 is printed word for word, "confirmed" included; any banned-word check exempts that exact line only.
- Ruling 11 (reading): `S_aero` is the literal unweighted sum, no w_k (§13 item 7, D16).
- Ruling 12 (reading): under FALLBACK, a lap whose median gap is NaN is not priced; `S_pace` stays undefined, shown as "—" with a reason, never 0 and never the 0.3-0.5 s bin (BUILD-ORDER rule 7; §13 items 7-8).
- Builder readings B-i to B-iv confirmed as written. B-ii stands only with its equivalence test, kept as SG4 evidence.
- Preflight D added: RUN START is refused while any of the eight open-choice values is unset or differs from its ruling.
- No threshold, tolerance, floor, trim, window, bin, minimum, B, seed, season split, race list or go/no-go rule changes. Every value here is committed before SG1-SG7 and before RUN START.

## After the decision is recorded

1. The owner commits this file alone.
2. `shasum -a 256 _roadmap/_wake-calibration/wi/WC-10-amendment-B1-open-choices-DRAFT.md` on the committed text. Record the digest and commit on DD-WC20 in `status/build-log.json`, beside the registration's.
3. The code sets the eight `OPEN_CHOICES` values (five in `design_a`, three in `diagnostics`), implements `"copy"` for ruling 5, rejects unknown `x1_trim` values (ruling 6), prints the tie count (ruling 7), writes parquet to `_artifacts/WC-10/discovery/` (ruling 9), exempts summary line 2 from any banned-word check (ruling 10), and adds the preflight check of section D and the B-ii test, in a separate commit.
4. SG1-SG7 are run on that commit, after this amendment is committed. Only then may RUN START be written.

```
Commit:   ______________________
SHA-256:  ______________________
```
