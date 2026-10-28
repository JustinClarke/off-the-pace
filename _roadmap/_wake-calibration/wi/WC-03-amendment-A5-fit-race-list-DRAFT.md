# WC-03 pre-registration, amendment A5 (DRAFT): the fit-race list for the bootstrap plan and θ_now

**Status: DRAFT, proposed. Opus-delegated: written by the Opus lead session on 2026-10-28 under the owner's delegation; not decided, not the owner's signature, not committed, not hashed.** It amends `wi/WC-03-preregistration-DRAFT.md` (SHA-256 `518c3348…`) and would replace amendment A4 ruling 4b if adopted. The registered text and A1-A4 are not edited. **The owner must choose an option before the real run.** Under the current code (A4 4b as written) the run is expected to stop with an error after G3 has been written, which §0 counts as the one completed run: no verdict, and no rerun.

**When it was made, stated plainly.** 2026-10-28, before any fit, score, curve, class count or real-data gate. It rests only on counts made outcome-blind (decision record L2, L7; `_evidence/WC-03-prep-2026-10-28/`): which built races have at least one fit-eligible pass before the loss trim. No loss, time or gate value was read.

---

## The problem

- §8c and G5 speak of **68** fit races (2022-2024), of which "at least 60 must contribute fit passes". §3 gives the older-car fit as **55** races (2018-2020). So the registered text expects some fit races to contribute no fit pass, and still to be resampled.
- The code builds the bootstrap plan from the races that **contribute** fit passes (`contest.run_era`: `sorted(fit["race_key"].unique())`). A4 ruling 4b then requires θ_now's panel races to equal that list exactly, and otherwise stops the run with an error.
- Counts on the registered pass table (pass "d"), before the ±2 s loss trim (the trim can only remove more):

| Era | Built races in the fit seasons | Contributing | Built, no fit pass | In bronze laps but not built |
|---|---|---|---|---|
| main 2022-2024 | 68 | 66 | `2022_18` Japan, `2024_21` São Paulo: every pass excluded, mostly `wet` | none |
| older 2018-2020 | 55 | 53 | `2019_11` Germany, `2020_14` Turkey | 2018 Australia and Bahrain (no telemetry), 2020 Sakhir and Tuscany (no corner positions) |

- The yardstick panel (`WI01_PANEL_SQL`) drops laps flagged for rainfall (`rainfall_flag`) but not intermediate or wet-tyre laps without it. So it may hold laps of the four wet races. It very likely holds laps of the four races that have no pass table, because they have bronze laps. Whether it does is not known without building the panel, which is G3 check 2 and is not run here.
- **Consequence.** Main era: if the panel has any lap of 2022 Japan or 2024 São Paulo, the run stops in `theta_now_draws`. Older era: it almost certainly stops. In both cases this happens after G3 and G2 have been written to PROVENANCE.txt.

## Options

- **(a) Union list (recommended).** The fit-race list of an era is every race of its fit seasons that is in the pass table **or** in the yardstick panel. Each race's circuit comes from the race calendar (`build_pass_table.race_calendar`, the §6 circuit key), not from the fit passes. The A1 plan resamples circuits, then races, over this list. A drawn race with no fit pass adds nothing to the curve. A drawn race with no panel lap adds nothing to θ_now. θ_now is fitted on **all** fit-season panel laps, exactly as §2d says. The curve is fitted on all fit passes, exactly as §6 says. "The same drawn fit races" (§2d, §8c, A1) holds by construction. G5 still counts contributing races (66 ≥ 60). Main era: if the panel has no extra race, the list is the 68 races §8c names.
- **(b) Built list.** The fit-race list is the built pass-table races only (68 and 55, the counts §3 and §8c state). θ_now uses only panel laps of those races, and laps of other races are counted and left out. This departs from §2d for the older era (four races' laps leave θ_now). In the main era it departs only if the panel holds a race the pass table lacks, which no count suggests.
- **(c) Keep A4 4b as written.** No code change. The run refuses or stops whenever the lists differ, so the registered run is likely to end with no verdict.

**Why (a).** It is the only option that changes no registered fit set: §2d's θ_now rows and §6's curve rows are both exactly as registered. It matches the 68 that §8c names. Its only effect is that a race with nothing to contribute on one side can still be drawn. That is how §8c already treats a race "drawn twice": as frequency, with no new data.

**Effect on the curve intervals (stated, not hidden).** Under (a), a circuit's race count includes its non-contributing race, so a draw can pick that race more than once and give that circuit copy fewer passes. That makes the curve intervals slightly wider than under the 66-race plan. The direction is conservative for W1 and P1(c). The size is not computed.

## Exact new text (option (a))

**A4 ruling 4b, replace with:**

> **4b. The fit-race list (amendment A5).** An era's fit-race list is every race of its fit seasons that has a pass-table row or a yardstick-panel row. Each race's circuit is its §6 circuit key from the race calendar. The A1 plan is drawn over this list. θ_now is refitted in each draw on that draw's race multiplicities over all panel laps of the fit seasons (§2d). The curve is refitted on the same draw's fit passes (§6). A drawn race with no fit pass contributes no pass; a drawn race with no panel lap contributes no θ_now row. A race with a fit pass or a panel lap that is not on the list is an error, and the run refuses **before G3 is written** (see "Order" below). G5 is unchanged and counts the races that contribute fit passes.

**Order (amendment A5).** Before any warehouse read and before G3: build the fit-race lists from the pass table and the race calendar. After the panel is built (G3 checks 2-3), check that every fit-season panel race is on the list. The list is a union, so this can fail only if the calendar lacks a race. If it fails, the run records "no verdict: fit-race list incomplete", which is a setup failure under §9.

## What does not change

No threshold, margin, bin, trim, minimum, B, seed, season split, verdict rule, fit set or scored set changes. A1's draw order is unchanged; only the list it draws over grows. A2 and A3 are untouched.

## Code (written behind a switch, off by default)

`run_wc03.A5_FIT_RACE_LIST` is `None` (A4 4b as written) until the owner decides. Set it to `"union"` (option (a)) or `"built"` (option (b)). Once it is set, the CLI also requires this file (`run_wc03.A5_DOC`) to be committed, unchanged and recorded with its SHA-256 on WC-03, exactly as for A1-A4. While it is `None`, the CLI refuses before reading the warehouse whenever the pass table shows a fit-season race with no fit-eligible pass. That makes the A4 4b failure a refusal, not a spent run. Tests: `tests/test_run_wc03.py` and `tests/test_contest.py`, `test_a5_*`.

## After the decision

1. The owner records the option chosen here (or rules otherwise), commits this file alone, and records its SHA-256 and commit on WC-03 in `status/build-log.json` beside A1-A4.
2. The owner sets `A5_FIT_RACE_LIST` in `run_wc03.py` (and updates `A5_DOC` if the file is renamed on commit), in a separate commit.
3. Nothing is fitted, scored or gated on real data before both steps.
