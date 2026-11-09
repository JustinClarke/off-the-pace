# WC-10 (proposed) - Exploratory traffic levels: pace, aero, tyre (PLAN, DRAFT)

**Status: PLAN, DRAFT, not registered.** Written by an agent on 2026-10-29 for the owner. Nothing is fitted. This is not a pre-registration: under BUILD-ORDER rule 4, nothing below may be fitted until a pre-registration is committed alone and its SHA-256 is recorded in the log. WC-10 is not in `status/build-log.json`. Adding it, and every ruling marked **OWNER**, is the owner's call. The pre-registration, A1-A6, the build log and every other file are unchanged. No number from the archived dirty-air method (DA-03) is used.

**What the owner asked for.** For a driver on a lap or stint: how likely is it that following another car is costing them (1) **tyre** life, (2) **pace** (time), (3) **aero** grip in the wake? Show each as a level (none/barely, low, medium, high, maximum) on a replay of an archived race (WC-07). A rough working estimate is acceptable. A causal proof is not needed.

**Short answer.** A **pace** level can be done now. An **aero** level can be done with caveats, as a proxy that may turn out to be not identifiable. A **tyre** level probably cannot be identified with this data and should be planned as "—" unless the data shows otherwise. The way to isolate the effect is **not** the registered "own clean passes within ±4 laps" reference. It is a within-driver, within-stint, within-corner comparison with field-wide lap effects, which has about five times as much usable data close to the car (§3). A rough version takes about a week, including a short registration. The full version, with a sealed confirmation and a replay, takes about 5-7 weeks.

---

## 1. Where things stand (read from the sources)

- The registered WC-03/WC-04 contest stopped at G3 check 4 (`_evidence/WC-04-2026-10-29/PROVENANCE.txt`). The file count matched (1,214), but the digest was `aaaf711d…` against the registered `aed1c27d…`. The cause: five São Paulo laps paths came back from `glob` in NFD form (draft A6). Nothing was fitted or scored. SCORECARD.md line 1: "No verdict … The flat penalty stays."
- Prereg §0: "One run, no reruns". A run is "completed" once any evidence file holds a gate result, and the G3 result line counts. The run guard in `run_wc03.py` refused a restart (build-log, last entry). Any new attempt needs a new registration.
- The design note's top risk is **selection**: drivers stuck in traffic have no clean reference, and that is where the loss is largest (`WC-design-note.md`, "Top risks" 1; NOISE-INVENTORY #21: only 22.2 % of following braking passes have a measured reference, 17.0 % in 2025).
- WC-07 (replay) is SPEC and not built. It shows measurements only. "No loss, delta, coefficient, curve or scale" may be shown, and the loss scale is WC-08, which is gated on WC-03/04/05.

## 2. What the data can see (evidence: `s01_channels.py`)

All figures below are counts or coverage from bronze, with no outcome summarised. The outputs are in the scratchpad (paths in §10).

