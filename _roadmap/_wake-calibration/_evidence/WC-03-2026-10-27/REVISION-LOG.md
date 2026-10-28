# WC-03 pre-registration: revision log (2026-10-28)

Revision of `_roadmap/_wake-calibration/wi/WC-03-preregistration-DRAFT.md` after `PAPER-REVIEW.md`. Still DRAFT: not signed, not committed, not hashed. `build-log.json` and `BUILD-ORDER.md` not edited. No curve, loss, verdict or gate was computed on the pass table. `data/ci.duckdb` and `data/bronze` not written (one bronze laps file read to confirm the `race_id` format). `data/dev.duckdb` was only byte-copied to scratch.

## Changes

| # | Change | Review finding |
|---|---|---|
| 1 | Flat-now comparator added (θ_now × same-lap share, θ_now refitted on 2022-2024); W1 must beat both flat and flat-now by the 0.5 % margin | F1 |
| 2 | "Contest slightly favours the flat penalty" replaced by a three-way statement of which way it leans | F1 |
| 3 | 2026-10-21 same-lap scoping (0.473 vs 0.331; 0.881) declared as prior knowledge; flat-now tied to it | F1 |
| 4 | Yardstick rerun done (below) and recorded in §2e; G3 split into owner branches A/B | F2.1 |
| 5 | Panel wrapper reads a scratch copy only and writes to scratch only; `d1` itself not run | F2.3 |
| 6 | Unknown laps stay unknown (shipped `dirty_air_tax_s`, unfilled `dirty_air_share_lap`); panel's filled `d_lag1` used only in G3 | F2.2 |
| 7 | Trains: whole-stint-in-traffic invisibility stated; W2 on train laps; mixed stints reported; one third of stints have no clean comparison (0.32-0.36, 2022-2025) | F3 |
| 8 | No car ahead: named reason `no_car_ahead`, counted, charged 0 | F5b |
| 9 | Trim order fixed and non-circular (no-traffic baseline, once, then frozen) | F5c |
| 10 | Lap totals from existing `seg_start_t`/`seg_end_t` (time overlap); no new column; `seg_offset_m` sign corrected | F5a |
| 11 | Classes: racecraft > no_leader_time > held_up > dirty_air, complementary boundary at ref + 2 × spread; spread recomputed from donors; car ahead's row keyed by (`leader`, `leader_lap`, `corner_id`) | F5d, F5e |
| 12 | Join key (`season`, `race_id`, `driver`, `lap`) ↔ (`race_year`, `race_id`, `driver_id`, `lap_number`) with `lap_id` cross-check (new G6) | F5f |
| 13 | Verdict scope: 2022-2025 only; older cars own curve, never decides; 2018-2021 keep flat; "no verdict" for any short minimum (G5) | F4, F6 |
| 14 | P1: `|far| ≤ 0.25 × near`, near > 0, and interval of near − far above 0 | F7 |
| 15 | Pit-stop: reported figure (ratio with interval), 200-stop minimum, no pass/fail; two-table scorecard | F7, F9 |
| 16 | Bootstrap: cluster method stated, B = 1,000 fixed (no fallback), minimum 60 fit / 20 held-out races, no reruns after any printed result | F8 |
| 17 | Fourteen first-draft choices (C1-C14) and five new ones (N1-N5) marked proposed, pending owner | owner instruction |
| 18 | Smaller: bins [lower, upper); main curve = contest curve; 2026 pit check on 2026 curve; 2026 runs once; WC-04 items 1-2 superseded | F5g-i, F6, F10 |

## Yardstick rerun (read-only, scratch only)

**Scripts that produced 0.331:** `_roadmap/_fixes/_evidence/wi-12-2026-09-27/d1_build_panels_wi12.py` (`WI01_PANEL_SQL`, Gate 1) and `d2_fit_wi12.py` (section W, F2 = `feols(partial_residual_s ~ d_lag1 | stint_id + age_bin, vcov CRV1 race_id)`, W40 gate). Committed output `d2_output.txt`: F2 0.331347, n 138,679; panel 138,970; fingerprint 0.5033413666. Last recorded rerun in the build logs: after WI-02b, 2026-09-29. None found after the v15 (CO-04, 2026-10-15) or v16 (CO-09 + CO-15, 2026-10-24; CO-33 seal 2026-10-26) label changes.

**How it was run.** `data/dev.duckdb` (SHA-256 `7173444b0745130769863c123fb5c04c7e5edd8be7a1fb2dbf614637d3214f9f`) copied to `/private/tmp/claude-501/-Users-justin-github-off-the-pace/b032368a-69cb-47e7-b591-7234689fb01e/scratchpad/yardstick/db/dev.duckdb` (same SHA-256). Wrapper `/private/tmp/claude-501/-Users-justin-github-off-the-pace/b032368a-69cb-47e7-b591-7234689fb01e/scratchpad/yardstick/rerun_theta.py` imports d1's SQL, opens the copy `read_only=True`, fits F2 exactly as d2, writes only `rerun_theta_result.json` beside itself. `d1`/`d2` were not run (they read the warehouse path and write into committed evidence). `/Users/justin/github/off-the-pace/.venv/bin/python`, pyfixest as installed.

**Result: does not reproduce 0.331.**

| | 2026-09-27 | 2026-10-28 |
|---|---|---|
| Panel rows / shipped calibration n | 138,970 / 138,970 | 135,841 / 135,841 |
| Pooled-slope fingerprint | 0.5033413666 | 0.4777453471 (d1 Gate 1 FAIL) |
| F2 θ (n) | 0.331347 (138,679) | **0.304987** (135,675), SE 0.0184, 95 % CI 0.2686-0.3413 |
| W40 (rounds to 0.331) | PASS | FAIL |
| F2 with unknown laps left unknown | n/a | 0.305056 (135,663) |
| Panel laps with shipped tax NULL | n/a | 12; shipped lag = panel lag on all others |

The shipped tax still applies the declared 0.331 (shipped θ = declared). The warehouse panel moved; the declared value was not refitted. G3 as first written would have stopped the run, so the draft now asks the owner to pick branch A (label bump first, re-sign) or B (test the shipped 0.331; G3 checks the panel has not moved since 2026-10-28).

## Not fixed

- The covering note listing the "fourteen choices" is not in the repo; C1-C14 were reconstructed from the draft and may not match its numbering.
- G3 cannot be closed by wording: it needs the owner's branch choice (and, under A, a label change outside this item).
- F8's "15 of 24 races" extra W1 condition was not added: it would change the owner-approved win rule.
