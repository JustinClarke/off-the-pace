# DA-03 pre-registration (DRAFT until committed)

**Status.** Written 2026-10-24 during DA-02, before any fit on the real panel. The estimator `transform/tasks/coefficients/fit_dirty_air_microsector.py` refuses to run unless it is given the SHA-256 of this file, so the order is: the owner reads this, edits anything they want changed, commits it, then runs `python -m tasks.coefficients.fit_dirty_air_microsector --print-prereg-sha256` and passes that hash to the fit. Any edit after the hash is recorded changes the hash and voids the run. Nothing below was chosen after seeing a coefficient. The only real-panel numbers looked at are the DA-02 descriptives (sample counts, validity shares, the raw loss-versus-gap curve, the lap-total identity), recorded in `_evidence/DA-02-2026-10-24/`.

## Data (frozen at DA-02)

- Panel: `int_microsector_proximity`, built from `int_microsector_crossings`, 20 micro-sectors per lap (DD8), seconds grain (DD7), 2018-2025, 171 races. Sensitivity (registered, cannot rescue a failed primary result): the same fit on a panel rebuilt with `microsector_n: 10`.
- Rows used: `invalid_reason IS NULL`, `y_s` present, `ahead_y_s` present. That drops lap 1, pit-lane micro-sectors, off-track, boundaries interpolated across more than 1 s, any micro-sector where the circuit-wide track status was not all clear (or changed inside it), the two laps after an SC, VSC or red-flag lap, rows with no car ahead, and rows with a lapped car ahead within 3 s (DD5). Beyond 3 s a lapped car ahead is in the reference band.
- Known holes carried as exceptions (DD6): 2018 Australia and Bahrain have no telemetry; 2018 China and Germany have a partial track-status timeline; marshal-sector maps are not in bronze, so a local yellow cannot be placed and every yellow drops the whole circuit for its duration.

## Model

`y_{d,l,m} = alpha_{d,l} + sum_k beta_k * 1[entry gap in band k] + gamma * aheadResid_{l,m} + delta * (tyre_life x micro-sector) + e`

- `alpha_{d,l}`: a driver-lap fixed effect. `y_s` is micro-sector time minus the field median for the same race, lap and micro-sector.
- Bands on the ENTRY gap only: <0.5, 0.5-1, 1-1.5, 1.5-2, 2-3 s, reference >3 s. The exit gap is an outcome and is never a regressor.
- `aheadResid` is the car ahead's own `y_s` in the same micro-sector.
- Standard errors clustered by race (CRV1); the 95% interval uses a t distribution with (races - 1) degrees of freedom.
- Specs run: `bands` (the five-band step function, descriptive), `lt1` (merged: <1, 1-1.5, 1.5-2, 2-3 s; the gate quantity), `p1`, `p2`, `lead`. Each on all years pooled, and separately for 2018-2021 and 2022-2025.

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
- **P3, mechanism.** Loss concentrated in high-speed corners, tow gain on straights. NOT ESTIMATED in DA-02: it needs a micro-sector to corner-class map that the panel does not carry. Until that map exists P3 is owed, and the gate cannot be passed; the fit reports it as `OWED`. The map must be fixed (and registered by amendment before the fit that uses it) from `stg_circuit_info` corner positions, not from the loss curve.
- **Lead window.** Spec `lead`, the exit gap banded on `y_s`. Not a clean placebo (losing time opens the gap mechanically); it must be zero or below. Reported, not gated.

## Forking paths

- Seconds is primary. Metres is not built (DD7). Micro-sector count 20 is primary; 10 is a sensitivity check. A passing sensitivity cannot rescue a failed primary result, and a failed one is reported as a caveat.
- Wording stays "adjusted traffic cost" until P1-P3 all pass (DD4). The wording decision is the owner's at the phase 2 gate.

## Not ruled out by this design

Pair-local shocks race control did not flag (no marshal-sector map); deliberate tyre saving while following; selection into who follows whom; DRS (the panel carries no DRS state, so a DRS gain inside 1 s pulls `beta(lt1)` toward zero; adding `drs_active` at entry to the panel is an OWED amendment, to be registered before the fit that uses it); era-specific timestamp noise (0.053-0.061 s in 2018-21, 0.067-0.078 s in 2022-25, DA-01) which attenuates `beta` differently by era.
