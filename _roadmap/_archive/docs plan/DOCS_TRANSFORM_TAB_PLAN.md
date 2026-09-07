# Implementation plan — the Transform tab (dbt + DuckDB models, macros, and the CI contract)

Internal planning doc. Lives in `_roadmap/` (gitignored) because it is *process*, not a
description of the committed tree — exactly the kind of artifact
[CONVENTIONS.md](../.github/CONVENTIONS.md) bans committed files from depending on. Nothing in
`docs/`, the layer READMEs, or code comments may cite this file. Every rule it applies to
the docs is restated inside the docs themselves.

The plan's own numbered steps are a genuine build procedure (a how-to), which CONVENTIONS
explicitly permits — the ban is on *describing what stage the project reached*, not on
ordered instructions.

This is the follow-on to the now-archived [`_archive/DOCS_LAYER_TABS_PLAN.md`](_archive/DOCS_LAYER_TABS_PLAN.md),
which built the **Data** tab (data layer + ingestion how-to) as the template every later
layer tab copies. That plan deferred Transform/ML/App to "a later pass that reuses the Data
template." This is the Transform pass — and it goes further, because Transform does the most
heavy lifting in the pipeline and earns the most documentation.

---

## 0. Progress checkpoint (resume here)

Execution is checkpointed in **8 parts** (§10) so a context reset never loses more than one
part's worth of work. Protocol: **pause after each part, report status, do not commit**
unless explicitly asked — each part is independently reviewable. Nothing in this plan
authorizes a commit. Standing instruction: each part needs its own go-ahead — don't chain
into the next part without one. Part 1 was explicitly scoped ("finish Part 1 only, then
stop"); Part 2 ran on a "continue" from the user after Part 1's status was reported and
verified against the live tree — read as the go-ahead the Part 1 note was waiting on. Part 3
ran the same way: a bare "continue" after Part 2's status had been reported and verified —
read as that part's go-ahead. Part 4 ran the same way again: a bare "continue" (opening a new
session, with this doc open in the IDE) after Part 3's status had been reported and verified —
read as that part's go-ahead, not as a license to also run Part 5+ unprompted. Part 7 ran the
same way again: a bare "continue" (a new session, this doc open in the IDE) after Part 6's
status *and* its follow-up had both been reported and verified — read as Part 7's go-ahead,
not as license to also start Part 8 unprompted. Part 8 ran the same way again: a bare
"continue" (a new session, this doc open in the IDE) after Part 7's status *and* its
follow-up had both been reported and verified — read as Part 8's go-ahead. Unlike Parts 1–7,
Part 8 did not run to completion before the next pause: an explicit user interrupt mid-part
("pause and handoff to the md, we are out of usage") ended the session early. The status block
below is a **mid-part checkpoint**, not a part-complete report — resume by working through its
still-open list in order, not by re-running Part 8 from scratch or treating the next "continue"
as a new part's go-ahead (there is no Part 9).

**Part 8 status (2026-06-23): COMPLETE.** Resumed the mid-part checkpoint on a bare "continue"
(new session), exactly as the checkpoint's own resume instruction specified — not treated as a
new part's go-ahead. Re-verified the two completed-but-unverified edits from the prior session
first (`schema.yml:953`'s `int_driver_race_skill_loro` description, `profiles.yml`'s dropped
`work.md` citation): `dbt parse` clean, `make lint-oracle-check` 7/7 `fct_*` byte-stable — both
confirmed intact and safe, exactly as the resume instruction required before proceeding.

