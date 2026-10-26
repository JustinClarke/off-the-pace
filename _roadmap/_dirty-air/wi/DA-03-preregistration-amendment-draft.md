# DA-03 pre-registration amendment: DA-02P draft for owner approval

This file is a draft. It is not the pre-registration, and it is not hashed by the fit. `fit_dirty_air_microsector.py` hashes `wi/DA-03-preregistration.md` at a fixed path, so the amendment takes effect only when the owner copies the text between the two markers below over that file, commits it alone, and records the new hash.

## Notes for the owner (not part of the registered text)

**Reference hash.** The committed `wi/DA-03-preregistration.md` at HEAD `82796dc` (working copy identical, no local edits) has SHA-256 `74df5902815dfe8e63006560fa687baf292910efe918cf0ede88a127348a49de`. This draft amends that version.

**What changes against that version.**
1. The DRAFT marking is removed from the title and the status paragraph.
2. P3 gets a fixed micro-sector to corner-class map (`int_microsector_corner_class`), fixed thresholds, a spec (`p3`) and a pass rule. Before this, P3 was `OWED` and had no numeric pass rule, so the gate could not be passed.
3. Two DRS specs are registered, both reported only: `drs_closed` (gap-based, drops micro-sectors where DRS is open at entry or exit) and `drs_location` (location-based, drops any micro-sector where any car had DRS open in that race). Neither gates P3. DRS is not a control in any spec.
4. The data section names the new panel columns. The "not ruled out" paragraph on DRS is updated.
5. Nothing else is changed: model, bands, primary quantity, P1, P2, lead window and the forking-path rules are as committed.

**Order of evidence.** The thresholds and buffers were written to a timestamped scratch file at 2026-10-25T10:34:36Z, before this session computed any corner speed, loss or gap number. The apex-speed definition was tightened at 10:37:41Z, still before any speed was computed (`THRESHOLDS_SET_FIRST.txt` in the DA-02P scratch folder, not kept in the repo). No loss-versus-gap number was used to set or check them. The only real-panel numbers looked at are row counts by class and DRS state (below) and the DA-02 descriptives, re-run byte for byte as a no-change check.

**Built and tested on a scratch copy only** (copy of `data/dev.duckdb`, sha256 `82c64d86...`, the DA-02 source). The model and test edits are uncommitted in the main tree. Re-run on the rebuilt dev after the owner commits them.

**Estimator (added 2026-10-25, uncommitted, synthetic tests only).** `fit_dirty_air_microsector.py` now runs `p3`, `drs_closed` and `drs_location` next to `bands`, `lt1`, `p1`, `p2` and `lead`, and P3 is no longer `OWED`. `p3`: the four `lt1` gap-band dummies interacted with `corner_class` (low, medium, high, flat, mixed, straight, link), driver-lap FE plus driver-race by corner-class FE, `tyre_life x corner_class` in place of `tyre_life x micro-sector`, `aheadResid`, race-clustered CRV1, rows of `2020_9` and `2020_16` dropped from `p3` only. The class main effects are spanned by the driver-race by corner-class FE, so they sit in the FE and are not separate coefficients (same model). Gate (a) `beta(lt1, high)` and gate (b) `beta(lt1, high) - beta(lt1, low)` (contrast interval from the clustered covariance, t with races - 1 df), pooled and in each era; P3 passes only if all three samples pass. `beta(lt1, flat)`, flat minus straight, straight, high minus straight, medium, mixed, link and the order check are REPORT-ONLY. Checked on a synthetic panel only (planted fast-corner loss and flat tow: high recovers only the loss, the flat class cannot move the verdict, the verdict is computed pooled and per era). Not run on the real panel.

**Class list.** low, medium, high, flat, straight, link, mixed, no_geometry. The row-count table below has the flat column (measured 2026-10-25 on the scratch build, after the map change).

