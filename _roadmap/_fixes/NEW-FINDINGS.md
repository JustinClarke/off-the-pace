# New findings — F50–F54

Found during reverification of F1–F49 (2026-09-24), not already in any of the three audit rounds.
Numbered to continue the audit's own convention without colliding with F1–F49. Written in the
audit's own format so they can be folded into the reports' own tables if desired.

---

## F50 — The Synthetic Teammate page has its own independent sign inversion

- **Severity:** High (fan). Distinct from F16 (display-only) and F28 (a different page's sign
  mismatch) — this inverts the **primary verdict** of nearly every row on its own page.
- **file:line:** `transform/models/intermediate/int_synthetic_teammate.sql:131-133` defines
  `driver_skill_proxy_s = teammate_pace_adjusted_s − ego_wc_lap_time_s`, i.e. **positive = ego
  faster** (matches the file's own header comment at line 5, and matches the convention
  `fct_driver_skill_features.sql:14` uses — the same ground truth F28 relies on to prove *that*
  finding). But the app reads it backwards everywhere:
  - `app/src/features/synthetic-teammate/methodology.tsx:14` — "Negative means the driver is
    faster."
  - `app/src/features/synthetic-teammate/page.tsx:36` — badge text "Skill proxy < 0: the driver is
    faster."
  - `app/src/features/synthetic-teammate/page.tsx:69` — cell coloring: negative → green.
  - `app/src/features/synthetic-teammate/transform.ts:21` — `verdict: 'ahead'` fires when
    `avg_skill_proxy_s < -0.1`.
- **Observed behaviour:** of 166 driver-seasons meeting the page's own eligibility filter, 65 are
  labeled "ahead" and 60 "behind" by the inverted rule — essentially the entire non-"even"
  population is showing the wrong verdict and the wrong color.
