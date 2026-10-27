# DA-03 pre-registration

**Status.** Written 2026-10-24 during DA-02. Amended 2026-10-25 by DA-02P (P3 corner-class map and pass rule, flat cut of 280 km/h confirmed, DRS specs including the location-based one) 2026-10-26 (lagged-gap check) and 2026-10-27 (P2 pass rule replaced by a precision limit), before any fit on the real panel. The estimator `transform/tasks/coefficients/fit_dirty_air_microsector.py` refuses to run unless it is given the SHA-256 of this file, this file is committed at HEAD unchanged, and the same hash is recorded in the build log. The order is: the owner commits this file on its own commit, then runs `python -m tasks.coefficients.fit_dirty_air_microsector --print-prereg-sha256`, records the hash in the build log (`prereg_sha256` on item DA-02P), and passes that hash to the fit. Any edit after the hash is recorded changes the hash and voids the run. Nothing below was chosen after seeing a coefficient. The only real-panel numbers looked at are the DA-02 descriptives (sample counts, validity shares, the raw loss-versus-gap curve, the lap-total identity), recorded in `_evidence/DA-02-2026-10-24/`, and the DA-02P row counts by corner class and DRS state. The corner-class thresholds were fixed before any loss-versus-gap number was looked at in DA-02P.

## Data (frozen at DA-02, extended by DA-02P)

- Panel: `int_microsector_proximity`, built from `int_microsector_crossings`, 20 micro-sectors per lap (DD8), seconds grain (DD7), 2018-2025, 171 races. Sensitivity (registered, cannot rescue a failed primary result): the same fit on a panel rebuilt with `microsector_n: 10`. The corner-class map is rebuilt with the same var, so the sensitivity panel gets its own map under the same thresholds.
- Rows used: `invalid_reason IS NULL`, `y_s` present, `ahead_y_s` present. That drops lap 1, pit-lane micro-sectors, off-track, boundaries interpolated across more than 1 s, any micro-sector where the circuit-wide track status was not all clear (or changed inside it), the two laps after an SC, VSC or red-flag lap, rows with no car ahead, and rows with a lapped car ahead within 3 s (DD5). Beyond 3 s a lapped car ahead is in the reference band.
- Known holes carried as exceptions (DD6): 2018 Australia and Bahrain have no telemetry; 2018 China and Germany have a partial track-status timeline; marshal-sector maps are not in bronze, so a local yellow cannot be placed and every yellow drops the whole circuit for its duration.
- DA-02P columns. `int_microsector_proximity` carries `drs_state_entry`, `drs_state_exit` and `drs_open` (DRS section below). They are carried only: no validity rule, band, `y_s` or field median reads them. No other pre-DA-02P column changes. `int_microsector_corner_class` maps each (race, micro-sector) to a corner class (P3 below).

## Model

`y_{d,l,m} = alpha_{d,l} + sum_k beta_k * 1[entry gap in band k] + gamma * aheadResid_{l,m} + delta * (tyre_life x micro-sector) + e`

- `alpha_{d,l}`: a driver-lap fixed effect. `y_s` is micro-sector time minus the field median for the same race, lap and micro-sector.
- Bands on the ENTRY gap only: <0.5, 0.5-1, 1-1.5, 1.5-2, 2-3 s, reference >3 s. The exit gap is an outcome and is never a regressor.
- `aheadResid` is the car ahead's own `y_s` in the same micro-sector.
- DRS state is never a regressor or control in any spec. Being within 1 s at the detection line is what opens DRS, so it sits on the path from the gap to the time.
- Standard errors clustered by race (CRV1); the 95% interval uses a t distribution with (races - 1) degrees of freedom.
- Specs run: `bands` (the five-band step function, descriptive), `lt1` (merged: <1, 1-1.5, 1.5-2, 2-3 s; the gate quantity), `p1`, `p2`, `p3`, `lead`, `drs_closed`, `drs_location`, `lag_gap`. Each on all years pooled, and separately for 2018-2021 and 2022-2025.

## Primary quantity and gate (design note section 6, phase 2)

`beta(lt1)`: the coefficient on "entry gap under 1 s" in spec `lt1`, in seconds lost per micro-sector (about 1/20 of a lap).

Continue only if all of these hold, pooled AND in each era:

1. `beta(lt1)` has a 95% interval that excludes 0 and is positive.
2. P1 (below) passes.
3. P2 (below) passes.
4. P3 (below) passes.
5. The sign of `beta(lt1)` does not flip between 2018-2021 and 2022-2025.
6. The lagged-gap check (below) passes.

Stop if P1 is about equal to `beta(lt1)`, or the sign flips between eras (design note section 7).

## Placebos

