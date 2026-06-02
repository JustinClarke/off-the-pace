# Transform Layer — Cleanup & Quality-Elevation Plan

> Status: IN PROGRESS, checkpointed for multi-session execution. Execution is user-gated (per
> standing rule: never commit/push without explicit ask — everything below is uncommitted working-tree state).
> Scope: `transform/` (dbt Core + DuckDB). Goal: raise documentation, methodology rigor, code
> quality, and CI hygiene to a consistent, contributor-ready standard — and lock in a repeatable
> "add a new transform + test" recipe that conforms to CI.

---

## CHECKPOINT STATUS & HANDOFF — read this first

A fresh session with zero prior context should start here, not at §0.

### Dashboard (verified 2026-06-19 by re-running the actual gates, not by reading diffs)

| # | Item | Status | Verified by |
|---|---|---|---|
| Phase 0 | Mechanical cleanup (orphan schema patches, dangling tests, doc moves) | ✅ DONE | `dbt parse` → **zero** missing-node warnings |
| Phase 1 | Documentation completeness (marts schema.yml, macros/README, model-authoring standard) | ✅ DONE | `dbt docs generate` → clean, no warnings |
| Phase 2 | Forward-compat (16 `arguments:` migrations + 6 `config:` moves) | ✅ DONE | `dbt parse` deprecation summary → empty (was 16+6) |
| Phase 3.2 | Placeholder tests tagged `tags: ['placeholder']` | ✅ DONE | 3 files tagged; `tests/README.md` table updated |
| Phase 3.3 | pytest coverage for fitters (weight_penalty, constructor_car_fe, degradation_isotonic, survival, provenance, seed_writer, check_freshness) | ✅ DONE | `pytest transform/tasks/coefficients/tests/` → 42/42 pass |
| Phase 3.1 | New singular tests for currently-unguarded invariants | ✅ DONE (session 8) | 2 new tests: `assert_affinity_ci_brackets_mean`, `assert_sc_hazard_probability_bounds`; both PASS, registered in tests/README |
| Phase 4.1 | `contract:` policy decision + doc | ✅ DONE (session 8) | Deliberate narrow-contract policy documented in `models/marts/README.md` (2 ML-input marts only; rest intentionally uncontracted) |
| Phase G | Fix the 11 CI-fixture build errors | ✅ DONE (session 8) | 4 missing fixture sources copied + 7 sparse-SE not_null scoped to multi-obs; `dbt build` ERROR=11→**0**, oracle regen (58/0-missing), all 7 fct_* byte-stable |
| Phase 4.2 | Em-dash normalization (`word-word` → `word  -  word`) | ✅ DONE (this session) | Fixed all 10 confirmed instances: `selectors.yml` ×2, `README.md` ×4, `macros/README.md` ×3, `models/reference/README.md` ×2 (sic, see note), `models/staging/README.md` ×2. Full repo sweep was scoped to `transform/` only — `app/`, `ingestion/` untouched (out of scope, pre-existing unrelated diffs). |
| Phase 4.3 | `make transform-check` target | ✅ DONE | Present in `Makefile`, chains parse→lint→build→test→pytest |
| Phase 4.4 | sqlfluff re-enable rules one at a time | SUPERSEDED by §6 (same work, §6 is the rigorous version) | — |
| §6 Phase A | Lint gate honesty (`.sqlfluff` profile pin) | ✅ DONE | `sqlfluff lint` now connects (exit 1 with real violations, not exit 2 profile-resolution error) |
| §6 Phase B | Byte-stability oracle script | ✅ DONE + NOW VALID | `scripts/snapshot_model_hashes.py` + `make lint-oracle-snapshot`/`lint-oracle-check`. **Session-4 fix:** pinned DuckDB intra-query `settings: threads: 1` (profiles) + excluded volatile `fit_timestamp` from hash → two consecutive builds = **0 drift / 60 models, all 7 fct_* stable**. Gate verified end-to-end (snapshot→rebuild→check exit 0). |
| §6 Phase C | Cosmetic lint batch (LT*/CP* auto-fix) | ✅ DONE + ORACLE-VERIFIED (session 5) | Auto-fix loop: **2,828 → 902** violations (63 model files, +2109/−1287). **Output-neutrality PROVEN session 5** via the documented pristine-vs-edited stash diff: stashed model `.sql` edits → built pristine ci.duckdb → snapshotted baseline → popped → rebuilt edited → `lint-oracle-check` **exit 0, all 7 fct_* byte-stable, zero non-fct drift**. Both builds PASS=413/ERROR=11 (the same pre-existing fixture fails). Residual 902 = LT05 396 (hand-break) + Phase D/E rules (AL01 279, ST07 97, AM05 69, ST01 33, etc.). Edits in working tree, uncommitted. |
| §6 Phase C.5 | LT05 long-line hand-break (the 396 residual) | ✅ DONE + ORACLE-VERIFIED (session 6) | 387/396 were standalone `--` comments → conservatively auto-wrapped to ≤80 (skip separators/tables/`\|`-lines); 9 SQL/jinja + 1 `\|`-comment hand-broken (config()/surrogate_key reflow, BETWEEN splits). **LT05 396→0, total 902→505, no new layout viols.** `dbt parse` clean; current edited tree built (PASS=413/ERROR=11 same pre-existing fails); `lint-oracle-check` **exit 0, all 7 fct_* byte-stable vs the session-5 pre-Phase-C baseline** → Phase C+LT05 proven output-neutral end-to-end. |
| §6 Phase D | Aliasing/structure batch (AL01, ST01/02, AM03, CV11, AL05) | ✅ DONE + ORACLE-VERIFIED (session 6) | `sqlfluff fix --rules AL01,AL03,AL05,RF02,RF04,ST01,ST02,AM03,CV11` + cosmetic settle pass. **AL01 279→0, ST01 33→0, ST02/AM03/CV11/AL05 cleared. Total 505→180.** ⚠️ **Caught a real regression:** AL05 auto-fix stripped `AS t(team_name, pu_family)` (the load-bearing VALUES column-list alias) from `dim_constructors` → Binder Error "team_name does not exist" → 26 downstream skips. Restored the alias + `-- noqa: AL05` (sqlfluff false-positive: it sees table alias `t` as unused under `SELECT *`, blind to the column-list). Swept diff — only this one `\) AS x(cols)` case existed. Rebuilt: **PASS=413/ERROR=11 baseline restored**, `lint-oracle-check` **exit 0, all 7 fct_* byte-stable.** |
| §6 Phase E | Semantic-risk batch (ST07/AM05 + leftovers) | ✅ DONE + ORACLE-VERIFIED (session 7) | **All 181 cleared → lint rule-clean.** Leftovers first (RF02 4 qualify, AL03 2 alias, RF04 2 `position` keyword→`-- noqa: RF04` w/ rationale, ST09 3 operand-flip, ST11 dead-join drop, AM01 redundant-DISTINCT drop, ST05 subquery→CTE). Then **ST07 96→0**: `sqlfluff fix --rules ST07` auto-converted 55, broke 4 models (Binder "ambiguous"/"does not have column" — the documented USING-collapse hazard); manually converted the remaining 41 USING→ON anchored to the correct FROM alias (caught int_corner_skill_residuals where the key lived in `lk` not `cm`). Then **AM05 69→0**: bare `JOIN`→`INNER JOIN` (cosmetic, autofix). Fixed the LT05/LT02 reflow fallout from the longer ON lines. **Oracle exit 0, all 7 fct_* byte-stable** through every batch; build held PASS=413/ERROR=11. 3 non-materialized files (int_pit_loss_circuit/int_sc_hazard_history/int_era_normalized) hand-verified output-neutral (no SELECT* over a converted join). `int_constructor_deg_sensitivity` has 0 ST07 (sqlfluff can't render it) → left untouched. Edits uncommitted. |
| §6 Phase F | Lock gate | ✅ DONE (session 7) | (a) `transform/.sqlfluffignore` excludes the PRS-unparseable `fct_ghost_race_finish.sql` → `sqlfluff lint models/` now exits **0** on a rule-clean tree (CI "green-by-accident" risk DISCHARGED — tree genuinely passes). (b) Oracle baseline moved to committed `transform/tests/model_hashes.baseline.json` (was gitignored `target/`); script DEFAULT_BASELINE updated; regenerated (50 models/8 missing). (c) Wired `lint-oracle-check` into `make transform-check` AND added CI "Gate 1c" step in dbt-ci.yml. (d) **Pinned `duckdb==1.5.3` in requirements.txt** (user chose pin-for-CI) so float-hashes match local↔CI — baseline computed on 1.5.3. (e) Documented honest lint+oracle gate in tests/README.md. NOTE: CI Gate 1b currently fails on the 11 pre-existing fixture errors → oracle Gate 1c unreachable until **Phase G** lands. After G, REGENERATE baseline (more models will materialize). Uncommitted. |

**Build health — NOW IN SCOPE (user directive 2026-06-19 session 7):** `dbt build` on CI fixtures has
11 pre-existing errors (`stg_track_status` fixture parquet missing + 6 `not_null` fails on sparse
driver-circuit-affinity SE/CI columns). Confirmed via `git stash` against original HEAD: HEAD had
**12** errors, current working tree has **11** (one fewer — a dead legacy test patch was removed in
Phase 0, not a real fix). **User asked to FIX these too, AFTER Phase E/F is done** (Phase G below).
Until then they don't block any phase gate above (oracle treats them as pre-existing).

### ✅ Phase G DONE + Phase 3.1 + 4.1 DONE + open-source clarity pass (2026-06-19 session 8)
**Build is now ERROR=0 on fixtures** (was ERROR=11). The "11" was actually **4 missing-fixture-source
errors** (circuit_info, results, session_status, track_status — NOT just track_status as prior note said)
+ **7 not_null fails** on sparse SE/CI cols.
- **Fixtures (root cause 1):** copied real bronze parquet for the 3 fixture races into
  `transform/tests/fixtures/bronze/{track_status,session_status,results,circuit_info}/` (small, 5–19KB each).
  Also extended `ingestion/src/create_fixtures.py` `DATASETS` to all 8 so this is reproducible.
- **Sparse SE (root cause 2):** the 7 cols are NULL **only** on degenerate single-obs fixture cells
  (`SQRT(NULLIF(posterior_var,0))`); on **real dev data they are NEVER null** (verified 998/998, 1359/1359,
  152/152). Fix = scoped `not_null` to `where: n_obs > 1` (affinity) / `n_races > 1` (ratings) in
  `models/intermediate/schema.yml`, with rationale comments. Range checks already ignore NULLs.
- **Oracle baseline REGENERATED** → now 58 models hashed / 0 missing (was 50/8); `fct_ghost_race_finish`
  now materializes + is in baseline + byte-stable. 2 models (mart_corner_skill_driver, stg_tyre_allocations)
  are empty on fixtures → null hash → warn-only (non-fct, acceptable).
- **Phase 3.1 (singular invariant tests):** added `assert_affinity_ci_brackets_mean.sql` (CI brackets
  posterior mean across both affinity models) + `assert_sc_hazard_probability_bounds.sql` (per-lap SC/VSC/any
  hazards ∈ [0,1], any ≥ components). Both registered in tests/README, both PASS.
- **Phase 4.1 (contract policy):** documented deliberate narrow-contract policy in `models/marts/README.md`
  (contracts ONLY on the 2 ML-input marts that bind to `ml/` ONNX pipeline; all other marts intentionally
  uncontracted). Also completed the marts README table (was 5 of 10) + fixed mangled em-dashes.
- **Open-source clarity sweep:** completed staging README table (was 7 of 12 models), fixed
  `race_id=`→`race=` + 4→8 datasets in fixtures/README, swept mangled em-dashes (intermediate/staging/
  coefficients READMEs + create_fixtures.py docstring) to the `  -  ` convention.
- **FINAL VERIFY:** `make transform-check` fully green — parse clean, sqlfluff "All Finished", build
  PASS=502/ERROR=0/SKIP=0, singular tests PASS, oracle "all 7 fct_* byte-stable", pytest 42 passed.
- **Uncommitted (user-gated).** New files: 4 fixture-source dirs of parquet, 2 new singular test `.sql`,
  `transform/tests/model_hashes.baseline.json` (regenerated). Modified: schema.yml, several READMEs,
  create_fixtures.py, tests/README.md, work.md.
- **REMAINING (oracle-independent, optional):** none of the original plan phases are open. Possible future
  polish only: force data into the 2 empty-on-fixture marts if you want 0-missing oracle. Otherwise the
  whole work.md plan (Phases 0–4 + §6 A–F + G + 3.1 + 4.1) is COMPLETE. Decide commit/push strategy
  (see "Risk to flag" — committing flips CI lint gate to genuinely-enforcing; whole effort should land
  as one reviewed branch).

### Phase G — Fix the 11 pre-existing CI-fixture build errors (user directive, do AFTER E/F)
The 11 ERROR=11 baseline breaks into two root causes:
1. **Missing `stg_track_status` fixture parquet** → cascade of skips + any test depending on it.
   Fix: add the missing fixture parquet under `tests/fixtures/bronze/` (mirror an existing
   bronze fixture's schema) so the staging model materializes on CI.
2. **6 `not_null` failures on sparse SE/CI columns** (`int_driver_circuit_era_affinity` shrunk_affinity_se_s
   / CI bounds, `int_driver_season_ratings` shrunk_residual_se_s) — these are legitimately NULL when a
   driver-circuit-era cell has too few races to estimate an SE. Fix: either (a) relax the test to
   `not_null` only where `n_races >= min`, (b) COALESCE a sentinel, or (c) drop `not_null` for genuinely
   sparse stats columns and document why. Decide per-column; don't blanket-suppress.
**Gate:** `dbt build --target ci` reaches ERROR=0 on fixtures; oracle still exit 0 (fct_* byte-stable).

### ✅ ORACLE FIXED — the byte-stability gate now works (resolved 2026-06-19 session 4)

**The §6 Phase B oracle is valid. The pipeline IS byte-reproducible build-to-build once DuckDB's
*internal* thread count is pinned to 1.** Session 3's "INVALID" diagnosis identified the right
*mechanism* (non-associative float aggregation) but the wrong *fix knob*. Resolution, fully verified
this session (two consecutive `dbt build --target ci` runs, hardened oracle → **0 drift across all 60
models, all 7 `fct_*` byte-stable**):

The drift had **two independent sources**, both now closed:
1. **5 `fct_*` + ~12 intermediates** — DuckDB *intra-query* multithreading. SUM/AVG/STDDEV over floats
   reorder across DuckDB's internal worker threads → bit-different results → propagate through the whole
   decomposition chain. **dbt's `threads:` does NOT control this** (it only sets model-level concurrency);
   session 3's experiment (A) tried `threads: 1` at the dbt level and saw *no improvement* (still 5 fct_
   + 15 int drift) — that's why it looked unfixable. The real knob is the **dbt-duckdb `settings:
   threads: 1`** block, which issues `PRAGMA threads=1` on the connection. With it, intra-query float
   reordering is gone: drift dropped 20 → 3.
2. **3 intermediates** (`int_constructor_structural_pace`, `..._qualifying`, `int_constructor_deg_sensitivity`)
   — each carries a `fit_timestamp = CAST(CURRENT_TIMESTAMP AS VARCHAR)` wall-clock column that changes
   every build. **Benign metadata; confirmed it does NOT propagate into any `fct_*` mart.** Fixed in the
   oracle by excluding `fit_timestamp` from the content hash (`VOLATILE_COLS` / `SELECT * EXCLUDE`).

**What landed this session (uncommitted working tree):**
- `profiles/profiles.yml`: `ci` target now `threads: 1` + `settings: { threads: 1 }` (+ explanatory
  comment). Cost: serial CI build — ~17s on fixtures, negligible. (`dev` left at `threads: 4` for
  full-data `make app-data` speed; the oracle gates on `ci`, not `dev`.)
- `scripts/snapshot_model_hashes.py`: `VOLATILE_COLS = {"fit_timestamp"}` excluded from the hash via a
  per-relation `EXCLUDE` clause (only applied when the column exists in that relation).
- Verified the wired `make lint-oracle-snapshot` → rebuild → `lint-oracle-check` loop: exit 0, "all 7
  fct_* models byte-stable," zero spurious non-fct warnings.

**Implication:** the byte-stable `fct_*` guardrail (§5 / §6.1) IS satisfiable with exact hashing.
§6 Phase C–F are **unblocked** — the gate can now verify every lint batch. (Tolerance-oracle option (B)
from session 3 is no longer needed.)

### ⚠️ Risk to flag to the user before going further
§6 Phase A (already done, uncommitted) flips the CI lint gate from **green-by-accident** (silent
profile-resolution error, exit 2, never evaluated a rule) to **red-for-real** (2,828 genuine
violations). If this is committed/pushed as-is, CI goes red for every future `transform/` PR until
§6 Phases C–F substantially land. Options: (a) keep this whole effort on a branch and don't merge
until §6 is far enough along, (b) temporarily widen `.sqlfluff` `exclude_rules` as a stopgap, or
(c) accept red CI during active cleanup. Not decided — surface to user, don't pick unilaterally.

### Next action (pick this up first)
**Phase C + LT05 output-neutrality is now PROVEN (session 6, see dashboard rows).** Resume at:
1. ~~Verify Phase C didn't move output~~ ✅ DONE session 5.
2. ~~Hand-break the 396 residual LT05 long lines~~ ✅ DONE session 6 (LT05 396→0, oracle exit 0).
3. ~~Phase D (aliasing AL01 etc.)~~ ✅ DONE session 6 (505→180, oracle exit 0; caught+fixed dim_constructors regression).
4. ~~Phase E (semantic-risk)~~ ✅ DONE session 7 (ST07 96→0, AM05 69→0, all leftovers; oracle exit 0). Lint rule-clean.
5. ~~Phase F (lock the gate)~~ ✅ DONE session 7 (.sqlfluffignore PRS file, committed baseline, transform-check +
   CI Gate 1c wiring, duckdb==1.5.3 pin, tests/README doc).
6. **Phase G (user directive)** — **NEXT / START HERE.** Fix the 11 pre-existing CI-fixture build errors (missing
   stg_track_status fixture parquet + 6 sparse-SE not_null fails). See the Phase G section under the dashboard.
   After ERROR=0, REGENERATE the oracle baseline (`make lint-oracle-snapshot`) since more models will materialize.
   Phase 3.1 (singular invariant tests) and 4.1 (`contract:` policy) also remain, oracle-independent.
Phase 3.1 (singular invariant tests) and 4.1 (`contract:` policy) remain oracle-independent and unblocked.

Phase 3.1 (singular invariant tests) and 4.1 (`contract:` policy) remain oracle-independent and unblocked.

**Working-tree state right now:** Phase C cosmetic auto-fixes ARE applied (63 model files, lint
2,828→902) and restored after the stash experiment. `ci.duckdb` currently holds a *pristine-tree* build
(from the stash experiment), NOT a build of the current edited models — so a fresh `dbt build` is needed
before trusting anything. Nothing committed.

**Caveat on the oracle baseline:** it's written to `target/model_hashes.baseline.json`, which is
gitignored (dbt convention). That's correct for a within-session snapshot→fix→check loop, but Phase F
(wire `lint-oracle-check` into `transform-check`/CI) will need to decide whether to commit a baseline
to a persistent path, since CI starts with no `target/`.

### Handoff Log (newest first — append, don't rewrite history)

**2026-06-19 (session 7)** — **§6 Phase E (semantic-risk batch) DONE + oracle-verified; lint now rule-clean.**
First noted the working tree was unexpectedly CLEAN — Phases 0–D had been **committed** in `da0cf76` (not left
uncommitted as prior checkpoints assumed). Rebuilt ci.duckdb fresh (PASS=413/ERROR=11 baseline), snapshotted the
oracle. Then Phase E in tiers: (1) **leftovers** — RF02×4 qualify, AL03×2 alias (`2 AS sector`), RF04×2
(`position` keyword → kept + `-- noqa: RF04` rationale, after `"position"` quoting just traded RF04→RF06),
ST09×3 operand-flip, ST11 dropped the dead `stint_numbers` join, AM01 dropped redundant DISTINCT, ST05
hoisted a subquery to a `stint_lengths` CTE; rebuild+oracle exit 0. (2) **ST07 96→0** — ran
`sqlfluff fix --rules ST07` (converted 55), which broke 4 models with Binder ambiguity (the documented
USING-collapse hazard: an ON-join exposes a duplicate key, making a sibling `USING` ambiguous). Manually
converted ALL 41 remaining USING→ON anchored to the right FROM alias; one gotcha — int_corner_skill_residuals'
`USING(lap_id)` actually resolved to `lk.lap_id` (lap_keys), not `cm`. (3) **AM05 69→0** — bare `JOIN`→`INNER JOIN`
(autofix, cosmetic). Cleaned up LT05/LT02 reflow fallout (autofix + 5 hand-breaks). **Oracle exit 0 / all 7 fct_*
byte-stable after every batch**; the 3 non-materialized files (int_pit_loss_circuit/int_sc_hazard_history/
int_era_normalized) hand-verified output-neutral. `int_constructor_deg_sensitivity` left untouched (0 ST07 — sqlfluff
can't render it). **`sqlfluff lint models/` is now rule-clean; sole remaining failure was the fct_ghost_race_finish
PRS** (unparseable).
**THEN completed Phase F (lock gate) same session:** `.sqlfluffignore`'d the PRS file → `sqlfluff lint models/`
exits **0**; moved the oracle baseline to committed `transform/tests/model_hashes.baseline.json` (script
DEFAULT_BASELINE updated) + regenerated it; wired `lint-oracle-check` into `make transform-check` and added CI
"Gate 1c"; **pinned `duckdb==1.5.3` in requirements.txt** (user picked pin-for-CI when asked) so float-hashes match
local↔CI; documented the honest gate in tests/README.md. **Did NOT start Phase G** — user asked to hand off here.
No commit/push (user-gated). Uncommitted files this session: ~30 model `.sql` (ST07/AM05/leftover fixes),
`transform/.sqlfluffignore` (new), `transform/tests/model_hashes.baseline.json` (new), `transform/scripts/
snapshot_model_hashes.py`, `transform/tests/README.md`, `Makefile`, `requirements.txt`,
`.github/workflows/dbt-ci.yml`, `work.md`.

**⏭️ NEXT SESSION STARTS HERE → Phase G (user directive): fix the 11 pre-existing CI-fixture build errors.**
See the "Phase G" section under the dashboard. Two root causes: (1) missing `stg_track_status` fixture parquet
(+ its cascade), (2) 6 `not_null` fails on genuinely-sparse SE/CI columns (driver-circuit-era affinity + driver
season ratings). After fixing → `dbt build --target ci` must reach ERROR=0, then **REGENERATE the oracle baseline**
(`make lint-oracle-snapshot`) because newly-materializing models (incl. possibly fct_ghost_race_finish) need
hashes, and re-run `make lint-oracle-check`. Working tree state: clean build of current edited models in ci.duckdb;
lint exits 0; oracle exits 0 vs the committed 50-model baseline.

**2026-06-19 (session 6, cont.)** — **§6 Phase D (aliasing/structure batch) done + oracle-verified.**
Ran `sqlfluff fix --rules AL01,AL03,AL05,RF02,RF04,ST01,ST02,AM03,CV11` then a cosmetic settle pass for the
reflow cascade → **AL01 279→0, ST01 33→0, ST02/AM03/CV11/AL05 cleared; total 505→180.** First rebuild flagged a
regression: PASS dropped 413→387, ERROR 11→12 — AL05's auto-fix had stripped `AS t(team_name, pu_family)` (the
VALUES column-list alias) off `dim_constructors`, breaking `LEFT JOIN ... USING (team_name)` (Binder Error,
26 downstream skips). Restored the column-list alias + `-- noqa: AL05` with a rationale comment (sqlfluff
false-positive — sees the `t` table alias as unused under `SELECT *`, can't see the column-list is load-bearing).
Grepped the whole diff for other `\) AS x(cols)` strips — only this one existed. Rebuilt: PASS=413/ERROR=11
baseline restored, `lint-oracle-check` exit 0, all 7 fct_* byte-stable. Remaining 180 are all Phase E
semantic-risk (ST07 97/AM05 69/RF02 4/ST09 3/RF04 2/AL03 2/ST11/ST05/AM01). Noted `fct_ghost_race_finish.sql`
is unparseable by sqlfluff (PRS max-depth-255) → lint-exempt. Did NOT start Phase E. No commit/push (user-gated).

**2026-06-19 (session 6)** — **Cleared the 396 residual LT05 long lines (§6 Phase C.5), oracle-verified.**
Classified first: 387/396 were standalone `--` comment lines, only 9 real SQL/jinja. Wrote a conservative
auto-wrapper (only rewrites lines whose stripped content starts with `--`, preserves indent + `-- ` prefix,
`break_long_words=False`/`break_on_hyphens=False`, skips separators/tables/`|`-lines) → wrapped 386, skipped 1
(`|constructor|` pipe comment). Hand-broke the 9 SQL/jinja lines (multiline `{{ config(...) }}` &
`generate_surrogate_key([...])`, BETWEEN splits) + the 1 skipped comment; fixed 2 LT02 from an over-indented
BETWEEN. Result: **LT05 396→0, total 902→505**, zero new layout violations. `dbt parse --target ci` clean.
Rebuilt current edited tree on fixtures (PASS=413/ERROR=11 — same pre-existing sparse-SE not_null + missing
stg_track_status fixture fails) and ran `lint-oracle-check` → **exit 0, all 7 fct_* byte-stable vs the
session-5 pre-Phase-C baseline** ⇒ Phase C + LT05 proven output-neutral end-to-end. Did NOT start Phase D.
No commit/push (user-gated). Files: 53 model `.sql` (comment wraps + 10 hand-breaks), work.md.

**2026-06-19 (session 5)** — **Verified §6 Phase C is output-neutral** (the documented next action).
Ran the pristine-vs-edited oracle diff exactly as specified: `git stash push -- 'transform/models/**/*.sql'`
(stashed only the 57 Phase C model edits; kept profiles.yml determinism fix + scripts/ + schema/doc
edits) → `dbt build --target ci` pristine → `make lint-oracle-snapshot` (baseline = 50 models, 8 missing
on fixtures) → `git stash pop` → `dbt build --target ci` edited → `make lint-oracle-check` → **exit 0,
"all 7 fct_* byte-stable vs baseline," zero non-fct drift.** Both builds reported identical
PASS=413/ERROR=11 (the same pre-existing fixture fails — sparse SE/CI not_null + stg_track_status). Phase C
(2,828→902 lint, 63 files) is confirmed pure cosmetic. Did NOT start the LT05 hand-break or Phase D/E.
No commit/push (user-gated). No files changed except work.md (this checkpoint).

**2026-06-19 (session 4)** — **Fixed the "invalid" oracle** (full detail in ✅ ORACLE FIXED above —
the headline of this session). Ran session-3's recommended experiment (A): dbt `threads: 1` alone did
NOT help (still 5 fct_ + 15 int drift run-to-run) — confirming the drift is *intra-query*, not dbt
model-concurrency. Added dbt-duckdb `settings: threads: 1` (PRAGMA threads=1) to the `ci` profile →
drift collapsed 20 → 3. Traced the residual 3 to a `fit_timestamp = CURRENT_TIMESTAMP` wall-clock column
in the constructor-pace family (does NOT reach any fct_); excluded it from the oracle hash via
`VOLATILE_COLS`/`EXCLUDE`. Two consecutive `dbt build --target ci` then hashed **identical across all 60
models** (all 7 fct_ stable). Verified the wired make-target loop (snapshot→rebuild→check) exits 0.
§6 Phase C–F unblocked. Did NOT re-run Phase C output-neutrality check (the pristine-vs-edited stash diff
— that's the documented next action) and did NOT touch Phase 3.1/4.1. No commit/push (user-gated). Files
changed: `profiles/profiles.yml`, `scripts/snapshot_model_hashes.py`.

**2026-06-19 (session 3)** — Started §6 Phase C, then discovered the oracle is invalid (full detail in
🛑 ORACLE INVALID section above — the headline finding of this session). Sequence: built ci.duckdb
fresh + took a clean baseline (50/58 models, lint count confirmed 2,828). Ran the cosmetic auto-fix
loop `sqlfluff fix --rules LT01,LT02,LT05,LT06,LT03,LT12,CP01,CP02,CP03` → **2,828→902** violations,
stable over 5 passes (63 files changed). Rebuilt + oracle-checked → 2 fct_ + 14 int "drifted." Suspected
my edits, so **stashed all model edits and rebuilt the pristine tree** → oracle STILL reported 5 fct_ +
15 int drifted vs baseline with zero code change ⇒ pipeline is float-nondeterministic build-to-build, the
exact-md5 oracle can't gate. Popped the stash (Phase C edits are back in the working tree, unbuilt).
A `dev.duckdb` baseline attempt OOM'd hashing a full-data table (string_agg over millions of rows blows
the default mem limit) — `fct_ghost_race_finish` remains uncovered regardless. **Stopped here at user
request to hand off for a fresh chat.** No gate re-run trustworthy until the oracle is fixed (threads=1
determinism test OR tolerance-based rewrite — see Next action). Phase 3.1 / 4.1 still untouched and are
oracle-independent. No commit/push (user-gated).

**2026-06-19 (session 2)** — Sanity-checked `dbt parse --target ci` stays warning- and
deprecation-clean (the 10-second check the prior session deferred — confirmed clean). Then built §6
Phase B end-to-end: `transform/scripts/snapshot_model_hashes.py` reads `target/manifest.json` for the
60 model nodes, hashes each materialized relation in a DuckDB warehouse with an order-independent
`md5(string_agg(md5(CAST(t AS VARCHAR)) ORDER BY ...))` (validated deterministic + ~0.03s/table),
records `target/model_hashes.baseline.json`. Models in the manifest but absent from the DB (8 on CI
fixtures, incl. fct_ghost_race_finish + the stg_track_status-fixture-dependent chain) are recorded as
"missing", not drift. `--check` mode diffs vs baseline: **hard-fails (exit 1) on any fct_\* drift**,
warns-only on non-fct drift, exit 2 if no baseline. Proved all three exit paths with a tampered
baseline. Wired `make lint-oracle-snapshot` + `make lint-oracle-check` (added to `.PHONY` + visible in
`make help`). All 7 fct_* report byte-stable against the fresh baseline. Did NOT start Phase C (lint
fixes) — that's the next action. No commit/push (user-gated).

**2026-06-19** — Investigated git status showing extensive uncommitted `transform/` changes despite
this doc's stale "PLAN ONLY" header — a prior session clearly executed Phases 0–3(partial)/4.3 and
§6-A without updating this doc (the "usage depletion" scenario this checkpoint structure now exists
to prevent). Re-verified every claim against live gates rather than trusting the diff (see Dashboard
+ confirmed pre-existing-vs-introduced build errors via `git stash` comparison). Then executed Phase
4.2 (em-dash sweep) end-to-end as the first tracked checkpoint: grepped all of `transform/`'s
prose docs (READMEs + `selectors.yml`), manually triaged real mangled-dash instances vs legitimate
hyphenated compounds (noisy — naive regex over-matches model names and compound words badly), fixed
all 10 confirmed instances. **Stopped here on explicit user signal (low usage budget)** before
starting §6 Phase B — did not touch Phase 3.1 or 4.1. No gate re-run after the em-dash fixes (pure
prose/comment changes, zero SQL/YAML structural risk — skipped re-verification to conserve budget;
a future session should still sanity-check `dbt parse` stays clean before moving on, since it's a
10-second check).

---

## 0. Snapshot of what exists today

- **dbt project** (`off_the_pace`), dbt-duckdb, 60 model files across 4 layers:
  - staging 12 · reference 4 · intermediate 34 · marts 10
- **Tests**: 33 singular SQL tests (`tests/`) + generic schema tests + 1 pytest module
  (`tasks/coefficients/tests/test_fit_compound_cliff.py`).
- **Python coefficient layer**: 8 modules in `tasks/coefficients/` (4 `fit_*.py` + `survival.py`,
  `provenance.py`, `seed_writer.py`, `check_freshness.py`).
- **CI** (`.github/workflows/dbt-ci.yml`): 7 gates — `dbt parse` → fixture check → `dbt seed` →
  fast_build selector → full build → singular identity tests → pytest harness → `sqlfluff lint`
  → `dbt docs generate`.
- **Lint**: `.sqlfluff` (duckdb dialect, dbt templater, UPPER keywords/functions, lower identifiers).
- **Docs**: per-layer `README.md`, rich SQL header comments (identity math in-file), Mintlify site.

`dbt parse` currently **succeeds**, but emits a wall of warnings (see §1). CI is green only because
dbt downgrades "missing ref" in singular tests to a warning and **silently drops the test**.

---

## 1. Audit — concrete weak spots (all verified against the repo)

### A. Dead references that silently disable tests (highest priority — correctness risk)
`dbt parse` warns and **drops** these; they look like guards but run on nothing:

| Symptom (from `dbt parse`) | File | Action |
|---|---|---|
| `assert_pos_degradation` depends on missing `fct_driver_degradation` | `tests/assert_pos_degradation.sql` + `tests/schema.yml` | Delete or repoint to a live model |
| `assert_constructor_coefficient_signs` depends on missing `dim_constructor_championship` | `tests/assert_constructor_coefficient_signs.sql` | It's a `SELECT 1 WHERE FALSE` placeholder — convert to a real test against `int_constructor_structural_pace`, or remove the dangling `ref()` |
| schema patch for missing `fct_driver_degradation` (LEGACY) | `tests/schema.yml` | Remove the legacy block + its generic tests |
| schema patch for missing `int_constructor_pace_index` | `models/intermediate/schema.yml` | Remove orphan patch |
| schema patch for missing `int_stint_metrics` | `models/intermediate/schema.yml` | Remove orphan patch |
| schema patch for missing `int_corner_residuals` (+5 generic tests) | `models/intermediate/schema.yml` | Remove orphan patch; the real model is `int_corner_skill_residuals` |

### B. Documentation living in the wrong place / missing
- Mart models `dim_events` and `fct_lap_residuals` are documented in **`tests/schema.yml`**, not
  `models/marts/schema.yml`. Move them.
- `fct_telemetry_deltas` has **no schema.yml entry at all** (no description, no column docs/tests).
- `mart_degradation_history_envelope`, `mart_corner_skill_driver`, `dim_events` exist as marts but
  the README "Feature Marts" DAG doesn't list the `mart_*` family.
- `macros/README.md` references a **nonexistent** `assert_lap_residual_identity.sql` and omits
  `circuit_id_from_name.sql`, `normal_cdf.sql`, `clean_lap_filter.sql`.

### C. Forward-compat / deprecation debt (`dbt parse` summary)
- `MissingArgumentsPropertyInGenericTestDeprecation` × 16 — generic tests using the pre-1.10
  arg style; will break on dbt 2.x.
- `PropertyMovedToConfigDeprecation` × 6 — `where:`/config keys that moved under `config:`.
- 2 unused config paths: `seeds.off_the_pace._archive`, `seeds.off_the_pace._pending`.

### D. Test-coverage asymmetry (methodology)
- 8 Python modules in `tasks/coefficients/`, **1** test file. CI runs the entire
  `tasks/coefficients/tests/` dir, so adding tests is "free" coverage with no CI wiring.
- Several singular tests are **Placeholder / Inert** (`SELECT 1 WHERE FALSE`) per `tests/README.md`.
  They pass vacuously — track them so they don't masquerade as coverage.

### E. Consistency / polish
- Prose em-dashes are mangled to hyphens in several `README.md` / `selectors.yml` descriptions
  (e.g. "deferred-not yet wired", "~2 min on CI fixtures"). Repo convention (memory) is the
  double-space ` - ` prose marker; normalize.
- Only the 2 ML-contract marts enforce `contract:`. Decide a deliberate policy for the rest.

---

## 2. Implementation plan (phased, each phase independently shippable & CI-green)

### Phase 0 — Mechanical cleanup (zero behavior change, low risk) ✅ do first
1. Remove the 3 orphan schema patches in `models/intermediate/schema.yml`
   (`int_constructor_pace_index`, `int_stint_metrics`, `int_corner_residuals`).
2. Resolve the 2 dangling singular tests in `tests/`:
   - `assert_pos_degradation.sql` → delete (model retired) **or** repoint to a live deg model.
   - `assert_constructor_coefficient_signs.sql` → either implement the documented real check against
     `int_constructor_structural_pace`, or drop the `ref()` to remove the warning.
   - Remove the matching `fct_driver_degradation` legacy block from `tests/schema.yml`.
3. Move `dim_events` + `fct_lap_residuals` docs from `tests/schema.yml` → `models/marts/schema.yml`.
4. Delete unused `seeds._archive` / `seeds._pending` config keys (or create the dirs they expect).
5. **Gate:** `dbt parse` emits **zero** missing-node warnings.

### Phase 1 — Documentation completeness
1. Add full `models/marts/schema.yml` entries for `fct_telemetry_deltas`,
   `mart_corner_skill_driver`, `mart_degradation_history_envelope` (description + per-column docs).
2. Bring every mart to a documentation baseline: model-level description, grain statement, and a
   description on every column.
3. Fix `macros/README.md` (remove phantom macro; document all 7 macros with signature + example).
4. Refresh `transform/README.md` DAG to include the `mart_*` family and `dim_events`.
5. Add a short **"Model authoring standard"** section (see §3) to `models/README.md` so the
   in-file header-comment convention (identity math, BREAKING CHANGE log) is documented, not folklore.
6. **Gate:** every model in every `schema.yml` has a description; `dbt docs generate` clean.

### Phase 2 — Forward-compat (kill deprecations)
1. Migrate the 16 generic tests to the current `arguments:` property form.
2. Move the 6 `PropertyMovedToConfig` keys under `config:`.
3. **Gate:** `dbt parse` deprecation summary is empty.

### Phase 3 — Methodology & test depth
1. Add a singular test per **invariant** that's currently only prose in a header comment but unguarded
   (e.g. monotonic field pace, non-negative survival weights) — reuse the
   `assert_additive_identity` macro where it's an additive closure.
2. Convert Inert/Placeholder tests in `tests/README.md` to active where the upstream model now exists;
   for the rest, add a `tags: [placeholder]` so a selector can exclude them from "real coverage" counts.
3. Add pytest modules for the untested fitters (`fit_weight_penalty`, `fit_constructor_car_fe`,
   `fit_degradation_isotonic`, `survival`, `provenance`, `seed_writer`, `check_freshness`) — target a
   stated minimum (e.g. each public function has ≥1 happy-path + 1 edge test).
4. **Gate:** `make dbt-test` + pytest harness green; placeholder count is explicit, not hidden.

### Phase 4 — Best-practices & consistency
1. Decide and document a `contract:` policy (which marts are public contracts vs internal).
2. Normalize prose em-dashes per repo convention across `transform/` markdown + `selectors.yml`.
3. Add a `make transform-check` target chaining the exact CI gates locally
   (`dbt parse` → `sqlfluff lint` → `dbt build --selector fast_build` → singular tests → pytest)
   so contributors reproduce CI before pushing.
4. Tighten `sqlfluff` config if desired (currently excludes `L034`, `L036`) — re-enable one rule at a
   time, auto-fixing, only if it doesn't churn the whole tree.

> Each phase is a separate reviewable change. Phase 0 is the unblock; 1–4 can land in any order after.

---

## 3. Model-authoring standard (to document in `models/README.md`)

Codify the existing-but-undocumented conventions so new models match the house style:

- **Header comment** (every model): one-line purpose; for decomposition/identity models, the full
  additive identity with units (`= a_s + b_s + ...`, positive = slower) and a per-term source map;
  a dated `BREAKING CHANGE:` log line when a column's meaning changes.
- **Naming**: `stg_` / `int_` / `fct_` / `dim_` / `mart_` prefixes; `_s` suffix = seconds,
  `_se_s` = standard error in seconds, `*_flag` = boolean. Keep it consistent.
- **Materialization**: staging = view, intermediate = view (+`tags: [intermediate]`),
  reference/marts = table (set in `dbt_project.yml`; don't override per-model without reason).
- **Refs only** — never hardcode a table name; `{{ ref(...) }}` for models, `{{ source(...) }}` for bronze.
- **Macros over copy-paste**: `clean_lap_filter`, `normalize_compound`, `bayesian_shrinkage`,
  `posterior_variance`, `normal_cdf`, `circuit_id_from_name`, `assert_additive_identity`.
- **Vars** for tunable knobs (`era_boundary`, `outlier_exclude_ratio`, `ghost_short_run_threshold`),
  never magic numbers inline.
- **Every model gets a `schema.yml` entry** in its own layer file: description + grain + column docs;
  generic tests (`not_null`/`unique`/`accepted_values`/`relationships`) on keys and enums.
- **sqlfluff-clean**: UPPER keywords/functions, lower identifiers, trailing commas.

---

## 4. Runbook — add a NEW transform model + tests that pass CI

This is the repeatable recipe. Example: a new intermediate model `int_example_metric`.

### Step 1 — Create the model
- File: `models/intermediate/int_example_metric.sql`
- Start with the header comment (purpose + identity/units if applicable).
- Body is a single `SELECT` using `{{ ref(...) }}` for every upstream; vars for any constant.
- Inherits view materialization + `intermediate` tag from `dbt_project.yml` (no per-file config needed).

### Step 2 — Document it (same layer's schema.yml)
- Add to `models/intermediate/schema.yml`: model `name`, `description` (purpose + grain), and a
  `description` for **every** output column.
- Add generic tests on keys/enums:
  ```yaml
  - name: int_example_metric
    description: "One row per <grain>. <what it computes / how>."
    columns:
      - name: lap_id
        description: "Grain key."
        tests: [not_null, unique]
      - name: compound
        tests:
          - accepted_values:
              arguments: { values: ['SOFT','MEDIUM','HARD','INTERMEDIATE','WET'] }
  ```
  (Use the `arguments:` form to stay deprecation-free — see Phase 2.)

### Step 3 — Add invariant tests
- **Generic** (above) for null/unique/enum/relationship checks.
- **Singular** (`tests/assert_example_metric_<invariant>.sql`) for anything mathematical: a test
  passes when it returns **zero rows**. For additive closures, prefer the macro:
  ```sql
  -- Fails if <component_a> + <component_b> != <total> within 1e-3.
  {{ assert_additive_identity(
       model=ref('int_example_metric'),
       total_col='total_s',
       component_cols=['component_a_s','component_b_s'],
       tolerance=0.001) }}
  ```
- Register it in `tests/README.md` (the status table: ✅ Active / ⏸️ Inert / 📝 Placeholder).

### Step 4 — Wire downstream + selectors (if needed)
- If a mart consumes it, add the `ref()` there; if it's a new public surface, decide on `contract:`.
- If it must run in CI's fast smoke gate, confirm the selector path covers it
  (`fast_build` = staging+reference only; intermediate/marts run in the full-build gate — usually
  no selector change needed).

### Step 5 — Reproduce CI locally before any push
Run the same gates CI runs, in order. From `transform/` with the venv active
(`source ../.venv/bin/activate`):
```bash
dbt deps                                                    # Gate 0 prep
dbt parse  --profiles-dir profiles --target ci              # Gate 0: must be warning-clean now
dbt build  --profiles-dir profiles --target ci \
  --vars '{"bronze_base": "../transform/tests/fixtures/bronze"}'   # Gate 1b: full build + generic tests
