# WI-07 — Guard repairs: safe tooling, blocking drift baselines, real test coverage

**Group:** 09 scoring instruments · **Depends on:** nothing · **Blocker:** none.

**Findings folded in:** F11 (Low-Med), F34 (Medium, process), **F53** (new, Low).

**Reverification:** CONFIRMED-AS-STATED on both, with one clarification (F11 is structural, not a
one-off incident) and one severity note (F34 is arguably understated — three of the seven named
tests are literal dead-code stubs, not near-misses).

---

## F11 — the audit's own tooling mutates a shipped artefact, and it's wired into CI/Makefile

`ml/src/features.py:705`, inside `_check()`: `load_features(..., persist_encoders=True)`
unconditionally. Confirmed by reading `main()` (`:734-747`): **no dry-run flag exists anywhere in
the CLI** — only `--check`, `--duckdb`, `--manifest`. Both `Makefile:195` and
`.github/workflows/ml-ci.yml:135` invoke `--check` directly.

**This is a structural risk, not a one-time incident from the audit's own run.** CI's blast radius is
limited only because GitHub-hosted runners are ephemeral and `ml-ci.yml`'s own header says the
workflow never commits — the mutation doesn't persist there. But any **local** invocation against
`data/dev.duckdb` (exactly what happened during the original audit) overwrites the real
`ml/models/encoders.json` with encoders derived from whatever the holdout resolver currently returns
(which, per `WI-03`/F4, may not match the vocabulary baked into the currently-shipped ONNX models).
It's a live landmine for any engineer running `--check` locally, every time.

## F34 — tests that cannot fail

All seven named tests read in full, independently, against their current SQL bodies:

- **Literal dead-code stubs** (`SELECT 1 WHERE FALSE`), counted toward the green 672-PASS total
  regardless: `assert_cliff_stints_have_falloff`, `assert_constructor_confidence_monotone`,
  `assert_sector_aggregates_to_lap` (this one's 25-line header derives the real identity it never
  actually runs, ending in a self-documented "Gate: PASSIVE / INFORMATION ONLY (Placeholder test)"
  comment).
- **Pass by construction:** `assert_aero_penalty_negative` checks `dirty_air_tax_s < 0`, but the
  column is built via `CLAMP(θ×share, 0, 5.0)` — structurally can never go negative.
  `assert_track_evolution_monotone` checks a slope that's built as `LEAST(OLS_slope, 0.0)` — forced
  ≤0 by construction.
- **Blind to their own named defect:** `assert_stint_boundaries_correct` (named for "laps assigned to
  wrong stint near pit stops") only checks that `age_in_stint` rises monotonically by rank — it never
  touches pit-stop laps or stint boundaries, and passes on all three F24 races.
  `assert_cliff_predictions_valid` (named for "seed failed to join") only flags exact `0.0`/`0.5` —
  it misses F7's real no-cell default range (0.050-0.060).

**Reverification note:** this is arguably understated at "Medium(process)." Three of the seven are
not edge cases the test almost catches — they are dead code that has been silently inflating the
suite's PASS count, indefinitely, with a comment admitting it.

## F53 (new) — no safe re-run path exists

Documented fully in `../reference/new-findings.md`. Two instances that block a clean fix for F11 and for
reproducing this audit's own reverification:

1. `verify_findings.py`'s `_db.py` resolves `REPO` one directory short of the real repo root when run
   from its tracked location in this checkout — the reports' own documented invocation
   (`.venv/bin/python _improvements/reference/.../verify_findings.py`) fails immediately.
2. `features.py`'s CLI has no `--persist-encoders`/dry-run flag to fix F11 with — one has to be
   built, not just toggled.

## Method

1. **F11.** Add a `--persist-encoders` flag to `features.py`'s CLI, default `False`; change `_check()`
   to pass it through instead of hardcoding `persist_encoders=True`. Update the Makefile and CI
   invocation only if they actually need persistence (audit whether they do — `ml-ci.yml`'s own
   header claims they don't).
2. **F34.** Delete the three literal stubs or actually implement them —
   `assert_sector_aggregates_to_lap`'s header already contains the correct tolerance-bounded math, so
   that one is a near-zero-effort real implementation. Fix `assert_aero_penalty_negative` and
   `assert_track_evolution_monotone` to check the pre-clamp expression, not the post-clamp column.
   Rewrite `assert_stint_boundaries_correct` to actually check stint boundaries against `stg_pits`
   (this becomes T19, replacing it — see `WI-05`). Rewrite `assert_cliff_predictions_valid` to flag
   the real no-cell default range, not just the literal 0/0.5.
3. **F53.** Fix `_db.py`'s `REPO` resolution (hardcode the absolute repo path, or walk up to the
   nearest `.git`). Add the CLI flag from step 1.
4. Re-snapshot both drift baselines (`data-profile-check`'s 2026-09-07 baseline, `lint-oracle-check`'s
   2026-09-11 baseline) on the current v14 build and make them blocking — both are currently red for
   expected reasons and gate nothing.

## Acceptance

- Running `python -m ml.src.features --check` locally does not mutate `ml/models/encoders.json`
  unless explicitly asked to.
- `verify_findings.py` runs from its documented invocation in this checkout without a path patch.
- No dbt test in the suite can pass regardless of the condition it's named to check — every test
  either can fail, or is deleted.
- The 672-PASS count (or whatever it becomes after F34's fixes) means what it says.
- Both drift-baseline gates are green against the current build and block future drift, not stale
  and silently gating nothing.

## Tests to add

T11 (F11, now buildable once F53's flag exists), T12 (audit coverage), T15 (baseline re-snapshot),
T26 (F34, no vacuous test bodies), T27 (wire `verify_findings.py` into CI, non-blocking).

## Definition of done

`verify_findings.py`'s F11 and F34 checks flip to CLEARED; the CLI has a real dry-run path; both
drift baselines are blocking and green; T26 is wired in and would fail against the pre-fix test
bodies (proving it actually checks something).