- **P1, the car behind.** Spec `p1` adds a dummy for a car BEHIND within 1 s on the same lap (a higher-lap car behind is lapping the driver, a blue-flag case, and is excluded from the dummy). Pass: the P1 coefficient has a 95% interval that includes 0 and an absolute size below one third of `beta(lt1)`. Rules out a general close-racing effect; does not rule out a confound specific to the car ahead.
- **P2, no level shift.** Spec `p2`, run on rows with the car ahead beyond 3 s only: the coefficient on "3-5 s" against ">5 s" must have a 95% interval no wider than 0.008 s, and an absolute size below one third of `beta(lt1)`. Both must hold. (This replaces "the interval includes 0": with this many rows a shift too small to matter can exclude 0, and a wide interval would include 0 by imprecision.) Also reported: the five-band coefficients must not rise as the gap grows (monotone shrinking).
- **P3, mechanism.** Loss concentrated in high-speed corners, tow gain on straights. Defined below.
- **Lagged gap.** Spec `lag_gap`, a check against timing error at the entry crossing. Defined below.
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

## Lagged-gap check (DA-02P, owner ruling 1, option (a))

- **Why.** `y_s` for micro-sector m is built from the driver's crossings of boundary k (the entry of m) and boundary k + 1. The entry gap is built from the driver's and the car ahead's crossings of boundary k. Both read the driver's crossing at k, so a timing error there moves the gap and the time together: a crossing recorded early shortens the gap and lengthens the micro-sector. That can push `beta(lt1)` up with no real effect.
- **Lagged gap.** The same driver's entry gap at boundary k - 1 (the entry of micro-sector m - 1; for m = 0, the last micro-sector of the previous lap). It is taken only when that row exists, is the boundary directly before k, and is itself a valid row (`invalid_reason IS NULL`, so the same rules on timing, pit lane, flags, car ahead and lapped cars apply); otherwise it is missing. It reads only crossings of boundary k - 1, so it shares no crossing with `y_s` (boundaries k and k + 1). It is the gap to whichever car was ahead at boundary k - 1, which may not be the car ahead at k. The estimator derives it from `int_microsector_proximity`; no panel column is added.
- **Spec `lag_gap`.** Spec `lt1` with its four bands (<1, 1-1.5, 1.5-2, 2-3 s, reference >3 s) on the lagged gap in place of the entry gap. The entry gap is not in the spec. Driver-lap fixed effect, `aheadResid` (the car ahead at k, in micro-sector m), tyre age by micro-sector and race clustering are as in `lt1`. Rows with no lagged gap are dropped from `lag_gap` only (every lap 2 micro-sector 0 among them, since lap 1 rows are invalid).
- **Passes** (gate 6) if `beta(lag lt1)`, the coefficient on "lagged gap under 1 s", is positive with a 95% interval that excludes 0, pooled AND in each era. The gap changes over one micro-sector, so `beta(lag lt1)` is expected to be smaller than `beta(lt1)`; its size is reported and not compared with `beta(lt1)`.
- **Role.** A check, not a new primary. `beta(lt1)` stays the primary quantity, P1's one-third rule uses `beta(lt1)`, and a passing `lag_gap` cannot rescue a failed primary result.

## Forking paths

- Seconds is primary. Metres is not built (DD7). Micro-sector count 20 is primary; 10 is a sensitivity check. A passing sensitivity cannot rescue a failed primary result, and a failed one is reported as a caveat.
- The P3 thresholds (120 and 200 km/h, fixed for every track, D1 accepted), the straight buffers (100 m and 150 m) and the apex-speed definition are fixed above. The flat class and its 280 km/h cut are fixed above (D5 / DD10; 280 confirmed by the owner, 2026-10-25). No alternative cut is run or reported.
- Wording stays "adjusted traffic cost" until P1-P3 all pass (DD4). The wording decision is the owner's at the phase 2 gate, which confirms the owner's 2026-10-25 ruling of "adjusted traffic cost".

## Not ruled out by this design

Pair-local shocks race control did not flag (no marshal-sector map); deliberate tyre saving while following; selection into who follows whom; DRS (being within 1 s at the detection line is what makes DRS available, so the main spec keeps the micro-sectors where it is open and never controls for it; a DRS gain inside 1 s pulls `beta(lt1)` down, toward zero or below; `drs_location` drops every micro-sector where any car had DRS open in the race and `drs_closed` drops the rows where it was open, so both show the size of that pull, but `drs_closed` selects on a state the gap causes, and neither is an unconfounded estimate); era-specific timestamp noise (0.053-0.061 s in 2018-21, 0.067-0.078 s in 2022-25, DA-01). Noise at crossings the gap and `y_s` do not share attenuates `beta`, differently by era. Error at the shared entry crossing can bias `beta(lt1)`, upward included; `lag_gap` is the registered check against that, and timing error at boundary k - 1 only attenuates `beta(lag lt1)`.