**Owner decisions in this text.** Each is marked in the draft where it applies.
- D1. ACCEPTED 2026-10-25 (owner: "okay perf"). Fixed cut-offs for every track. The apex-speed classes: low under 120 km/h, medium 120 to under 200, high 200 and above. Straight buffers: 100 m before and 150 m after. Pooled apex-speed distribution checked: 200 km/h matches a dip that holds across seasons; 120 km/h is a physics choice.
- D5. RESOLVED 2026-10-25 (DD10): owner chose B, split flat-out kinks into their own class before the fit. Rule: "flat: apex speed at or above 280 km/h, not a straight". The 280 km/h number is taken from the corner analysis (205 of 869 high-corner race entries, 24%) and is CONFIRMED by the owner, 2026-10-25. A micro-sector holding both a high-speed and a flat apex stays "mixed" and is outside the fast-corner test (owner confirmed 2026-10-25). Flat is excluded from the high-speed effect and reported separately. Done 2026-10-25 (uncommitted): the map SQL has the flat class (`flat_min_kph = 280`, high is 200 to under 280), the test `assert_microsector_flat_high_disjoint` checks the split, the `p3` spec has the flat class, and the row-count table below is re-measured on the scratch build.
- D2. ACCEPTED 2026-10-25. The P3 exceptions: 2020 Tuscan and 2020 Sakhir. Also, 2021 Belgium borrows apex speeds from 2022.
- D3. AMENDED AND APPROVED 2026-10-25 (owner: "yes mate update it", "lets do your proposed fix"). The P3 pass rule is now two gates, (a) and (b), required pooled and in each era 2018-21 and 2022-25. (b) is high minus low, replacing the earlier "fast minus straight", and the straight estimate is reported, not gated. This is the owner-approved rule of 2026-10-25 and replaces the earlier wording, which the owner had not read. The spec `p3` also gets driver-race by corner-class fixed effects and tyre age by corner class.
- D4. ACCEPTED 2026-10-25, extended the same day. The gap-based DRS drop rule: drop micro-sectors where DRS is open at entry or exit, and drop unknown. A location-based version is added: drop any micro-sector where any car had DRS open in that race. Both are reported as secondary, neither gates P3, and neither can rescue a failed main result.
- DD4 wording. The wording is "adjusted traffic cost" (owner, 2026-10-25); the phase 2 gate confirms it. The pre-registration still says the wording is the owner's call at that gate.
- Commit order ACCEPTED 2026-10-25: model and test edits first, then the pre-registration alone. Path A or B: owner selected B on 2026-10-25 (DD2), gated on DA-03 and DA-04 (no label moves until both pass; B needs an ML retrain on ml-fresh-start). It is not part of this registered text and B has passed nothing.

**Row counts (fit rows: valid, `y_s` and `ahead_y_s` present; 3,000,201 rows).** MEASURED 2026-10-25 on the scratch build (copy of `data/dev.duckdb` sha256 `82c64d86...`, map rebuilt with the flat class; dbt PASS=41 ERROR=0). Row counts only; no `y_s` value was read. These replace the pre-split counts.

| Era | high | flat | medium | low | straight | link | mixed | no_geometry |
|---|---|---|---|---|---|---|---|---|
| 2018-21, all gaps | 191,847 | 47,850 | 226,291 | 250,631 | 212,764 | 292,645 | 99,409 | 31,466 |
| 2018-21, gap under 1 s | 34,504 | 8,665 | 41,271 | 42,927 | 36,698 | 51,335 | 17,028 | 7,153 |
| 2022-25, all gaps | 225,229 | 69,908 | 272,391 | 313,429 | 268,530 | 371,877 | 125,934 | 0 |
| 2022-25, gap under 1 s | 51,062 | 17,028 | 62,818 | 73,666 | 61,413 | 90,439 | 29,026 | 0 |

Map micro-sectors (one per race and micro-sector; 3,420 in 171 races):

| Era | high | flat | medium | low | straight | link | mixed | no_geometry |
|---|---|---|---|---|---|---|---|---|
| 2018-21 (79 races) | 219 | 65 | 265 | 288 | 251 | 335 | 117 | 40 |
| 2022-25 (92 races) | 248 | 86 | 306 | 347 | 303 | 407 | 143 | 0 |