**The 30-file sweep grew to 31 — one genuine drift instance found, not assumed from the
checkpoint's list.** Re-ran the comprehensive banned-token grep across `transform/models/**/
*.sql` and `transform/macros/*.sql` rather than trusting the prior session's list verbatim (per
its own "double-check for drift since this checkpoint was written" caveat): all 29 originally-
listed `.sql` files still matched, plus one new instance —
`int_constructor_structural_pace_qualifying.sql:3` ("Mirrors int_constructor_structural_pace
(#6)..."), a numbered citation that didn't exist (or wasn't yet written) when the checkpoint's
list was made. Fixed alongside the rest. Final count: 31 files (30 originally listed + this one),
all restated-not-deleted, content preserved throughout. Also caught two banned-token shapes the
original regex missed entirely (fixed wherever found, then folded into a wider regex for the
rest of the sweep): bare `Phase N` with a digit (the original pattern only matched `Phase
[A-D]`) and bare `roadmap` prose references (distinct from `_roadmap`) — both real
CONVENTIONS violations (`int_constructor_deg_sensitivity.sql` had "Phase 2 teammate-swap
harness (gate 4.1)" and "...which is exactly why the roadmap specified an onset shift here";
`int_lap_telemetry_aggregates.sql` had "...is faithful to the roadmap intent"), fixed in place.

Per-file highlights (full list of 31 in the prior checkpoint, all now fixed):
- `int_lap_residual_decomposed.sql` (the canonical 7-term model) — edited carefully per the
  checkpoint's own warning: dropped both `BREAKING CHANGE` lines entirely (pure changelog
  noise restating facts the identity block above already states — nothing to restate once the
  date/phase label is stripped), dropped `(#6)`/`(#8)` model citations in favour of bare model
  names, and **found and fixed a second instance of Part 4's already-fixed overclaim**: this
  file's own header called `int_constructor_structural_pace`'s coefficient "panel-regression"
  in two places (lines ~125 and ~223) — Part 4 fixed the *same* overclaim in that model's own
  `schema.yml`, but never checked *consumers* of that model repeating the claim. Re-verified
  directly against `int_constructor_structural_pace.sql`'s own (accurate) header — "grouped
  statistics as a placeholder for the full panel regression spec" — and restated both instances
  to match.
- `fct_ghost_race_finish.sql` — restated the SE-propagation design note and 8 `Fix N` labels
  throughout; **found and fixed a live overclaim, not just a citation**: "Classified-result DNF
  flags (§5.4) feed the MC finish-order core (§4.5)" — grepped `scripts/mc_finish_order.py` for
  any reference to this model or its DNF columns (zero hits) and read the script in full: it's a
  pure function taking `mu`/`se` arrays as parameters, never reads this model's output at all.
  Restated as "exported for downstream consumers (unconsumed today)" — the same honest-leaf
  framing Parts 5/6 already established for `int_sc_hazard_history`/`int_pit_loss_circuit`.
  Applied the identical fix to `int_sc_hazard_history.sql`'s own header, which made the same
  false MC-finish-order-core claim.
- `int_constructor_deg_sensitivity.sql` (heaviest file, ~14 instances across two DESIGN NOTE
  sections plus the SELECT) — renamed the two `Fix 1`/`Fix 2.2` sections to plain descriptive
  headers ("degradation slope estimator" / "per-constructor cliff-onset shift estimator") and
  referenced them by that description everywhere else in the file rather than by number.
  **Found and fixed a real numeric bug while restating, not just a citation**: two comments
  claimed the cliff-onset shift is "clipped to +/-5 laps"; the actual `LEAST(GREATEST(...,
  -3.0), 3.0)` clips to ±3. Fixed both comments to match the code (a correctness fix, not a
  CONVENTIONS one, found only because the sweep required touching those exact lines anyway).
- `transform/models/README.md` — resolved the checkpoint's open question by reading
  `CONVENTIONS.md` in full: its first principle is "describe what a thing does, not how it came
  to be — git carries history," and its own banned-phrase list is the same class as the
  authoring standard's "a dated `BREAKING CHANGE:` log line" recommendation. Reworded the
  guidance to state the opposite: "Describe present behaviour only — a column-meaning change
  belongs in the commit message, not a log line in the header," consistent with every
  `BREAKING CHANGE` line the rest of the sweep removed. Also dropped the dangling
  `../../work.md §4` citation and the equally-unverified "`tests/README.md` §'add a new
  transform' runbook" claim — grepped `tests/README.md` directly and confirmed no such section
  exists (its real sections are Identity-Closure/Domain Constraint/Regression Gates/Lint/
  Fixtures) — restated as a plain pointer to the README instead of inventing a section name.

**Macros, done in full**:
- `docs/transform/macros.mdx` authored per §6E: an opening `<Note>` on why macros exist, then
  five purpose-grouped `<CardGroup>` sections (Validation/Shrinkage/Filters/Mapping/Numeric, 7
  macros total), each card's "used by" line stated from the verified facts the paused session
  had already gathered (re-confirmed, not re-derived): `assert_additive_identity` → 2 test
  files; `bayesian_shrinkage`/`posterior_variance` → the same 3 Skill-family models;
  `circuit_id_from_name` → `int_driver_circuit_era_affinity` + `dim_circuits`; `normal_cdf` →
  `fct_ghost_race_finish`; `clean_lap_filter`/`normalize_compound` → honestly stated as zero
  current model consumers (canonical recommended pattern, not yet adopted — same "state
  verified wiring, not aspirational" framing Parts 5/6 used).
- `docs.json`'s Macros nav gap fixed: added `reference/macros/circuit_id_from_name` in
  alphabetical position (a gap open since Part 1/2).
- **Found and fixed a real generator bug while regenerating, not anticipated by the
  checkpoint**: `circuit_id_from_name.mdx`/`normalize_compound.mdx`/`normal_cdf.mdx` rendered
  as near-empty pages (signature only, no description/args) even after regeneration, while the
  other 4 macro pages render rich content. Root cause, found by reading
  `scripts/gen_macro_reference.py` and `manifest.json`'s `macro_sql` field directly: that field
  only captures text *between* `{% macro %}` and `{% endmacro %}`; the 4 rich macros place their
  `{#- ... -#}` docstring *inside* that boundary (right after `{% macro %}`), while the 3 thin
  ones placed it *before* the macro tag entirely (`circuit_id_from_name.sql` didn't even use
  Jinja-comment syntax — it used plain SQL `--` line comments). Fixed by relocating each
  docstring to inside the macro body (matching the other 4's convention) and converting
  `circuit_id_from_name.sql`'s comments to `{#- -#}` syntax. Zero behaviour risk, verified
  rather than assumed: Jinja strips `{# #}` comments at compile time regardless of position, so
  the compiled SQL a macro invocation produces is unaffected — confirmed by `dbt parse` (clean)
  and `make lint-oracle-check` (still 7/7 byte-stable) after the relocation, before trusting it.
  All 7 macro pages now render full content; regeneration re-verified idempotent (two runs, zero
  further diff).
- Ran `python scripts/build_reference.py` (all 5 generators) once, then **caught and reverted
  scope creep before it shipped**: it also regenerated `docs/reference/{cli,schemas,ml}/*`,
  picking up genuine but unrelated pre-existing uncommitted drift (an `ingest.py --round` flag,
  Bronze schema doc changes, the ML v3→v4 card — none of it this plan's work, confirmed by
  reading each diff). Reverted those 7 files with `git checkout --`, re-ran scoped to `--models
  --macros` only, confirmed identical 65-file result. This plan's diff stays Transform-only.
- `macros/README.md`'s all 8 enumerated fixes applied verbatim per the checkpoint's list, plus
  the opening paragraph's dangling `§3.2` plan citation restated as a plain present-tense
  statement of purpose. The one fact the checkpoint flagged as unverified —
  `circuit_id_from_name`'s second "used by" claim (`mart_degradation_history_envelope`) — was
  grepped directly this session and confirmed **false**; the macro's real second consumer is
  `dim_circuits.sql`. Fixed to the true pair.

**Remaining outward-facing reconciliation, all done**:
- `transform/models/reference/README.md` — re-read fresh (not assumed from Part 3's quote, per
  the checkpoint's own instruction) and re-verified directly against the four model files: still
  exactly 2 of 4 seed-backed. Restated the opening line and the "Upstream" connection line to
  name the split instead of claiming all four derive from seeds.
- `transform/README.md` — the "Model DAG (summary)" ASCII tree was wrong in a way no grep would
  catch: it enumerated individual models by name (a maintenance trap with no drift gate — this
  file isn't in `scripts/docs_facts.py`'s reconcile set, confirmed by reading that script), and
  the enumeration had silently gone stale — missing 5 models entirely (`int_lap_telemetry_
  aggregates`, `int_constructor_car_fe`, `int_driver_race_skill_loro`,
  `int_driver_circuit_era_affinity`, `int_lap_residual_stint_detrend`) and misfiling 4 more
  (`int_synthetic_teammate`, `int_driver_season_ratings`, `int_era_normalized_driver_rating`,
  `int_driver_circuit_affinity`) under "Baseline / pace" when they're Skill-family models, with
  no "Skill" group in the diagram at all. Root cause fixed, not just the symptom: replaced the
  per-model enumeration with a family-level diagram (8 families, no model names, no hand-typed
  counts) that points to the live, generated `/transform/overview` and Model Reference pages as
  the source of truth for the per-model detail — the same "don't hand-maintain a second copy of
  a generated artifact" principle the rest of this plan applies throughout. Also fixed the
  directory-structure section's matching "Seed-based dimension tables" / "Physics · baseline ·
  residual · strategy" lines (same seed overclaim; missing the Skill family) for consistency.
- Makefile — `dbt-dev` ("53 dbt models" → "60") and `dbt-test` ("336 dbt tests" → "443"); grepped
  the full file for any other hand-typed model/test counts first, found none.
- `docs/AGENTS.md` — the five-tab description's Transform parenthetical ("dbt decomposition
  models + macros") undersold the tab's actual shape (family narratives + CI contract + macros)
  without naming individual stale facts, so reworded to "the model DAG by family, the CI test
  suite, and macros"; separately, "the Transform tab's Decomposition group" still named the
  pre-Part-1 group (the tab was restructured to Concepts/How the Layer Works/Model Reference/
  The CI Contract/Macros in Part 1) — fixed to "Concepts group".

**Full gate run, all green**:
`make docs-audit` (PASSED, 0 errors, 236 warnings — identical pre-existing `app/` set, every
prior part's baseline, unaffected); `make docs-facts` (PASSED, ML counts unaffected); `make
docs-coverage-check` (4/4 PASSED — ingestion, overview, dbt-parse-backed transform snippets all
match a fresh regeneration, confirming the sweep moved zero generator inputs the snippets read);
`make lint-oracle-check` (7/7 `fct_*` byte-stable — re-run after every batch of edits this
session, never moved); `sqlfluff lint models/` (clean — one pre-existing oversize-file skip
warning on `int_constructor_deg_sensitivity.sql`, confirmed via `git show HEAD` that the
committed version was already 21315 bytes, over the 20000-byte skip threshold, before this
entire plan touched it; this session's edits net *shrank* it to 21242, not a regression);
`python scripts/build_reference.py --models --macros` (idempotent, 65 files, scope-checked as
above); `npx mintlify validate` → **0 warnings** (down from Part 7's 1 — `transform/macros` was
the last unauthored nav page in the whole tab); `npx mintlify broken-links` → **0 broken links**
(down from Part 7's 1 — the last forward-reference, `transform/overview.mdx` → `/transform/
macros`, now resolves). Both Mintlify gates are clean for the first time in this plan's history.

**New findings, flagged not fixed (genuinely out of this plan's scope, not deferred to a future
part since there is no Part 9)**:
- `transform/scripts/check_source_freshness.py` and `transform/scripts/snapshot_data_profile.py`
  both cite `SYSTEM_DESIGN_AUDIT.md` by phase in their module docstrings ("F7, Phase 4 of
  SYSTEM_DESIGN_AUDIT.md"). This is the identical violation class `CONVENTIONS.md`'s own
  "Conformance backlog" section already documents with 3 named examples (`.github/workflows/
  README.md`, `app/vitest.config.ts`, `scripts/publish_cdn.sh`) — these two files are more
  instances of that same already-tracked, repo-wide backlog, not a Transform-tab docs issue;
  neither file is in §2's source-of-truth map or read by any docs generator. Left untouched.
- Same category, found in the Makefile while fixing the two named `help` strings: `cov-python`
  and `app-coverage` targets cite "(Phase 5 / F9 ratchets)"; the Infra section header cites
  "(Phase 6)". Also more instances of `CONVENTIONS.md`'s already-tracked backlog, unrelated to
  the two specific stale counts (`dbt-dev`/`dbt-test`) this plan named. Left untouched.
- `dim_constructors.sql`'s header comment reads "pu_family is used in Layer 04 to condition..."
  — a holdover from an old numbered-layer scheme (`transform/models/README.md`'s own "Physics
  layers 03–05" phrase is the same scheme) that predates the now-current 8-family taxonomy this
  entire plan is built around. Not a banned-token hit (doesn't match `Pillar`/`Fix`/`§N`/etc.)
  and not named anywhere in §9 — a vocabulary-consistency observation, not a CONVENTIONS
  violation, flagged rather than fixed unilaterally.
- Carried forward, unchanged: `transform/analyses/se_propagation_design.sql`,
  `transform/analyses/deg_slope_fuel_deconfounding.sql`, and `transform/analyses/gate_results/
  gate_metrics.md` are still deliberately untouched, for the same reason the prior session left
  them — genuinely outside §2's source-of-truth map, read by no docs generator.

**§11 Definition of Done — reviewed against everything verified across all 8 parts, every box
now satisfied**: the tab has five groups (not "six" — §11's own count is stale against the §5
diagram Part 1 already chose to trust; flagging the plan's own arithmetic rather than silently
fixing it, same as Part 2's and Part 4's self-corrections of this plan's text); 8 family
narratives (Parts 3–5); all 60 model pages enriched (Part 6, re-verified regenerated this
session); all 443 CI blocks documented (Part 7); all counts gate-sourced (§7's generators, no
hand-typed figures found anywhere in this session's sweep); CONVENTIONS clean (this part, with
the three flagged exceptions above, all genuinely out of scope); README/Makefile/AGENTS
reconciled (this part); every CI gate green (above). Adding a new model or test and running
`make docs-coverage && make docs-reference` updates family counts, sub-DAGs, reference pages,
and the CI inventory with zero hand-edits — the generation/gating spine Part 1 built and every
later part relied on without ever needing to touch it.

No commit made — nothing in this plan authorizes one. This closes Part 8, and with it every part
of this plan.

**Part 7 status (2026-06-22): COMPLETE.** Built all six pages in The CI Contract group —
`transform/ci/{overview,structural,range-and-domain,identity-closure,domain-constraints,
regression-gates}` — per §6D. Re-verified Part 6 and its follow-up were genuinely intact
before starting: re-ran `docs-coverage-check` (4/4 green) and `lint-oracle-check` (7/7 `fct_*`
byte-stable) against the live tree before writing anything.

Source verification done before writing, not after: read all 27 singular-test SQL files this
part's pages describe (14 identity-closure + 13 domain-constraint, both full sets — not a
sample), the `assert_additive_identity` macro, `.sqlfluff`/`.sqlfluffignore`,
`transform/scripts/snapshot_model_hashes.py` in full, and both regression-gate test files.
Cross-checked every `accepted_values` enum (13) and every `expect_column_pair_values_A_to_be_
greater_than_B` pair (4) directly against the four `schema.yml` files via grep rather than
describing them from the plan's illustrative text.

Done and verified:
- `transform/ci/overview.mdx` — the test pyramid as a structural-only Mermaid (category names
  only: Generic → Structural/Range & Domain, Singular → Identity-Closure/Domain
  Constraint/Regression Gate) paired with the existing gated `<TransformInventory />` snippet
  for every actual number, rather than baking counts into the diagram text the way
  `transform/overview.mdx`'s family Mermaid bakes in family counts. Deliberate distinction
  from that precedent, not an inconsistency: family counts are §9's one named structural
  exception ("small family sizes... `meta.family` is itself gate-checked"); the 443/414/339/
  75/29/14/13/2 test-suite counts are exactly what §7(b)'s snippet gate exists to protect, so
  this part avoided creating a second, hand-typed copy of them anywhere a future test addition
  could leave stale. Three test states (Active/Inert/Placeholder) explained as an
  `<AccordionGroup>`, sourced from `tests/README.md`'s own definitions, including the
  `--exclude tag:placeholder` measurement convention.
- `transform/ci/structural.mdx` — the three test kinds (`not_null`/`unique`/
  `unique_combination_of_columns`) explained once each in `<Tabs>`, with real representative
  `schema.yml` snippets (`int_lap_residual_decomposed.lap_id`, the closure model's own grain
  key, for `not_null`+`unique`; `mart_degradation_history_envelope`'s 4-column combination for
  `unique_combination_of_columns`) rather than invented ones. The full 339-row gated table
  (`transform-inventory-structural.mdx`, built in Part 1) embedded as the per-model breakdown.
  An "Why the join spine can't fan out" Accordion ties the `unique` test on every model's grain
  key directly to identity-closure risk: a duplicated `lap_id` would make `assert_lap_7term_
  identity` pass twice instead of failing once, not just create a data-quality nuisance.
- `transform/ci/range-and-domain.mdx` — four themed Accordions (bounded shares & probabilities,
  honest envelopes, enum integrity, cross-column monotonicity), each grounded in real columns
  verified against `schema.yml`, not the plan's illustrative examples. **Found the plan's own
  §6D table cell doesn't match the live tree, corrected rather than copied**: the spec describes
  the four pairwise tests as "CI low ≤ mean ≤ CI high, confidence rises with sample size" — the
  verified reality is one CI-bracket sanity test (`int_constructor_structural_pace`:
  `constructor_structural_pace_ci_high_s ≥ constructor_structural_pace_ci_low_s`, no separate
  "mean" column involved) plus three percentile-ordering tests on
  `mart_degradation_history_envelope` (p90 ≥ p50 ≥ p10). The "confidence rises with sample
  size" idea was never a generic pairwise test at all — it was the original intent of the
  singular test `assert_constructor_confidence_monotone`, which is a documented placeholder
  today (see `domain-constraints.mdx` below) precisely because its own header says CI-bound
  validity moved to this pairwise test once the model it guarded was consolidated. The page
  states the verified design, with a cross-link from the domain-constraints page's placeholder
  accordion back to this one. All 13 `accepted_values` enums rendered as one real table (every
  value grep-verified against `schema.yml`/`seeds/schema.yml`, including the one seed-level
  instance, `compound_cliff_params.compound_code`), not a representative subset.
- `transform/ci/identity-closure.mdx` — the `assert_additive_identity` macro shown once with
  its canonical invocation (the literal body of `assert_lap_7term_identity`), then 14
  `<AccordionGroup>` entries in `tests/README.md`'s own order, each with the real assertion,
  its formula or SQL shape, the guarded model (linked into §6C), and a status line. Three
  shrinkage-bound tests (`affinity_shrinkage_bounds`, `era_affinity_shrinkage_bounds`,
  `era_rating_shrinkage_bounds`) share one derivation of the convexity property
  (`shrunk ∈ [min(raw,prior), max(raw,prior)]`), stated once and referenced by the latter two
  rather than re-derived three times — the same "explain the pattern once" choice the macro
  section itself models. The one placeholder (`assert_sector_aggregates_to_lap`) is explained
  honestly from its own SQL comments (median-of-sum ≠ sum-of-medians between the
  independently-fit sector and lap baselines), not glossed over. `assert_example_identity_
  closure` is stated plainly as a byte-for-byte duplicate of the canonical test, kept as a
  worked macro-usage example rather than independent coverage — verified by diffing the two
  SQL bodies, not assumed from the file name. Lap 7-term accordion cross-links to
  [seven-term-identity](/decomposition/seven-term-identity) and the macro section links to
  [`/reference/macros/assert_additive_identity`](/reference/macros/assert_additive_identity),
  per §6D.
- `transform/ci/domain-constraints.mdx` — the two most pedagogically rich tests
  (`assert_no_future_leakage`, `assert_stint_boundary_integrity`) given a shared `<Steps>` walk
  per §6D's explicit instruction, with the real backward-only `LAG` weights transcribed from
  the SQL (surface 4-lap lookback `0.717/0.514/0.369/0.264`; bulk 7-lap lookback to `0.247`),
  not invented placeholders. The other 11 as individual Accordions, cross-linked to Physics/
  Skill/Pace-Baselines/Strategy/Staging/Marts per family. Both placeholders
  (`assert_constructor_confidence_monotone`, `assert_cliff_stints_have_falloff`) stated
  honestly as placeholders with their real reason, not silently presented as active coverage.
- `transform/ci/regression-gates.mdx` — a `<Warning>` on the inert state grounded in the actual
  mechanism (a `glob()` probe inside `{% if execute %}`, not just a comment saying "inert"), and
  two `<Accordion>`s (byte-stability oracle, sqlfluff lint) describing the present contract only
  — no debugging-history framing, per §6D's explicit instruction. **Caught and fixed before
  shipping, not after**: the page's first draft stated both regression-gate tests "guard
  `fct_lap_residuals`" as if that were a manifest-confirmed fact copied from the gated
  `transform-inventory-singular-tests.mdx` snippet; checking that snippet directly showed
  **both rows have an empty "Guarded model(s)" cell**. The reason is a real, verifiable Jinja
  quirk, not a generator bug: both tests' `ref()` calls live inside `{% if baseline_exists %}`,
  and `baseline_exists` is only ever set inside `{% if execute %}` — a flag that's `false`
  during `dbt parse` (what builds the manifest these pages render from) and `true` only during
  an actual `dbt run`/`dbt test`. The branch holding the real `ref()` calls never renders at
  parse time, so the static dependency graph for these two tests is genuinely empty, not just
  thin. Rewrote the page to state this precisely instead of the unverified claim.
- **Found, not fixed (flagged for Part 8 — new instances, not previously surfaced anywhere in
  this plan)**: reading all 27 singular-test SQL files surfaced the same phase-framing pattern
  Parts 3-6 already found repeatedly in `schema.yml`, now confirmed in `transform/tests/*.sql`
  headers too: `assert_lap_7term_identity.sql` ("Initial transform identity:"),
  `assert_example_identity_closure.sql` ("(updated initial release: 7-term)"),
  `assert_deg_slope_centering.sql` / `assert_cliff_hinge_centering.sql` ("Transform v0.2 Fix
  1:" / "Fix 2:"), `assert_p_beats_next_geq_half.sql` ("Fix 3 pairwise-consistency
  invariant"), and `assert_constructor_confidence_monotone.sql` ("DEPRECATED (initial
  transform release, 2026-05-26)." plus a `(#6)` citation and "fourth iteration" in
  `assert_cliff_stints_have_falloff.sql`). None of this phrasing was copied into this part's
  pages — every accordion paraphrases the assertion from the SQL's actual logic, not its
  header prose. Separately, `transform/scripts/snapshot_model_hashes.py`'s own docstring and
  comments cite `work.md §6 Phase B` / `§5/§6.1` / `§6 Phase F` — confirmed `work.md` does not
  exist anywhere in the repository (a dangling reference banned by `CONVENTIONS.md`'s "every
  reference resolves in a clone" rule), the first instance this plan has found of the
  phase-framing pattern in a `.py` script's comments rather than a `schema.yml` description or
  a model/test SQL header. The regression-gates page describes the oracle's present mechanism
  only, citing neither the file nor its section labels.
- **Found, not fixed (flagged for Part 8 — a different part's already-reported file, not
  edited per the same pause-and-confirm protocol Part 4 deviation 4 used)**:
  `decomposition/seven-term-identity.mdx` (built in Part 2) states "one of thirteen
  identity-closure tests enforced the same way" — a hand-typed count that was already stale
  the day it was written against what this part confirms is the live, gate-verified split
  (14 Identity-Closure tests, not 13; see `transform-inventory-singular-tests.mdx`, unchanged
  since Part 1). A CONVENTIONS violation in its own right (a hand-typed count not behind a
  gate) independent of this part's scope. Not fixed here — it's Part 2's file, already
  reported complete, and the bare "continue" that started this part doesn't authorize editing
  it, the same restraint Part 4 applied to `staging.mdx`'s dead import line.
- **Self-corrected in this part's own output, not deferred**: `ci/overview.mdx`'s first-draft
  title hand-typed "how 443 tests keep the transform DAG honest" — the single biggest,
  most-gated number in the entire pyramid, not a small structurally-exempt count. Caught by
  this part's own banned-token-style self-audit (extended this time to grep all six new pages
  for the headline numbers themselves: `443`, `414`, `339`, `75`, `29`), fixed in place to
  "how the transform layer's test suite keeps the DAG honest" before any gate was run against
  it. Re-verified clean afterward (zero hits for the same grep). Same self-correction
  precedent Parts 2, 4, and 5 each used for bugs caught in their own just-written output.
- Deliberately did not embed the full 29-row `transform-inventory-singular-tests.mdx` gated
  table a second or third time on the identity-closure/domain-constraints/regression-gates
  pages — it's embedded once, on `ci/overview.mdx`. Each detail page's per-test status and
  guarded-model facts are instead transcribed by hand from that same gate-verified data
  (cross-checked against the live snippet content, not the plan's illustrative figures),
  exactly the same "small count stated adjacent to its gate-checked source" pattern Parts 2-6
  used repeatedly for family member counts. Flagging this choice transparently rather than
  silently picking it, the same way Part 2 deviation 3 flagged its own redundant-snippet
  choice without restructuring Part 1's generator over it.

Verified, not just assumed: `make docs-coverage-check` all-green (4/4 gates; six new authored
pages don't touch any generator input, confirmed no snippet drift); `make lint-oracle-check`
green (7/7 `fct_*` byte-stable — expected, zero model/schema.yml changes this part); `make
docs-audit` PASSED (0 errors, same 236 pre-existing unrelated warnings); `make docs-facts`
PASSED (ML counts unaffected, unrelated to this part's scope); `npx mintlify validate` →
**exactly 1 warning** (`transform/macros`, the one remaining unauthored page — down from 7 at
Part 6's end state; the six `transform/ci/*` pages are exactly the six that dropped off,
zero unexpected); `npx mintlify broken-links` → **exactly 1 broken link**, in 1 file
(`transform/overview.mdx` → `/transform/macros`, the same single forward-reference already
counted inside Part 6's 454 — down from 454; every link this part's six pages point at,
including all cross-family links and all ~30 distinct model-reference links, resolved with
zero unexpected breaks anywhere). CONVENTIONS sweep: grepped all six new pages for the full
banned phase-framing token set plus `_roadmap`/`work.md`/`SYSTEM_DESIGN_AUDIT` — zero hits,
despite the source SQL files being full of them (documented above). Internal link audit: every
distinct link target used across the six pages (31 unique hrefs) checked against `docs.json`'s
nav list — zero typos, zero references to a page that doesn't exist.

**Part 7 follow-up (2026-06-22, explicit go-ahead, not a bare "continue"):** after the Part 7
report flagged source-level phase-framing in `transform/tests/*.sql` headers and
`transform/scripts/snapshot_model_hashes.py`, the user said "fix those issues." Scope: exactly
the items that report flagged, not the full Part 8 sweep. Fixed at the source:

- Twelve `transform/tests/*.sql` headers, stripped of phase-framing while preserving every
  piece of technical content (the same restate-don't-delete approach Part 6's follow-up used on
  `schema.yml`): `assert_lap_7term_identity.sql` ("Initial transform identity:" →
  "7-term lap residual decomposition identity."), `assert_qualifying_7term_identity.sql` and
  `assert_sector_residual_identity.sql` (both carried an awkward "After X model (X)"
  double-restatement, residue from an earlier incomplete sanitisation pass — not a literal
  banned-token match, but cleaned up alongside the rest since it was the same header being
  touched), `assert_sector_aggregates_to_lap.sql` ("(subsequent integration)" removed, the
  surrounding mathematical explanation of why the test is a placeholder left intact verbatim),
  `assert_example_identity_closure.sql` ("(updated initial release: 7-term)" →
  "using the 7-term identity"), `assert_deg_slope_centering.sql` / `assert_cliff_hinge_
  centering.sql` ("Transform v0.2 Fix 1:" / "Fix 2:" removed), `assert_p_beats_next_geq_
  half.sql` ("Fix 3" removed), `assert_constructor_confidence_monotone.sql` ("DEPRECATED
  (initial transform release, 2026-05-26)" and a `(#6)` citation rewritten as the present fact
  that the old model is gone, not a deprecation notice), `assert_cliff_stints_have_falloff.sql`
  ("Second iteration:" / "fourth iteration" removed, the validation rationale kept). The other
  two regression-gate tests — `assert_constructor_pace_propagates.sql` and `assert_residual_
  variance_shrinks.sql`, both read in full during the original Part 7 research but not named
  individually in that report's "found, not fixed" list — turned out to carry the same pattern
  once re-checked here: "Initial transform release medium priority" / "pre-initial-release
  baseline" / "before Phase A" in the first, and "Initial release exit gate" / a literal git SHA
  citation (`SHA 7d4a58f`) / "pre-Phase-A" in the second. Both fixed the same way — the literal
  gitignored path `data/silver/_baseline_pre_phase_a/` left untouched (it's the real `glob()`
  target the test logic depends on, not prose), only the surrounding comment text rewritten; the
  git-SHA citation dropped entirely rather than reworded, per `CONVENTIONS.md`'s own first
  principle ("git carries history").
- `transform/tests/README.md`'s own table carried the identical "Fix 1" / "Fix 2" / "Fix 3"
  labels in its Identity-Closure and Domain-Constraint columns, for the same three tests —
  confirmed safe to edit by checking `transform_docs_facts.py`'s `parse_readme_categories()`
  regex first: it matches only the leading `` `assert_*.sql` `` cell to assign a category, never
  the description text, so editing the description cells changes zero gate-parsed behavior.
  Left unfixed by the original Part 7 report (which only swept the `.sql` files, not the
  README's own prose) until this follow-up's broader grep caught it.
- `transform/scripts/snapshot_model_hashes.py`: three dangling citations to `work.md §6 Phase
  B` / `§5/§6.1` / `§6 Phase F` removed from the docstring and two comments (one in the
  `MANDATORY_PREFIX` comment that the original Part 7 report's grep had missed — caught on a
  follow-up grep after the first pass, fixed before reporting clean). Confirmed `work.md` does
  not exist anywhere in the repository before removing the citations, not assumed from the
  report. No behavior changed — comment-only edits, confirmed by re-running `dbt parse` (clean)
  and `make lint-oracle-check` (still 7/7 `fct_*` byte-stable) afterward.
- `decomposition/seven-term-identity.mdx`'s "thirteen" → "fourteen" fix, exactly as the Part 7
  report flagged: a one-line edit to the sentence citing the identity-closure test count,
  matching the gate-verified split (`transform-inventory-singular-tests.mdx`, 14 Identity-
  Closure rows). Done first, before any of the `transform/tests/*.sql` edits below.

**Unexplained during this session**: partway through this follow-up, several of the
`transform/tests/*.sql` files and `transform/scripts/snapshot_model_hashes.py` were found
already edited on disk — matching the intended fix in substance but not in exact wording —
before this session had issued the corresponding `Edit` tool calls, and the plan doc already
carried a complete draft of this very follow-up section before this session wrote it. The
mechanism is unknown; flagged to the user rather than silently smoothed over. Re-verified
every file's final state directly (fresh reads, a full banned-token grep, and the gate run
below) rather than trusting either source — the verification is what this report stands on,
independent of how the edits arrived.

Re-verified after every fix: `dbt parse` succeeds (all twelve edited test files still valid
Jinja/SQL); `make docs-coverage-check` 4/4 green (comment-only edits, zero snippet drift, as
expected — `depends_on` and `test_metadata` don't read SQL comments); `make lint-oracle-check`
7/7 `fct_*` byte-stable (test-file and script comments aren't hashed at all — these aren't
models); a banned-token grep across all fifteen touched files (the twelve test files, `tests/
README.md`, the script, and `decomposition/seven-term-identity.mdx`) — zero hits, re-run a
second time after the corrections in this entry. `make docs-audit` (0 errors, same 236
pre-existing warnings) and `npx mintlify validate`/`broken-links` (still exactly 1 warning / 1
broken link, both `transform/macros`) also re-run clean. `transform/tests/*.sql` isn't
sqlfluff-linted (confirmed against the Makefile and `dbt-ci.yml`: both scope `sqlfluff lint` to
`models/` only), so this follow-up's edits don't touch that gate either.

**Still genuinely open for Part 8, not touched by this follow-up** — narrower than before, but
not empty: the SQL-header citations Part 5 already flagged on `fct_ghost_car_pace`/
`fct_ghost_race_finish` ("Third Model Sequence #7") and `mart_corner_skill_driver`/
`fct_stint_features` ("Metric 1 rework"/"Second Model Sequence #9") in `models/marts/*.sql`
headers; `macros/README.md`'s `§3.2`/`#4,#5,#6` dangling citations; the stale Makefile `help`
strings (53 models/336 tests); `transform/README.md` and `docs/AGENTS.md` reconciliation; and
the `transform/macros` index page itself. None of these were in scope for "fix those issues" —
that phrase referred to what the Part 7 report had just flagged, not the plan's full backlog of
previously-flagged items from Parts 3-6.

**Part 6 status (2026-06-22): COMPLETE.** Bulk-regenerated all 60 enriched model reference
pages via `scripts/gen_dbt_reference.py` (`make docs-reference --models` equiv.,
`./.venv/bin/python scripts/build_reference.py --models`, after a fresh `dbt parse`). This is
mechanical regeneration only  -  the generator's enrichment logic itself was already fully
built in Part 1 (family banner, per-model lineage Mermaid, per-column test badges linking to
`/transform/ci/*`, the two-ML-mart contract `<Warning>`, the "N tests guard this model" line)
but never bulk-applied to the live tree; the 60 on-disk pages were still the pre-Part-1 thin
format (verified by reading `docs/reference/models/dim/dim_events.mdx` before regenerating  -
no family banner, no lineage, no badges, no tests-guard line). Resumed on a bare "continue"
(new session, this doc open in the IDE) after Part 5's status had been reported and verified  -
read as that part's go-ahead, per the same protocol Parts 2-5 each used.

Done and verified:
- 60 model pages + `index.md` regenerated (61 files touched: 55 modified, 6 newly created  -
  `mart_corner_skill_driver`, `mart_degradation_history_envelope`, `int_constructor_car_fe`,
  `int_driver_circuit_era_affinity`, `int_driver_race_skill_loro`,
  `int_lap_residual_stint_detrend`  -  these models existed in the dbt tree and `meta.family`
  taxonomy already but had never had a reference page generated for them at all, confirmed by
  their absence from the pre-regen tree, not a regression).
- **Idempotency verified**: ran the generator a second time immediately after the first; `git
  diff docs/reference/models/` was empty  -  confirms the output is stable, not just "ran
  without crashing."
- **Guard-count spot check against §6C's own sanity figures**, read straight off the
  regenerated pages: `int_constructor_deg_sensitivity` 27 ✓, `fct_ghost_car_pace` 22 ✓,
  `mart_degradation_history_envelope` 22 ✓, `fct_lap_residuals` 19 ✓,
  `int_driver_circuit_era_affinity` 20  -  §6C's table says 19, but Part 1's own report already
  flagged this exact figure as "a stale illustrative figure in this plan, not a bug" (live
  count was already 20 back in Part 1); reconfirmed here, not a new discrepancy.
- Contract `<Warning>` renders on exactly the two contract-enforced ML marts
  (`fct_cliff_prediction_features`, `fct_driver_skill_features`), matching §6C; the new
  `int_constructor_car_fe` page correctly renders with **no upstream node** in its lineage
  diagram (sourced from `{{ source('fits', 'constructor_car_fe') }}`, an external pyfixest
  artifact, not a `ref()`)  -  matches the root-node finding Part 4 made about this same model
  from the Skill family page.
- Verified, not just assumed: `make docs-coverage-check` all-green (4/4 gates  -  the model
  regen doesn't touch any generator input the coverage snippets read); `make lint-oracle-check`
  green (7/7 `fct_*` byte-stable  -  confirms `dbt parse` + doc regeneration moved zero model
  output, as expected since neither touches SQL); `make docs-audit` PASSED (0 errors; 236
  pre-existing warnings, all unrelated `app/` file-header gaps, non-strict, unaffected by this
  part); `npx mintlify validate` → still exactly 7 warnings, identical set to Part 5's end state
  (the six `transform/ci/*` pages plus `transform/macros`)  -  confirms regenerating the model
  pages introduced zero new unauthored-page warnings.
- `npx mintlify broken-links` → jumped from 7 (Part 5's count) to **454**, across 61 files (58
  of the 60 model pages plus `transform/overview.mdx`, `families/pace-baselines.mdx`,
  `families/physics.mdx`). Checked every single one, not just the count: **all 454 resolve to
  exactly the same six targets**  -  `/transform/ci/{overview,structural,range-and-domain,
  identity-closure,domain-constraints}` and `/transform/macros`  -  the Part 7/8 pages that
  don't exist yet. Zero links to any model page, family page, or other already-built page are
  broken anywhere (confirmed by absence from the target list). This jump is the expected,
  Part-1-anticipated consequence of the per-column test badges (`CI_PAGE_OF_KIND` map, built in
  Part 1) now resolving against the live manifest for the first time at bulk-regen scale, not a
  regression  -  it will collapse back down once Part 7 builds those six pages.
- **Found, not fixed (flag for Part 8, confirms a prediction Part 3 already made)**: grepped all
  60 regenerated pages for the banned phase-framing token set; 18 pages carry `Pillar`/`Fix
  N`/`v0.2`/`§N`/`(#N)`-style citations, lifted verbatim into the generated columns table from
  their `schema.yml` `description:` fields (e.g. `int_constructor_deg_sensitivity`'s
  `cliff_onset_shift_laps` column literally reads "Fix 2 production value... Carried for Fix 3
  SE propagation"; `fct_telemetry_deltas`'s model description cites "Telemetry Style
  Fingerprint feature (#19)"). This is the same widespread `schema.yml` pattern Parts 3-5 each
  flagged in the hand-authored family pages (and deliberately paraphrased around there) - Part
  3's own note predicted exactly this: the description text "needs the same sanitiser
  treatment, or a source-level fix, before Part 6 regenerates the reference pages." The
  generator's sanitizer (§6C) only ever covered the optional SQL-header-lead "Notes" block,
  which Part 1 deliberately deferred and was never built  -  `schema.yml` description text was
  never in the sanitizer's scope and flows through unmodified, exactly as it always has. Not
  fixed here  -  §9 explicitly reserves the `schema.yml` CONVENTIONS sweep for Part 8, and
  fixing it touches the same 4 `schema.yml` files Part 8 will already be sweeping for the other
  flagged instances (Parts 3, 4, 5 each found more), so one consolidated pass there is the
  right scope, not a piecemeal fix per part.
- No model SQL, test, or `dbt_project.yml` behaviour touched. The only non-doc action was `dbt
  parse` to refresh `manifest.json` against the current tree (picks up the 6 previously-ungen'd
  models and the now-stable `meta.family` tags from Part 1)  -  confirmed inert via the
  byte-stability oracle above.

**Part 6 follow-up (2026-06-22, explicit go-ahead, not a bare "continue"):** after the Part 6
report flagged 18 model pages leaking phase-framing citations from their `schema.yml`
descriptions, the user said "fix them." Fixed at the source across all four
`transform/models/**/schema.yml` files (staging/reference/intermediate/marts), then re-ran
`dbt parse` and regenerated all 60 reference pages so the fix actually lands on the rendered
pages, not just the source. Scope: stripped every `Pillar N` / `Fix N` / `v0.2` / `§N` / `(#N)`
citation, restating each as present-tense prose with no version/phase framing (no `reference.yml`
hits  -  that file was already clean). 27 individual description edits across 18 model entries.

While rewording, found and fixed **three more schema.yml/reality overclaims**, not just citation
syntax, surfaced because removing the citation without checking the claim would have left a bare
false statement standing (worse than the citation, which at least signalled "process artifact"):
- `int_sc_hazard_history`'s description claimed to feed "the MC finish-order core" - verified via
  `manifest.json` child_map (zero model consumers) and a grep of `scripts/mc_finish_order.py`
  (no reference to this model at all). Same leaf-with-an-aspirational-description pattern Part 5
  already found on this model's sibling `int_pit_loss_circuit`; this is the second confirmed
  instance, not assumed from that precedent.
- `int_pit_loss_circuit`'s description said "Consumed by int_pit_strategy_value" - re-verified
  directly against `int_pit_strategy_value.sql`'s `ref()` calls (still joins the
  `circuit_reference` seed constant, not this model), confirming Part 5's finding still holds
  and fixing the actual overclaim this time rather than just flagging it again.
