# Finding verdicts — reverification of F1–F49, plus F50–F54

A static record of what the reverification concluded about each finding. It does **not** say
whether a fix has been done: execution state lives only in
[`../status/build-log.json`](../status/build-log.json) (run `python3 _roadmap/_fixes/status/board.py`).
The "Fix file" column names the doc in [`../wi/`](../wi/) that carries the fix.

Reverified 2026-09-24 against the same `data/dev.duckdb` build the audit used (v14, fingerprint
`87e1d013…`), by five independent read-only passes that re-read cited source directly rather than
trusting the audit's own probes. `verify_findings.py` (patched copy) also confirms **51/51**
mechanical checks PRESENT live — see [`../README.md`](../README.md).

**Verdict legend:** CONFIRMED = matches as stated. ARGUABLE = mechanism holds, some part of the
characterization (severity, cost framing, or fix) is debatable — see the linked WI file for detail.
UNDERSTATED = the audit's own severity tag is lower than the evidence supports. None came back
OVERBLOWN, INVALID, or STALE-OR-FIXED.

| ID | Title | Reverification | Severity: orig → call | Fix file |
| :-- | :-- | :-- | :-- | :-- |
| F1 | Label fabricated (`pace_delta_s` COALESCE to 0) | CONFIRMED | Critical → Critical | WI-01 |
| F2 | Compound seed fitted on the scored race | ARGUABLE (stint-life cost 5–10× larger than headlined) | High → High | WI-02 |
| F3 | Browser can't score v14 (manifest contract) | CONFIRMED | High → High | WI-04 |
| F4 | Holdout resolver can never resolve | CONFIRMED | High(process) → High, top priority | WI-03 |
| F5 | θ_air pools every season | CONFIRMED | Medium → Medium | WI-01 |
| F6 | Fuel counts from realised last valid lap | CONFIRMED | Medium → Medium | WI-05 |
| F7 | Missing 2025 seed cells fabricate cliff features | CONFIRMED | Medium → Medium | WI-02 |
| F8 | 2018 Italian GP silently dropped | CONFIRMED (no Fix: in original) | Medium → Medium | WI-05 |
| F9 | Eligibility depends on the in-race seed + label term | ARGUABLE (no Fix: in original; selects on a proxy of y) | Medium-Low → Medium | WI-02 |
| F10 | Qualifying feature reads race-day data | CONFIRMED | Low-Medium → Low-Medium | WI-08 |
| F11 | Audit CLI mutates shipped artefact; drift gates red | CONFIRMED (structural, not one-off — wired into Makefile + CI) | Low-Med → Low-Med | WI-07 |
| F12 | 2018 fabricated free air | CONFIRMED (mechanism; magnitude not rerun) | Low → Low | WI-09 |
| F13 | `race_id` loaded as INTEGER | CONFIRMED | Low → Low | WI-09 |
| F14 | 3 DSQs read as classified | CONFIRMED | Low → Low | WI-09 |
| F15 | Counterfactual "Actual Pts" ≠ official | CONFIRMED | (unranked) → **Medium(fan)** | WI-11 |
| F16 | `ANY_VALUE` picks arbitrary constructor/teammate | CONFIRMED | Low → Low | WI-11 |
| F17 | `pu_family`/`driver_number` wrong, unread | CONFIRMED (flagged as slow rot — unknown_pu already 16%) | Low → Low, watch | WI-09 |
| F18 | 2020_1 lap numbering offset (bronze) | CONFIRMED | Low → Low | WI-09 |
| F19 | `session_type` declared, absent | CONFIRMED (yml asserts a safeguard that was never built — worse than silence) | Low → Low | WI-09 |
| F20 | Doc drift (7 instances) | CONFIRMED | Low → Low (systemic in aggregate) | WI-09 |
| F21 | Offline parquet fits stale since 12a-1 | CONFIRMED | Low-Med → Medium | WI-05 |
| F22 | Rubber/ambient subtracted twice | CONFIRMED (hand-rederived) | High → High | WI-01 |
| F23 | θ_air calibrated on fabricated laps; tax under-applied | CONFIRMED | High → High | WI-01 |
| F24 | Stint numbering ignores pit stops (bronze) | CONFIRMED | Medium → Medium | WI-05 |
| F25 | 2018 stint-1 lap-1 unassigned (bronze) | CONFIRMED | Medium → Medium | WI-05 |
| F26 | Rain flag contradicts tyres run (bronze) | CONFIRMED (fix ARGUABLE — see WI-05) | Medium → Medium | WI-05 |
| F27 | Wet-Race Specialist uses 0 rain laps | CONFIRMED | Medium(fan) → **higher, near-null-result** | WI-11 |
| F28 | Quali-vs-Race mixes sign conventions | CONFIRMED | Med-High(fan) → Med-High (near-noise some seasons) | WI-14 |
| F29 | Blind-Test compares wrong horizon | CONFIRMED | Medium(fan) → **Medium-High(fan), most consequential** | WI-11 |
| F30 | Tyre-Cliff KM validation is circular | CONFIRMED | Med-Low(fan) → Med-Low | WI-11 |
| F31 | Pit-strategy loses SC/VSC/red stops | CONFIRMED | Medium → Medium | WI-13 |
| F32 | Starting fuel exceeds FIA max | CONFIRMED | (unranked) → Low-Med, self-limiting | WI-05 |
| F33 | 2018 quali `is_accurate` gate drops 26% | CONFIRMED | (unranked) → Medium | WI-05 |
| F34 | 7 dbt tests cannot fail | CONFIRMED | Medium(process) → **understated, 3 are dead-code stubs** | WI-07 |
| F35 | Circuit×constructor interaction double-counts a level | CONFIRMED (no Fix:/no "how wrong" in original; cancels from ML label — bundled for change-mgmt, not correctness) | Low → Low | WI-01 |
| F36 | Waterfall "observed delta" has a phantom 3rd term | CONFIRMED (bug is in the SQL header comment itself) | Low → Low | WI-11 |
| F37 | Home page: fake circuit count, fake model count | CONFIRMED, **worse than described** (5/5 false against model_card.json's own field) | (unranked) → **Medium(fan)** | WI-11 |
| F38 | Field base carries −(field compound cost) | CONFIRMED (hand-rederived) | High → High, largest single label shift by magnitude | WI-01 |
| F39 | NULL tyre age → 10s wear cap (DuckDB LEAST) | CONFIRMED (GREATEST also skips NULL — tighter than stated) | Low-Med → Low-Med | WI-02 |
| F40 | Equal-car rating compares P20 vs teammate median | CONFIRMED | Medium(fan) → Medium | WI-14 |
| F41 | Seed fitter: silent defaults + fuel-contaminated gradient | CONFIRMED | Med-Low → Med-Low | WI-02 |
| F42 | Compound grip/temperature unit errors | CONFIRMED | Low → Low | WI-01 |
| F43 | Pit-lane car counted as "car ahead" | CONFIRMED | Low-Med → Low-Med | WI-15 |
| F44 | Circuit Affinity heatmap all-green | CONFIRMED | Medium(fan) → **High(fan) for this page specifically** | WI-14 |
| F45 | Era offset reverses the gap it removes | CONFIRMED (magnitude not rerun) | Low-Med(fan) → Low-Med | WI-14 |
| F46 | Hidden Performance: false identity + wrong rank key | CONFIRMED, split severity: (a) text Low, (b) rank key Medium | Low(fan) → mixed | WI-14 |
| F47 | Push proxy reads fuel burn as pushing | CONFIRMED (also touches ML contract, not fan-only) | Low-Med → Low-Med | WI-15 |
| F48 | DRS-train coding non-monotone in gap | CONFIRMED | Low-Med → Low-Med | WI-01 / WI-15 |
| F49 | surface/bulk ratio capped ≤0.5 by construction | CONFIRMED (also ML contract feature #19, not fan-only) | Low(fan) → Low, broader reach | WI-15 |
| **F50** | *New:* Synthetic Teammate page sign inversion | — | **High(fan)** | WI-14 |
| **F51** | *New:* `event_driven` laps not excluded; `correction_weight` never applied | — | Medium (ML) | WI-01 |
| **F52** | *New:* F6+F32 fuel bugs compound on the same neutralized races | — | Low-Medium | WI-05 |
| **F53** | *New:* `verify_findings.py`/`features.py` have no safe re-run path | — | Low (process) | WI-07 |
| **F54** | *New:* `dim_constructors.pu_mapping` has no completeness test | — | Low (process) | WI-09 |

**51 of 49+5 = 54 findings checked** (F9 and F15 are manual-only, not on `verify_findings.py`'s
board, matching the original reports).
