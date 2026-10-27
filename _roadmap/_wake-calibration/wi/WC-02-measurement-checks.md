# WC-02 - Phase 1: measurement checks

**Status: not started, not registered.** Depends on WC-01. Design: [`WC-design-note.md`](WC-design-note.md).

**Goal.** Show the measurements are good enough before any curve is fitted.

**Inputs.** The WC-01 pass table; bronze lap timing (S1, S2 and finish-line crossings); `reference/jolpica/pit_stops` and the lap files for pit laps.

**Checks.**
1. **Timing agreement, per race.** The derived time gap against the timing feed at S1, S2 and the finish line. Flag a race if the median absolute error is over 0.1 s.
2. **Car ahead pits.** Locate the **1,124** events where the car ahead pits while the follower is within 1.5 s and stays out (83 in 2018 up to 192 in 2024). Confirm each has the follower's segment deltas 2 laps before and 2 laps after. This item only builds and counts the event set; the contrast itself is a validation step (WC-04) and the modelled-tier check (WC-05).
3. **Minimum-speed agreement.** Minimum-speed and segment-time deltas rank passes the same way, per corner class.

**Done when.** Each check has a per-race or per-class result in `_evidence/WC-02-<date>/`, flagged races are listed, and the owner has seen which races drop out. No loss curve is fitted here.

**Risks.**
- Gap timing noise (DA-01 measured 0.05-0.08 s median absolute error) attenuates estimates and flips order under 0.25 s; averaging over the approach window reduces it but it does not vanish.
- The car-ahead-pits events are rare and only 2 laps either side; a pre-trend before the stop would mean baseline drift.