Changed by the split: 169 of 3,420 micro-sectors left `high`, 151 to `flat` (65 in 2018-21, 86 in 2022-25) and 18 to `mixed` (9 and 9, a high and a flat apex in one micro-sector). In fit rows: high to flat 47,850 (2018-21) and 69,908 (2022-25); high to mixed 6,036 and 6,330. No other class changed. Check: old high = new high + flat + high-to-mixed in every cell (for example 191,847 + 47,850 + 6,036 = 245,733), and the old mixed = new mixed minus high-to-mixed.

DRS-closed rows: 2,791,198 of 3,000,201 (93.0%). Under 1 s: 175,886 of 239,581 (2018-21) and 268,843 of 385,452 (2022-25). Most DRS-open rows are on straights: under 1 s on straights, 12,358 of 36,698 (2018-21) and 17,396 of 61,413 (2022-25) are DRS-closed. So the DRS-closed straights are mostly straights without a DRS zone.

---8<--- PROPOSED TEXT OF wi/DA-03-preregistration.md (copy everything between the markers) ---8<---

# DA-03 pre-registration

**Status.** Written 2026-10-24 during DA-02. Amended 2026-10-25 by DA-02P (P3 corner-class map and pass rule, flat cut of 280 km/h confirmed, DRS specs including the location-based one), before any fit on the real panel. The estimator `transform/tasks/coefficients/fit_dirty_air_microsector.py` refuses to run unless it is given the SHA-256 of this file. The order is: the owner commits this file on its own commit, then runs `python -m tasks.coefficients.fit_dirty_air_microsector --print-prereg-sha256`, records the hash in the build log, and passes that hash to the fit. Any edit after the hash is recorded changes the hash and voids the run. Nothing below was chosen after seeing a coefficient. The only real-panel numbers looked at are the DA-02 descriptives (sample counts, validity shares, the raw loss-versus-gap curve, the lap-total identity), recorded in `_evidence/DA-02-2026-10-24/`, and the DA-02P row counts by corner class and DRS state. The corner-class thresholds were fixed before any loss-versus-gap number was looked at in DA-02P.

## Data (frozen at DA-02, extended by DA-02P)

- Panel: `int_microsector_proximity`, built from `int_microsector_crossings`, 20 micro-sectors per lap (DD8), seconds grain (DD7), 2018-2025, 171 races. Sensitivity (registered, cannot rescue a failed primary result): the same fit on a panel rebuilt with `microsector_n: 10`. The corner-class map is rebuilt with the same var, so the sensitivity panel gets its own map under the same thresholds.
- Rows used: `invalid_reason IS NULL`, `y_s` present, `ahead_y_s` present. That drops lap 1, pit-lane micro-sectors, off-track, boundaries interpolated across more than 1 s, any micro-sector where the circuit-wide track status was not all clear (or changed inside it), the two laps after an SC, VSC or red-flag lap, rows with no car ahead, and rows with a lapped car ahead within 3 s (DD5). Beyond 3 s a lapped car ahead is in the reference band.
- Known holes carried as exceptions (DD6): 2018 Australia and Bahrain have no telemetry; 2018 China and Germany have a partial track-status timeline; marshal-sector maps are not in bronze, so a local yellow cannot be placed and every yellow drops the whole circuit for its duration.
- DA-02P columns. `int_microsector_proximity` carries `drs_state_entry`, `drs_state_exit` and `drs_open` (DRS section below). They are carried only: no validity rule, band, `y_s` or field median reads them, and every pre-DA-02P column is unchanged. `int_microsector_corner_class` maps each (race, micro-sector) to a corner class (P3 below).

## Model

`y_{d,l,m} = alpha_{d,l} + sum_k beta_k * 1[entry gap in band k] + gamma * aheadResid_{l,m} + delta * (tyre_life x micro-sector) + e`