dbt test   --profiles-dir profiles --target ci \
  --vars '{"bronze_base": "../transform/tests/fixtures/bronze"}' \
  --select test_type:singular                               # Gate 2: identity/singular tests
pytest tasks/coefficients/tests/ -v --tb=short              # Gates 2–5: python harness (if fitter touched)
sqlfluff lint models/ --disable-progress-bar                # Lint: hard-fails CI on style regressions
dbt docs generate --profiles-dir profiles --target ci \
  --vars '{"bronze_base": "../transform/tests/fixtures/bronze"}'   # Docs gate
```
Target after Phase 4: `make transform-check` wraps all of the above into one command.

### Step 6 — Definition of done (CI conformance checklist)
- [ ] `dbt parse` warning-clean (no missing-node, no new deprecations).
- [ ] Model has a `schema.yml` entry: description + every column described.
- [ ] At least one generic test on the grain key; singular test for any identity/invariant.
- [ ] `sqlfluff lint` passes (UPPER keywords, lower identifiers, trailing commas).
- [ ] Full `dbt build` + `dbt test` green on CI fixtures.
- [ ] `tests/README.md` status table updated if a singular test was added.
- [ ] README DAG / layer docs updated if a new public surface was introduced.

---

## 5. Sequencing & guardrails
- **Order:** Phase 0 → 1 → 2 → (3, 4 in parallel). Phase 0 unblocks honest CI signal; do it first.
- **One concern per change** so review and `dbt parse`/lint diffs stay legible.
- **No data-shape changes** in this effort — cleanup must keep all `fct_*` outputs byte-stable;
  if a model's columns must change, that's a separate, contract-aware change.
- **User-gated**: do not run `make app-data` / publish / commit / push as part of this. Per standing
  rule, surface results and wait for explicit go.
- **Effort estimate:** Phase 0 ≈ 1 sitting; Phase 1 ≈ docs pass; Phase 2 mechanical; Phase 3 the
  largest (real tests); Phase 4 polish.

---

## 6. Full sqlfluff lint-clean — implementation plan

> Status: PLAN ONLY (user-gated). Discovered while wiring `make transform-check`: the lint gate
> has **never actually enforced**. This section is the full-fix plan.

### 6.0 The bug (why this is needed)
- CI runs `sqlfluff lint models/` (a documented *hard-failure* gate) but **never sets up a dbt
  profile** for it, and the committed `.sqlfluff` set no `profiles_dir`. sqlfluff's dbt templater
  therefore fell back to `~/.dbt/profiles.yml` (locally: a stale **absolute** iCloud path that
  doesn't resolve) → sqlfluff exits **2** (profile-resolution error) *before evaluating any rule*.
  The gate has been green-by-accident / red-by-error, never enforcing style.
- **Fixed prerequisite (already done):** `transform/.sqlfluff` now pins
  `profiles_dir = profiles`, `profile = off_the_pace`, `target = ci`, so the templater connects via
  the checked-in profile (relative `../data/ci.duckdb`) both locally and in CI. *This is what makes
  the gate able to run at all — and what exposes the backlog below.*

### 6.1 The backlog (measured against the real config, excludes L034/L036 only)
**2,828 violations** across **60** model files. By rule:

| Risk tier | Rules | Count | Auto-fix? |
|---|---|---|---|
| Cosmetic (no semantic change) | LT01 spacing (862), LT02 indent (575), LT05 long-line (707), CP01/02/03 caps (176), LT03/LT06/LT12 | ~2,330 | Mostly — but layout rules **cascade**: a single `sqlfluff fix` pass *raised* the count to 2,703 (reflow interactions). Needs iterative passes + manual LT05 line-breaks (~389 long lines the fixer can't split). |
| Aliasing/struct (review, usually safe) | AL01 implicit alias (279), AL03/AL05, RF02/RF04, ST01/ST02, AM03, CV11 | ~330 | Yes, but verify each. |
| **Semantic-risk** | **ST07 USING→ON (97)**, AM05 implicit/cross join (69), ST05/ST09/ST11 | ~170 | Risky: `USING(k)` collapses the key to one column, so `SELECT *` / unqualified key refs can change output. **39 of 60 files** are touched by ST07/AL01/AM05. |

**Hard guardrail:** 7 `fct_*` marts must stay **byte-stable** (per §5). The semantic-risk tier is
exactly where that can break.

### 6.2 Phased fix (each phase independently shippable, oracle-verified, separate commit)

**Phase A — Gate honesty (DONE / verify).** `.sqlfluff` profile pin landed. Confirm
`sqlfluff lint models/` *connects* (exit 1 = real violations, not exit 2 = no profile) both locally
and on a CI runner (lint runs *after* `dbt seed`/`build`, so `../data/ci.duckdb` exists by then).

**Phase B — Build the byte-stability oracle (prereq for everything after).**
- New `scripts/snapshot_model_hashes.py`: for every model relation in `ci.duckdb` (and optionally
  `dev.duckdb` on real data), compute an **order-independent content hash**
  (`SELECT md5(string_agg(md5(row_to_json(t)::TEXT), '' ORDER BY 1))` or per-model parquet + sha256),
  write `target/model_hashes.baseline.json`. The 7 `fct_*` are the mandatory subset; hash all models.
- Re-runnable as `make lint-oracle-check` → diffs current vs baseline, **fails on any `fct_*` drift**.

**Phase C — Cosmetic batch (zero semantic risk).** Rules LT*, CP*. Loop
`sqlfluff fix models/ --rules LT01,LT02,LT05,LT06,LT03,LT12,CP01,CP02,CP03` until `sqlfluff lint`
count stops dropping; then hand-break the residual LT05 long lines. CP02 lowercases identifiers
(DuckDB identifiers are case-insensitive unless double-quoted — safe; spot-check no quoted ids).
**Gate:** oracle identical for ALL models; singular identity tests green.

**Phase D — Aliasing/structure batch.** AL01 (add explicit `AS`), AL03/AL05, RF02/RF04, ST01/ST02,
AM03, CV11. Mostly mechanical; review the handful of RF (references) fixes. **Gate:** oracle identical.

**Phase E — Semantic-risk batch, ONE FILE AT A TIME.** ST07 (USING→ON), AM05, ST05/ST09/ST11.
- For each ST07 site: rewrite `JOIN x USING (k)` → `JOIN x ON a.k = x.k [AND ...]`, then fix any
  now-ambiguous unqualified `k` / `SELECT *` column references the USING-collapse was hiding.
- After **each file**, re-run the oracle; **revert immediately** if any model hash changes until refs
  are reconciled. AM05: make implicit joins explicit. **Gate:** oracle identical after every file.

**Phase F — Lock the gate.**
- `.sqlfluff` keeps only the deliberate `L034, L036` exclusions (per §4.4); document any rule left
  excluded with a one-line rationale comment in `.sqlfluff`.
- CI: keep `sqlfluff lint models/` as hard-fail (now genuinely enforcing). Add `lint-oracle-check`
  to `make transform-check` so future style fixes can't silently move `fct_*` output.
- Docs: note in `tests/README.md` / `models/README.md` that lint is enforced and that the byte-stable
  oracle gates it. Update §0 of this doc (CI gate description) to reflect the now-honest lint gate.

### 6.3 Sequencing & guardrails (this effort)
- **Order:** A → B → C → D → E → F. B is the unblock — never fix a rule before the oracle exists.
- **Oracle after every batch**; `fct_*` byte-stability is the hard gate. Singular identity tests
  (`assert_*_identity`) run each phase as a second mathematical guard on decomposition closure.
- **One rule-tier per commit** (mirrors §4.4 "re-enable one rule at a time"); semantic-risk tier is
  one-file-per-step, not one-commit-for-all.
- **No column/contract changes**: USING→ON must preserve the projected column set. If a fix *requires*
  a column change, stop — that's a separate contract-aware change.
- **User-gated**: surface diffs and oracle reports; do not commit/push/publish without explicit go.
- **Effort:** B ≈ small script; C the bulk of the line-count but low-risk/iterative; D mechanical;
  E the slow, careful part (39 files, file-by-file verify); F polish.
