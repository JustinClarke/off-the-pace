# WC-03 / WC-04 run package: what has to happen before the owner's yes can be acted on

Prepared 2026-10-28 by the Opus lead session (delegated; DRAFT). **Nothing here has been run on real data.** The commands are exact; the outputs are what the code writes, checked on synthetic data only (`transform/tasks/wake_calibration/tests/`).

## A. Owner steps, in order (the run refuses until 1-4 are done)

1. **Decide draft amendment A5** (`wi/WC-03-amendment-A5-fit-race-list-DRAFT.md`). Recommended: option (a), "union". Without A5 the CLI refuses: two built 2022-2024 races (2022 Japan, 2024 São Paulo) have no fit pass, so A4 ruling 4b would stop the run after G3 had been written.
2. **Commit A5 alone.** Then set `A5_FIT_RACE_LIST = "union"` (or `"built"`) in `transform/tasks/wake_calibration/run_wc03.py`, in its own commit.
3. **Record the digests** on WC-03 in `status/build-log.json` as `amendments: [{doc, sha256, commit}, …]`. Hash each file as committed. Recomputed 2026-10-28 from HEAD, for the owner to check, **not recorded by the agent**:

   | doc | commit | SHA-256 (committed text) |
   |---|---|---|
   | wi/WC-03-amendment-A1-circuit-bootstrap.md | 5aee6b2 | `19a39c42a12e2ed46ba8e2afb8721f5daece2636e7e7a2e9ad2b0c6eefaaf99b` |
   | wi/WC-03-amendment-A2-no-reference-class.md | e310510 | `6464e28a419b3304e4d46552f996a529484df2a446257f14c6d3ae0921ce4082` |
   | wi/WC-03-amendment-A3-last-lap-exclusion.md | 83134a3 | `f3e10f14abacf7718a9c1467e1ea8d2438167a69b983d3fbf36b455ddea693e3` |
   | wi/WC-03-amendment-A4-rulings.md | c872547 | `992413314afb0cf34f3e25c7de9056d459928d9ffb016ac218d0518a67f8ddb1` |
   | wi/WC-03-amendment-A5-fit-race-list-DRAFT.md | (after step 2) | `shasum -a 256` on the committed file |

   The pre-registration is already recorded (`518c3348…`, 839e0f4) and still matches.