- `alpha_{d,l}`: a driver-lap fixed effect. `y_s` is micro-sector time minus the field median for the same race, lap and micro-sector.
- Bands on the ENTRY gap only: <0.5, 0.5-1, 1-1.5, 1.5-2, 2-3 s, reference >3 s. The exit gap is an outcome and is never a regressor.
- `aheadResid` is the car ahead's own `y_s` in the same micro-sector.
- DRS state is never a regressor or control in any spec. Being within 1 s at the detection line is what opens DRS, so it sits on the path from the gap to the time.
- Standard errors clustered by race (CRV1); the 95% interval uses a t distribution with (races - 1) degrees of freedom.
- Specs run: `bands` (the five-band step function, descriptive), `lt1` (merged: <1, 1-1.5, 1.5-2, 2-3 s; the gate quantity), `p1`, `p2`, `p3`, `lead`, `drs_closed`, `drs_location`. Each on all years pooled, and separately for 2018-2021 and 2022-2025.

## Primary quantity and gate (design note section 6, phase 2)

`beta(lt1)`: the coefficient on "entry gap under 1 s" in spec `lt1`, in seconds lost per micro-sector (about 1/20 of a lap).

Continue only if all of these hold, pooled AND in each era:

1. `beta(lt1)` has a 95% interval that excludes 0 and is positive.
2. P1 (below) passes.
3. P2 (below) passes.
4. P3 (below) passes.
5. The sign of `beta(lt1)` does not flip between 2018-2021 and 2022-2025.

Stop if P1 is about equal to `beta(lt1)`, or the sign flips between eras (design note section 7).

## Placebos

- **P1, the car behind.** Spec `p1` adds a dummy for a car BEHIND within 1 s on the same lap (a higher-lap car behind is lapping the driver, a blue-flag case, and is excluded from the dummy). Pass: the P1 coefficient has a 95% interval that includes 0 and an absolute size below one third of `beta(lt1)`. Rules out a general close-racing effect; does not rule out a confound specific to the car ahead.
- **P2, no level shift.** Spec `p2`, run on rows with the car ahead beyond 3 s only: the coefficient on "3-5 s" against ">5 s" must have an interval that includes 0. Also reported: the five-band coefficients must not rise as the gap grows (monotone shrinking).
- **P3, mechanism.** Loss concentrated in high-speed corners, tow gain on straights. Defined below.
- **Lead window.** Spec `lead`, the exit gap banded on `y_s`. Not a clean placebo (losing time opens the gap mechanically); it must be zero or below. Reported, not gated.

## P3: corner-class map and test (DA-02P)

**Map.** `int_microsector_corner_class`, one row per (race, micro-sector), built from corner geometry and apex speed only. It reads no gap and no time loss.