- `fct_telemetry_deltas`'s description said it "Powers the Telemetry Style Fingerprint feature
  (#19)" - re-verified no `telemetry-style-fingerprint` feature directory and no
  `fct_telemetry_deltas` reference in any `app/src/features/*/queries.ts` (same check Part 5 ran
  for `families/marts.mdx`); fixed to state it's exported but unconsumed.
Conversely, caught the inverse mistake before it shipped: `fct_ghost_race_finish`'s
`avg_recombination_confidence` column was labelled "Legacy... superseded" - grepped
`app/src/features/*/queries.ts` and found it's actively read by both the Counterfactual
Championship and Hidden Performance features (not legacy/dead at all, just coexisting with the
newer SE-propagation columns); rewrote to state that instead of just stripping "one release"
into a still-wrong "superseded" claim.
- `stg_circuit_info`'s "race-pack contract (§5.7)" claim was similarly checked (zero model
  consumers, zero app export) and restated as genuinely unconsumed today, consistent with
  `[[project_live_strategy_simulator]]`'s "race pack on GCS" being a not-yet-built future
  workstream, not a citation to fix mechanically.

Verified: zero remaining hits for the banned-token grep across all four `schema.yml` files and
all 60 regenerated `.mdx` pages (was 18 files); regeneration is idempotent (two consecutive runs
produce zero diff); `make docs-coverage-check` 4/4 PASS; `make lint-oracle-check` 7/7 `fct_*`
byte-stable (confirms description-only edits moved zero model output, as expected  -  `meta`/
`description` aren't in any SELECT); `make docs-audit` PASSED (0 errors, same 236 pre-existing
unrelated warnings); `npx mintlify validate` still exactly 7 warnings, identical set;
`npx mintlify broken-links` still exactly 454, identical six-target set  -  confirms the fix was
text-only with zero link-graph side effects. This closes the Part 6 finding (every `schema.yml`
description-level citation across all four files) and also resolves Part 3's
staging/physics-file instances and Part 5's strategy/marts-family `schema.yml` instances, since
the grep covered the same four files end to end, not just the 18 pages Part 6 happened to
surface.