| Source | What exists | Coverage / resolution | Use here |
|---|---|---|---|
| Telemetry `car` rows | `speed_kph`, `throttle_pct` (0-100, 100 distinct values), `brake` (**on/off only**), `nGear`, `RPM`, `DRS` (codes 0-14) | median spacing **0.24 s** in every season, p90 0.40 s in 2022-25: about **4 Hz, roughly 20 m between samples at 300 km/h** | min speed, exit speed, coast time, partial-throttle share, DRS-open flag |
| Telemetry `pos` rows | `X`, `Y`, `Z`, `distance_m`; FastF1 `DriverAhead` on 91-94 % of samples | about 0.12-0.13 s | gap (the builder's own crossing-order method), not `DriverAhead` |
| **Not in bronze** | steering angle, lateral/longitudinal g, tyre temperatures or pressures, wheel speeds, ride height, fuel load. `telemetry_full/` and `pos_data/` are empty | — | **no direct sliding, grip or downforce signal** |
| Laps | `LapTime` 98-99 %, `TyreLife` 98-100 %, `Compound` about 100 %, three sectors 97-98 %, speed traps `SpeedST` 91-92 % (99.9 % in 2025), `SpeedI1` 84-86 %, `IsAccurate` 82-89 %, `Position` about 100 % | one row per lap | lap pace, tyre age, the tow/DRS signature at the trap |
| Weather | track temperature, rainfall, wind | once per minute, all races | wet exclusion, a track-temperature control |
| Pass table (pass d) | per-corner `gap_s`, `seg_time_s`, `min_speed_kph`, `leader`, `behind_1s`, `clean`, exclusion `reason`, `corner_class` | 2,927,753 rows, 2018-2025 | the unit of analysis |

**Proxies for each factor, and what they cannot separate.**
- **Pace**: corner segment time against the driver's own expected time, and lap time against the stint level. This is solid, apart from the selection and drift issues covered in §3.
- **Aero**: the wake removes downforce, and downforce matters more the faster the corner. The signature is therefore a **minimum-speed (and exit-speed) deficit that is larger in fast corners than in slow ones at the same gap**, in passes where the car ahead is not slower ("dirty air", not "held up"). The 4 Hz data can also give coast time before braking and partial-throttle share. **Not identifiable:** true downforce loss versus a driver lifting by choice to avoid the gearbox ahead, versus saving front tyres. All three give a lower fast-corner minimum speed. The fast-versus-slow contrast narrows the confusion but does not remove it. The level would read "aero-like loss", not "downforce lost".
- **Tyre**: the only signal is lap time. There is no temperature or sliding data. The estimand would be "lap time still lost **after** leaving the wake, per lap spent close", a carry-over. This is confounded with tyre saving while stuck (the opposite sign), with pushing after a release, and with strategy, because the car behind often pits off-cycle. **Probably not identifiable** at a level worth showing (§5).
- **DRS is collinear with following** (`s03_drs_exposure.py`, 2023): **91 %** of laps with a median braking-corner gap under 1 s have DRS open at some point, against **3 %** of free laps. Mean open share is 14.2 % of samples against 0.25 %. A lap-level pace number is therefore the net of wake loss and DRS/tow gain. Corner-level numbers on braking corners carry less of the DRS gain but are not free of it: entry speed after a DRS straight is higher.

## 3. How to isolate the effect: designs compared (evidence: `s02`, `s05`, `s06`)

All counts use the registered pass table, braking corners, kept passes only, yielding excluded. "Close" means 0 ≤ gap < 1 s. "Free" means no car ahead or a gap over 3 s. "2022-25" is the ground-effect era.

| # | Design | Usable data (outcome-blind counts) | Identifies | Main risk | Verdict |
|---|---|---|---|---|---|
| A | **Within driver × stint × compound × corner, with field corner × lap effects and a tyre-age trend** (dose-response by gap bin) | Close passes in a group that also has ≥2 free passes: **107,451 of 215,970 (50 %)**, 2022-25. By class: fast 17,430, medium 46,211, slow 43,810, from 76-89 races. Per team in 2025: **54-64 %**, against own-clean 14-28 % | pace per corner class and gap; aero via fast − slow | drift over a stint (tyre, fuel, track), absorbed by the trend and field-lap terms; "catching" bias (§6) | **Primary** |
| B | Fast-versus-slow contrast inside A | laps with a close pass in **both** a fast and a slow corner: 2,044-4,454 per season | the aero signature | lifting/saving look the same | **Part of A** (the aero estimand) |
| C | Car ahead pits, follower released (natural experiment) | pass-table events (follower close/following on L, car ahead's pit lap on L+1, follower stays out): **1,640** in 2018-25, of which **551** are free on L+2. WC-02 had 530 with readings on both sides | pace jump on release | small; release coincides with the follower's own strategy phase | **Check, not estimator** |
| D | Teammate matched (driver close, teammate free, same lap, same compound, tyre age within 5 laps) | **4,875** driver-laps, 378-811 per season | lap pace net of field | driver offset; teammates on different strategies | cross-check |
| E | Event study at state changes inside a stint | free→following 58-120 per season (774 total); following→free 113-186 (1,226) | pre-trends, tyre carry-over | thin | diagnostic; the tyre estimate (§5) |
| F | Within-lap near versus far (same lap, some corners close, some free) | only **136-453 laps per season** have ≥2 close and ≥2 free corners | — | gap barely changes within a lap | **reject** |
| G | Registered own clean ±4 laps (WC-03) | measured share among passes at 0.5-1 s: **8.6 %** (2022-25), 13.4 % (2018-21). About 20,900 close passes | pace | selection: the closest passes are the least covered | **retire for this purpose** |
| H | Mixed stints, lap level (≥3 following and ≥3 free laps) | **2,250** stints (1,231 in 2022-25); 1,509-2,751 following laps per season inside them | lap pace, tyre slope | small; within-stint only (prereg §8d) | lap-level arm of A; tyre |

**Why A beats G.** G needs ≥2 clean passes of the same corner within ±4 laps, and someone stuck behind for 6 laps has none. A uses the driver's free passes of that corner **anywhere in the stint**, with a tyre-age trend and a field-wide lap effect standing in for the narrow window. That lifts support close to the car from about 10 % to about 50 %, and makes team coverage much more even. The price is that A depends on modelling drift over the stint correctly. That is checkable (§6) and is the main thing the discovery stage must test.

**Formal sketch of A** (to be fixed in the registration, not here). For pass *i* of driver *d*, corner *c*, lap *l*, stint *s*, race *r*, outcome *y* (segment time, minimum speed or exit speed):

    y_i = α[d,s,c] + φ[r,c,l] + g(tyre_life_i; compound, circuit) + Σ_b β[class_c, b, k_i]·1{gap_i ∈ b} + γ·behind_1s_i + ε_i

- α is the driver-stint-corner level.
- φ is the field-wide corner-lap effect (fuel burn, rubbering-in, wind), estimated from free passes of other cars on the same lap.
- *b* runs over the registered gap bins under 3 s, with the 3 s+ band as baseline.
- *k* is the pass class: held up (the car ahead's own expected time at the corner, from its own α, is slower than the follower's) or dirty air.

Inference uses a race-cluster bootstrap. Passes with gap under 0.3 s are reported but are not used in any gate, because of the 0.05-0.08 s timing noise (WC-02).

**Recommendation.** **Primary: A**, at corner level for pace and aero, plus its lap-level arm (H) for net lap pace. **Cheap fallback** if A fails its drift checks: lap level only, with lap time on stint FE + field lap FE + tyre trend + median-gap bin. That gives a pace level only, with aero and tyre "—", and C (release events) as the sanity check.

## 4. Turning estimates into levels, honestly

**The score per factor and lap** (modelled, from the fitted curves and the lap's **state** only):
- **Pace** `S_pace`: expected seconds lost over the lap's braking corners = Σ_k w_k · β_pace(class_k, bin_k, class of pass_k). The weights w_k are the registered no-double-counting weights (prereg §7). Straights and flat-out corners are not priced (as in prereg §4b C1). The page says this.
- **Aero** `S_aero`: expected minimum-speed deficit in the dirty-air class over the lap's fast and medium corners, **minus** the slow-corner deficit at the same gap (km/h). This is the part that scales with speed.
- **Tyre** `S_tyre`: θ_carry × (close laps so far in this stint), in s/lap carried. Only if the tyre gate passes (§5).

**Levels.**
- **None/barely** is definitional where it can be: no car ahead, or gap ≥ 3 s at every braking corner. Otherwise it applies when the score is below the 50th percentile of the discovery seasons' distribution among following laps, **or** when the bins the lap uses have a discovery interval that includes 0.
- **Low** 50th-75th, **medium** 75th-90th, **high** 90th-98th, **maximum** ≥ 98th percentile. "Maximum" means "about as large as this data has seen for that factor", not a physical limit.
- The cut points are computed once on discovery and written into the confirmatory registration as fixed numbers. They are not changed after confirmation. **OWNER**: quantile cuts (recommended, because no effect size is known yet) or physical cuts (for example in tenths of a second). Physical cuts would have to be chosen after seeing discovery effects, and that is allowed only because discovery is declared seen.
- **Why levels and not seconds.** One lap's own measured loss cannot be resolved. The seen noise floor (§9 item 4) is **0.31 s SD** (MAD 0.14 s) for free-lap times after a tyre trend, and 0.06 s per corner pass. A single lap's effect below about 0.6 s cannot be told apart from noise. The level is therefore the **typical effect for a car in this state**, not what this driver lost on this lap.

**Uncertainty.** Each lap's score gets a race-cluster bootstrap interval from the discovery fit.
- **Firm**: the 80 % interval sits inside one level.
- **Between**: it spans two adjacent levels, shown as "low–medium".
- **Uncertain**: it spans three or more levels, shown as text and not as a level chip.

**Labels (repo vocabulary).**

| Shown | Label | Rule |
|---|---|---|
| Car ahead, gap (s, m), DRS open, tyre age, compound | **measured** | from timing and traces |
| Pace, aero and tyre levels | **modelled** | always: they come from a model of the state. Each carries the DD-WC2 disclaimer **word for word**: "Normalised from other compounds, based on stints from other drivers or the general performance of the tyres after removing other factors." |
| A factor whose gate failed, a lap that is excluded (SC/VSC, yellow, pit, wet, restart, track limits), no gap, or a held-up/dirty-air class that is unknown (aero only) | **unavailable** | "—" with the reason, never 0 and never "none" |

**OWNER**: the DD-WC2 wording was written for modelled references and fits a level badly. Rule 7 requires it verbatim. Recommendation: keep it verbatim and add a second, separate line, "Level = typical effect for a car in this situation, not a measurement of this lap". That needs a ruling, because rule 7 says "word for word".

## 5. The tyre factor, stated plainly

- **Estimand:** θ_carry is the lap time a driver still loses on **free** laps after an episode close behind, per close lap in that episode. It sits beyond the tyre-age trend of their own free laps in the same stint, with the field lap effect removed.
- **Data:** following→free transitions number 1,226 (2018-25). Close episodes have a median length of 2 laps and a p90 of 6-7 laps. There are 1,228 episodes of ≥5 laps in 2022-25 and 611 in 2018-21 (`s05`).
- **Power is not the binding problem; bias is.** As a naive scale: about 4 free laps either side of a 4-lap episode at 0.31 s SD gives roughly 0.05 s per close lap per stint, and about 0.003 s pooled over 500 stints, before clustering.
- **The confounders do not average out.** They are tyre saving while stuck (makes θ look negative), pushing after a release (negative), and off-cycle pitting (truncates the "after" laps). The registration should pre-declare that the tyre level is shown only if:
  - θ_carry's confirmation interval is above 0, **and**
  - the pre-trend on the 3 free laps before an episode is flat, **and**
  - the effect grows with episode length.

  Otherwise tyre shows "— not identifiable with this data". **Expect "—".**

## 6. Failure modes: how each is detected or mitigated

| Risk | Detection / mitigation |
|---|---|
| **Leakage** (thresholds tuned on the test) | Discovery is 2022-2023 and confirmation is 2024-2025, sealed. Cut points and gates are fixed in the confirmatory registration before any 2024-25 outcome is read. The 2018-21 era has its own split (2018-19 / 2020-21) and is optional. |
| **Confirmation seasons are not unseen in general** | prereg §2e: the 2026-10-21 same-lap scoping used 2018-2025 and showed that lap-level traffic fits lap time. Declared (§9). The confirmatory tests are therefore corner-level, fast-vs-slow and level calibration, not "is there any lap-level traffic effect". |
| **Multiple testing** | One primary gate per factor (§7, C1/C2/C5) under Holm across the three. Everything else is "diagnostic", labelled so, and never moves a level. |
| **Gap noise 0.05-0.08 s** | The 0-0.3 s bin is excluded from gates. Its estimate is reported, and the replay maps it to the level of the 0.3-0.5 s bin. |
| **Catching bias** (a driver closes up because they are faster, so close passes look fast; the reverse when falling back) | Refit with the gap taken from the **same corner on the previous lap** (predetermined). A large change flags the bias. Report the estimate split by whether the gap was shrinking or growing. |
| **Held up versus dirty air** | Classify by the car ahead's own expected corner time (its α) against the follower's. Aero uses dirty-air passes only. If the car ahead has no free-pass support, the class is "unknown" and aero is "—". Expect slow corners to be the least reliable (WC-02 check 3: minimum-speed vs time agreement is lowest in slow corners, Spearman −0.47). |
| **Tyre saving / lifting while following** | Coast time before braking, and partial-throttle share, by gap bin. A rise that is equal in slow and fast corners points to saving or being held up, not wake. Reported with the aero level as a confidence note. |
| **Fuel burn, track evolution, wind** | The field corner-lap effect φ comes from other cars' free passes on the same lap. Check: no residual trend in free passes over the stint (pre-registered tolerance). The ±stint-window variant (window ±4 / ±8 laps instead of the whole stint) must agree. |
| **DRS** | DRS is collinear at lap level (91 % against 3 %, §2). Corners entered from a DRS zone (DRS open in the 300 m approach) are tagged and reported separately. Lap-level pace is labelled "net of DRS/tow". In 2026 there is no DRS, so a refit is needed. |
| **Era** (2022 ground-effect cars against 2018-21; 2026 rules) | Separate fits; no pooling across eras. No levels for 2026 until WC-09 ingests 2026 and a 2026 registration exists. |
| **Team coverage** | FE support per team is printed (2025: 54-64 %, `team_support.csv`). Levels on stuck-all-stint drivers are extrapolated from drivers whose gap varied. Report the effect by "share of stint spent close" tertile. |
| **Wet, SC/VSC, yellows, pits, restarts** | Inherited WC-01 exclusions. Those laps show "—" with the reason. |
| **Data-gate trap (what killed WC-03)** | §8: paths are NFC-normalised, the gate is dry-run before RUN START, and a gate failure that read no outcome is restartable. |

## 7. Gates (to be fixed in the confirmatory registration; proposal)

All gates are on 2024-2025 with the race-cluster bootstrap (fixed draws and seed), using bins from 0.3 s up.
- **C1 Pace dose-response:** the pace effect in the 0.5-1.0 s band is above 0 (lower end of the interval > 0) in every corner class; the 2-3 s band is ≤ 25 % of it (P1 logic reused); and the near band is above the far band. Fail: no pace level, and the fallback is reported.
- **C2 Aero signature:** in dirty-air passes at 0.3-1.0 s, the fast minus slow minimum-speed deficit has its whole interval above 0. This is stricter than the registered P2, which only required "not wholly below 0", because here it carries a claim. Fail: aero shows "—".
- **C3 Level calibration** (pace, plus aero if C2 passes): on confirmation laps, the mean observed within-stint residual rises across levels; the "high" and "none" means have non-overlapping intervals. It can only test changes within a stint, as prereg §8d says. Fail: the levels are collapsed to three (none / some / high) and reported.
- **C4 Release check** (reported, sign only): on car-ahead-pits events in 2024-25, the follower's adjusted lap time improves on release, and the predicted level before release is ≥ low.
- **C5 Tyre:** §5. Fail: tyre shows "—".

## 8. Staged plan with go/no-go gates and cost

| Stage | What | Weeks | Model (BUILD-ORDER guidance) | Go / no-go |
|---|---|---|---|---|
| 0 Outcome-blind prep | Reproduce this plan's counts into `_evidence/WC-10-<date>/` with PROVENANCE (the scratch copies here do not count, rule 8). Build a **sidecar** table keyed by pass (exit speed at apex+100 m, coast time, partial-throttle share, DRS-open-in-approach, previous-lap gap) into `_artifacts/WC-10/` with SHA256SUMS. `PASS_COLUMNS` is unchanged. Write the input data gate: content hashes, **NFC paths**, dry-run against real inputs reading no outcome | 1 | `opus-5` (new derived columns; a claim boundary) | ≥ 5,000 identifying close passes per class in 2022-23 and ≥ 30 races; the gate dry-run passes |
| 1 Discovery registration | A short pre-registration: seasons split, A's specification, outcomes, the list of what discovery will produce, the "seen" list (§9), confirmation sealed. **Committed alone, hashed, recorded** (rule 4) | 2-3 days | `fable-5.1` for the identification text; owner signs | owner signature |
| 2 Discovery fit | Fit A on 2022-23 (pace, minimum speed, exit speed), lap arm, held-up/dirty split, θ_carry. Diagnostics: drift, window variants, lagged gap, DRS-tagged split, coast/throttle, release events. Compute level cut points | 1-2 | `fable-5.1` | dose-response visible and drift checks inside tolerance, else switch to the fallback (lap level, pace only) |
| 3 Confirmatory registration + run | Fix cut points, gates C1-C5, Holm, draws, seed, data gate, restart rule. Commit alone and hash. Run once on 2024-25 | 1-1.5 | `fable-5.1` (run), `opus-5` (scorecard) | gates decide which factors get a level |
| 4 Replay MVP | Build WC-07 (ReplaySource as specified) plus a `levels(season, race)` input: per lap and car, car ahead, gap, three level chips with label, confidence and disclaimer, and "—" with reasons. Tests: every value labelled, disclaimer on every modelled value, no 0 for unavailable | 1-2 | `opus-5`; `sonnet-5` for wiring once the spec is settled | owner reviews one race per season |
| 5 Optional | Causal (trailing) variant; older era with its own split; 2026 after WC-09 | 1-2 each | `fable-5.1` / `opus-5` | separate registrations |

**Total:** about 5-7 weeks for the full version. Pace-only via the fallback: about 2-3 weeks.

**The fastest useful thing (about 5 working days).**
1. Stage-0 counts and the gate dry-run, cut down to essentials: 1 day.
2. A one-page discovery registration, committed and hashed: half a day. This is required. Rule 4 has no exploratory exception.
3. Fit A on 2022-23 for pace and minimum speed by class, plus the lap-level arm: 2 days.
4. One known 2023 race as a static per-lap level table (CSV or HTML mock, labelled "exploratory, discovery data, in-sample, not confirmed"): 1 day.

What the owner can conclude from it:
- whether a gap dose-response is visible with the design that avoids selection;
- whether fast corners lose more minimum speed than slow ones (is an aero level plausible at all?);
- whether tyre carry-over is anywhere near detectable;
- whether the levels look sensible on a race they know.

What the owner cannot conclude: that any of it generalises. 2024-25 stay sealed for that.

**Live replay.**
- WC-07 already defines per-lap, per-car gap, car ahead, reference status and labels behind a `ReplaySource` interface. It is not built.
- The registered reference (±4 laps, both sides) uses **future laps**, so it is not causal. A trailing version is too thin: with own clean passes in laps L-4..L-1 only, measured share at 0.5-1 s is **3.1 %** (2022-25). Even with every earlier lap of the stint it is only 15.3 % (`causal_reference_k*.csv`).
- Design A's **levels** need only the lap's state (gap, corner class, pass class, tyre age, close laps so far) plus curves fitted on other seasons. They are close to causal. The exceptions:
  - corner geometry and classes come from that race's clean-air medians;
  - the held-up/dirty split needs the car ahead's level, estimated from the whole stint.
- **Recommendation:** v1 is a **retrospective replay** (computed after the race, played back lap by lap, badge "retrospective"). Stage 5 can add a trailing-only variant and report how often its level agrees with v1.
- True live needs the OpenF1 feed, which is DD-WC3 and open.

## 9. What the new registration must fix up front, and the "seen" list

**Fix up front:**
- The season split, with confirmation sealed.
- Design A's exact specification: groups, field effects, tyre trend, bins, pass-class rule.
- The outcome columns and the sidecar definitions.
- The cut-point rule and, in the confirmatory document, the numbers.
- Gates C1-C5 and Holm.
- Bootstrap draws and seed.
- Labels, disclaimer and "—" rules.
- "Replay v1 is retrospective".
- **The data gate:**
  - hashes taken on NFC-normalised paths;
  - a dry run before RUN START;
  - an explicit rule that a gate failure that reads no outcome column is restartable, and that a run "completes" only once an outcome-derived number is written. This closes the trap that ended WC-03.
- No DA-03 number. WC-10 does **not** decide the label's flat penalty. That decision stays where WC-03 left it.

**Declared prior knowledge (prereg §2e style):**
1. prereg §2e items 1-2: the 2026-10-21 same-lap scoping on 2018-2025, and the 0.305 reference-fit rerun.
2. WC-02 check 3: the minimum-speed against time Spearman correlations (−0.64 fast, −0.59 medium, −0.47 slow).
3. **This plan's outcome-blind counts** (§2, §3; scripts `s01`, `s02`, `s03`, `s05`, `s06`). They read structural columns only: gap, flags, classes, tyre life, DRS state. No segment time, minimum speed, reference or loss was read in them.
4. **This plan's noise floor: SEEN, outcome values** (`s04_noise_floor_2022.py`, **2022 only**, clean passes and all-clean laps only, so no traffic-loaded pass or lap was read). Within-group SD after a tyre-life trend, by corner class:

   | Class | Segment time SD (MAD) | Minimum speed SD (MAD) | Passes |
   |---|---|---|---|
   | Fast | 0.060 s (0.026) | 3.02 km/h (1.64) | 8,846 |
   | Medium | 0.063 s (0.031) | 2.44 km/h (1.28) | 28,341 |
   | Slow | 0.064 s (0.034) | 1.86 km/h (0.98) | 26,730 |

   Free-lap time SD is 0.313 s (MAD 0.139), over 3,866 laps and 347 stints. 2022 is a discovery season, so this does not touch confirmation.
5. Everything stage 2 produces on 2022-23 (by construction).

## 10. The stalled WC-03/WC-04 and A6 (recommendation; **OWNER** rules)

- **WC-03 and WC-04:** close as CLOSED, "no verdict: G3.4 digest mismatch (NFC path names); nothing fitted or scored". This is the first row of prereg §9, so the flat penalty stays. A restart under that registration is not possible under §0, and A6 cannot make it so.
- **A6:** record it as "not adopted for WC-03" (it cannot rescue the run). Commit the NFC fix and its test anyway, as the record of the cause, and carry NFC-normalised hashing into WC-10's data gate.
- **WC-05 and WC-08:** point them at WC-10 so that closing WC-03 does not unblock them. The build-log's last entry already notes this risk.
- **WC-07:** its rule "no loss … or scale" would have to be relaxed for WC-10 levels once the confirmation passes. That makes WC-10 the successor to WC-08's gate. This is an owner ruling.
- **Also correct the build-log 18:00 entry** by a new entry, as the last handoff asks.

**Scratch evidence for this plan.** Session-temporary; not artefacts under rule 8. Stage 0 reproduces them.
- Scripts: `/private/tmp/claude-501/-Users-justin-github-off-the-pace/8181e7c5-a382-4f57-810c-d9bfc1b25df3/scratchpad/scripts/`
- Outputs: `/private/tmp/claude-501/-Users-justin-github-off-the-pace/8181e7c5-a382-4f57-810c-d9bfc1b25df3/scratchpad/out/`
- Files: `tel_channels_by_season.csv`, `tel_sample_spacing_monza.csv`, `tel_car_spacing_by_season.csv`, `laps_channels_by_season.csv`, `weather_by_season.csv`, `lap_states_by_era.csv`, `within_lap_contrasts.csv`, `mixed_stints.csv`, `transitions.csv`, `car_ahead_pits_release.csv`, `teammate_pairs.csv`, `causal_reference_k{4,8,99}.csv`, `drs_by_state_2023.csv`, `fe_support.csv`, `close_episode_lengths.csv`, `team_support.csv`, `noise_clean_pass_2022.csv`, `noise_free_lap_2022.csv`.
- Inputs read only: `_artifacts/WC-03-run/pass-table/*.parquet` (pass d) and `data/bronze/{telemetry,laps,weather}`.
- `data/dev.duckdb` was not touched.

## 11. Is this too much to ask?

| Ask | Verdict | Why |
|---|---|---|
| "Is this driver following, and how closely?" | **Feasible now, measured** | gap agrees with timing within 0.1 s in 168 of 169 races (WC-02) |
| Pace level per lap | **Feasible now, modelled** | design A has about 107k identifying close passes in 2022-25; per-pass noise 0.06 s; braking corners only, net of DRS at lap level |
| Aero level per lap | **Feasible with caveats** | a proxy (fast − slow minimum-speed deficit, dirty-air passes); cannot separate downforce loss from lifting or saving; shown only if C2 passes |
| Tyre level per lap/stint | **Probably not**; plan for "—" | lap time only, no temperature/sliding data; confounded by saving, pushing after release and strategy; shown only if C5 passes |
| A per-lap **measured** loss for one driver | **Not feasible** | 0.31 s lap noise; levels are typical effects for the state, not this lap's loss |
| Live (in-race) levels | **Not now** | needs DD-WC3 (OpenF1); v1 is a retrospective replay |
| 2026 | **Not now** | no 2026 data in bronze (WC-09); no DRS, so a refit is needed |

**Unsure / to verify in Stage 0.**
- Whether the 4 Hz car data resolves exit speed and coast time well enough. At about 20 m per sample in fast corners, brake-onset shifts under about 20 m are invisible.
- Whether the field corner-lap effect can be estimated in races with few free cars.
- Whether the "catching" bias is small. The lagged-gap check (§6) decides that.

---

## Review note, 2026-10-29 (outcome-blind reality check before queuing)

Written by a review agent (Opus) while turning this plan into WC-10a-l in `status/build-log.json`. The body above is not changed. Every number here is a count or coverage of structural columns (gap, flags, classes, tyre life, DRS state, `distance_m`, sample times). No segment time, minimum speed, delta, reference or lap time was read. `data/dev.duckdb` was not touched. Scripts and CSVs are session scratch (`.../scratchpad/review/scripts/r01_identification.py`, `r02_claims.py`, `r03_splits.py`; outputs in `.../scratchpad/review/out/`). WC-10a reproduces them into `_evidence/`.

**Claims checked**

| Claim | Result | Reviewer's number |
|---|---|---|
| 107,451 of 215,970 close passes identifying (2022-25) | CONFIRMED, definition clarified | Exact match. The definition is a group (race, driver, stint, compound, corner) with **≥2 close AND ≥2 free** passes. §3 says only "≥2 free". With ≥2 free alone it is 113,271. |
| Per team 2025: 54-64 % vs own-clean 14-28 % | DIFFERS (definition) | Those figures are for **following passes at 0-3 s**, not close passes. For close passes (<1 s) in 2025: identifying **42-55 %** against own-clean **4.5-15.8 %**. The ratio still favours A. |
| Trailing reference 3.1 % at 0.5-1 s | CONFIRMED | 3.13 % (n = 155,803; symmetric ±4 = 8.7 %) |
| DRS 91 % vs 3 % (2023) | CONFIRMED | 91.2 % vs 3.2 %; mean open share 14.3 % vs 0.24 % |
| 1,640 release events / 551 free on L+2 | CONFIRMED as counted, **but the definition has a hole** | 1,635 / 551. Only **848 (52 %)** have the pitting car equal to the follower's car ahead on lap L. Identity-matched and free on L+2: **362** (2024-25: **112**). |
| Sidecar derivable at ~4 Hz | CONFIRMED with resolution limits | Car rows carry `distance_m`, `throttle_pct`, `brake` (on/off), `DRS`. 2022-25 car-row spacing: median 0.24 s / **13 m**, p90 0.40 s / **25 m**, p99 **37-38 m**. Exit speed at apex+100 m is an interpolation between samples up to ~25 m apart. Coast time resolves to about 0.25 s. The previous-lap gap comes from the pass table, and it exists for **86.6 %** of identifying close passes. |
| Stage-0 go/no-go (≥5,000 identifying close passes per class in 2022-23, ≥30 races) | PASSES | fast 7,951 (37 races), medium 21,063 (43), slow 20,045 (43) |

**Holes in the identification (these change what the registration must say)**

1. **One-sided support. This is the biggest one.** Of the 107,451 identifying close passes, only **23,687 (22 %)** have free passes of the same corner both before and after them in the stint. **64,960 (60 %)** have free passes only *after* them: close early in the stint, free later. Within the identifying groups, corr(close, tyre_life) = **−0.34**. The nearest free pass is a median **7** tyre-age laps away (p90 20; 34 % more than 10 laps). For most of the data, the close-vs-free contrast is therefore estimated *through* the shape of g(tyre_life) and φ. It is not a local comparison. A driver-specific tyre slope cannot be separated from the effect where support is one-sided. **Change:** the registration must pre-declare a **bracketed-subset** estimate as a gate-level robustness check with a numeric tolerance. In 2022-23 the bracketed counts are fast 1,674, medium 4,128 and slow 3,995, so the fast class will be wide. If the bracketed estimate disagrees beyond tolerance, design A falls back as §3 describes. The "about 50 % support" in §3 should be read as about 11 % *locally* supported (23,687 / 215,970), which is close to G's 8.6 %. A's advantage rests on the drift model, as §3 already says. It is a bigger dependence than the text implies.
2. **Stuck-all-stint drivers.** In stints where at least 80 % of braking passes are close, there are 40,294 close passes (18.7 % of 2022-25 close passes), and only **13 %** of them are identifying. The 50-80 % tier has 65,827 passes, 36 % identifying. The <50 % tiers are about 71 % identifying. In 85,358 close passes (40 %) the group has **no** free pass, so α absorbs everything and those passes contribute nothing. The effect is learned from drivers whose gap varied and is applied to stuck drivers by assumption. **Change:** report the effect by close-share tier (as §6 says), and mark a level on a stint with a close share of 80 % or more as "extrapolated" in the confidence note.
3. **Release events (C4).** The 1,640/551 set counts a release whenever *any* car the follower had a pass behind on L+1 pits. Use the identity-matched set (pitting car = car ahead on L), or WC-02's restated set (DD-WC9, DD-WC10). In 2024-25 that is about 112 events: enough for a sign check, nothing more.
4. **Field corner-lap effect φ.** There is a median of 5 other free cars per (race, corner, lap). **26 %** of identifying close passes have fewer than 3, and almost none have 0. φ can be estimated, but it is noisy. Register a minimum count, with a fallback to a lap-level φ.
5. **Catching bias check is weak.** Where the previous-lap gap exists, **73 %** of those passes were also close on the previous lap, so the lagged-gap refit mostly re-labels the same passes. Make the **shrinking vs growing gap split** the primary catching diagnostic, and keep the lagged refit secondary.

Not checkable outcome-blind: whether the dose-response exists, how big the drift is, and whether lifting/saving dominates the aero contrast. Those are discovery questions.
