# CO-32 — W11 option C: micro-sector dirty-air pricing, its registered fit, then the v17 label version

**Status:** SPEC (build log, item CO-32). DA-02 panel and checks built and tested on scratch copies; nothing fitted on real data. Build log: `status/build-log.json`.

**Group:** 1 data settled · **Depends on:** `CO-30`, `CO-31` · **Blockers:**
- **Fit step (DA-03): blocked until the owner commits `_roadmap/_dirty-air/wi/DA-03-preregistration.md`.** It is a DRAFT. The estimator refuses to run without the SHA-256 of the committed file. No fit on real data before that.
- P3 (mechanism placebo) is OWED: no micro-sector to corner-class map exists, so the DA-03 gate cannot pass until the map is built and registered by amendment.
- DRS state is not in the panel (owed amendment to the pre-registration).
- The label step (DA-05) waits on DD2 (path A or B) in the dirty-air log.

Raised 2026-10-24 from watch W11 (owner ruled option C wanted, 2026-10-23; D8 2026-10-24: v17 work).

**Sources:** `_roadmap/_dirty-air/` (README, `wi/DA-design-note.md`, `wi/DA-02-tables.md` to `wi/DA-05-label-and-app.md`, `wi/DA-03-preregistration.md`, `status/build-log.json`), `transform/models/intermediate/int_microsector_crossings.sql`, `transform/models/intermediate/int_microsector_proximity.sql`, `transform/tasks/coefficients/fit_dirty_air_microsector.py`, `transform/dbt_project.yml` (`microsector_*` vars).

---

## Plan: follow `_roadmap/_dirty-air`, do not duplicate it

The phases, gates and stop rules are in the dirty-air track and its own build log. This item only tracks that work from this build order, and ships its result in v17 with CO-30 and CO-31.

| Phase | Dirty-air item | State on 2026-10-24 |
| :-- | :-- | :-- |
| 1 Tables | DA-02 | Panel and checks built on scratch; evidence in `_roadmap/_dirty-air/_evidence/DA-02-2026-10-24/`. Gate (loss rises as the gap shrinks) met on the raw curve. |
| 2 Identification | DA-03 | Estimator written, 6 synthetic-panel tests pass. **Fit not run.** Blocked on the pre-registration commit (above). |
| 3 Validation | DA-04 | Not started. |
| 4 Label and app | DA-05 | Not started; waits on DD2. |

DA-02 numbers (scratch copy, 2026-10-24): `int_microsector_crossings` and `int_microsector_proximity` 3,743,701 rows each (20 per lap, 171 races); 3,039,930 valid (81.3% of all, 95.1-98.3% of timing-valid rows per season; Gate A >= 90% holds). Raw loss vs field median by entry gap: <0.5 s +0.068, 0.5-1 +0.018, 1-1.5 +0.010, 1.5-2 +0.006, 2-3 +0.003, >3 -0.007 s per micro-sector. Lap-total identity median abs 0.026-0.032 s.

## Steps left, in order

1. Owner reviews and commits `DA-03-preregistration.md` (optionally with the P3 map and DRS amendments).
2. DA-03: run `fit_dirty_air_microsector` with the committed file's SHA-256; report the gate pooled and by era; sensitivity at `microsector_n: 10`.
3. DA-04: held-out season, honesty tests, out-of-sample gain.
4. DA-05: owner rules DD2; path B moves the label and joins the v17 baseline re-take with CO-31.
5. Add the three new models to `transform/models/intermediate/README.md` (only in `schema.yml` today).

## Tests it relies on

- `assert_microsector_car_ahead_is_previous_crossing`, `assert_microsector_excludes_pit_lane`, `assert_microsector_lap_total_identity`, `assert_microsector_validity_rules`, `assert_microsector_agrees_with_blue_flags`, and the schema tests on the two micro-sector models.
- `transform/tasks/coefficients/tests/test_fit_dirty_air_microsector.py` (synthetic panel: planted effects recovered, P1 fails when a following confound is planted, gate fails with no effect) and `test_no_vacuous_singular_tests.py`.
- The fixture-scale CI build: the coverage guards in `assert_microsector_lap_total_identity` and `assert_microsector_excludes_pit_lane` must hold or skip cleanly at 3 races.

## Definition of done

DA-03 to DA-05 closed in `_roadmap/_dirty-air/status/build-log.json` on their own gates; the label decision recorded; the v17 label version (with CO-30 and CO-31) built on a rebuilt dev with 0 errors after the baseline re-take. W11 clears when this item is in the build order (it is, from 2026-10-24); the owner records that. Do not commit; the owner commits.

Run on `fable-5.1` for the DA-03 fit and its inference; `opus-5` for the rest.