- Corner positions: `dim_corners` (FastF1 `stg_circuit_info` apexes, per session; a race with no corner table borrows the nearest season of the same event, as `dim_corners` records).
- Micro-sector position in metres: micro-sector m spans `[m, m + 1) * lap_length_m / 20`. `lap_length_m` is the race median of `distance_m / relative_distance` over on-track position samples from lap 2 (the lap length FastF1's lap fraction is computed against).
- Apex speed of a corner: on each green racing lap (lap 2 or later, `is_valid_lap`, lap track status '1', not an SC, VSC or red-flag lap, sample on track), the minimum position-channel speed within 50 m either side of the apex; then the median over laps. When a race has no green racing lap and `dim_corners` already borrows its geometry from another season, the corner takes that season's apex speed (today only 2021 Belgium, from 2022).
- Apex class [owner decision D1, ACCEPTED 2026-10-25: fixed cut-offs of 120 and 200 km/h for every track. The pooled distribution was checked: 200 km/h matches a dip that holds across seasons, while 120 km/h is a physics choice. Owner decision D5, RESOLVED 2026-10-25 (DD10): flat-out kinks get their own class, cut at 280 km/h taken from the corner analysis (205 of 869 high-corner race entries, 24%), CONFIRMED by the owner 2026-10-25]:
  - **low**, apex under 120 km/h. Hairpins and chicanes, where grip is mostly mechanical (tyres and suspension). Downforce grows with the square of speed, so at 120 km/h a car has about a third of the downforce it has at 200 km/h (0.6 squared is 0.36). Losing downforce in a wake costs least here.
  - **medium**, 120 to under 200 km/h. Mechanical and aero grip both matter.
  - **high**, 200 km/h and above and below 280 km/h. Grip is mostly aerodynamic: an F1 car makes roughly its own weight in downforce somewhere around 150-200 km/h, and more above that. This is where running in a wake should cost most, which is the P3 prediction.
  - **flat**, apex speed at or above 280 km/h, not a straight (280 km/h confirmed by the owner, 2026-10-25). Flat-out kinks, where the car barely lifts and a following car may get a tow. Mixing them into high would blend tow gain into the fast-corner test, so they are split out and reported separately.
- Micro-sector `corner_class`: **low**, **medium**, **high** or **flat** when every apex inside the micro-sector has that class; **mixed** when the apexes inside have more than one class (so a micro-sector holding both a high-speed and a flat apex is mixed and is outside the fast-corner test, owner confirmed 2026-10-25); **straight** when there is no apex inside, none in the 100 m before its start and none in the 150 m after its end; **link** when there is no apex inside but there is one inside those buffers. The 150 m after the end covers braking and turn-in for the next corner: braking from top speed for a slow corner takes roughly 100-130 m, and the apex is beyond the braking point. The 100 m before the start covers the exit of the previous corner, where the car is still traction-limited. So a straight is where the car is at or near full speed, which is where a tow acts. Positions wrap across the lap line.
- Coverage (dbt test `assert_microsector_corner_class_covers_panel`): every race in the panel has all 20 micro-sectors with a usable class. Registered exceptions [owner decision D2]: 2020 Tuscan (`2020_9`, Mugello) and 2020 Sakhir (`2020_16`, Bahrain outer loop). FastF1's corner table for both is empty in bronze and neither layout was raced in another season. They stay in every other spec and are left out of `p3` only (31,466 of 3,000,201 fit rows, 1.0%, all in 2018-2021).
- ACCEPTED (D1): the thresholds (120 and 200 km/h, fixed for every track), the buffers (100 m and 150 m) and the apex-speed definition are fixed by this amendment. RESOLVED (D5 / DD10): flat-out kinks have their own class, cut at 280 km/h (confirmed by the owner, 2026-10-25). They change only by a new amendment committed before a fit, never after seeing a coefficient.

**Spec `p3`.** Spec `lt1` with each of its four gap-band dummies interacted with `corner_class` (low, medium, high, flat, mixed, straight, link), plus class main effects. So `beta(lt1, c)` is the under-1 s effect in class c against >3 s in the same class. Registered model terms that differ from `lt1`: (i) driver-race by corner-class fixed effects, so a car that is quick on straights but slow in corners cannot pass as a wake effect; (ii) tyre age by corner class (`tyre_life x corner_class`) in place of the shared micro-sector index (`tyre_life x micro-sector`). The driver-lap fixed effect, `aheadResid` and clustering are as in `lt1`. Rows from the two exception races are dropped.

**P3 passes** if both of these hold, pooled AND in each era (2018-21 and 2022-25) [owner decision D3, the owner-approved rule of 2026-10-25, replacing the earlier wording, which the owner had not read]. In (a) and (b), `high` means apex 200 km/h and above and below 280 km/h; flat is not part of `high`:

- (a) The fast-corner loss, `beta(lt1, high)` (flat excluded), is positive with a 95% interval that excludes 0.
- (b) `beta(lt1, high) - beta(lt1, low)` is positive with a 95% interval that excludes 0. The fast corners lose more than the slow corners. This replaces "fast minus straight".

There is no third gate. The straight estimate `beta(lt1, straight)`, the difference `beta(lt1, high) - beta(lt1, straight)`, and the DRS-closed and location-based DRS results are REPORTED, not gated, and cannot pass or fail P3.

Also reported, not gated: `beta(lt1, flat)` and `beta(lt1, flat) - beta(lt1, straight)` (the flat class is excluded from the high-speed effect and cannot pass or fail P3), `beta(lt1, medium)`, `beta(lt1, mixed)`, `beta(lt1, link)`, and whether the order is high >= medium >= low (flat is not in this order). `p3` is also reported on the DRS-closed rows and on the location-based DRS rows (DRS section below). Those versions test the wake effect and the tow without DRS, because in the main panel the straights include DRS gains.

## DRS spec (DA-02P)

- Staging keeps FastF1 DRS code 8 as its own state: `off` (codes 0, 1), `eligible` (8: within 1 s at the detection line, may open in the next zone), `open` (10, 12, 14), `unknown` (any other code; under 0.04% of valid rows).
- Panel: `drs_state_entry` and `drs_state_exit` are the DRS state of the last position sample before the entry and exit boundaries. `drs_open` is TRUE when either is `open`, FALSE when both are `off` or `eligible`, NULL otherwise. The exit state is used as well as the entry state because DRS often opens partway through a micro-sector: entry only would keep the micro-sector where the flap opens.
- **Spec `drs_closed`** [owner decision D4]: spec `lt1` on the rows where `drs_open` is FALSE. Micro-sectors where DRS is open at entry or exit are dropped, and unknown or missing DRS state is dropped too (209,003 of 3,000,201 fit rows, 7.0%). Its quantity is `beta(lt1)` on those rows, pooled and in each era.
- Role: the DRS-closed (gap-based) result is reported as secondary next to `lt1`, not gated, and does not gate P3. A passing `drs_closed` cannot rescue a failed main result, and a sign flip against the primary is reported as a caveat. Dropping DRS-open rows selects on a state that the gap itself causes, and the DRS-closed rows under 1 s on straights are mostly straights without a DRS zone. So `drs_closed` bounds the DRS share of `beta(lt1)`. It is not an unconfounded estimate.
- **Spec `drs_location`** [owner decision D4, extended 2026-10-25]: spec `lt1` on the rows left after dropping any micro-sector where any car had DRS open in that race (DRS open at entry or exit for any car, any lap). The drop is fixed by the track, not by the gap, so it does not select on a state the gap causes. Its quantity is `beta(lt1)` on those rows, pooled and in each era. Reported only, and does not gate P3. Both DRS specs are secondary: neither gates P3, and neither can rescue a failed main result.
- `eligible` (code 8) is kept as its own state and carried in the panel. It is not used as a control in any spec, for the same reason as above.

## Forking paths

- Seconds is primary. Metres is not built (DD7). Micro-sector count 20 is primary; 10 is a sensitivity check. A passing sensitivity cannot rescue a failed primary result, and a failed one is reported as a caveat.
- The P3 thresholds (120 and 200 km/h, fixed for every track, D1 accepted), the straight buffers (100 m and 150 m) and the apex-speed definition are fixed above. The flat class and its 280 km/h cut are fixed above (D5 / DD10; 280 confirmed by the owner, 2026-10-25). No alternative cut is run or reported.
- Wording stays "adjusted traffic cost" until P1-P3 all pass (DD4). The wording decision is the owner's at the phase 2 gate, which confirms the owner's 2026-10-25 ruling of "adjusted traffic cost".

## Not ruled out by this design

Pair-local shocks race control did not flag (no marshal-sector map); deliberate tyre saving while following; selection into who follows whom; DRS (the main spec keeps DRS-open micro-sectors, so a DRS gain inside 1 s pulls `beta(lt1)` toward zero; `drs_closed` and `drs_location` bound this but selects on a state the gap causes); era-specific timestamp noise (0.053-0.061 s in 2018-21, 0.067-0.078 s in 2022-25, DA-01) which attenuates `beta` differently by era.

---8<--- END OF PROPOSED TEXT ---8<---
