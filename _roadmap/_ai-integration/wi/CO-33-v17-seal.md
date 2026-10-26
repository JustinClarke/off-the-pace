# CO-33 - Seal label version v16

**Status:** SPEC, PARKED by the owner 2026-10-25 until the dirty-air DA-02P wrap-up is committed. The earlier scratch rehearsal no longer counts (the tree has moved); re-run step 1 before step 3.

**Why this exists.** CO-30 (thin cells; panel SQL in ac9e798, test in 82796dc) and CO-31 (restart window 4; in 82796dc) are committed but CO-31 moves labels, so the v16 build, the isolation refit and the label-stability baseline still have to be done. The owner ruled to seal the transform label version (v16) now, without waiting for dirty air, because dirty air (path A) moves no labels.

**Steps.**
1. Rehearse on a scratch copy: car-FE refit and isolation refit into the scratch `fits/`, the CI fixture refresh, the full dev build with `field_restart_adjacent_laps = 4`.
2. Check: `assert_prior_season_labels_frozen` fails only on the expected v16 move, and the isolation panel has 127,476 rows (confirmed by the 2026-10-25 rehearsal at restart window 4 and the owner's ruling, "whatever is true will prevail"; the earlier 127,478 was the window-2 figure).
3. Owner approves the final write into `data/fits` and `data/dev.duckdb`.
4. Re-take `transform/seeds/label_stability_baseline.csv` for v16 (one snapshot), then `dbt build` with 0 errors (CO-31 definition of done).
5. Re-take the two byte-oracle baselines (W21, option c) after the final build. W6 also needs continue-on-error removed from Gate 1c (owner's call).
6. Orchestrator re-runs the CO-30, CO-31 and CO-33 definitions of done; only then LANDED, and W10 clears by hand.

**Owner decisions.** Approve step 3, and the final commit of the baseline files.

**Not in scope.** DA-05 path choice. ML retrain (parked on its own branch).

**Naming (owner, 2026-10-25).** v16 is the transform label version and v17 is the ML model. This item seals v16. The file name still says v17 for now. Open for the owner (D11): the CO-17 bump of 2026-10-24 was also called v16 in D8 and in the committed seed notes.