4. **Commit the code** (see the session's file list), so that PROVENANCE can name a commit. G1 runs the test suite from the working tree.
5. **Commission the fable-5.1 review** (hard gate before G3). Scope: `reml_fit` and `_reml_parts`, the A1 bootstrap (`resample_plan`, `plan_draw_stats`), the lap counting (`lap_weights`, `lap_design`, `scored_set`), `contest.py`, and **the new code**: `pitstop.py`, `sensitivity.py`, `report.py`, the A5 path in `contest.run_era` and `run_wc03.era_lists`, and `estimator.reference_spread(half_window)`. Ask for worked checks and synthetic cases, not a read-through.
6. **Give an explicit yes to the run.**

## B. Commands (from the repository root unless stated)

```bash
# 0. Before: the warehouse file's timestamp (it must not change during the run)
stat -f '%Sm %z' data/dev.duckdb              # 2026-10-28 reading: Oct 26 12:12:10 2026, 1905799168 bytes

# 1. Scratch copy of the warehouse, in its own folder, named dev.duckdb (§2d; BUILD-ORDER rules 5 and 8)
RUN=_roadmap/_wake-calibration/_artifacts/WC-03-run
mkdir -p $RUN/warehouse $RUN/pass-table
cp data/dev.duckdb $RUN/warehouse/dev.duckdb

# 2. Rebuild the pass table with the committed builder (§2a), and compare with pass "d"
cd transform
../.venv/bin/python -m tasks.wake_calibration.build_pass_table --out ../$RUN/pass-table --workers 6
cd ..
(cd $RUN/pass-table && shasum -a 256 pass_table_*.parquet races.csv) | diff - <(grep -v layout_checks _roadmap/_wake-calibration/_artifacts/WC-01-pass-table-d/SHA256SUMS) && echo "pass table = pass d"
(cd $RUN/pass-table && shasum -a 256 * > SHA256SUMS)

# 3. Dry check (reads pass-table structure only; no warehouse, no bronze, no gate)
cd transform
../.venv/bin/python -m tasks.wake_calibration.run_wc03 \
    --scratch-db ../$RUN/warehouse/dev.duckdb --pass-table-dir ../$RUN/pass-table \
    --evidence-dir ../_roadmap/_wake-calibration/_evidence/WC-04-<date> --owner-yes --check-only
#    expected: "checks passed; no warehouse or bronze data read (pass-table structure only, for the A5 pre-flight)"

# 4. The one run (§0). Not to be repeated once any result line exists.
../.venv/bin/python -m tasks.wake_calibration.run_wc03 \
    --scratch-db ../$RUN/warehouse/dev.duckdb --pass-table-dir ../$RUN/pass-table \
    --evidence-dir ../_roadmap/_wake-calibration/_evidence/WC-04-<date> --owner-yes
#    prints the scorecard's first line; exit 0 = a verdict line written, 2 = stopped (G3, G2 or the A4 4b guard)
```

The duration on real data has not been measured. Expect G1 (the test suite, about 11 min) plus five full chains of 1,000 draws each: main, older, ±2, ±6, and without Las Vegas.

## C. Expected outputs in `_evidence/WC-04-<date>/`

- `PROVENANCE.txt`: RUN START, RESULT WRITING STARTED, G3 (4 checks with values), G2, G6 counts, VERDICT WRITTEN, one `TABLE 2 <step>: done | not computed (…)` line per report step, RUN COMPLETED.
- `SCORECARD.md`:
  - line 1 is the verdict (§9);
  - line 3 is "This contest checks changes in traffic within a stint, not the level of a whole stint spent in a train.";
  - then, only if W1 holds but not in a sensitivity run, a line saying so (§12b);
  - Table 1 (G1-G7, W1-W3, the contest point table);
  - Table 2: counts, coverage and contest per team, mixed stints, the no-reference half, gains, under attack, the pit-stop figure (2022-2025, 2025, 2018-2021), the older cars, the three sensitivity runs, the 0.305 diagnostic, and the WC-02 minimum-speed pointer.
- CSVs:
  - curves: `main_curve.csv`, `class_curve_dirty_air.csv`, `class_curve_held_up.csv`, `older_curve.csv`, `older_class_curve_dirty_air.csv`;
  - contest: `contest.csv`, `older_contest.csv`, `theta_now.csv`, `lap_drops.csv`;
  - counts: `counts_no_car_ahead.csv`, `counts_no_reference.csv`, `counts_class_bin_season_race.csv`;
  - teams: `coverage_per_team.csv`, `contest_per_team.csv`;
  - pit stops: `pit_events_{main,2025,older}.csv`, `pit_drops_{main,2025,older}.csv`.
- Not yet produced by the CLI: the §15 chart (loss against gap per class, main and older curve), and the split of the evidence into `WC-03-<date>/` (curve) and `WC-04-<date>/` (verdict). Both are presentation work after the run; neither touches a number.

## D. Checks before anyone reads the scorecard

1. `stat -f '%Sm %z' data/dev.duckdb` is unchanged from step 0, and `git status --porcelain data/` is empty.
2. PROVENANCE has exactly one RUN START with RESULT WRITING STARTED after it (restarts are allowed only before that line, §0), and shows `n_draws 1000, seed 20261027, synthetic False`.
3. The G1 line reports the pytest summary with 0 failed.
4. G3.1 = `7173444b…3214f9f`; G3.4 = 1,214 files, `aed1c27d…1690b4`; G3.2 = rows 135,841 and shipped n 135,841; G3.3 = 0.4777453471 (±1e-9).
5. G2 is "all identical"; the rebuilt pass table equals pass "d" (step 2 diff); G6 `lap_id_mismatches` is 0.
6. Every `TABLE 2 … not computed` line is read and its reason understood. Such a line never changes the verdict, but it is a gap in Table 2.
7. Then the owner reads `SCORECARD.md` first, before anything else uses the result (§15). No figure goes to the app, the label or the replay view until the owner has ruled.