- **Why it is wrong:** the app-layer sign convention is the exact opposite of the warehouse
  column's own documented and structurally-consistent meaning. This is the same defect class as F28
  (page reads a signed column backwards) but on a different page, with a different root cause (no
  shared code path with F28's bug), and it flips a *displayed verdict*, not just a ranking.
- **Verdict:** Definitely wrong.
- **Earliest point:** app layer (`transform.ts`, `page.tsx`, `methodology.tsx`); the warehouse
  column is correct.
- **Isolated or systematic:** systematic — every row on the page.
- **ML impact:** none (this proxy is fan-surface only, same as F28's family).
- **Recommended fix:** flip the three sites' comparisons (`< -0.1` → `> 0.1` for "ahead", swap the
  color rule, rewrite the methodology sentence). Add a page-level regression test asserting the
  sign convention against a fixture row with a known ego-faster case.
- **Test:** new — `app/src/features/synthetic-teammate/*.test.ts` asserting verdict sign against
  `fct_driver_skill_features`'s own documented convention.
- **How I could be wrong:** if the intended UX convention really is "negative shown as ahead" for
  narrative reasons independent of the warehouse's sign, this would be a documentation choice, not a
  bug. Nothing in the methodology text supports that reading, though — it explicitly claims to
  describe the underlying pace comparison, so the current text is either wrong about its own sign or
  wrong about the underlying data.

---

## F51 — `event_driven` (SC/VSC/red-flag/restart) laps are never excluded from training eligibility, and `correction_weight` is computed but never applied

- **Severity:** Medium (ML). Sits in exactly the files already being touched for the WI-01 label
  bump.
- **file:line:**
  - `transform/models/marts/fct_cliff_prediction_features.sql` — `is_training_eligible` filters
    `age_in_stint > 3 AND anomaly_class NOT IN ('mistake', 'conditions')`. It does **not** exclude
    `'event_driven'` (`transform/models/intermediate/int_lap_anomaly_flags.sql:220-233` — SC / VSC /
    red-flag / restart / local-yellow laps).
  - `transform/models/intermediate/int_event_corrections.sql` computes `correction_weight`, which
    `int_lap_residual_decomposed.sql` carries through as metadata (the model's own header says it is
    "carried but NOT applied here"). A repo-wide grep of `ml/src/*.py` for `correction_weight` and
    `event_flag_any` returns **zero hits** — it is never used as a downweight or sample weight
    anywhere in training.
  - `int_field_pace_curve.sql`'s own eligibility CTE (the base F1 depends on) also has no
    `correction_weight` filter, so SC/VSC-affected laps can enter the field-pace baseline itself,
    not only the label side.
- **Observed behaviour:** live query confirms **9,016 of the currently-eligible training rows
  (~6.4%)** are `event_driven`.
- **Why it is wrong:** a column purpose-built to downweight anomalous-event laps (§4.6 of the
  charter) exists, is computed correctly (F13 ruled out the feared seasonal bias), and is then
  discarded before it reaches the model. This is adjacent to F9 (both are about
  `is_training_eligible`) but distinct: F9 is a seed-circularity problem on the *kept* population;
  this is a full category of contaminated laps with **no exclusion mechanism at all**.
- **Verdict:** Definitely wrong (mechanism); ML magnitude unmeasured.
- **Earliest point:** `fct_cliff_prediction_features.sql` (eligibility) and `int_field_pace_curve.sql`
  (baseline).
- **Isolated or systematic:** systematic, ~6.4% of the eligible population plus contamination of the
  field baseline every SC/VSC race touches.
- **ML impact:** four of five families (trio, cliff); stint-life uses a different eligibility path.
- **Recommended fix:** either exclude `anomaly_class = 'event_driven'` from `is_training_eligible`
  (mirroring `'mistake'`/`'conditions'`), or apply `correction_weight` as an XGBoost sample weight
  rather than a hard filter — the latter is more consistent with the column's own design intent and
  avoids further shrinking an already-filtered eligible population. Either way, add the same
  exclusion/weighting to `int_field_pace_curve`'s eligibility CTE, since it currently lets these laps
  into the F1-affected baseline.
- **Test:** new — `assert_event_driven_laps_excluded_or_weighted.sql`, checking that no
  `event_driven` lap is both `is_training_eligible` and carries `correction_weight = 1.0`.
- **How I could be wrong:** it's possible event-driven laps were deliberately left in because
  degradation under SC/VSC conditions is itself informative (different physics, not necessarily
  wrong to learn from) — in which case the fix is "apply the weight," not "exclude," and that
  decision needs a ruling the same way F9's does.

---

## F52 — F6's fuel lap-count bug and F32's uncapped fuel formula compound on the same neutralized races

- **Severity:** Low-Medium.
- **file:line:** `transform/models/intermediate/int_lap_fuel_state.sql` — the `race_lap_counts` CTE
  derives `race_lap_count = MAX(lap_number)` from **valid laps only** (the same `laps` CTE that
  excludes lap 1 and any SC/VSC/red-flagged lap, per F1's mechanism). That count then feeds directly
  into F32's `initial_fuel_kg = race_lap_count × fuel_consumption_rate_kg_per_lap` formula, which
  (per F32) has no regulatory cap of any kind.
- **Why it matters together:** a heavily-neutralized race gets **both** defects at once — F6's wrong
  (short) lap count and F32's missing cap — on the same handful of races. Fixing them independently
  (F6's "count from all laps, not just valid ones" and F32's "cap at regulatory max / scheduled
  laps") is fine individually, but a single joint test would catch a race where one fix papers over
  the other's symptom without the underlying number being right.
- **Verdict:** Definitely wrong (mechanism); not previously stated as a joint effect in the audit.
- **Recommended fix:** fix both per their own WI-05 specs (scheduled-laps column on `dim_events`
  handles both), and add one test that checks the *combination* — implied fuel burn per race
  should be plausible against the scheduled distance, not just "some cap."
- **Test:** fold into T6/T24 (already proposed) as a single combined assertion rather than two
  independent ones.
- **How I could be wrong:** if T6 and T24 both land against the same new `scheduled_laps` column,
  the compounding automatically resolves and this note is moot — it's a sequencing/test-design note,
  not a distinct code defect.

---

## F53 — No safe, read-only re-run path exists for either the audit's verification tooling or the ML features CLI

- **Severity:** Low (process).
- **Two instances:**
  1. `_improvements/reference/transform_forensic_audit_artefacts/round2/_db.py`'s `REPO = ...
     parents[4]` resolves to `_roadmap/`, not the actual repo root
     (`/Users/justin/github/off-the-pace`), when run from its real location in this checkout. Running
     `verify_findings.py` as the reports themselves instruct
     (`.venv/bin/python _improvements/reference/.../verify_findings.py`) fails immediately with
     `FileNotFoundError`. It only works if invoked from wherever the original audit's sandbox had its
     checkout root one directory shallower than here. This was patched in a scratch copy to
     reverify (see `README.md`), not in the tracked file.
  2. `ml/src/features.py`'s CLI (confirmed by direct read of `main()`, lines ~734-747) defines only
     `--check`, `--duckdb`, `--manifest` — **no dry-run or read-only flag exists at all.** F11's
     recommended fix ("make `--check` read-only") therefore can't be "use the existing safe mode";
     one has to be built first.
- **Recommended fix:**
  1. Fix `_db.py`'s `REPO` computation (either hardcode the absolute repo path, since the artefact
     is only ever meant to run against this one repo, or compute it more robustly, e.g. by walking
     up to the nearest `.git`).
  2. Add a `--persist-encoders` flag to `features.py`'s CLI, defaulting to `False`, and change `_check()`
     to pass it through instead of hardcoding `persist_encoders=True` — this is the concrete
     prerequisite for F11's T11.
- **Test:** T11 (already proposed for F11) now has a stated dependency: it can't be written until
  the flag in fix (2) exists.
- **How I could be wrong:** (1) is unambiguous — it's a path bug, not a design choice. (2) is a
  process gap, not a defect in output; someone could reasonably choose to fix it a different way
  (e.g. a separate `check_only.py` entry point instead of a flag).

---

## F54 — `dim_constructors.pu_mapping` has no completeness test, so `unknown_pu` will keep growing silently

- **Severity:** Low (process); precursor to F17 recurring.
- **file:line:** `transform/models/reference/dim_constructors.sql`'s hardcoded 16-row `pu_mapping`
  VALUES list (the same one F17 already shows is missing `Alfa Romeo Racing`, `Kick Sauber`, and
  `Racing Bulls` — 3 of 19 constructors, ~16%, all post-rename entities).
- **Observed behaviour:** no schema test or dbt test anywhere asserts a bound on
  `count(*) filter (where pu_family = 'unknown_pu')`, and no test fires when a new constructor name
  (a team rename, which F1 does roughly every 1-2 seasons) lands without a corresponding
  `pu_mapping` row.
- **Why it matters:** F17 is currently ruled "harmless — consumed by nothing that computes," but
  that ruling is about *today's* consumers, not a structural guarantee. The next team rename (a
  plausible near-term one given F1's history) grows `unknown_pu` further with zero signal.
- **Recommended fix:** add a warn-level dbt test asserting `unknown_pu` share does not increase
  build-over-build, or (better, per F17's own recommended ruling) key `pu_family` on the constructor
  *entity* using the same alias pattern `macros/circuit_id_from_name.sql` already uses for circuits,
  which would make the mapping rename-proof rather than needing to catch renames after the fact.
- **Test:** new — `assert_pu_family_coverage.sql`, warn-level, checking `unknown_pu` count against a
  stored baseline.
- **How I could be wrong:** if `pu_family` genuinely stays unconsumed forever (F17's finding), this
  is pure defense-in-depth with no realized cost. It's cheap enough to add regardless.