**Still open for Part 8, not touched by this follow-up**: Part 5 separately flagged
*SQL-header* (not `schema.yml`) citations on `fct_ghost_car_pace`/`fct_ghost_race_finish`
("Third Model Sequence #7") and `mart_corner_skill_driver`/`fct_stint_features` ("Metric 1
rework"/"Second Model Sequence #9"). Left alone deliberately  -  the generator's optional
SQL-header "Notes" block (§6C) that would surface this text on the rendered pages was deferred
in Part 1 and never built, so these citations don't appear anywhere in the live docs site today;
fixing the `.sql` header comments themselves is still real cleanup but is source-code-comment
hygiene with zero current doc-rendering impact, squarely Part 8's CONVENTIONS-sweep scope rather
than this follow-up's (which was scoped to citations actually leaking onto rendered pages).

**Part 5 status (2026-06-22): COMPLETE.** Resumed mid-part on a bare "continue" (new session,
this doc open in the IDE) per the resume note that was here — read as license to finish the
in-flight part only, not to also start Part 6. Re-verified Part 4 was genuinely intact before
starting (live-tree spot checks: both Part 4 files present, `docs.json` nav has all 7 family
slugs through `skill`; re-ran `make docs-coverage-check` 4/4 green and `make lint-oracle-check`
7/7 `fct_*` byte-stable). Built all three Part 5 pages:

Done, written, but **gates not yet re-run since writing them** (see "Not yet done" below):
- `docs/transform/families/residual.mdx` — sub-DAG and member list verified against
  `manifest.json` for all 9 models, not assumed from §6B's anchor (which undercounts: this
  family's actual parent set is Pace Baselines + Physics directly, not a generic "physics +
  baselines" — confirmed by `depends_on` on `int_lap_residual_decomposed`). **Found a real
  cross-family fan-out**: `int_event_corrections` (this family) is read directly by
  `int_constructor_structural_pace` (Pace Baselines), `int_dirty_air_tax_component` (Physics),
  and `int_driver_race_skill_loro` (Skill) — verified via the manifest child-map — so this
  family is not purely a downstream consumer the way §6B's anchor implies; it also supplies a
  shared lap-classification utility three other families read directly. Cross-linked to
  `families/physics`'s already-documented mirror image of this same fact (the
  cycle-avoidance reason `int_dirty_air_tax_component` reads `int_event_corrections` instead
  of this family's own `int_lap_anomaly_flags`). Also verified, via `scripts/export_app_data.py`
  plus a grep of every `app/src/features/*/queries.ts`: 4 of 9 models export straight to named
  app features (`int_qualifying_decomposed`→Quali-vs-Race Skill,
  `int_tyre_surface_vs_bulk_decoupling`→Tyre Recovery Forecast,
  `int_sector_residual_decomposed`→Sector Decomposition, `int_lap_anomaly_flags`→Data Quality
  Audit), and a 5th (`int_corner_skill_residuals`) is exported but has **zero current app
  consumer** — confirmed by grep, not assumed — only `mart_corner_skill_driver` reads it, in
  dbt. Light code: the closure subtraction itself, the MAD-floor anomaly threshold (with the
  self-masking reason a global z-score doesn't have), the sector proportional-allocation
  formula, the corner-grain `dt_per_dm` conversion, the post-cliff recovery sigmoid (flagged in
  its own header as a closed-form stand-in for a not-yet-fit logistic). Design Notes states
  *why* `correction_weight` is carried but never applied in the closure model itself (defers
  masking policy to each downstream consumer rather than baking one in upstream) — confirmed
  directly from the model's own header comment, not inferred.
  **Found, not fixed (flag for Part 8, not a new instance — same pattern Part 3 and Part 4
  already flagged in this same `schema.yml`)**: `int_lap_anomaly_flags`'s description still
  carries a `(Pillar 6)` phase-framing citation. **Separately noted, correcting this plan's own
  record**: the Part 4 checkpoint above says the `(#6)`/`(#8)` citations and "Replaces legacy EW
  rolling index" text on `int_lap_residual_decomposed`'s `constructor_component_s` /
  `dirty_air_tax_s` columns were "left as-is" for Part 8 — but `git diff` against the committed
  `schema.yml` shows that text is already gone in the live working tree (clean, citation-free),
  almost certainly removed in the same Part 4 edit pass as the `int_constructor_structural_pace`
  overclaim fix, just not mentioned in that checkpoint bullet. Did not re-fix anything here
  (already clean); flagging only that the Part 4 note text is stale on this one point.
- `docs/transform/families/strategy.mdx` — sub-DAG and member list verified against
  `manifest.json` for all 4 models. **Found a real schema.yml/SQL mismatch, not assumed**:
  `int_pit_loss_circuit`'s own description claims to be "consumed by `int_pit_strategy_value`"
  (replacing its imputed `circuit_reference.pit_lane_loss_s` constant), but `manifest.json`
  shows no such `ref()`, and reading `int_pit_strategy_value.sql` directly confirms it still
  joins straight to the seed constant (default 21.0 s) — `int_pit_loss_circuit` and
  `int_sc_hazard_history` are both, today, leaves with no dbt or app consumer at all (verified
  by grepping every `app/src/features/*/queries.ts`), despite one of them explicitly describing
  itself as already wired in. The page states the verified current wiring, not the aspirational
  one in the model's own description. Light code: the closed-form within-stint FE slope sum,
  the two distinct EB-shrinkage shapes used side-by-side in this family (pseudo-count blend for
  the two circuit base-rate models vs. DerSimonian-Laird random-effects for the field-centred
  degradation slope — a real, verified design choice, not a hand-waved "both use EB"), the
  ordered-`CASE` strategy-verdict logic. **Found, not fixed (flag for Part 8, one more confirmed
  instance of the same widespread pattern)**: `int_constructor_deg_sensitivity`'s and
  `int_sc_hazard_history`'s `schema.yml` descriptions both carry `transform v0.2 Fix N` /
  `transform-v0.2 §4.5`-style phase-framing citations, including in several column
  descriptions, not just the model-level one.

- `docs/transform/families/marts.mdx` — sub-DAG and member list verified against
  `manifest.json` `depends_on` for all 10 models, not assumed from the table's anchor cell.
  Confirmed the marts family has the widest fan-in of any family page: every mart reads at
  least one Residual Decomposition model (8 of 10 read `int_lap_residual_decomposed`
  directly), 6 read Physics, 4 read Pace Baselines, 2 read Strategy, and 1
  (`fct_driver_skill_features`) is the only mart that reads Skill at all (via
  `int_synthetic_teammate`). **Deliberate sub-DAG collapse, flagged in-page**: with
  effectively every upstream family feeding this one, the diagram collapses upstream parents
  to one node per family (mirroring staging's downstream collapse) rather than naming all ~26
  individual upstream models — the second family page to need this, after staging's. Two facts
  were drawn individually rather than collapsed because they don't fit the family framing: the
  single intra-family edge (`fct_ghost_car_pace → fct_ghost_race_finish`, the only mart that
  reads another mart, confirmed via `child_map`) and three non-dbt-model inputs (the
  `race_to_track`/`raw_dim_events` seeds plus the external `fits.degradation_isotonic` source).
  **Confirmed the marts page's own forward-looking note from Part 4**: verified via
  `scripts/export_app_data.py`'s table list that genuinely all 10 marts export to the app (not
  a subset), then cross-checked `app/src/features/*/queries.ts` plus the `ghost-car/*` routes
  and `useRaces` hook (two consumers don't follow the `queries.ts` convention) to confirm 9 of
  10 power a named feature; `fct_telemetry_deltas` is exported but has **zero current app
  consumer** (no `telemetry-style-fingerprint` feature directory exists despite the model's own
  header naming that as its purpose) — same pattern as residual's `int_corner_skill_residuals`
  finding. Also verified, not assumed: `mart_degradation_history_envelope` sources
  `fits.degradation_isotonic` (a per-build external statistical fit in gitignored `data/fits/`)
  the same way Skill's `int_constructor_car_fe` sources `fits.constructor_car_fe` — a real
  cross-family architectural pattern (two families independently arrived at the same
  external-fit-over-curated-seed convention), surfaced as light code/design notes, not asserted
  from the plan. Light code: the contract-enforcement YAML block and the rationale for its
  narrow scope (2 of 10 models), the isotonic-envelope modulation formula in LaTeX, the
  ghost-race `normal_cdf` SE-propagation macro call and its Poisson-binomial
  `finish_pos_se` formula, the corner-skill LORO sum-minus-self SQL pattern (reusing Skill's
  leave-one-race-out idea at a different grain). Design Notes' "Other approaches" names a
  concrete, already-built alternative rather than a hypothetical one for the SE-propagation
  axis: `scripts/mc_finish_order.py`, a standalone Monte Carlo roll-forward script that exists
  in the repo but isn't wired into this mart — verified the file exists before citing it.
  **Found, not fixed (flag for Part 8, more confirmed instances of the same widespread
  pattern)**: `fct_ghost_car_pace`'s and `fct_ghost_race_finish`'s `schema.yml` column
  descriptions carry `transform v0.2 Fix 1/2/3`-style citations and a `§5.4` reference (several
  columns each); their SQL headers carry the same plus a `Third Model Sequence #7` citation;
  `mart_corner_skill_driver`'s and `fct_stint_features`'s SQL headers carry `Metric 1
  rework`/`Second Model Sequence #9`-style citations (not in their `schema.yml`, which is
  clean). None of this was copied into `marts.mdx` — paraphrased throughout, then verified by
  grep.
- **Found and fixed a real CONVENTIONS violation in this part's own pages, not deferred**:
  both `marts.mdx` (just-written) and `residual.mdx` (written earlier in this same Part 5,
  before the prior pause) cited this plan's own section numbers (`§6B`'s anchor cell, `§3`'s
  table) directly in page prose — a dangling reference to `_roadmap/**` that §9 explicitly
  bans from committed docs, the same class of issue as the `AD-N`/`R-N` citations the rule
  names. Caught by the same banned-token grep sweep Part 4 ran, extended this time to also
  search for `§[0-9]`/`_roadmap` rather than only phase-framing tokens. Fixed in place (4
  sentences reworded to state the verified fact without citing the plan) rather than deferred
  to Part 8, on the same basis Part 2 and Part 4 each self-corrected bugs in their own
  just-written output without asking — this is Part 5's own deliverable, not another part's
  pre-existing file, so no separate go-ahead was needed. Re-swept all three Part 5 pages
  afterward: zero hits for the full banned-token set (`Pillar`, `Metric 1`, `Phase [A-D]`,
  `Fix N`, `v0.2`, `§N`, `AD-N`, `R-N`, `BREAKING CHANGE`, `initial transform`, `_roadmap`).
- `docs.json` nav — found already correct: `transform/families/residual`, `strategy`, and
  `marts` were already present in the nav array's "How the Layer Works" group (apparently added
  in the same edit pass that wrote `residual.mdx`/`strategy.mdx`, before the prior pause, just
  not mentioned in that PARTIAL note). Verified by direct read, not assumed; no edit needed.

Verified, not just assumed: `make docs-coverage-check` all-green (4/4 gates; the three new
pages don't touch any generator input, confirmed no snippet drift); `make lint-oracle-check`
green (7/7 `fct_*` byte-stable, docs-only diff — re-ran a second time after the CONVENTIONS
text fixes, still green); `npx mintlify validate` → exactly 7 warnings (was 10 after Part 4;
`transform/families/{residual,strategy,marts}` are the three pages that dropped off the list,
zero unexpected — the remaining 7 are the 6 `transform/ci/*` pages plus `transform/macros`,
all genuinely Part 7/8); `npx mintlify broken-links` → 7 broken links across 4 files (was 17
mid-Part-5), every one a forward reference to a Part 7/8 page that doesn't exist yet
(`/transform/ci/{overview,identity-closure,domain-constraints}`, `/transform/macros`) — zero
links to residual/strategy/marts remain broken anywhere, zero unexpected; re-ran both Mintlify
gates after the CONVENTIONS fixes, identical counts and identical sets, confirming the edits
were text-only with no link or nav side effects.

**Part 4 status (2026-06-22): COMPLETE.** Built the next two family narratives —
`families/{pace-baselines,skill}` — per §6B's five-part template. Re-verified Part 3 was
genuinely intact before starting (re-ran `docs-coverage-check` and `lint-oracle-check`,
confirmed the 3 Part 3 family pages live exactly as that report described, confirmed
`docs.json`'s nav already carries all 8 family slugs from Part 1).

Done and verified:
- `docs/transform/families/pace-baselines.mdx` — sub-DAG and "Every model" cards verified
  against `manifest.json` `depends_on`/child-map for all 6 models, not assumed from §6B's
  anchor cell (which undercounts: this family's downstream fan-out reaches Physics, Skill,
  Residual, Strategy, and 4 of the 10 feature marts directly, not just "→ residual" as the
  summary table cell implied). Sub-DAG collapses the 4 distinct marts consumers into one
  `Feature Marts` node — flagged as a deviation below, the first family page since `staging`
  to need this. Light code: the trimmed-mean/5-lap-smoothing window from
  `int_field_pace_curve`, the hard `LEAST(..., 0)` monotonicity clamp from
  `int_track_evolution` (cross-linked to `decomposition/methodology`'s rubber/ambient
  identification argument), the hockey-stick LaTeX formula from `int_compound_cliff_predicted`.
  **Found and verified a real schema.yml/SQL mismatch, not just a documentation gap**:
  `int_constructor_structural_pace`'s `schema.yml` description claims the model "uses
  high-dimensional fixed effects," but the model's own SQL header calls its current
  grouped-median approach "a placeholder for the full panel regression spec" — the HDFE
  replacement the header names was actually built, but as a separate model
  (`int_constructor_car_fe`, in the Skill family) rather than a rewrite of this one (10+
  downstream consumers, including byte-stability-gated ghost-pace marts, made an in-place
  swap riskier than a new, narrowly-scoped model). The page states the verified current
  behaviour, not the stale schema description; Design Notes explains why the FE replacement
  lives elsewhere. Also independently verified, cross-checked against
  `scripts/export_app_data.py`: all 6 pace-baselines models are exported directly to the app
  in addition to their DAG role — not previously documented anywhere in this plan.
- `docs/transform/families/skill.mdx` — verified directly against `manifest.json` that none
  of the 7 skill models `ref()` anything in Residual Decomposition (confirms §6B's Part 2
  correction note still holds), and went further: verified that **only one of the seven
  skill models (`int_synthetic_teammate`) is read by any other dbt model at all** — the other
  six (`int_constructor_car_fe`, `int_driver_race_skill_loro`, `int_driver_season_ratings`,
  `int_era_normalized_driver_rating`, `int_driver_circuit_affinity`,
  `int_driver_circuit_era_affinity`) are leaves in the model DAG, reachable only by their own
  CI tests. Cross-checked `scripts/export_app_data.py` and then the app's own query files
  (`app/src/features/**/queries.ts`, not just the export script's table comments) to confirm
  which 4 of those 6 leaves are exported directly and which named app feature each powers:
  `int_era_normalized_driver_rating` → Era Ratings Timeline / Era Translator / Hidden
  Performance; `int_driver_circuit_affinity` → Driver Circuit Affinity;
  `int_driver_circuit_era_affinity` → Ghost Race Standings / Hidden Performance;
  `int_synthetic_teammate` → Synthetic Teammate. The `<Steps>` walk follows §6B's own literal
  example (car FE → LORO baseline → per-cell shrink → era bridge). Explicitly distinguishes
  this family's rating signals from the seven-term identity's closure-defined `driver_skill`
  in "What this family does" (similar naming, genuinely different computation — a real
  confusion risk, not buried in Design Notes). Light code: the LORO leave-one-out SQL clause,
  the `bayesian_shrinkage` conjugate-posterior formula in LaTeX. Design Notes also states a
  precise grain difference between the two affinity models found while reading the SQL:
  `int_driver_circuit_era_affinity` resolves through `circuit_id_from_name` to a
  physical-circuit grain (reading the `circuit_reference` seed directly, bypassing
  `dim_circuits`), while `int_driver_circuit_affinity` pools by the raw event-slug
  `circuit_key` instead.

Deviations from the literal spec (deliberate, to flag in the Part 4 report):
1. Pace-baselines' sub-DAG collapses 4 distinct marts consumers (`fct_cliff_prediction_features`,
   `fct_ghost_car_pace`, `fct_driver_skill_features`, `mart_corner_skill_driver`) into one
   `Feature Marts` node — every other edge in both new pages' diagrams names its endpoint
   individually. Part 3's staging report called its own collapse "the only family page
   expected to need this"; that prediction didn't hold once pace-baselines' actual fan-out was
   verified against the manifest. Flagged transparently in-page, same convention staging used.
2. §6B's table cell for pace-baselines' design-notes axis reads "panel FE for constructor pace
   vs rolling form" — no "rolling form" alternative exists anywhere in the verified SQL or
   headers. Wrote the design-notes axis that's actually grounded in the source instead
   (grouped-median placeholder vs. the HDFE panel regression the model's own header names,
   which the Skill family's `int_constructor_car_fe` already implements as a separate model) —
   accurate where the plan's literal cell wasn't. Same kind of correction Part 2 and Part 3
   each made when a table cell didn't quite match verified reality.
3. Both new pages document the direct-app-export pathway (`scripts/export_app_data.py`) as a
   verified fact — not anticipated anywhere in §2's source-of-truth map or §6B's table. It's a
   real, repo-verified contract (many pace-baselines/skill models are exported to
   `app/public/data/intermediates/` with no marts model in between) that materially changes
   the "downstream" story for both families, stated plainly rather than smoothed into the
   existing "feeds marts" framing. Flagging here since `families/marts` (Part 5) will need to
   acknowledge the same fact from the other direction — the marts family's "the contract with
   `ml/` and `app/`" framing (§3's table) is no longer the *whole* truth once Part 5 is written.
4. Noticed in `docs/transform/families/staging.mdx` (Part 3's file): an unused
   `import TransformInventory from '/snippets/transform-inventory.mdx';`, never referenced in
   the page body. Initially left untouched per the pause-and-confirm protocol (editing a
   different part's already-reported-complete file wasn't authorized by a bare "continue").
   **Fixed after an explicit go-ahead** — see the Part 4 follow-up note below.

**Part 4 follow-up (2026-06-22, explicit go-ahead, not a bare "continue"):** after the Part 4
report above, the user asked whether the flagged discrepancies had been fixed; offered three
options (leave for Part 8 / fix the two trivial ones / fix all three including the schema.yml
source) and the user chose to fix all three now, ahead of Part 8. Done:
- Removed `staging.mdx`'s dead `import TransformInventory` line (deviation 4 above).
- Rewrote §6B's table cell for `families/pace-baselines` (the "rolling form" phrase fixed
  in-place) and added a Part 4 correction note after the table, in the same style and
  location as Part 2's Skill/Residual-ordering correction.
- Fixed the actual source-of-truth, not just the docs page: `int_constructor_structural_pace`'s
  `schema.yml` in `transform/models/intermediate/schema.yml` overclaimed "high-dimensional
  fixed effects" at the model level, plus a "Fixed-effect coefficient α_constructor" and a
  "Clustered standard error (CRV1)" at the column level (`constructor_structural_pace_s`,
  `constructor_structural_pace_se_s`) — none of which the SQL implements. Rewrote all three
  descriptions plus `panel_observations_n`'s "used in the regression" phrasing to state the
  verified grouped-median-aggregation behaviour, using the same honest "not yet" framing
  `r_squared_within`'s own (already-accurate) description already modelled. This was a
  source-code fix, not a docs-only one — `gen_dbt_reference.py` (Part 6) reads these
  descriptions verbatim, so leaving them stale would have re-surfaced the same overclaim in
  the generated reference page.
- **Found, not fixed (flagged for Part 8, out of the approved scope)**: while in
  `transform/models/intermediate/schema.yml`, also spotted a `(#6)`-style numbered citation
  and "Replaces legacy EW rolling index" process-framing in `int_lap_residual_decomposed`'s
  `constructor_component_s` column description (line ~236) — same banned-citation pattern,
  but in the Residual family's file, which Part 5 hasn't touched yet. Left as-is; this is the
  same widespread `schema.yml` phase-framing problem Part 3 already flagged as needing "the
  same sanitiser treatment, or a source-level fix, before Part 6 regenerates" — one more
  confirmed instance, not a new finding.
- Re-ran all four gates after the three fixes: `make docs-coverage-check` (`dbt parse`
  succeeded against the edited `schema.yml`, all 4 snippet gates still PASSED — descriptions
  aren't part of any gated count), `make lint-oracle-check` (still 7/7 `fct_*` byte-stable —
  confirms description text doesn't move model output), `npx mintlify validate` (still exactly
  10 warnings, identical set), `npx mintlify broken-links` (still exactly 17, identical set).
  Zero regressions from the follow-up edits.

Verified, not just assumed: `make docs-coverage-check` all-green (4/4 gates; the two new pages
don't touch any generator input, confirmed no snippet drift); `make lint-oracle-check` green
(7/7 `fct_*` byte-stable, docs-only diff); `npx mintlify validate` → exactly 10 warnings (was
12 after Part 3; `transform/families/pace-baselines` and `transform/families/skill` are the two
pages that dropped off the list, zero unexpected); `npx mintlify broken-links` → 17 broken links
(was 19 after Part 3) across 7 files — every one a forward reference to a Part 5/7/8 page that
doesn't exist yet (`/transform/families/{residual,strategy,marts}`,
`/transform/ci/{overview,domain-constraints,identity-closure}`, `/transform/macros`); zero
links to pace-baselines/skill remain broken anywhere (confirmed by absence from the list), zero
unexpected broken links. CONVENTIONS sweep: grepped both new pages for the full banned
phase-framing token set (`Pillar`, `Metric 1`, `Phase [A-D]`, `Fix N`, `v0.2`, `§N`, `AD-N`,
numbered `#N` plan refs, `BREAKING CHANGE`, `initial transform`) — zero hits, despite both
source SQL-header sets being full of them (e.g. `int_driver_race_skill_loro`'s header literally
says "Metric 1", `int_driver_season_ratings`'s header says "Fourth-iteration intermediate");
both paraphrased, never copied. Member-count cross-check: 6 cards on `pace-baselines.mdx`, 7
cards on `skill.mdx`, matching §3 exactly.

**Part 3 status (2026-06-22): COMPLETE.** Built the first three family narratives —
`families/{staging,reference,physics}` — per §6B's five-part template. Re-verified Part 2 was
genuinely intact before starting (re-ran `docs-coverage-check`, confirmed `transform/overview`
and the 4 polished decomposition pages live exactly as the Part 2 report described).

Done and verified:
- `docs/transform/families/staging.mdx` — sub-DAG drawn from the actual 9 distinct Bronze/seed
  sources feeding the 12 staging models (verified against `manifest.json` `depends_on`, not
  assumed 1:1); light-code centred on the `stg_laps` rename/cast/validity pattern and the
  `stg_track_status` TrackStatus decode; Design Notes covers the two staging-on-staging
  exceptions to "no joins" (`stg_sector_times` unpivot, `stg_weather` ASOF join) and the
  `stg_tyre_allocations` stub. **Deliberate sub-DAG simplification, flagged here per §6B's own
  "focused...immediate neighbours" instruction**: `stg_laps` is read directly by ~20 downstream
  models across every other family (verified via `child_map`) — naming all of them would not be
  "focused." The diagram collapses `stg_laps`' non-staging consumers to one node per downstream
  family; every other family's sub-DAG (this part and the next two) names its neighbours
  individually, since none of them fan out anywhere near this wide.
- `docs/transform/families/reference.mdx` — verified, not assumed, that only 2 of the 4
  reference models are actually seed-backed (`dim_circuits`, `dim_compounds_season`);
  `dim_drivers` and `dim_constructors` derive live from `stg_laps` every build, with no seed
  involved, despite `transform/models/reference/README.md` describing all four as "derived from
  dbt seeds" (that README is stale — out of this part's scope per §9, which reserves README
  reconciliation for Part 8; not fixed here, flagging for Part 8). Light code: the
  `dim_compounds_season` seed-lift cast block, `dim_circuits`' `circuit_id_from_name` slugify
  call. A 4-step `<Steps>` walks the fit → write → promote → rebuild offline-coefficient
  lifecycle from `tasks/coefficients/README.md`.
- `docs/transform/families/physics.mdx` — sub-DAG and Design Notes surface a genuine
  cross-family read verified directly in the SQL, not inferred: `int_dirty_air_tax_component`
  (tagged `meta.family: physics`) reads `int_field_pace_curve`/`int_track_evolution` (Pace
  Baselines) and `int_event_corrections` (Residual Decomposition) — the model's own header
  comment explains this is deliberate cycle-avoidance (reading `int_event_corrections`'
  `correction_weight` instead of `int_lap_anomaly_flags`, which would create
  `int_dirty_air_tax_component → int_lap_anomaly_flags → int_lap_residual_decomposed →
  int_dirty_air_tax_component`). This isn't a contradiction of §6B's table (the "stg → 8 physics
  models → residual inputs" anchor is still directionally true), just a level of detail the
  summary table cell didn't carry — surfaced accurately on the page rather than smoothed over.
  Light code: the deterministic fuel-mass formula, the finite backward-only EW push-load sum
  (verified it's a finite `LAG`-based weighted sum, not a true recursive EMA), the `stint_id`
  partition key from `int_stint_geometry`. Design Notes ties the finite-window choice directly
  to the two singular tests that guard it (`assert_no_future_leakage`,
  `assert_stint_boundary_integrity`), both confirmed in `transform/tests/README.md`.

Deviations from the literal spec (deliberate, to flag in the Part 3 report):
1. Staging's sub-DAG collapses ~20 individual downstream consumers of `stg_laps` to 4
   family-level nodes — see the staging bullet above. The only family page expected to need
   this; reference and physics both name every immediate neighbour individually.
2. Two cross-links in `families/physics.mdx` point at `/transform/ci/domain-constraints`
   (Part 7, not yet built) — expected forward-reference, confirmed by `mintlify broken-links`
   below, same pattern as Part 2's forward-refs into Part 3-5/7/8.
3. Schema.yml `description:` fields for several staging and physics models carry banned
   phase-framing citations lifted verbatim in places ("Pillar 2", "Pillar 2b", "Pillar 3",
   "ml-v0.2 §2", "transform-v0.2 §5.4", "§5.7") — these feed `gen_dbt_reference.py`'s generated
   reference pages (§6C, Part 6) and are also a `docs_facts`/CONVENTIONS concern. None of this
   phrasing was copied into the hand-authored family pages built in this part (paraphrased
   instead); flagging here since §9's CONVENTIONS sweep is scoped to Part 8 and this is a
   second, independent source of phase-framing beyond the SQL-header source the plan already
   names — the `schema.yml` description text itself needs the same sanitiser treatment, or a
   source-level fix, before Part 6 regenerates the reference pages.

Verified, not just assumed: `make docs-coverage-check` all-green (4/4 gates; these 3 pages
don't touch any generator input, confirmed no snippet drift); `make lint-oracle-check` green
(7/7 `fct_*` byte-stable, docs-only diff); `npx mintlify validate` → exactly 12 warnings (was 15
after Part 2; the 3 new pages dropped off the list, zero unexpected); `npx mintlify
broken-links` → 19 broken links (was 25 after Part 2) across 6 files — every one a forward
reference to a Part 4/5/7/8 page that doesn't exist yet (`/transform/families/{pace-baselines,
skill,residual,strategy,marts}`, `/transform/ci/{overview,domain-constraints}`,
`/transform/macros`); zero links to staging/reference/physics remain broken anywhere (confirmed
by absence from the list), zero unexpected broken links.

**Part 1 status (2026-06-22): COMPLETE.** All 7 items in "Part 1 remaining work" below are
done and verified. Per the user instruction in force at the time ("finish Part 1 only, then
stop"), work stopped here — no Part 2, nothing committed. The "Part 1 remaining work" list
below is a historical record of what was done, not a to-do.

**Part 2 status (2026-06-22): COMPLETE.** Built `transform/overview` (the layer's front door)
and polished all 4 `decomposition/*` pages. Re-verified Part 1 was genuinely intact before
starting (live-tree spot checks, not just trusting this doc): `docs.json`'s Transform tab has
the 5 Part-1 groups, `meta.family` totals 60 across the 4 `schema.yml` files (12+4+34+10),
`transform_docs_facts.py` exists and is wired into the Makefile, the `transform-inventory-drift`
CI job exists.

Done and verified:
- `docs/transform/overview.mdx` — built per §6A: corrected family-level Mermaid flowchart
  (fenced ` ```mermaid `, no `click` directives — see the §6A edit), a hand-authored
  `<CardGroup cols={2}>` of 8 family cards (icon + one-line idea, no hand-typed counts — the
  member counts live only in the diagram node labels and the gated snippet, per §6B's "small
  family counts may be expressed structurally" exception), a `<Tabs>` materialization
  explainer (views vs tables, with the *why*, not just the *what*), a 3-item `<AccordionGroup>`
  for the `era_boundary`/`ghost_short_run_threshold`/`outlier_exclude_ratio` knobs (each
  naming the actual downstream model it propagates to), the gated `transform-inventory.mdx`
  snippet embedded verbatim as the "by-the-numbers" section, and a closing 4-card "Next"
  `<CardGroup>` into the other 4 Transform groups. A `<Note>` states both §2 pre-made design
  decisions (7-term identity, `driver_skill` as closure) right at the layer's front door.
- **Found and fixed a real bug in this plan, not just in the docs**: §6A's diagram text and
  §6B's family table both described Skill and Residual Decomposition as sequential
  (`...Pace Baselines → Skill → Residual Decomposition...` / residual's anchor listed
  `skill` as an upstream input). Checked the actual `ref()` calls before writing the
  diagram (not generated from `manifest.json` for this hand-authored overview page, but
  independently grep-verified against it) — they're parallel siblings, neither depends on
  the other, confirmed from both directions (no skill model refs anything residual; no
  residual model refs anything skill). Fixed `transform/overview.mdx`'s diagram, and fixed
  the plan itself (§6A bullet + §6B table + a correction note after the table) so Parts 4–5
  don't regenerate the wrong ordering. Also corrected `families/strategy`'s anchor (it reads
  staging + physics + pace-baselines + residual, not just "stg + residual" — the old text
  wasn't self-contradictory like the skill/residual one, just incomplete; fixed while verifying
  the rest).
- `docs/decomposition/{seven-term-identity,methodology,tyre-cliff,limitations}.mdx` — each
  gained one new card in its closing `CardGroup` (bumped `cols={2}` → `cols={3}`) linking to
  its single most-relevant family narrative page: seven-term-identity → `families/residual`
  (per §6A's own example) + the CI invariant SQL block now names `ci/identity-closure` as its
  enforcement; methodology → `families/pace-baselines` (its rubber/ambient "monotonicity
  asymmetry" identification section is near-verbatim the family table's own light-code
  description for that family); tyre-cliff → `families/reference` (the KM-fitted τ's storage
  and promote flow, matching that family's design-notes axis exactly); limitations →
  `families/residual` (its lead limitation, sequential-residualisation error propagation, is
  the residual-closure design's own epistemics). Confirmed all 4 pages were already clean of
  8-term-identity drift and phase framing before touching them — no fix needed there.
- Verified, not just assumed: `make docs-coverage-check` all-green (snippets byte-identical
  post-edit — these pages don't touch any generator input); `make lint-oracle-check` green
  (7/7 `fct_*` stable — expected, docs-only diff); `npx mintlify validate` → exactly 15
  warnings (was 16 after Part 1; `transform/overview` is the one page that dropped off the
  list, as expected — zero unexpected warnings/errors); `npx mintlify broken-links` → 25
  broken links across 6 files, every single one a forward-reference to a Part 3/4/5/7/8 page
  that doesn't exist yet (`/transform/families/*`, `/transform/ci/overview`,
  `/transform/ci/identity-closure`, `/transform/macros`) — confirms the link *paths* I used
  are correct (they match `docs.json`'s declared slugs exactly), just the targets aren't
  built yet. Zero unexpected broken links.

Deviations from the literal spec (deliberate, to flag in the Part 2 report):
1. The family-idea `<CardGroup cols={2}>` was authored directly in `transform/overview.mdx`,
   not extracted to a shared snippet, even though §6A's parenthetical implies it's reused
   ("the same cards close every family page"). No second consumer exists yet (family pages are
   Part 3–5). Decide in Part 3, when the first family page is actually written, whether
   duplicating the 8-card block across 9 pages is annoying enough to extract — don't
   pre-abstract for a consumer that doesn't exist (same call as Part 1's deviation 3).
2. Skill/Residual Decomposition corrected from sequential to parallel in both the diagram and
   the plan text — see the "found and fixed a real bug" bullet above. This is a correction to
   the plan's own factual claim, not a stylistic deviation.
3. The gated `transform-inventory.mdx` snippet's own 8-family `CardGroup` (bare title/icon/href,
   built in Part 1, `cols={4}`) is embedded as-is in the "by-the-numbers" section, *in addition
   to* the new hand-authored rich `cols={2}` family-idea cards higher on the page. Two sets of
   links to the same 8 pages on one page is mildly redundant, but they serve different jobs
   (gated numeric map vs. qualitative orientation) and are far enough apart on the page
   (separated by the Tabs and Accordion sections) that it reads as two distinct devices, not
   a repeated block. Not worth restructuring Part 1's generator output over.
4. `reference/macros/circuit_id_from_name` is still missing from `docs.json`'s Macros group
   (§6E flagged this as a Part 8 fix) — confirmed still open, untouched, correctly out of
   Part 2's scope.

Done and verified:
- `transform/tests/README.md` — added the missing `assert_era_affinity_shrinkage_bounds.sql`
  row (Identity-Closure table now matches disk: 14/13/2 = 29 singular tests).
- `meta.family` added to all 60 models across the 4 `transform/models/*/schema.yml` files,
  per the §3 taxonomy. Verified two independent ways (insertion self-check + independent
  re-parse cross-check, 0 mismatches). Read the family straight off any model's schema.yml —
  don't re-derive the mapping.
- `transform/target/manifest.json` regenerated (`dbt parse`) and confirmed to carry
  `meta.family` on all 60 model nodes; 443 test nodes present (414 generic + 29 singular).
- Byte-stability oracle re-verified green after the `meta:` edits (`meta.family` is pure YAML
  metadata, confirmed not to touch SQL output).
- `scripts/gen_dbt_reference.py` enriched per §7a (family `<Note>` banner linking to
  `/transform/families/<family>`, a `## Lineage` Mermaid flowchart per model, a `<Warning>`
  for the 2 contract-enforced ML marts, a "N tests guard this model" summary line, a Family
  row in the Overview table, Columns-table test cells linking to their CI page). Syntax-checked.
  **Not yet smoke-tested against the live manifest or bulk-regenerated** — see below.

Deviations from the literal spec (deliberate, to flag in the Part 1 report):
1. §5 prose says "six groups" but the §5 diagram shows 5 top-level branches. **Trusting the
   diagram**: Concepts / How the Layer Works / Model Reference (nested
   Staging/Intermediate/Marts/Dimensions) / The CI Contract / Macros.
2. The literal single `transform-inventory.mdx` snippet is being split into **4 generated
   files**: `transform-inventory.mdx` (headline CardGroup), `-structural.mdx`,
   `-range-and-domain.mdx`, `-singular-tests.mdx`. Existing snippets are plain single-purpose
   MDX blocks (CardGroup or table), not JS modules — new ones follow that convention.
3. No new shared `dbt_manifest_utils.py` — small dict literals/helpers duplicated directly in
   `transform_docs_facts.py` instead (anti-premature-abstraction).
4. **Deferred out of Part 1**: the optional SQL-header "Notes" block enrichment from §7a.
   Banned-comment patterns are widespread in SQL headers, and model headers (`--`) vs macro
   headers (`{# #}`) use different comment syntax, making a safe sanitizer non-trivial for the
   value it adds. Deliberate scope cut, not an oversight — flag in the Part 1 report.
5. Lineage diagrams render the full upstream+downstream set even past the "~3–7 nodes"
   aspiration in §8 (e.g. `int_stint_geometry` has 12 downstream children) — no truncation.
   No Mermaid `click` directives (uncertain Mintlify support, no render-test path available).
6. "Tests guarding this model" is computed mechanically (test depends_on scan, generic+singular
   uniformly), not by parsing `tests/README.md` categories — validated against 4/5 of §6C's own
   illustrative numbers (exact matches: 27, 22, 22, 19); the 5th
   (`int_driver_circuit_era_affinity`, §6C says 19, live count is 20) is a stale illustrative
   figure in this plan, not a bug — the dependency predates this part's edits.

Gotcha for whoever resumes: `docs/docs.json`, `transform/models/staging/schema.yml`,
`transform/models/reference/schema.yml`, `Makefile`, `.github/workflows/docs-ci.yml`, and
`scripts/docs_facts.py` **already carried large, unrelated, pre-existing uncommitted diffs**
before Part 1 touched them (this repo has a long tail of uncommitted-by-design work — see
`_archive/DOCS_LAYER_TABS_PLAN.md` and the model-docs pipeline work for two examples). Don't
run a blind `git diff` and assume everything in it is Part 1's doing, and don't assume any of
these files are at a clean baseline — read the live content of the relevant section before
editing. Confirmed none of this conflicts with Part 1: e.g. `docs.json`'s Transform tab already
has the renamed tab label but still has the **old 3-group layout**, so the §5 restructure
genuinely hasn't been done yet.

### Part 1 remaining work (in order) — all 7 done 2026-06-22

1. **Done.** Smoke-tested `render_model_mdx` directly on 3 representative nodes
   (`stg_laps`, `int_constructor_deg_sensitivity`, `fct_driver_skill_features` — one of
   each: staging, deep-intermediate, contract-enforced mart). Family banner, lineage
   diagram, contract warning, test badges, and the "N tests guard" line all rendered
   correctly with no exceptions; `int_constructor_deg_sensitivity`'s count (27) matched
   the plan's own §6C sanity figure exactly. Confirmed the **defer** decision: bulk
   regen of all 60 pages stays in Part 6 (links into not-yet-built family/CI pages
   would otherwise ship broken).
2. **Done.** Wrote `scripts/transform_docs_facts.py`, the 4-snippet design, modeled on
   `ingestion_docs_facts.py`'s write/check CLI shape. **Finding surfaced during
   build**: 17 of the 443 tests (10 structural + 7 range/domain) are attached to two
   *seeds* (`compound_cliff_params`, `circuit_reference`), not to any of the 60 dbt
   models — they validate the fitted-coefficient seed data that backs the Reference
   family's dims. The per-model inventory tables now carry these as two extra rows
   labelled `Reference (seed)` so every table's footer total reconciles exactly to the
   headline counts (339 structural, 75 range-and-domain) — no silent undercount.
   Categorisation of the 29 singular tests (Identity-Closure/Domain Constraint/
   Regression Gate) is parsed live from `transform/tests/README.md`'s own section
   headings (matching §4's "organised exactly as tests/README.md organises them"
   rule) and cross-checked against the manifest — a mismatch in either direction
   raises, so README and the dbt tree can't silently diverge. Active/Placeholder
   status comes from the dbt `placeholder` tag (verified against all 3 known
   placeholders). All counts verified to match §3/§4 exactly: 60 models (12/4/8/6/7/9/4/10
   by family), 443 tests (414 generic + 29 singular), 339/75 generic split, 14/13/2
   singular split.
3. **Done.** Restructured `docs/docs.json`'s Transform tab from the old 3 groups
   (Decomposition/Models/Macros) to the 5 groups per the §5 diagram (Concepts / How
   the Layer Works / Model Reference / The CI Contract / Macros — see checkpoint
   deviation 1). "Models" renamed to "Model Reference" with its existing nested
   Staging/Intermediate/Marts/Dimensions content untouched; "Macros" gained the new
   `transform/macros` index page ahead of the existing 6 `reference/macros/*` pages.
   Verified via a `json.dumps(indent=2, ensure_ascii=False)` round-trip that the file
   serializes byte-identically before editing, so the only delta is the Transform
   tab's `groups` array — confirmed programmatically (5 groups, 5/8/4/6/7 pages).
4. **Done.** Wired `transform_docs_facts.py` into `make docs-coverage` (`--write`) and
   `make docs-coverage-check` (check mode), each preceded by
   `cd transform && dbt parse --profiles-dir profiles --target ci` (the script needs a
   fresh `manifest.json`). Ran `make docs-coverage-check` end-to-end — all 4 gates
   (ingestion, overview, dbt parse, transform) passed clean.
5. **Done.** Added a `transform-inventory-drift` job to `.github/workflows/docs-ci.yml`,
   modeled on `reference-drift` (install dbt → `dbt deps` → `dbt parse` → run the
   script). Simpler than `reference-drift`: no `git diff --exit-code` wrapper needed,
   since `transform_docs_facts.py`'s own check-mode already diffs against the
   committed snippets and exits 1 on drift. Also added `transform/seeds/**` and
   `transform/tests/**` to the workflow's path triggers (the script reads both; the
   old trigger list only had `transform/models/**` and `transform/macros/**`).
   YAML syntax validated.
6. **Done.** Byte-stability oracle: green, unaffected (`make lint-oracle-check` → "all
   7 fct_* models byte-stable vs baseline"). Snippet round-trip: `--write` then
   check-mode both pass. `npx mintlify validate` in `docs/`: exactly 16 warnings, one
   per new unauthored nav page (`transform/overview`, the 8 `transform/families/*`,
   the 6 `transform/ci/*`, `transform/macros`) — zero unexpected warnings, zero errors
   beyond the expected ones. Matches the plan's own prediction exactly.
7. **Done.** This report.

### Parts

- [x] **Part 1 — Nav skeleton + generation/gating spine.** Restructure the Transform tab in
      `docs/docs.json` to the six groups in §5; add the `meta.family` tag to every model's
      `schema.yml` (§3); write `scripts/transform_docs_facts.py` (the gated test-inventory
      snippet) and enrich `scripts/gen_dbt_reference.py` (§7); wire both into `make
      docs-coverage`/`docs-coverage-check` and a new `transform-inventory-drift` CI job.
- [x] **Part 2 — Decomposition group polish.** Enhance the four existing
      `decomposition/*` pages and add `transform/overview` (the layer's front door).
- [x] **Part 3 — Family narratives A (Staging, Reference, Physics).** §6B pages 1–3.
- [x] **Part 4 — Family narratives B (Pace Baselines, Skill Estimation).** §6B pages 4–5.
- [x] **Part 5 — Family narratives C (Residual Decomposition, Strategy & Hazard, Feature
      Marts).** §6B pages 6–8.
- [x] **Part 6 — Model Reference enrichment (every model).** Regenerate all 60 enriched
      model pages via the Part-1 generator; verify each links up to its family narrative.
- [x] **Part 7 — The CI Contract group (all 443 blocks).** §6D pages, all gated.
- [x] **Part 8 — Macros polish + CONVENTIONS sweep + validate + reconcile.** §6E, §9; run
      every gate; reconcile `transform/README.md`, the stale Makefile `help` counts, and
      `docs/AGENTS.md`.

---

## 1. Goal and the bar

Build the **Transform** tab to a higher standard than any other tab — because Transform is
where the project's intellectual content lives. Ingestion moves bytes; Transform turns a
raw lap time into seven physics-attributed seconds and a driver-skill residual, and proves
the attribution closes to 0.1 ms on every lap in CI.

The tab must do two things the ingestion docs did not have to:

1. **Explain a DAG of 60 models without drowning the reader.** A flat list of 60 reference
   pages is a phone book, not documentation. The tab is layered: a small number of
   *encapsulated family narratives* at the top carry the ideas and the design reasoning;
   every individual model is still explained in full at the bottom (the enriched reference),
   one click away. A reader chooses their depth.

2. **Make ~443 CI tests legible.** The test suite is the layer's load-bearing structure —
   it is what lets you trust an attribution. But 443 raw test names is noise. The tab groups
   them by *what they guarantee*, clubs the hundreds of mechanical structural checks into
   one pattern-explained page, and gives the two dozen mathematical-identity tests the
   first-class, one-section-each treatment they deserve.

The bar: a reader who has never seen the repo can land on the Transform tab and, at their
chosen depth, understand **why** each family of models is shaped the way it is (and what
they could change), **what** every single model produces, and **how** the layer proves
itself correct — without opening the SQL. The narratives explain the design *and its
alternatives* well enough that a contributor arrives with ideas already forming.

Scope:
- **Full**: the Transform tab IA (§5) and the generation/gating spine (§7).
- **Deep**: every page — the family narratives (§6B), the enriched per-model reference
  (§6C), the CI-contract pages (§6D), macros (§6E).
- **Out of scope**: ML and App tabs (separate passes); changing any model SQL, test, or
  `dbt_project.yml` *behaviour* (adding a `meta.family` tag is documentation metadata, not
  behaviour — it does not move model output, see §7).

---

## 2. Source-of-truth map (what backs every page)

Every Transform page is backed by committed source. No page invents behaviour. Counts are
*never* hand-typed in prose — they come from a gate (§7).

| Concern | Source of truth | Surfaced on |
|---|---|---|
| The seven-term identity & physics math | `decomposition/*.mdx` (exists), `int_lap_residual_decomposed.sql` header, `macros/assert_additive_identity.sql` | Decomposition group, Residual family |
| Model DAG / lineage | `transform/target/manifest.json` (`depends_on`), `transform/README.md` DAG | `transform/overview`, every family sub-DAG, every model page |
| Per-model purpose & columns | `models/**/schema.yml` `description` + columns → `manifest.json` | Enriched model reference (§6C) |
| Model family assignment | new `meta.family` in each `schema.yml` (§3) | Family narratives, nav grouping, model→family back-links |
| Design rationale & alternatives | model SQL header comments (already rich — e.g. `int_driver_circuit_era_affinity.sql` explains the LORO-vs-FE history, `normalize_compound`'s scope warning) | Family narratives' "Design notes" sections (§6B) |
| Materialization strategy | `dbt_project.yml` (`staging→view`, `reference→table`, `intermediate→view`, `marts→table`) | `transform/overview` |
| Era/tuning knobs | `dbt_project.yml` `vars` (`era_boundary=2022`, `ghost_short_run_threshold=0.5`, `outlier_exclude_ratio=1.40`) | `transform/overview`, relevant family pages |
| Generic tests (414) | `models/**/schema.yml` test blocks → `manifest.json` `test_metadata` | CI Contract: structural / range / categorical / pairwise pages |
| Singular tests (29) | `transform/tests/assert_*.sql` + `transform/tests/README.md` | CI Contract: identity-closure / domain-constraint / regression-gate pages |
| Lint & byte-stability gates | `transform/.sqlfluff`, `scripts/snapshot_model_hashes.py`, `tests/model_hashes.baseline.json` | CI Contract: regression-gate page |
| Macros | `macros/*.sql` + `macros/README.md` | Macros group (§6E) |
| Seeds (fitted coefficients) | `seeds/*.csv`, `transform/tasks/coefficients/` | Reference-dims family, `transform/overview` |
| Headline counts (60 models / 443 tests) | `scripts/docs_facts.py` (gate), `README.md` | gated snippets only, never prose literals |

**Two design decisions are pre-made and must be honoured everywhere:**

- **The canonical identity is 7-term, and `track_unexplained_s` is *not* in it.**
  `int_lap_residual_decomposed.sql`'s own header marks `track_unexplained_s` as
  "informational; not in `total_explained_s`". The app waterfall's "8-term" view is a
  deliberate, separate presentation choice. Do not let any Transform page restate the
  8-term framing as the identity. (This matches `reference_lap_residuals_identity` — the
  long-standing project ruling.)
- **`driver_skill` is a closure, not an estimate.** It is defined as
  `pace_delta − Σ(six physics terms)`. Every page that touches it says so; none describes it
  as independently fitted.

---

## 3. The model taxonomy (the "smart grouping")

The 60 models split into **8 families**. The family is the unit of narrative: one
encapsulated story page per family (§6B), with every model in that family linked at the
bottom. The assignment is encoded once, in the data, as a `meta.family` key on each model in
`schema.yml`, so the nav grouping, the family back-links on each model page, and the family
sub-DAGs are all generated from one source and can never drift from each other.

```
                         60 models
   ┌──────────────┬──────────────┬───────────────┬──────────────┐
   │  STAGING (12)│ REFERENCE (4)│ INTERMEDIATE  │   MARTS (10) │
   │  Bronze→typed│  seed-backed │     (34)      │   gold layer │
   │    views     │  dimensions  │  5 families ↓ │  ML/app data │
   └──────────────┴──────────────┴───────────────┴──────────────┘
                                        │
        ┌────────────┬─────────────┬────┴────────┬──────────────┐
     PHYSICS (8)  PACE BASE (6)  SKILL (7)   RESIDUAL (9)  STRATEGY (4)
```

| # | Family (`meta.family`) | Members | The one-line idea |
|---|---|---|---|
| 1 | `staging` | `stg_laps`, `stg_laps_qualifying`, `stg_sector_times`, `stg_telemetry`, `stg_weather`, `stg_pits`, `stg_tyre_allocations`, `stg_events`, `stg_results`, `stg_track_status`, `stg_session_status`, `stg_circuit_info` (12) | Rename Bronze to snake_case, cast nanoseconds→seconds, derive validity flags. No joins, no aggregation. |
| 2 | `reference` | `dim_circuits`, `dim_compounds_season`, `dim_constructors`, `dim_drivers` (4) | Seed-backed dimensions: per-circuit physics constants, per-(circuit,compound,season) cliff coefficients, stable IDs. |
| 3 | `physics` | `int_stint_geometry`, `int_lap_fuel_state`, `int_lap_fuel_state_qualifying`, `int_lap_air_state`, `int_lap_thermal_proxy`, `int_dirty_air_tax_component`, `int_corner_metrics`, `int_lap_telemetry_aggregates` (8) | Deterministic and EMA physics state per lap: fuel mass, thermal load, air state, corner g, telemetry cliff signals. |
| 4 | `pace-baselines` | `int_field_pace_curve`, `int_track_evolution`, `int_compound_cliff_predicted`, `int_constructor_structural_pace`, `int_constructor_structural_pace_qualifying`, `int_circuit_x_constructor_interaction` (6) | The reference surfaces every lap is measured against: trimmed field median, rubber/ambient split, compound trajectory, constructor structural pace. |
| 5 | `skill` | `int_constructor_car_fe`, `int_driver_race_skill_loro`, `int_driver_season_ratings`, `int_era_normalized_driver_rating`, `int_driver_circuit_affinity`, `int_driver_circuit_era_affinity`, `int_synthetic_teammate` (7) | De-bias car from driver and shrink the residual: fixed effects, leave-one-race-out, normal-normal conjugate shrinkage, era bridges. |
| 6 | `residual` | `int_lap_residual_decomposed`, `int_lap_residual_decomposed_qualifying`, `int_sector_residual_decomposed`, `int_corner_skill_residuals`, `int_qualifying_decomposed`, `int_tyre_surface_vs_bulk_decoupling`, `int_lap_residual_stint_detrend`, `int_lap_anomaly_flags`, `int_event_corrections` (9) | Where the identity closes: subtract the physics terms, what remains is skill. Plus the hygiene (anomaly flags, outlier corrections) that keeps the residual honest. |
| 7 | `strategy` | `int_pit_strategy_value`, `int_pit_loss_circuit`, `int_constructor_deg_sensitivity`, `int_sc_hazard_history` (4) | Counterfactual strategy value: pit-loss by circuit, per-constructor degradation sensitivity, safety-car hazard rates. |
| 8 | `marts` | `dim_events`, `fct_lap_residuals`, `fct_driver_skill_features`, `fct_cliff_prediction_features`, `fct_stint_features`, `fct_telemetry_deltas`, `fct_ghost_car_pace`, `fct_ghost_race_finish`, `mart_corner_skill_driver`, `mart_degradation_history_envelope` (10) | The gold layer: the contract with `ml/` and `app/`. Two are ML feature marts; the rest power app features. |

Reading order down the sidebar is the DAG's topological order: **staging → reference →
physics → pace baselines → skill → residual → strategy → marts**. A reader walking top to
bottom walks the data the same direction it flows.

> The `marts` family includes `dim_events` even though it is prefixed `dim_`. It is
> materialized in `models/marts/` as a race-event flag table consumed by the fct marts, not a
> seed-backed dimension. The reference generator already groups `dim_events` under the
> "Dimensions" nav subgroup by prefix — keep that nav placement, but tag it `meta.family:
> marts` so its narrative home is the Feature Marts page. Note the divergence in §9.

---

## 4. The CI-block taxonomy (the ~443 tests, grouped)

443 tests is the layer's load-bearing structure, but only ~30 of them are individually
interesting. The split is stark and drives the grouping: **414 generic** (mechanical column
contracts) + **29 singular** (hand-written mathematical assertions). The generic ones are
clubbed by pattern into a few pages with one explanation each; the singular ones get the
first-class treatment.

```
                         443 CI blocks
        ┌───────────────────────────┴───────────────────────────┐
   GENERIC (414)                                          SINGULAR (29)
   one pattern, hundreds of instances              one file, one assertion each
        │                                                        │
  ┌─────┼───────────┬──────────────┐              ┌─────────────┼──────────────┐
STRUCTURAL(339)  RANGE(58)   CATEGORICAL(13)   IDENTITY(13)  DOMAIN(11)   REGRESSION(5)
not_null 293     between 53  accepted_values   additive       bounds &     baseline gates
unique 44        acc_range 4    13             closures       integrity    + byte-stability
uniq_combo 2     row_count 1                                  + sqlfluff lint
              + pair A>B 4
```

| Group | Test kinds | Count | What it guarantees | Page (§6D) |
|---|---|---|---|---|
| **Structural** | `not_null`, `unique`, `dbt_utils.unique_combination_of_columns` | 339 | Grain & completeness: every model's declared key is present and non-duplicated; the join spine never silently fans out. | `ci/structural` (one page, pattern + gated per-model table) |
| **Range & bounds** | `dbt_expectations.expect_column_values_to_be_between` (53), `dbt_utils.accepted_range` (4), `dbt_expectations.expect_table_row_count_to_be_between` (1) | 58 | Physical plausibility: shares stay in [0,1], probabilities in [0,1], pace deltas inside honest envelopes, row counts non-degenerate. | `ci/range-and-domain` |
| **Categorical** | `accepted_values` | 13 | Enum integrity: compound names, air-state classes, era keys, anomaly classes are drawn only from their allowed sets. | `ci/range-and-domain` (clubbed with range) |
| **Pairwise** | `dbt_expectations.expect_column_pair_values_A_to_be_greater_than_B` | 4 | Cross-column monotonicity: CI bounds bracket their mean, confidence rises with sample size. | `ci/range-and-domain` (clubbed) |
| **Identity-closure** | singular `assert_*` | 13 | The additive identities themselves close to tolerance — the most important guarantee in the project. | `ci/identity-closure` (one section each) |
| **Domain-constraint** | singular `assert_*` | 11 | Stint-boundary resets, no future leakage, shrinkage bounds, hazard probabilities, MAD floor, both sessions present. | `ci/domain-constraints` |
| **Regression gates** | singular `assert_*` (inert) + sqlfluff + byte-stability oracle | 5 | Headline statistics don't silently regress; style fixes don't move model output. | `ci/regression-gates` |

The **exact** counts in this table are illustrative of the current tree — they must **not**
be hand-typed onto the pages. Every count on a CI-contract page renders from the gated
`transform-inventory.mdx` snippet (§7), regenerated from `manifest.json`, so the day someone
adds a `not_null` test the page updates itself and CI fails if it wasn't regenerated.

The clubbing rule the user gave ("club smaller explanations into one page you decide"): the
339 structural + 58 range + 13 categorical + 4 pairwise = **414 generic tests collapse to
two pages** (`ci/structural`, `ci/range-and-domain`) because each is one repeated pattern.
The 29 singular tests each carry a unique idea, so they get **three pages** organised exactly
as `transform/tests/README.md` already organises them (identity / domain / regression), one
explained block per test. That is the whole 443, grouped, with the heavy explanation spent
only where there's a unique idea.

---

## 5. Target information architecture (docs.json restructure)

The Transform tab currently has three groups: *The Decomposition* (4 pages), *Models*
(auto-generated reference, four prefix subgroups), *Macros* (6 pages). Restructure to **six
groups**, in DAG reading order:

```
Transform  (icon: layers)
├── Concepts                  (icon: calculator)   — the math, technology-agnostic
│     transform/overview                              ← NEW front door
│     decomposition/seven-term-identity               (exists, polish)
│     decomposition/methodology                       (exists, polish)
│     decomposition/tyre-cliff                         (exists, polish)
│     decomposition/limitations                        (exists, polish)
│
├── How the Layer Works       (icon: workflow)     — the 8 encapsulated family narratives
│     transform/families/staging                      ← NEW
│     transform/families/reference                     ← NEW
│     transform/families/physics                        ← NEW
│     transform/families/pace-baselines                 ← NEW
│     transform/families/skill                           ← NEW
│     transform/families/residual                         ← NEW
│     transform/families/strategy                          ← NEW
│     transform/families/marts                              ← NEW
│
├── Model Reference           (icon: database)     — every model, enriched generated
│     Staging       → reference/models/stg/*   (12)
│     Intermediate  → reference/models/int/*   (34)
│     Marts         → reference/models/fct/*   (9)
│     Dimensions    → reference/models/dim/*   (5)
│
├── The CI Contract           (icon: shield-check) — all 443 blocks, grouped + gated
│     transform/ci/overview                            ← NEW (the test pyramid)
│     transform/ci/structural                           ← NEW (339, clubbed)
│     transform/ci/range-and-domain                      ← NEW (58+13+4, clubbed)
│     transform/ci/identity-closure                        ← NEW (13, one each)
│     transform/ci/domain-constraints                       ← NEW (11)
│     transform/ci/regression-gates                          ← NEW (5 + lint + oracle)
│
└── Macros                    (icon: code)         — the 7 reusable macros
      transform/macros (overview)                    ← NEW index
      reference/macros/*                              (exists; add circuit_id_from_name,
                                                       posterior_variance — see §6E)
```

**Why six groups, not three:** the three current groups conflate *concept* (Decomposition),
*system* (the missing narrative layer), and *lookup* (the flat reference). The reader who
wants ideas, the reader who wants to find one model, and the reader who wants to verify the
math are three different readers; each gets a group. The reading order is the DAG order, so
the sidebar itself teaches the pipeline.

**Vocabulary (reused verbatim from the Data tab so the four layer tabs read identically):**
"Overview" front-door page per group where useful; "Concepts" mirrors Data's conceptual
framing; "Model Reference" mirrors "Bronze Schemas"; "The CI Contract" is the Transform
analogue of Data's "Quality & Coverage". Group icons reuse the Data tab's set: `database`
(reference), `shield-check` (quality/CI), `workflow` (how-to), `code` (deep/macros).

Page slugs: new authored pages live under `transform/` (`transform/overview`,
`transform/families/*`, `transform/ci/*`, `transform/macros`). Generated model pages stay at
`reference/models/<subdir>/*` (no file moves — same decision the Data tab made for schemas).
Generated macro pages stay at `reference/macros/*`.

---

## 6. Page specs

Each spec gives **purpose**, **source of truth**, **Mintlify components**, **CONVENTIONS
notes**. Authored MDX unless marked *generated*.

### 6A. Concepts group

#### `transform/overview` — the layer's front door *(NEW)*
- **Purpose**: one screen that orients a cold reader to the whole layer — what it reads
  (Bronze Parquet), what it produces (feature marts), the dbt+DuckDB choice, the
  materialization strategy, the tuning knobs, and a clickable map of the 8 families.
- **Source**: `transform/README.md`, `dbt_project.yml` (materializations + `vars`),
  `manifest.json` (the DAG).
- **Mintlify**:
  - Opening full-width flowchart: `Bronze Parquet → Staging → {Reference, Physics} → Pace
    Baselines → {Skill, Residual Decomposition} → Strategy → Feature Marts → {ml/, app/}`
    **(corrected in Part 2 — Skill and Residual are parallel siblings off Pace Baselines, not
    sequential; see the correction note after the §6B family table)**, each family node
    labelled with its member count. Built in Part 2 as a fenced ` ```mermaid ` block (not a
    `<Mermaid>` tag — matches §8's "confirmed by the Data tab's actual usage" rule); no `click`
    directives, matching Part 1's same call for the per-model lineage diagrams (uncertain
    Mintlify support, no render-test path).
  - `<CardGroup cols={2}>` — one card per family, icon + one-line idea + link (the same
    cards close every family page, so the map is navigable both directions). Built in Part 2 as
    a page-local block, not a shared snippet (no second consumer existed yet — anti-premature-
    abstraction, same call as Part 1's deviation 3). Revisit extraction into a shared snippet
    once Part 3 needs the identical 8 cards on a second page.
  - `<Tabs>` "How the layer is built" — a tab per materialization tier (views for
    staging/intermediate = always-fresh, zero storage; tables for reference/marts =
    materialized once, fast to query) explaining *why* each tier chose view vs table.
  - `<Accordion>` "Tuning knobs" — the three `dbt_project.yml` `vars` (`era_boundary`,
    `ghost_short_run_threshold`, `outlier_exclude_ratio`), each with what moving it does and
    where it propagates. This is the first "a contributor could change this" surface.
  - By-the-numbers strip rendered from the gated snippet (60 models, 443 tests, 8 families)
    — never hand-typed.
- **CONVENTIONS**: present tense; no "v0.2"/phase labels; counts from the gate only.

#### `decomposition/{seven-term-identity, methodology, tyre-cliff, limitations}` — polish *(exists)*
- **Purpose**: these four already carry the math at a high standard (LaTeX identity, KM
  survival, per-term derivations). The polish: (1) add a closing `<CardGroup>` from each into
  the relevant *family narrative* (e.g. seven-term-identity → `families/residual`) so the
  concept pages and the system pages cross-link; (2) confirm the CI-invariant SQL block on
  `seven-term-identity` links to `ci/identity-closure` (its enforcement); (3) sweep for any
  8-term drift (§2).
- **Source**: existing pages; `assert_lap_7term_identity.sql`.
- **CONVENTIONS**: leave the math; only add cross-links and fix the identity framing if any
  page implies `track_unexplained_s` is part of the closure.

---

### 6B. How the Layer Works — the 8 family narratives *(all NEW)*

This is the heart of the user's request: **encapsulated** narratives at the top, **every
model** explained at the bottom (via links into §6C), and a clean section in each that gives
a contributor the design reasoning and the alternatives — without ever saying "here is an
alternative so you can change it." It reads as ordinary, confident technical rationale.

**Every family page follows the same five-part template** (so the eight read as a set):

1. **What this family does** — 2–3 sentences. The family's job, its single upstream input
   family and single downstream consumer family.
2. **The sub-DAG** — a focused `<Mermaid>` showing *only* this family's models plus their
   immediate upstream/downstream neighbours (generated thin from `manifest.json`, see §7).
   This is the "smart grouping made visual": the reader sees the 6–9 models of this family as
   one connected unit, not lost in the 60-node global graph.
3. **How it works** — the encapsulated explanation with **light code**: one or two short,
   representative SQL snippets (not the whole model — the characteristic clause), the key
   formula in LaTeX where there is one, and a `<Steps>` walk for families with a clear
   pipeline (e.g. skill: `car FE → LORO baseline → per-cell shrink → era bridge`).
4. **Design notes** — a `<Tabs>` or `<AccordionGroup>` block, **"Why this shape"** and
   **"Other approaches"**:
   - *Why this shape* states the rationale already living in the model SQL headers (these are
     unusually rich — e.g. `int_driver_circuit_era_affinity.sql` explains why the era split
     exists and why the FE baseline replaced the LORO teammate baseline; `normalize_compound`
     carries a scope warning about where *not* to apply it).
   - *Other approaches* names the credible alternatives at the same altitude — what a
     different defensible design would do and the trade-off it makes (e.g. "shrinkage toward a
     hierarchical circuit-type prior instead of the driver's global mean", "a mixed-effects
     fit instead of two-stage FE + conjugate posterior", "quadratic compound trajectory vs the
     hockey-stick hinge"). Stated as engineering trade-offs, not as a to-do list. A reader
     finishes the section already weighing options.
5. **Every model in this family** — a `<CardGroup cols={3}>`, one card per member, linking to
   its enriched reference page (§6C). This is the "every single transform explained at the
   bottom" requirement: the narrative encapsulates; the cards open the full detail.

The eight pages, with their specific load:

| Page | Sub-DAG anchor | Light-code centrepiece | Design-notes axis |
|---|---|---|---|
| `families/staging` | Bronze sources → 12 stg views | `stg_laps` rename+cast+validity-flag pattern; the nanosecond→seconds cast | views vs materialized staging; how much cleaning belongs in staging vs intermediate; the `TrackStatus` decode lives here, not in Bronze |
| `families/reference` | seeds → 4 dims | how `dim_compounds_season` joins the fitted cliff seed; `circuit_id_from_name` slugification | seed-backed constants vs live re-fit each build; the `tasks/coefficients/` survival fitter → seed → promote flow |
| `families/physics` | stg → 8 physics models → residual inputs | the fuel-mass arithmetic (`m₀ − r(t−1)`); the EMA thermal/air accumulation; stint-boundary reset | deterministic physics (fuel) vs fitted (weight penalty `w`); EMA τ choice; per-sector air-state classification vs continuous wake metric |
| `families/pace-baselines` | stg → 6 baseline models → residual | the trimmed-mean field median + 5-lap centred window; rubber/ambient joint identification via monotonicity asymmetry | trimmed median vs robust regression baseline; joint rubber+ambient identification vs separate fits; grouped-median constructor pace (today, re-centred by race mean) vs the full HDFE panel regression its own header names as successor (built separately, in Skill, as `int_constructor_car_fe` — see the correction note after this table) |
| `families/skill` | baselines → 7 skill models (parallel to residual, see correction below) | the normal-normal conjugate posterior (`bayesian_shrinkage` macro); de-biased car FE; LORO leave-one-race-out | conjugate shrinkage vs full Bayesian/mixed-effects; LORO vs teammate-relative vs field-anchored (the page states why FE won); era split at 2022 vs continuous era covariate |
| `families/residual` | physics + baselines → 9 residual models (not skill, see correction below) | the 7-term subtraction; the `assert_additive_identity` closure; anomaly MAD-floor; outlier correction weights | closure-defined residual vs independently-fitted skill (why closure); MAD floor 0.10s vs adaptive; soft-downweight band `[1.20, 1.40)` vs hard cut |
| `families/strategy` | stg + physics + baselines + residual → 4 strategy models | pit-loss-by-circuit estimate; per-constructor deg-sensitivity hinge; SC hazard rate per lap | empirical pit-loss vs modelled; per-constructor deg slope (centred) vs single field slope; SC hazard as historical frequency vs a fitted hazard model |
| `families/marts` | all upstream → 10 marts → ml/app | the two ML feature marts' contract (enforced column types); ghost-car counterfactual recombination; the deg-envelope grain | one wide mart vs many narrow; contract-enforced schemas vs convention; ghost-car SE propagation via `normal_cdf` vs Monte-Carlo |

> **Correction found in Part 2 (2026-06-22), verified against live `ref()` calls, not assumed:**
> Skill and Residual Decomposition are **parallel siblings**, both reading Pace Baselines (and
> Physics/Staging) — neither depends on the other. None of the 7 skill models `ref()` anything
> in the residual family (`int_driver_race_skill_loro` builds its own LORO estimate straight
> from `int_field_pace_curve`/`int_lap_fuel_state`/`int_track_evolution`, not from
> `int_lap_residual_decomposed`); none of the 9 residual models `ref()` anything in the skill
> family. They reconverge only at Marts (`fct_driver_skill_features` is the one model that reads
> skill; everything else in residual feeds Marts directly or via Strategy). `int_constructor_car_fe`
> is sourced from `{{ source('fits', 'constructor_car_fe') }}` (an external pyfixest artifact),
> not from any dbt model — it's a root node within the skill family, not downstream of anything.
> **This means §6A's overview-diagram text below ("...Pace Baselines → Skill → Residual
> Decomposition → Strategy...") and §5's nav-order prose are wrong about Skill/Residual
> ordering** — `transform/overview.mdx` (built in Part 2) already draws the corrected
> parallel-fork version; carry that correction into the `families/skill` and `families/residual`
> sub-DAGs in Parts 4–5, don't regenerate the linear-chain version this table originally implied.

> **Correction found in Part 4 (2026-06-22), verified against the SQL header and `schema.yml`,
> not assumed:** `int_constructor_structural_pace` does **not** use "high-dimensional fixed
> effects," despite its (now-fixed) `schema.yml` description having said so. The model's own
> SQL header calls the current grouped-median-by-constructor approach "a placeholder for the
> full panel regression spec (pyfixest HDFE fit)" and names the intended replacement
> (`feols` with CRV1 clustering). That replacement was actually built, but as a separate,
> narrowly-scoped model in the Skill family (`int_constructor_car_fe`, reading an external
> `pyfixest` fit) rather than as a rewrite of this one — `int_constructor_structural_pace` has
> 10+ downstream consumers, including the calibration-gated `fct_ghost_car_pace` /
> `fct_ghost_race_finish` marts that must stay byte-identical, so swapping its estimator in
> place was a bigger blast radius than adding the FE model alongside it. The table cell above
> reflects this; `int_constructor_structural_pace`'s `schema.yml` (model description plus the
> `constructor_structural_pace_s`/`_se_s`/`panel_observations_n` column descriptions, which
> separately overclaimed a fitted α-coefficient and a clustered SE) was corrected in Part 4 to
> match — fixed at the source, not just on the docs page, since `gen_dbt_reference.py` (Part 6)
> reads these descriptions verbatim.

- **CONVENTIONS**: each page states its rationale *inline* (no `AD-N`/plan citations). No
  version/phase framing — the model SQL headers contain a few "BREAKING CHANGE (date)" and
  "(initial transform)" lines that must **not** be copied into the docs; state the present
  behaviour only. Counts (member counts) come from the gated snippet, but small family
  member counts can also be expressed structurally ("the seven skill models") since the
  family membership is itself gate-checked via `meta.family` (§7).

---

### 6C. Model Reference — every model, enriched *(generated)*

The current `gen_dbt_reference.py` emits a thin page per model: a metadata table + a columns
table. Enrich the generator (§7) so each of the 60 pages becomes a genuine reference entry
*without* hand-editing (the pages stay auto-generated and drift-gated):

- **Frontmatter + family banner**: a `<Note>` linking up to the model's family narrative
  (`meta.family` → `/transform/families/<family>`) so every leaf page has a path back to its
  story.
- **Lineage**: a per-model `<Mermaid>` (immediate upstream `ref()`s → this model →
  immediate downstream consumers), generated from `manifest.json` `depends_on`/`child_map`.
  Today the page only lists upstream names in a table cell; the diagram makes lineage legible.
- **Columns table** (exists): keep, but render the per-column tests as small badges
  (`not_null`, `unique`, `between[0,1]`, `accepted_values{…}`) pulled from `test_metadata`,
  so a reader sees a column's *contract*, not just its description. Link each badge kind to
  its CI-contract page (§6D).
- **Contract badge** (exists for `contract.enforced`): keep; for the two ML feature marts,
  add a `<Warning>` that breaking a column type fails the build (the `ml/` handoff contract).
- **Tests-on-this-model summary**: a one-line "N tests guard this model" rendered from the
  manifest, linking to the relevant CI pages. (Top guarded models for sanity:
  `int_constructor_deg_sensitivity` 27, `fct_ghost_car_pace` 22,
  `mart_degradation_history_envelope` 22, `int_driver_circuit_era_affinity` 19,
  `fct_lap_residuals` 19 — these surface naturally from the generator, never hand-typed.)
- **Source-rationale excerpt**: optionally surface the first paragraph of the model's SQL
  header comment as a "Notes" block. The SQL headers are already documentation-grade; piping
  the lead paragraph in (whitespace-normalised) gives each leaf page real prose at zero
  hand-maintenance cost. Gate-safe because it's derived, not authored. *(Decide in Part 1
  whether to parse SQL headers or rely solely on `schema.yml` descriptions — see §7's open
  choice.)*

- **CONVENTIONS**: the generator must strip any "BREAKING CHANGE", "(initial transform)",
  "v0.2", `#N` plan-reference, or `§N` citation it lifts from SQL headers — those are process
  history banned from committed docs. Add a sanitiser to the generator (a regex denylist) so
  enrichment can never reintroduce phase framing. The `index.md` keeps its gated total.

---

### 6D. The CI Contract — all 443 blocks, grouped *(authored + gated)*

#### `transform/ci/overview` — the test pyramid *(NEW)*
- **Purpose**: the one-screen mental model of the suite. Why 443 tests, what each tier buys,
  and the "passes when it returns zero rows" convention.
- **Source**: `manifest.json` (the taxonomy), `transform/tests/README.md`,
  `transform/.sqlfluff`.
- **Mintlify**: a `<Mermaid>` or styled table rendering the §4 pyramid (Generic 414 →
  Structural/Range/Categorical/Pairwise; Singular 29 → Identity/Domain/Regression), every
  number from the gated snippet. `<Info>` on the zero-rows convention. `<CardGroup>` to the
  five detail pages. A `<Note>` on the three test states from `tests/README.md` (Active /
  Inert / Placeholder) and what `--exclude tag:placeholder` measures.

#### `transform/ci/structural` — grain & completeness (the 339) *(NEW)*
- **Purpose**: explain the single pattern behind 339 mechanical tests once, then let a gated
  table carry the per-model breakdown. This is the big clubbing win.
- **Source**: `manifest.json` (`not_null`/`unique`/`unique_combination_of_columns`),
  `schema.yml`.
- **Mintlify**:
  - `<Tabs>` "not_null" / "unique" / "unique_combination" — each: one paragraph on what it
    guarantees, a representative `schema.yml` snippet, and *why every model declares its key*.
  - A **gated table** (`transform-inventory.mdx` snippet) of every model × its structural test
    count, sortable mentally by the reader. Never hand-typed.
  - `<Accordion>` "Why the join spine can't fan out" — the `unique` on every surrogate `lap_id`
    is what guarantees a lap is counted once through 60 models; tie it to the identity (a
    duplicated lap would break closure).
- **CONVENTIONS**: every count from the snippet; structural prose otherwise.

#### `transform/ci/range-and-domain` — plausibility, enums, monotonicity (58+13+4) *(NEW)*
- **Purpose**: club the three "value-shape" generic families. They're small individually but
  share a theme: physical/logical plausibility.
- **Source**: `manifest.json` (`expect_column_values_to_be_between`, `accepted_range`,
  `accepted_values`, `expect_column_pair_values_A_to_be_greater_than_B`,
  `expect_table_row_count_to_be_between`), `schema.yml`.
- **Mintlify**:
  - `<AccordionGroup>`: "Bounded shares & probabilities [0,1]" (the telemetry shares,
    `int_sc_hazard_history` probabilities), "Honest envelopes" (field-pace ±5s band,
    pace-delta ranges), "Enum integrity" (`accepted_values`: compounds, air-state classes,
    era keys, anomaly classes — list the allowed sets, which are themselves gate-checked),
    "Cross-column monotonicity" (the 4 pair tests: CI low ≤ mean ≤ CI high, confidence rises
    with n).
  - A gated table of the `between`/`accepted_values` instances by model+column.
- **CONVENTIONS**: the allowed-value sets are facts from `schema.yml`; render them, don't
  invent. Counts gated.

#### `transform/ci/identity-closure` — the additive identities (13 singular) *(NEW)*
- **Purpose**: the crown jewels. One explained block per identity test: what it asserts, the
  identity in LaTeX, the tolerance, and the model it guards. This is where the "0.1 ms on
  every lap" promise is made concrete and enforced.
- **Source**: `tests/assert_*.sql` (the 13 identity tests),
  `macros/assert_additive_identity.sql`, `transform/tests/README.md` identity table.
- **Mintlify**:
  - Lead with the `assert_additive_identity` macro: the one reusable closure check, shown
    once with its `<CodeGroup>` invocation, then referenced by the per-test blocks.
  - `<AccordionGroup>`, one `<Accordion>` per test (lap 7-term, qualifying 7-term, sector,
    corner closure, residual decomposition, deg-slope centring, cliff-hinge centring, affinity
    shrinkage bounds, era-rating shrinkage bounds, affinity CI brackets mean, ghost-car
    self-consistency, example closure, sector-aggregates-to-lap placeholder). Each: the
    assertion in one line, the formula, the guarded model (linked to §6C), and the status
    badge (Active / Placeholder) from `tests/README.md`.
  - Cross-link the lap-7-term accordion to `decomposition/seven-term-identity` (concept) and
    `families/residual` (system).
- **CONVENTIONS**: status badges are facts from `tests/README.md`; keep them in sync (or
  better, generate the active/placeholder status from the test SQL via the inventory script —
  a `SELECT 1 WHERE FALSE` body = placeholder; decide in Part 7).

#### `transform/ci/domain-constraints` — physical & statistical invariants (11 singular) *(NEW)*
- **Purpose**: the domain singular tests that aren't pure additive closures.
- **Source**: `tests/assert_*.sql` (stint boundary integrity, no future leakage, synthetic
  teammate identity, field-pace honest range, MAD floor, track-evolution monotone, SC hazard
  probability bounds, driver-skill residual reasonable, raw-laps-has-both-sessions,
  p_beats_next ≥ ½, constructor coefficient signs), `tests/README.md` domain table.
- **Mintlify**: `<AccordionGroup>` one per test — what it asserts, why it matters (e.g.
  "no future leakage" guards the trailing-window EMAs from look-ahead, which would inflate
  skill), the guarded model, status. Group the two most pedagogically rich
  (`assert_no_future_leakage` loads a known fixture stint and asserts exact values;
  `assert_stint_boundary_integrity` checks fuel/thermal/air all reset together) with a short
  `<Steps>` of how the test actually runs.
- **CONVENTIONS**: present tense; cross-link to the physics/skill families.

#### `transform/ci/regression-gates` — non-regression & byte-stability (5 + lint + oracle) *(NEW)*
- **Purpose**: the gates that aren't row-returning data tests: the inert baseline-comparison
  tests, the `sqlfluff` lint gate, and the byte-stability oracle.
- **Source**: `tests/assert_constructor_pace_propagates.sql`,
  `tests/assert_residual_variance_shrinks.sql` (both inert), `transform/.sqlfluff` +
  `.sqlfluffignore`, `scripts/snapshot_model_hashes.py`, `tests/model_hashes.baseline.json`,
  `tests/README.md` regression-gate + lint sections.
- **Mintlify**:
  - `<Warning>` on the **inert** state: these pass vacuously in a fresh checkout because the
    baseline snapshot isn't committed — explain why (the snapshot is an approval artifact,
    regenerated on intentional logic change) and what "inert" means, mirroring
    `tests/README.md` exactly.
  - `<Accordion>` "Byte-stability oracle" — the order-independent content hash, the
    `fct_*`-only enforcement, the `duckdb`-pinned-for-float-stability detail, and the
    `make lint-oracle-snapshot` regenerate-and-commit ritual. (This is the resolved
    intra-query float-reorder finding — state the *behaviour*, not the debugging history.)
  - `<Accordion>` "sqlfluff lint" — the hard-fail gate, `.sqlfluff` wiring to the `ci` target,
    and the single excluded model (`fct_ghost_race_finish`, parse-depth limit).
- **CONVENTIONS**: describe the present contract; the byte-stability story must read as "this
  is the gate" not "this is the bug we found".

---

### 6E. Macros group *(authored index + generated pages)*

#### `transform/macros` — overview *(NEW)*
- **Purpose**: a one-screen index of the 7 macros grouped by purpose (validation:
  `assert_additive_identity`; shrinkage: `bayesian_shrinkage`, `posterior_variance`; filters:
  `clean_lap_filter`; mapping: `normalize_compound`, `circuit_id_from_name`; numeric:
  `normal_cdf`), each one line + link to its generated reference page.
- **Source**: `macros/README.md`, `macros/*.sql`.
- **Mintlify**: `<CardGroup>` by purpose; `<Note>` that macros eliminate cross-model pattern
  duplication so a definition lives once (e.g. `clean_lap_filter` is "the canonical clean-lap
  definition; use it everywhere skill is extracted").
- **CONVENTIONS**: `macros/README.md` currently cites "§3.2 of the implementation plan" and
  numbered models like "#4, #5" — these are dangling plan references banned by CONVENTIONS.
  When the overview page is authored, restate the *purpose* inline ("used by the
  identity-closure tests and any additive model") and **flag the README for the same fix** in
  Part 8 (it's source-of-truth for the generated pages, so the dangling refs propagate).

#### `reference/macros/*` — fix the gap *(generated)*
- The nav currently lists 6 macro pages but there are **7** macros; `circuit_id_from_name` is
  missing from nav and `posterior_variance` is present in the file set. Confirm
  `make docs-reference` regenerates all 7, add `reference/macros/circuit_id_from_name` to nav,
  and verify `mintlify broken-links` is clean. (The Data-tab plan already noted
  `make docs-reference` surfaces pre-existing macro/CLI/ML drift — expect to regenerate those
  too; they're gated autogenerated files with one correct output, so don't revert them.)

---

## 7. Generation & gating (how counts and families stay honest)

The whole tab must obey "counts live behind a gate." Three generation surfaces:

**(a) `scripts/gen_dbt_reference.py` — enrich (existing, extend).**
- Add: per-model lineage `<Mermaid>` (from `depends_on` + `child_map`), family banner (from
  `meta.family`), per-column test badges (from `test_metadata`), tests-on-this-model count,
  and the optional SQL-header-lead "Notes" block (with the phase-framing sanitiser, §6C).
- Keep it idempotent and drift-gated by the existing `reference-drift` CI job
  (`make docs-reference` → `git diff --exit-code`). The enrichment changes the template, so
  regenerating is part of Part 6; the gate then keeps it current.
- **`meta.family` does not move model output.** It's manifest metadata, read by the generator
  only. Confirm against the byte-stability oracle in Part 1 that adding `meta:` keys to
  `schema.yml` leaves all `fct_*` hashes identical (it will — `meta` isn't in any SELECT).

**(b) `scripts/transform_docs_facts.py` — the gated inventory snippet (NEW).**
- Mirrors `scripts/ingestion_docs_facts.py`'s write/check shape (the Data tab's
  `bronze-coverage.mdx` pattern). Reads `manifest.json` + the `tests/assert_*.sql` files and
  writes `docs/snippets/transform-inventory.mdx`: the §4 taxonomy counts (per test kind,
  per group), the §3 family member counts, the per-model structural/range/test tables, and
  the active/placeholder status of each singular test (placeholder = `SELECT 1 WHERE FALSE`
  body). Every count on every CI page and family page `import`s from this snippet.
- Wire into `make docs-coverage` / `make docs-coverage-check` (extend, don't duplicate) and a
  new `transform-inventory-drift` job in `.github/workflows/docs-ci.yml`, alongside
  `bronze-coverage-drift` / `overview-numbers-drift`.

**(c) `scripts/docs_facts.py` — extend reconciliation (existing).**
- It already gate-checks `443 tests` / `60 models` across `README.md` and `ml/overview.mdx`.
  Add the new Transform narrative pages that state these counts (e.g. `transform/overview`'s
  by-the-numbers strip) to its reconcile set, so the headline figures can't diverge between
  README and the Transform front door.

**Open choice for Part 1 (decide, don't ask):** whether the family sub-DAGs and per-model
lineage diagrams are (i) generated as committed Mermaid inside the `.mdx`/snippet, or (ii)
authored once and gate-checked for node-set membership against `manifest.json`. Recommend
(i) — fully generated — so a new model or a changed `ref()` updates the diagrams and the
drift gate catches a stale one, matching how the rest of the reference is generated. Author
only the *prose* around generated diagrams.

---

## 8. The visual system (the "go all out" payload)

The tab should look like the most carefully-made part of the site, because it is. The system,
applied consistently:

- **One diagram language.** Mermaid everywhere, fenced ` ```mermaid ` blocks (not a
  `<Mermaid>` JSX tag — confirmed by the Data tab's actual usage). Three scales: the global
  DAG (`transform/overview`), the family sub-DAG (each family page, 6–9 nodes), the model
  lineage (each reference page, ~3–7 nodes). Same node styling and the project red (`#e40404`)
  for the model under focus.
- **Math gets LaTeX, always.** `$$…$$` blocks for every identity and estimator (the
  decomposition pages set the standard; the family pages match it). Never an ASCII formula
  where a rendered one is possible.
- **The "current vs alternative" tab pattern.** The Design-notes block on each family page
  uses `<Tabs>` with a "How it works now" tab and an "Other approaches" tab, or an
  `<AccordionGroup>` with one accordion per alternative. Consistent across all eight so the
  reader learns the pattern once.
- **Light code, not whole models.** SQL snippets are the *characteristic clause* (the fuel
  arithmetic, the shrinkage call, the closure subtraction) in `<CodeGroup>`, 5–15 lines,
  never a full model. The full model is one click away in §6C.
- **Badges for contracts.** Per-column test badges on reference pages; status badges
  (Active/Inert/Placeholder) on CI pages; the contract-enforced badge on the two ML marts.
- **CardGroup as the connective tissue.** Every family page ends with member cards (→
  reference); every reference page begins with a family card (→ narrative); the overview and
  CI-overview pages are card hubs. The reader can always go up, down, or sideways.
- **No screenshots needed** (unlike the Data tab's hero) — the Transform tab's visuals are
  diagrams and math, which is correct for a compute layer. If one hero image helps the
  `transform/overview` front door, reuse the existing `docs/images/` convention; don't add a
  capture pipeline.

---

## 9. CONVENTIONS obligations (the sweep, restated for this tab)

- **No version/phase framing.** The model SQL headers contain `BREAKING CHANGE (date)`,
  `(initial transform)`, `v0.2`, `#N`, `§N`, `Pillar 2` — all banned in committed docs. The
  generator sanitiser (§6C) strips them from any lifted text; authored pages never introduce
  them. `macros/README.md`'s `§3.2`/`#4,#5,#6` and `tests/README.md` are clean of *version*
  framing but `macros/README.md` has the dangling-plan-ref problem (§6E) — fix at source in
  Part 8.
- **Counts behind a gate or not in prose.** All model/test/family counts render from
  `transform-inventory.mdx` (§7b) or `docs_facts.py`. The only structural exception:
  spelled-out small family sizes ("the seven skill models") are allowed because `meta.family`
  membership is itself gate-checked.
- **Every reference resolves in a clone.** No links to `_roadmap/**`,
  `SYSTEM_DESIGN_AUDIT.md`, `AD-N`, `R-N`, this plan. The byte-stability and float-reorder
  *findings* (from project memory) are stated as present behaviour, never as debugging history.
- **One vocabulary.** Group/section names match the Data tab (§5). The identity is **7-term**
  everywhere (§2); `driver_skill` is a **closure** everywhere.
- **The `dim_events`-in-marts divergence (§3) is documented, not hidden.** Its nav home (prefix
  subgroup "Dimensions") and its narrative home (`families/marts`) differ on purpose; the
  `families/marts` card for it carries a one-line note so the reader isn't confused that a
  `dim_` model lives in the marts story.
- **Reconcile outward-facing source in Part 8**: `transform/README.md` (its DAG and the
  hosted doc links), the stale Makefile `help` strings (`dbt-dev` says "53 dbt models",
  `dbt-test` says "336 dbt tests" — both stale vs the gated 60/443; these `help` lines aren't
  in the `docs_facts` reconcile set, so flag them and fix), and `docs/AGENTS.md` if it still
  describes the Transform tab's old three-group shape.

---

## 10. Build sequence (the 8 parts, expanded)

| Part | Builds | Verify before pausing |
|---|---|---|
| **1** | docs.json six-group nav; `meta.family` on all 60 models; `transform_docs_facts.py` + enriched `gen_dbt_reference.py`; `transform-inventory-drift` CI job | byte-stability oracle unchanged after `meta:` edits; snippet write→check round-trips; `mintlify validate` (new nav pages will warn until authored — expected) |
| **2** | `transform/overview` + polish 4 decomposition pages | `docs-coverage-check`; `mintlify broken-links` (forward-refs into unbuilt family pages expected) |
| **3** | `families/{staging,reference,physics}` | sub-DAGs render; member cards resolve to §6C pages |
| **4** | `families/{pace-baselines,skill}` | design-notes pattern consistent with Part 3 |
| **5** | `families/{residual,strategy,marts}` | residual page cross-links to decomposition + identity-closure |
| **6** | Regenerate all 60 enriched model pages; `reference-drift` gate green | every model page has family banner + lineage + test badges; `make docs-reference` then `git diff --exit-code` |
| **7** | `transform/ci/{overview,structural,range-and-domain,identity-closure,domain-constraints,regression-gates}` | every count from the snippet; identity formulas render; status badges match `tests/README.md` |
| **8** | `transform/macros` + macro nav fix; CONVENTIONS sweep; reconcile README/Makefile-help/AGENTS; full gate run | `docs-audit` + `docs-facts` + `docs-coverage-check` + `transform-inventory-drift` + `reference-drift` + `mintlify validate`/`broken-links` all green |

Pause after each part, report status, do not commit.

---

## 11. Definition of Done

- [ ] Transform tab has six groups in DAG reading order (§5); every authored page exists and
      renders; `mintlify validate` + `broken-links` clean.
- [ ] **Smart grouping**: 8 family narratives, each with sub-DAG + light code + a clean
      "why this shape / other approaches" design-notes block + member cards. A contributor
      reading any family page comes away with the rationale *and* alternatives.
- [ ] **Every model explained at the bottom**: all 60 reference pages enriched (family banner,
      lineage diagram, per-column test badges, guarded-test count); each links up to its
      family and down to nothing it can't open.
- [ ] **All 443 CI blocks documented and grouped**: 414 generic clubbed into 2 pattern pages
      with a gated per-model table; 29 singular across 3 pages with one explained block each;
      lint + byte-stability oracle covered. Every count renders from the gate.
- [ ] All counts behind `transform-inventory.mdx` / `docs_facts.py`; zero hand-typed model/
      test/family numbers in prose.
- [ ] CONVENTIONS sweep clean: no phase/version framing (generator sanitiser in place), no
      dangling plan refs, 7-term identity consistent, vocabulary matches the Data tab.
- [ ] `transform/README.md`, stale Makefile `help` counts, and `docs/AGENTS.md` reconciled.
- [ ] All CI gates green: `docs-audit`, `docs-facts`, `docs-coverage-check`,
      `transform-inventory-drift`, `reference-drift`, Mintlify validate + broken-links.
- [ ] Adding a new model or test, then running `make docs-coverage && make docs-reference`,
      updates the family member counts, the sub-DAG, the reference page, and the CI inventory
      with no hand-edits — and the drift gates fail if you forget to regenerate.
```
