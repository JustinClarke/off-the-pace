# Implementation plan — per-layer Mintlify tabs, starting with Data (incl. Ingestion)

Internal planning doc. Lives in `_roadmap/` (gitignored) because it is *process*,
not a description of the committed tree — exactly the kind of artifact
[CONVENTIONS.md](../CONVENTIONS.md) bans committed files from depending on. Nothing
in `docs/`, the layer READMEs, or code comments may cite this file. Every rule it
applies to the docs is restated inside the docs themselves.

The plan's own numbered steps are a genuine build procedure (a how-to), which
CONVENTIONS explicitly permits — the ban is on *describing what stage the project
reached*, not on ordered instructions.

---

## 0. Progress checkpoint (resume here)

All 7 parts are complete — the Data tab (data layer + ingestion how-to) is fully built
per §10's Definition of Done, all boxes checked. Execution was checkpointed in 7 parts
so a context reset never lost more than one part's worth of work. Protocol confirmed
with the user: **pause after each part, report status, do not commit** unless explicitly
asked — each part is independently reviewable/commit-able. Everything below is still
uncommitted; nothing in this plan authorized a commit.

### Parts

- [x] **Part 1 — Nav skeleton + coverage gate.** `docs/docs.json` restructured to
      five tabs (Overview / Data / Transform / Machine Learning / App); old
      Reference tab removed and its groups redistributed (Bronze Schemas + CLI →
      Data; Models/Macros → Transform; ML Models → Machine Learning). New
      `scripts/ingestion_docs_facts.py` (mirrors `docs_facts.py`'s style)
      generates/checks `docs/snippets/bronze-coverage.mdx` from
      `verify_bronze.py --markdown`; wired into `make docs-coverage` /
      `make docs-coverage-check` and a new `bronze-coverage-drift` job in
      `docs-ci.yml`. Verified the write→check round-trip passes locally.
- [x] **Part 2 — Overview tab rewrite.** Recruiter-grade `index`/`introduction`/
      `key-concepts` per §3: hero `<Frame>`, layer-flow `<Mermaid>`, tech-stack
      `<CardGroup>`, by-the-numbers strip (gated, no hand-typed figures).
- [x] **Part 3 — Data-layer pages.** `data/overview`, `data/source-fastf1`,
      `data/source-jolpica`, `data/data-quality`, `data/known-issues` (§5.1–5.5).
- [x] **Part 4 — Ingestion Get Started + How to Ingest.** `ingestion/quickstart`,
      `ingestion/data-scope`, `ingestion/cli`, `ingestion/configuration`,
      `ingestion/monitoring` (§5.7–5.11). Deleted the superseded `docs/quickstart.mdx`.
- [x] **Part 5 — Ingestion Operations + Deep Dive.** `ingestion/verify`,
      `ingestion/manifest-report`, `ingestion/replay`, `ingestion/architecture`
      (§5.12–5.15). `architecture.mdx` is the code-walkthrough centrepiece: control-flow
      + retry-state Mermaid diagrams, a `<Steps>` lifecycle, and an `<AccordionGroup>`
      with one accordion per writer function (`_write_weather` … `_write_event_schedule`).
      Verified Part 5 with `make docs-coverage-check` + `make docs-audit` (0 errors,
      same 236 pre-existing app/ warnings) + `mintlify validate`/`broken-links` from
      `docs/` — zero broken links (every Part 3/4 forward-reference into Part 5 now
      resolves).
- [x] **Part 6 — Schema truth fix + generator enrichment.** Fixed the phantom-column
      bug in all 4 `ingestion/schemas/*.schema.json`; enriched `gen_schema_reference.py`
      to emit `<Warning>`/`<ResponseField>`; regenerated `docs/reference/schemas/*.mdx`;
      corrected `docs/reference/data-schemas.mdx`.
- [x] **Part 7 — CONVENTIONS sweep + validate + reconcile.** Grepped every Part 5/6 page
      for `KI-\d+`/`_roadmap`/`SYSTEM_DESIGN_AUDIT`/version labels (none found — clean by
      construction); reconciled `ingestion/README.md` and `docs/AGENTS.md` to the new
      tab vocabulary; `docs-audit` / `docs-coverage-check` / `docs-facts` / Mintlify
      validate+broken-links all green.

### Decisions made while executing — don't re-derive, apply these

- **Schema/CLI reference pages keep their existing file paths.** The DoD checklist
  says "file paths unchanged; nav-only move." `reference/schemas/*` and
  `reference/data-schemas` stay exactly where they are; only `docs.json` nav moved
  them into the Data tab. §4's `data/schemas/*` JSON sketch is illustrative IA
  naming, not a literal path — do not rename/move those files in Part 6.
- **`reference/cli/ingest` (generated) is not in nav.** Only the new authored
  `ingestion/cli` page gets a sidebar slot; the generated flag dump is linked to
  from inside that page rather than also listed in the sidebar — there's only one
  CLI command, unlike the 4 schema datasets which each warrant their own slot.
- **Overview tab gained two things beyond §4's literal sketch**: kept `repo-tour`
  in "What You Can Do" (it was in the old Documentation tab's Get Started group;
  §4's sketch just didn't mention it — dropping it would have orphaned it), and
  gave `reference/glossary` its own "Glossary" group (the old Reference tab's
  removal needed a new home for it; cross-cutting terminology fits Overview).
- **Tab icons** (unspecified in the plan): Overview=`home`, Data=`table`,
  Transform=`layers`, Machine Learning=`brain`, App=`layout-dashboard`. Existing
  group icons carried over unchanged.
- **Old `docs/quickstart.mdx` is currently nav-orphaned**, not yet deleted. It's
  superseded by the new `ingestion/quickstart` (Part 4) — delete it then; don't
  leave both live.
- **TrackStatus digit mapping is genuinely ambiguous across 3 sources** —
  `ingestion/SCHEMA.md` states one mapping, the old `reference/data-schemas.mdx`
  states a different one, and `transform/models/staging/stg_laps.sql`'s own regex
  logic (`is_safety_car_lap` matches digits 4/6/7, `is_vsc_lap` matches digit 5)
  implies a third — and that file's own inline comment example ("'41' =
  VSC+yellow") contradicts its own regex. **Resolution for the Data tab**: don't
  pick a winner. Document Bronze's `TrackStatus` as an opaque VARCHAR passthrough
  from FastF1 (ingestion applies no decoding) — interpreting it is a
  transform-layer concern, out of scope for Data-tab pages. Do not put a
  digit→meaning table on any `data/*` or `reference/schemas/laps` page.
- **Retry delay is 1s → 2s → 4s, not "1→2→4→8s."** `ingest.py`'s `_with_retry` has
  `max_attempts=4` with 3 sleeps between 4 attempts (`base_delay=1.0`,
  `delay = base_delay * 2**attempt` only when `attempt < max_attempts-1`); 8s is
  never reached. `DESIGN.md`'s resilience table and this plan's own §2 row are
  both wrong — write the code-accurate sequence into `ingestion/architecture` and
  `data/source-fastf1`, not the inherited claim.
- **Phantom-column bug confirmed in 4 places**, all needing the same fix in
  Part 6: `ingestion/schemas/{laps,telemetry,weather,race_control}.schema.json`
  (the generator's source data) plus the hand-written `reference/data-schemas.mdx`
  plus the already-generated `reference/schemas/telemetry.mdx` (inherits the bug
  from its `.schema.json` source — proves the fix must happen upstream, not in the
  template). Specifics: telemetry's `brake_pct` doesn't exist (FastF1 has no
  brake-pressure channel), `drs` is a BIGINT enum not boolean (10/12/14=open), the
  real column is `nGear` not `gear`; race_control's `code` doesn't exist and real
  columns are Title-Case (`Lap`/`Time`/`Flag`) not lowercase; weather and laps both
  claim a phantom `session` column (race laps get no session column at all; only
  qualifying laps get `session_type="Q"`). Ground truth for the fix is
  `ingestion/SCHEMA.md` (hand-verified against real Parquet `DESCRIBE` output).
- **`make simulate` is broken out of the box** (missing `--dry_run`;
  `replay_simulator.py` raises `ValueError` immediately without
  `EVENTSTREAM_CONNECTION_STRING`/`EVENTHUB_NAME`, since it targets a
  not-yet-deployed Azure EventHub streaming feature). Decision: document this
  accurately in `ingestion/replay` (show the working `--dry_run` invocation, flag
  the gap with a `<Warning>`) rather than patching the Makefile — fixing
  runtime/ops behavior is outside a docs-only plan's scope. Worth a separate
  follow-up callout to the user once the docs land.
- **"168 races" was stale/wrong** in `docs/index.mdx`, `docs/introduction.mdx`,
  `docs/quickstart.mdx` (×2), and `docs/findings/overview.mdx`. The real,
  gate-derived total is **149** (sum of the per-season `Laps` column in
  `docs/snippets/bronze-coverage.mdx`: 21+21+17+22+22+22+24, matching real F1
  calendars). Fixed it in the three Part 2 pages by replacing the literal with the
  new gated `overview-numbers` snippet (below); `quickstart.mdx` and
  `findings/overview.mdx` are untouched (out of this part's file list) — sweep them
  in Part 7 or flag to the user, don't leave "149" and "168" both live.
- **`docs/introduction.mdx` also said "sourced from FastF1 and OpenF1"** — wrong,
  the reference client is Jolpica (`jolpica_client.py`), not OpenF1. Fixed in the
  Part 2 rewrite to say FastF1 (timing) + Jolpica (standings/pit-stop reference),
  pointing at `/data/overview` (Part 3, not yet built).
- **New gated snippet: `docs/snippets/overview-numbers.mdx`**, generated by new
  `scripts/overview_docs_facts.py` (mirrors `ingestion_docs_facts.py`'s
  write/check shape). Sources every figure from disk instead of inventing a second
  literal: seasons + races parsed from the already-gated `bronze-coverage.mdx`;
  dbt models/tests + ML models reuse `docs_facts.py`'s existing `TARGETED`
  patterns against `README.md` (imported, not duplicated); app-feature count is
  `len(app/src/features/*/methodology.tsx)` (the same primary key
  `app_docs_audit.py` uses). Wired into `make docs-coverage` /
  `docs-coverage-check` (extended, not duplicated) and a new
  `overview-numbers-drift` CI job alongside `bronze-coverage-drift`. Embedded via
  Mintlify's `import X from '/snippets/overview-numbers.mdx'; <X />` pattern (no
  prior snippet was embedded anywhere yet, so this establishes the convention —
  reuse it verbatim in Part 3+, don't invent a second import style).
- **Real hero screenshot, not a mockup.** Installed Playwright into the existing
  `.venv` (gitignored, ~1.4G, not committed) and used the repo's own
  `agents/screenshot.py` to capture the **live** Degradation Simulator
  (`https://off-the-pace.web.app/ml/simulator`, 1920×1080, dark theme,
  viewport-only) since it's the flagship feature per the app's own home page
  (`SHOWCASE_HERO` in `app/src/routes/home/index.tsx`). Downscaled with `sips -Z
  1600` to 292 KB, saved at `docs/images/hero-degradation-simulator.png`. This is
  the **first image asset in `docs/`** — establishes `docs/images/` as the
  convention and confirms Mintlify resolves root-relative `/images/<file>.png`
  (verified via `mintlify validate`/`broken-links`, zero new warnings).
- **Deep math stayed out of Overview, on purpose.** `key-concepts.mdx` was
  previously a near-duplicate of `reference/glossary.mdx`'s accordions (full
  formulas, β-coefficients, Kaplan-Meier detail) — that content already lives
  twice (glossary + the four `decomposition/*` pages, now under the Transform
  tab per Part 1's nav move). Rewrote `key-concepts.mdx` as a thin orientation
  page (6 short sections, no formulas) that points outward to
  `/decomposition/seven-term-identity` and `/reference/glossary` instead of
  re-deriving anything. `introduction.mdx` keeps the one-line-per-term table (the
  right altitude for "what it does and why") but drops the enforced-CI-test SQL
  snippet and the full equation block — those now live only on
  `/decomposition/seven-term-identity`, which both Overview pages link to.
- **`docs/AGENTS.md` still describes the old two-tab structure** ("five content
  areas: Get Started, The Decomposition, Machine Learning, App & Visualizations,
  Reference tab") — stale since Part 1. Left as-is; in scope for Part 7's
  reconcile pass, not Part 2. Flag to the user if Part 7 is far off.
- Validated with `mintlify validate` + `mintlify broken-links` from `docs/`: the
  only warnings/broken links are the 14 not-yet-created Data-tab pages (Parts 3–6,
  expected) — zero issues attributable to the Part 2 pages, the new image, or the
  new snippet.
- **Part 3 dropped every hand-typed row/sample count the §5.1 sketch suggested**
  ("laps ~27k/race, telemetry ~90M/season, etc."). None of those are behind a
  drift gate, so per §7 rule 3 (and CONVENTIONS' "Counts live behind a gate or
  not in prose") the dataset cards on `data/overview` describe shape only — apply
  the same restraint in Parts 4–6 rather than reusing the spec sketches' literal
  estimates verbatim (`ingestion/quickstart`'s "~100 MB, 2–5 min" is explicitly
  exempted already, since §5.7 sources it from the `--dry-run` formula, not a
  hand count).
- **Mermaid is plain fenced ` ```mermaid ` code blocks, not a `<Mermaid>` JSX
  tag** — confirmed against Part 2's actual usage in `docs/index.mdx`, despite
  §6's component table naming `<Mermaid>`. Use fenced blocks in Part 5
  (`ingestion/architecture` has the heaviest Mermaid load — pipeline flowchart +
  retry state diagram).
- **Jolpica reference data feeds no dbt source today** — `grep -rln jolpica
  transform/` is empty. `jolpica_client.py`'s own docstring claims it feeds
  "historical marts"; `data/source-jolpica` deliberately does **not** repeat that
  claim, phrasing it instead as decoupled-and-not-yet-consumed. Don't let later
  parts (or a regenerated reference page) restate the docstring's claim as
  current fact.
- **DQ schema-gate precision**: re-reading `ingest_race` vs `ingest_qualifying`
  directly (not just DESIGN.md's resilience table) shows the schema check blocks
  the write **only** for race laps — `ingest_qualifying` discards the check's
  pass/fail (`_, dupe_count = _run_quality_checks(...)`) and never gates on it at
  all, even for a missing required column. Row count / null rate / duplicate
  checks never block either session type. `data/data-quality`'s Tabs/table encode
  this precisely; keep the same precision when `ingestion/architecture` (Part 5)
  narrates the same code path — don't regress to the simpler "schema blocks race,
  everything else warns" framing without the qualifying-never-gates nuance.
- **FastF1 version citations are split by page on purpose**: `data/source-fastf1`
  describes the tz-aware/timedelta `Time` handling generically, with no version
  number (per §5.2's own CONVENTIONS note); `data/known-issues` is where the
  FastF1 v3.8.3 attribution for the 2024 `session_time_s` null actually lives,
  since that page is the root-caused known-issue catalogue. Not an inconsistency
  — don't "fix" one page to match the other.
- **New Data-tab card icons** (unspecified in the plan, extending the existing
  Tab-icon decision): `gauge`=laps, `radio`=telemetry, `thermometer`=weather,
  `megaphone`=race control, `flag`=FastF1, `trophy`/`award`/`timer`=Jolpica's
  three endpoints. Reuse these verbatim for the same concepts in Parts 4–6 rather
  than picking new icons for the same dataset.
- Validated Part 3 with `make docs-coverage-check` (both snippet gates pass
  unchanged — Part 3 only *imports* `bronze-coverage.mdx`, never edits it) and
  `mintlify validate` + `mintlify broken-links` from `docs/`: the only output is
  the same pre-existing 9 nav-only warnings (Parts 4–6 pages, expected since Part
  1) plus 4 broken links from the new pages forward-linking into
  `ingestion/quickstart`/`ingestion/manifest-report`/`ingestion/architecture`
  (Part 4–5, not yet built) — zero issues attributable to Part 3's own content,
  mirroring Part 2's precedent of forward-linking into not-yet-built pages.
- **`docs/quickstart.mdx` was NOT actually nav-orphaned** (correcting the Part 3
  note above) — `docs/index.mdx` and `docs/introduction.mdx` (Part 2) both had a
  live "Quick Start" `<Card>` linking `/quickstart` with copy specifically about
  *building the warehouse and querying `fct_lap_residuals` with DuckDB* (`make
  setup && make dbt-dev`), which is Transform-layer content, not ingestion
  content. Deleting the file per Part 4's instruction without fixing those cards
  would have broken two live homepage links. Fixed both cards in place to point
  at `/ingestion/quickstart` with copy matching what that page actually covers
  ("ingest your first race in five minutes") — the DuckDB-build-and-query
  narrative has **no page today** and is lost until the Transform tab gets its
  real pass; flag to the user if that gap matters before then. Also fixed
  `transform/README.md`'s now-dead `.../quickstart` hosted link (→ split into
  `.../ingestion/quickstart` for setup + `.../decomposition/seven-term-identity`
  for what the layer computes) since it's an inbound link from outside `docs/`
  that `mintlify broken-links` can't see.
- **`scripts/docs_facts.py` hardcoded `docs/quickstart.mdx`** as one of 3 files
  it reconciles headline counts across (dbt model/test counts vs README.md and
  `docs/ml/overview.mdx`). Deleting the file broke `make docs-facts` outright
  (`FILE NOT FOUND`). Fixed by dropping the entry — the new
  `ingestion/quickstart.mdx` correctly carries no hand-typed dbt counts at all
  (CONVENTIONS' counts-behind-a-gate rule), so there's nothing in Part 4's pages
  to reconcile against; re-add a Transform-tab page here when one exists that
  states these counts in prose.
- Verified Part 4 against the real CLI: read `ingest.py`'s `_build_parser`/
  `main` directly rather than trusting the plan's own §5.9 sketch — confirms
  `--start-season`/`-s`/`--end-season`/`--round`/`--session`/`--skip-telemetry`/
  `--telemetry-full`/`--force`/`--dry-run`/`--log-level` and the exact validation
  errors (mutually-exclusive season args, start>end, `--round` needs a single
  season). Dropped the `--telemetry-full` help text's `(v0.2)` suffix per
  CONVENTIONS (no version labels survive into docs).
- **The "Test fixtures" data-scope row is `make test-all`, not `make dbt-dev`.**
  `make dbt-dev`'s `bronze_base` var defaults to `../data/bronze` (real Bronze on
  disk) — it does **not** read `transform/tests/fixtures/bronze/` unless you pass
  `--vars '{"bronze_base": "../transform/tests/fixtures/bronze"}'` explicitly,
  which is exactly what `make test-all`/`test-fast` (and CI) do. Caught by
  reading `transform/models/staging/src_formula1.yml` and the Makefile rather
  than trusting the plan's §5.8 sketch's implied "fixtures → `make dbt-dev`"
  pairing — don't repeat that pairing in Part 5+.
- **Offline tests have no on-disk fixture Parquet.** `ingestion/tests/` has no
  `fixtures/` directory; `make test` runs `pytest` against small in-memory
  pandas DataFrames and mocked FastF1 responses (`test_ingestion.py`,
  `test_jolpica.py`). Don't describe it as "fixture Parquet" anywhere else in
  Part 5.
- Validated Part 4 with `make docs-coverage-check` + `make docs-facts` (after the
  fix above) + `make docs-audit` (0 errors; the 236 warnings are pre-existing
  app/ file-header gaps, unrelated to this plan) + `mintlify validate` +
  `mintlify broken-links` from `docs/`: the only output is 4
  validate-warnings/6 broken-links, all forward-references into
  `ingestion/{verify,manifest-report,replay,architecture}` (Part 5, not yet
  built) — zero issues attributable to Part 4's own content.

- **`make simulate` Warning placed on `ingestion/replay`, not deferred.** Confirmed
  directly against `replay_simulator.py`: live mode needs `EVENTSTREAM_CONNECTION_STRING`/
  `EVENTHUB_NAME` and the flag is `--dry_run` (underscore — `replay_simulator.py`'s own
  argparse, unlike `ingest.py`'s hyphenated `--dry-run`). The page leads with a
  `<Warning>` and the working `--dry_run` invocation rather than the broken `make simulate`
  default, matching the decision already logged above.
- **Retry sequence restated as 1s → 2s → 4s on `ingestion/architecture`**, consistent with
  the earlier correction (no 8s reached — `max_attempts=4` only allows 3 sleeps). The
  Mermaid state diagram and prose both encode this; `_with_retry`'s 4th-attempt failure
  re-raises immediately with no further wait.
- **Found and fixed a path-pattern bug beyond the plan's named phantom-column list**:
  `reference/data-schemas.mdx` claimed telemetry has a `session=<Q|R>/` partition segment.
  Reading `ingest.py` directly shows `_write_telemetry`/`_write_race_control` are called
  only from `ingest_race`, never `ingest_qualifying` — telemetry and race control are
  **race-only** datasets with no `session=Q/` directory at all. Only **laps and weather**
  ever get that segment (qualifying only). Fixed the path-variable table and both
  datasets' "File pattern" lines in `data-schemas.mdx`; the 4 `.schema.json` files and
  generated pages were already dataset-scoped so didn't carry this specific bug.
- **`session` vs `session_type` phantom-column fix applies to laps, weather, and
  telemetry — three schema files, not the two the plan's specifics line named.**
  `ingest.py` only ever writes a `session_type="Q"` column, and only on the qualifying
  branch (`ingest_qualifying` for laps, the `session_type=="Q"` branch of `_write_weather`).
  Race files of every dataset carry no session column at all; telemetry never gets one
  either way (race-only, see above). Replaced each phantom `session` (required, enum
  `R`/`Q`) property with an optional `session_type` (`"Q"`-only, not required) on
  `laps.schema.json`/`weather.schema.json`, and removed the property entirely from
  `telemetry.schema.json` (race_control never declared one).
- **Generator enrichment: new `x-phantom-columns` schema field, not folded into
  `x-notes`.** Each `.schema.json` gained a top-level `x-phantom-columns: [{name, reason}]`
  array; `gen_schema_reference.py` renders it as a `<Warning>` block before `## Columns`
  when present. Keeps the phantom-column list structured and dataset-scoped instead of
  free text, and it's the same shape `known-issues.mdx`'s hand-written Accordion already
  uses, so the two surfaces (generated schema page, hand-written known-issues catalogue)
  stay easy to keep in sync by eye.
- **Columns render as `<ResponseField>`, replacing the old markdown table** — per §6's
  component-coverage table, which named `<ResponseField>` for schema columns specifically.
  `nullable`/`required` is now expressed via the `required` attribute rather than a
  Yes/No table cell; `*Source: …*` is appended in prose inside the field body.
- **`telemetry.schema.json` gained a real `nGear` column it never had** (was simply
  absent, not phantom-named-wrong) and lost `brake_pct` (phantom) and a boolean `drs`
  (renamed `DRS`, integer enum, 10/12/14=open) — matches `SCHEMA.md`'s hand-verified
  column list. Did **not** also fix `DriverNumber`'s declared type (`integer` vs the
  real `VARCHAR`) or `LapNumber` (`integer` vs real `DOUBLE`) — those weren't named in
  the plan's phantom-column bug list and are a type-precision issue, not a phantom-column
  one; flagging here rather than silently expanding scope.
- **`race_control.schema.json`'s `Time` column re-typed** from `string`/"HH:MM:SS format"
  (wrong — `SCHEMA.md` has it as `TIMESTAMP_NS`, a real timestamp, not a formatted string)
  to `integer` + `x-dtype: "TIMESTAMP_NS"`, matching the `int64`-with-`x-dtype` pattern
  already used elsewhere in the same file for nanosecond columns. `session_time_s`'s
  description corrected from "use `time` column instead" to "use `Lap` for joins instead"
  — the lowercase `time` was phantom, and the actual established join key (from
  `known-issues.mdx`) is `Lap`, not `Time`.
- **`ingestion/README.md`'s Bronze Coverage table was self-contradictory**, not just
  stale: its own per-season rows summed to 148, but the printed Total row said 168 —
  simple arithmetic drift from hand-maintenance, compounding the already-known stale-168
  problem from the docs site (see the earlier 149-vs-168 finding above). Replaced the
  hand-typed table with a pointer to the live gated table on `/data/known-issues`,
  removing the second hand-copy of the same data rather than re-syncing it once more.
  Also fixed: the fixtures-scope command (`make dbt-dev` → `make test-all`, same
  established correction as the docs site), `pytest tests/ -v` → `make test` (the former
  would also collect the network-dependent `test_integration_fastf1.py`, since no pytest
  marker excludes it by default), and `schemas/telemetry.schema.json`'s description
  "18Hz" → "~10 Hz" (the real sample rate per `SCHEMA.md`/docstrings).
- **`docs/AGENTS.md` reconciled** (flagged as stale-since-Part-1 and deferred to Part 7 in
  an earlier note): its "five content areas" line still described the old
  Documentation/Reference two-tab world. Rewrote to name the five real tabs and state
  that each layer tab folds in its own generated reference, no separate Reference tab.
  Left **"The Decomposition"** and **"App & Visualizations"** group-name references
  alone — both names are still accurate; they're now nav *groups* nested inside the
  Transform and App tabs respectively, not removed, just re-homed.
- **`make docs-reference` (full regen: schemas + CLI + macros + ML card) surfaced
  pre-existing, unrelated drift** when run as part of Part 7's validation pass: the
  generated `reference/cli/ingest.mdx` was missing the `--round` flag entirely (added to
  `ingest.py` at some point after that page was last generated), `reference/macros/`
  was missing a `circuit_id_from_name` macro page, and `reference/ml/degradation-model-v1.mdx`
  was still showing v3 model metrics despite the project's ML artifacts already being at
  v4 (see `[[project_ml_docs_v4_publish]]` in memory — a separate, earlier, already-complete
  body of work). None of this is Parts 5–7 scope; it's regenerated-from-source content
  that happened to be stale before this session touched it. Left the regeneration in
  place rather than reverting it — these are gated, autogenerated files with one correct
  output for the current source state, and reverting would just reintroduce the drift
  the gate exists to catch. Flag to the user since it touches files outside this plan's
  named list.

### Files touched so far (all uncommitted)

- `docs/docs.json` — rewritten, 5-tab nav
- `scripts/ingestion_docs_facts.py` — new
- `docs/snippets/bronze-coverage.mdx` — new, generated
- `Makefile` — added `docs-coverage`, `docs-coverage-check` (Part 2 extended both)
- `.github/workflows/docs-ci.yml` — added `bronze-coverage-drift` job (Part 2 added
  `overview-numbers-drift`)
- `scripts/overview_docs_facts.py` — new (Part 2)
- `docs/snippets/overview-numbers.mdx` — new, generated (Part 2)
- `docs/index.mdx`, `docs/introduction.mdx`, `docs/key-concepts.mdx` — rewritten
  (Part 2)
- `docs/images/hero-degradation-simulator.png` — new, real screenshot (Part 2)
- `docs/data/overview.mdx` — new (Part 3)
- `docs/data/source-fastf1.mdx` — new (Part 3)
- `docs/data/source-jolpica.mdx` — new (Part 3)
- `docs/data/data-quality.mdx` — new (Part 3)
- `docs/data/known-issues.mdx` — new (Part 3)
- `docs/ingestion/quickstart.mdx` — new (Part 4)
- `docs/ingestion/data-scope.mdx` — new (Part 4)
- `docs/ingestion/cli.mdx` — new (Part 4)
- `docs/ingestion/configuration.mdx` — new (Part 4)
- `docs/ingestion/monitoring.mdx` — new (Part 4)
- `docs/quickstart.mdx` — deleted (Part 4, superseded)
- `docs/index.mdx`, `docs/introduction.mdx` — Quick Start card retargeted to
  `/ingestion/quickstart` (Part 4)
- `transform/README.md` — dead `.../quickstart` hosted link fixed (Part 4)
- `scripts/docs_facts.py` — dropped the now-deleted `docs/quickstart.mdx` entry
  (Part 4)
- `docs/ingestion/verify.mdx` — new (Part 5)
- `docs/ingestion/manifest-report.mdx` — new (Part 5)
- `docs/ingestion/replay.mdx` — new (Part 5)
- `docs/ingestion/architecture.mdx` — new (Part 5)
- `ingestion/schemas/laps.schema.json` — phantom `session`→`session_type` fix,
  `x-phantom-columns` added (Part 6)
- `ingestion/schemas/weather.schema.json` — same `session`→`session_type` fix,
  `x-phantom-columns` added (Part 6)
- `ingestion/schemas/telemetry.schema.json` — removed `brake_pct`/phantom `session`,
  `drs`→`DRS` enum, added real `nGear` column, `x-phantom-columns` added (Part 6)
- `ingestion/schemas/race_control.schema.json` — removed phantom `code`, Title-Cased
  `lap`/`time`/`flag`→`Lap`/`Time`/`Flag`, `x-phantom-columns` added (Part 6)
- `scripts/gen_schema_reference.py` — enriched: `<Warning>` block from
  `x-phantom-columns`, columns rendered as `<ResponseField>` instead of a table (Part 6)
- `docs/reference/schemas/{laps,weather,telemetry,race_control}.mdx` — regenerated
  (Part 6, generated)
- `docs/reference/data-schemas.mdx` — corrected: phantom columns, telemetry/race-control
  path pattern, OpenF1→FastF1 attribution, 168-races literal removed (Part 6)
- `ingestion/README.md` — reconciled: doc links retargeted to the Data tab + new
  ingestion how-to pages, self-contradictory coverage table replaced with a link to the
  gated table, `make dbt-dev`→`make test-all` (fixtures row), `pytest tests/ -v`→
  `make test`, "18Hz"→"~10 Hz" (Part 7)
- `docs/AGENTS.md` — "five content areas" line updated to the five real tabs (Part 7)
- `docs/reference/cli/ingest.mdx`, `docs/reference/macros/index.md`,
  `docs/reference/macros/circuit_id_from_name.mdx` (new),
  `docs/reference/ml/degradation-model-v1.mdx` — regenerated via `make docs-reference`;
  pre-existing drift unrelated to this plan, see the note above (Part 7, generated)

---

## 1. Goal

Restructure the Mintlify site from two tabs (`Documentation`, `Reference`) into a
**tab per pipeline layer**, so the site mirrors the canonical reading order defined
in CONVENTIONS.md (`ingestion → transform → ml → app`). Build the **Data** tab
first, to production quality, as the template every later tab copies.

The **Data** tab is a single tab that owns the whole data layer: where the data comes
from and how it is shaped (sources, Bronze schemas, quality, known issues) **and** how
to populate it (the ingestion how-to — quickstart, CLI, monitoring, ops, architecture
deep-dive). Ingestion is *not* a separate tab; it is the operational half of Data.

The bar: a reader who has never seen the repo can land on the Data tab, ingest
their first race in five minutes, and — if they want — understand every line of
`ingestion/src/` and every exception it swallows, without opening the source. The
docs explain the code *and* its failure modes better than the code explains itself.

Scope of this plan:
- **Full**: the target tab layout (sketched, §3) and the docs.json restructure (§4).
- **Deep**: the Data tab — every page (data-layer + ingestion how-to), its source of
  truth, its Mintlify components, and its CONVENTIONS obligations (§5–§7).
- **Deferred**: Transform / ML / App tab content. Those tabs are stubbed in the nav
  now; their pages are a later pass that reuses the Data template.

---

## 2. Source-of-truth map (what the Ingestion docs must cover)

Every Ingestion page is backed by real code. No page invents behaviour. This is the
authoritative list of what exists and where:

| Concern | File | Key facts to surface |
|---|---|---|
| CLI controller / orchestration | `ingestion/src/ingest.py` | season range vs single round; `--session R/Q/both`; `--force`, `--dry-run`, `--skip-telemetry`, `--telemetry-full`; mutually-exclusive `--start-season`/`-s`; per-season → per-round → per-session loop |
| Per-dataset writers | `ingest.py` `_write_weather/_write_race_control/_write_telemetry/_write_telemetry_full/_write_pos_data/_write_results/_write_track_status/_write_session_status/_write_circuit_info/_write_event_schedule` | each wrapped in its own try/except; one bad file never aborts a race |
| Retry / backoff | `ingest.py` `_with_retry` (1→2→4→8s, 4 attempts) | transient network/FastF1 blips recover automatically |
| Idempotency | `ingest_race`/`ingest_qualifying` `target.exists() and not force` | re-run after crash resumes from the gap |
| Schema fingerprint | `ingest.py` `_schema_fingerprint` (SHA-1, 12 chars, sorted cols) | makes FastF1 column drift detectable |
| Run manifest | `ingest.py` `_make_manifest_row`/`_write_manifest` | one `run_<id>.parquet` per run; status ok/skip/error + rows + dq flag + fingerprint |
| Data-quality engine | `ingestion/src/data_quality.py` | `validate_bronze_schema` (raises), `assert_row_count` (min 50), `check_null_rates` (5%), `check_lap_key_duplicates`; `LAP_KEY_COLUMNS`, `REQUIRED_COLUMNS` |
| DQ severity tiers | `ingest.py` `_run_quality_checks` + DESIGN.md | schema fail on **race** → skip write + record `error`; low rows / high nulls / quali → warn only |
| Reference-data client | `ingestion/src/jolpica_client.py` | Ergast→Jolpica succession; standings + classified pit stops; 429 `Retry-After`, pagination (limit 100), `_throttle` ≥0.30s; *reference, not timing* |
| Config / env | `ingestion/src/environment.py` | `FASTF1_CACHE_DIR`, `INGESTION_LOG_LEVEL`, `INGESTION_TIMEOUT_SECONDS`; `.env` discovery; no credentials |
| Monitor | `ingestion/scripts/monitor_ingest.py` | stdlib-only tail; exits non-zero on `[DQ FAIL]`/process death, 0 on `=== COMPLETE:` |
| Verify | `ingestion/verify_bronze.py` | counts/nulls/dupes/schema; partial-season aware; `--markdown` regenerates coverage |
| Manifest report | `ingestion/manifest_report.py` | latest status per session + schema-drift across runs; non-zero on error/drift |
| Replay demo | `ingestion/src/replay_simulator.py` | `make simulate` lap-by-lap replay of a Bronze race |
| Schemas (column truth) | `ingestion/SCHEMA.md`, `ingestion/schemas/*.schema.json` | per-dataset columns, nanosecond time units, DRS enum (10/12/14), phantom columns, Spa 7077 m |
| Design rationale | `ingestion/DESIGN.md` | Bronze-is-dumb, append-only, Hive partitioning, gate-races/warn-quali, resilience table |
| make targets | `Makefile` | `ingest-all`, `ingest-recent`, `ingest-jolpica`, `verify-bronze`, `monitor-ingest`, `manifest-report`, `simulate`, `test`, `test-integration` |

"Exceptions" the user asked to document are **two kinds**, and both get first-class
coverage:
1. **Code exceptions** — what `try/except` catches, what `ValueError` the DQ engine
   raises, what blocks a write vs. what only warns, the retry envelope, the 429 path.
2. **Data exceptions** — the known-issue catalogue (2024 `session_time_s` null, Las
   Vegas timing flags, pre-season Rd 0), the *expected* gaps (SC/pit-out telemetry,
   red-flagged short sessions), and the phantom columns that look real but aren't.

---

## 3. Target information architecture (the "lay the layers out" sketch)

Five tabs. The first orients readers to what the app *does*; the second (Data) explains
the data **and** how to populate it — sources, Bronze schemas, data flow, quality,
known issues, *plus* the full ingestion how-to; the next three are the remaining
pipeline layers, in reading order, each with its generated reference folded in. No
separate Reference tab and no separate Ingestion tab — every layer owns its own
reference, and ingestion lives inside Data.

```
Overview              ── lightweight: what the app does, home-page features, use cases
Data                  ── sources, Bronze schemas, flow, quality, known issues +
                         ingestion how-to (quickstart, CLI, monitoring, ops, architecture)
                         (this plan — built first)
Transform             ── dbt + DuckDB models & macros (stub now; later pass)
Machine Learning      ── XGBoost → ONNX models & validation (stub now; later pass)
App                   ── React visualizations & features (stub now; later pass)
```

**Overview tab** (lightweight, app-centric — *and* a recruiter-grade landing page):
This tab is the first thing a stranger sees, so it doubles as a portfolio cover. It must
look impressive at a glance and explain the system at a high level without any math.

Content:
- What the system does and why (the elevator pitch, not the seven-term math).
- Home page tour — link to the live app's features and what each visualizes
  (Ghost Race Standings, Degradation Simulator, etc.), oriented around *what you can
  do*, not *how we computed it*.
- Quick case studies or highlights (e.g. "Here's what we found about X driver at Y
  circuit").
- No deep decomposition math; that's internal to the layers (transform) where it's
  enforced by CI.

Recruiter-facing visuals (the "make it impressive" payload):
- **Hero**: a one-line value proposition + a `<Frame>` containing a screenshot or short
  loop of the live app (the most visually striking feature, e.g. the Degradation
  Simulator or Ghost Race Standings).
- **Layer-flow diagram**: a horizontal `<Mermaid>` flowchart of the whole pipeline —
  `Sources (FastF1 · Jolpica) → Ingestion (Bronze) → Transform (dbt + DuckDB) →
  Machine Learning (XGBoost → ONNX) → App (React)` — light, labelled, clickable through
  to each layer tab. This is the "light graph of the flow of the layers" the diagram
  the recruiter sees first.
- **Tech-stack overview**: a `<CardGroup>` of the core technologies grouped by layer
  (Python · FastF1 · DuckDB · dbt · XGBoost · ONNX Runtime Web · React · Vite · GCS ·
  Firebase), each card a one-line "what it does here" + an `<Icon>` or small logo via
  `<Frame>`/`<img>`. High level, no version pinning.
- **By-the-numbers strip**: a `<CardGroup>` of headline figures (seasons covered,
  races, models, app features) — all rendered from the gated coverage snippet / docs
  facts, **never** hand-typed (CONVENTIONS §counts).
- Optional `<Steps>` "How a question becomes a chart" — a 4-step narrative tracing one
  insight from raw timing to an app visual, linking into the layer tabs.

Visual / CONVENTIONS notes:
- Logos must be self-hosted or linked from official brand assets and used only to
  identify the tool, implying no endorsement; keep them small and monochrome-friendly
  for the dark theme. Prefer the existing `lucide` icon set where a brand logo isn't
  essential.
- All figures come from the docs-facts / coverage gate, not literals; present tense, no
  version or phase framing.

**Data tab** (new, owns the data layer *and* the ingestion how-to). Two halves, top to
bottom: the data-layer explanation first (what exists), then the ingestion how-to (how
to populate it).

*Data-layer half (what exists):*
- Overview: sources (FastF1, Jolpica), why they matter, data flow.
- Sources: FastF1 quirks, Jolpica as Ergast successor, politeness contract.
- Bronze schemas (laps, telemetry, weather, race control, results, track/session
  status, circuit info) — every column, nanoseconds, enums, phantom columns.
- Data quality: checks, severity tiers, what blocks the write vs warns.
- Known issues & expected gaps: 2024 nulls, sparse telemetry, red-flagged sessions.
- Coverage table (gated snippet).

*Ingestion how-to half (how to populate Bronze):*
- Get Started: quickstart, choose data scope.
- How to Ingest: CLI reference, configuration, monitoring.
- Operations: verify, manifest report, replay simulator.
- Architecture deep-dive: code walkthrough, per-writer try/except, retry envelope,
  idempotency, schema fingerprinting.

**Transform/ML/App tabs** (later passes):
- Each carries its own generated reference (dbt models + macros, ML models + validation,
  app features) folded into narrative pages so a reader lands on the Transform tab and
  has everything Transform there — no jumping to a separate Reference tab.

Mapping from today's two tabs:
- Today's **Documentation** tab: `Get Started` + `Quickstart` → **Data** (the ingestion
  how-to half); `The Decomposition` → **Overview** (lightened, app-centric); `Case
  Studies` → **Overview**; `Machine Learning` → **ML tab** (later); `App &
  Visualizations` → **App** tab (later).
- Today's **Reference** tab: `Bronze Schemas` + `ingest` CLI → **Data** tab; Models /
  Macros / ML Models → folded into their respective layer tabs.

---

## 4. docs.json restructure

`navigation.tabs` becomes five tabs: Overview (lightened), Data (new — data layer +
ingestion how-to), Transform, ML, App. No Reference tab and no Ingestion tab — each
layer owns its reference, and ingestion is folded into Data.

**Overview tab** (lightened):
```jsonc
{
  "tab": "Overview",
  "icon": "home",
  "groups": [
    {
      "group": "What You Can Do",
      "icon": "lightbulb",
      "pages": [
        "index",          // app tour, home-page features
        "introduction",   // what the system does & why
        "key-concepts"    // high-level ideas (pace, compounds, etc.)
      ]
    },
    {
      "group": "Case Studies",
      "icon": "flag",
      "pages": [
        "findings/overview",
        "findings/sao-paulo-2021"
      ]
    }
  ]
}
```

**Data tab** (new — owns the data layer *and* the ingestion how-to). One tab, eight
groups: the four data-layer groups first (what exists), then the four ingestion how-to
groups (how to populate it). The reading order down the sidebar is "understand the data
→ populate the data".
```jsonc
{
  "tab": "Data",
  "icon": "table",
  "groups": [
    // --- Data layer: what exists ---
    {
      "group": "Overview",
      "icon": "info",
      "pages": [
        "data/overview"           // sources, why they matter, data flow
      ]
    },
    {
      "group": "Sources",
      "icon": "plug",
      "pages": [
        "data/source-fastf1",
        "data/source-jolpica"
      ]
    },
    {
      "group": "Bronze Schemas",
      "icon": "database",
      "pages": [
        "data/data-schemas",
        "data/schemas/laps",
        "data/schemas/telemetry",
        "data/schemas/weather",
        "data/schemas/race_control"
      ]
    },
    {
      "group": "Quality & Coverage",
      "icon": "shield-check",
      "pages": [
        "data/data-quality",
        "data/known-issues"
      ]
    },
    // --- Ingestion how-to: populate Bronze ---
    {
      "group": "Get Started",
      "icon": "rocket",
      "pages": [
        "ingestion/quickstart",
        "ingestion/data-scope"
      ]
    },
    {
      "group": "How to Ingest",
      "icon": "workflow",
      "pages": [
        "ingestion/cli",
        "ingestion/configuration",
        "ingestion/monitoring"
      ]
    },
    {
      "group": "Operations",
      "icon": "activity",
      "pages": [
        "ingestion/verify",
        "ingestion/manifest-report",
        "ingestion/replay"
      ]
    },
    {
      "group": "Deep Dive",
      "icon": "code",
      "pages": [
        "ingestion/architecture"
      ]
    }
  ]
}
```

Page slugs keep their `data/*` and `ingestion/*` prefixes (the on-disk folders are not
moved in this pass); only the nav unifies them under one Data tab. The eight group names
stay distinct so the sidebar reads as two clear halves.

**Transform / ML / App tabs** (stubbed now, detailed later). Each gets 2–3 narrative
pages + a reference section (dbt models + macros, ML models + validation, app
features), all within the same tab.

**Map from today:**
- Today's `Documentation` → `Overview` (lightened) + `Data` (new, incl. the ingestion
  how-to).
- Today's `Reference` → folded into `Data` (schemas, sources, CLI) + future
  Transform/ML/App tabs.

CONVENTIONS check on the nav itself: tab/group names use one vocabulary — "Get
Started", "How It Works", "Quality & Operations" — and the same names will be reused
verbatim when Transform/ML/App tabs are built, so the four layer tabs read
identically.

---

## 5. Pages — the Data tab (data layer + ingestion how-to)

One tab, two halves. The **data-layer** half explains what exists (sources, schemas,
quality, flow); the **ingestion how-to** half is the procedure (quickstart, CLI,
monitoring, ops, architecture deep-dive). Each spec gives: **purpose**, **source of
truth**, **Mintlify components**, and **CONVENTIONS notes**. Pages are authored MDX
unless marked *generated*. Page slugs keep `data/*` and `ingestion/*` prefixes.

---

### Data-layer pages (`data/*`)

### 5.1 `data/overview` — what the Bronze layer is and how data flows
- **Purpose**: one screen that orients a cold reader to the data layer — where data
  comes from (FastF1, Jolpica), Bronze's job (raw, partitioned, no computation), the
  datasets it holds, how they flow downstream, and the schema fingerprint that detects
  drift.
- **Source**: README intro, DESIGN.md §"Bronze is dumb", SCHEMA.md directory tree,
  `ingest.py` schema_fingerprint.
- **Mintlify**: opening `<Mermaid>` flowchart (FastF1/Jolpica → ingest → data/bronze/
  laps/telemetry/weather/race_control/… → transform); `<CardGroup cols={2}>` of the
  datasets (each one line: laps ~27k/race, telemetry ~90M/season, etc.) with icons +
  links to schema pages; `<Note>` "Bronze is dumb — all business logic lives in dbt";
  `<Info>` "No credentials required"; `<Warning>` "Raw data: nanosecond timedeltas,
  enums, sparse gaps during SC/pit-out."
- **CONVENTIONS**: present tense; no "v0.2". The "168 races" and "550M telemetry rows"
  are rendered from the gated snippet, not literals here.

### 5.2 `data/source-fastf1` — the primary timing source
- **Purpose**: what FastF1 provides, its quirks (schema drift, on-disk cache, timezone
  handling), and the retry envelope that absorbs transient blips.
- **Source**: `ingest.py` `_load_race_session`/`_load_qualifying_session`, `_with_retry`,
  SCHEMA.md nanosecond/enum notes.
- **Mintlify**: `<Note>` no-auth + cache to `data/cache/`; `<Warning>` nanosecond
  time units and the DRS enum (10/12/14 = open) — "decode once in staging, don't copy
  magic numbers"; `<Accordion>` "Schema drift between seasons" → fingerprint detects it
  (see `data/quality`); `<Tip>` on-disk cache makes even `--force` re-pulls cheap.
- **CONVENTIONS**: no version history ("v3.8.3 changed `Time` column type") — state the
  workaround inline ("handles both timedelta and tz-aware `Time` correctly").

### 5.3 `data/source-jolpica` — reference data (standings, pit stops)
- **Purpose**: Ergast's successor, Jolpica — what it provides (driver/constructor
  standings + classified pit stops), and why it's *reference*, not timing.
- **Source**: `jolpica_client.py`, Makefile `ingest-jolpica`.
- **Mintlify**: `<Note>` Ergast shut down after 2024; Jolpica is the Ergast-compatible
  successor; `<ParamField>` for CLI (`--start-season`, `--end-season`, `--rounds`,
  `--min-interval`); table of endpoints (driver/constructor standings, pit stops) →
  output path; `<Warning>` politeness contract — ≥0.30s between calls, 429 honours
  `Retry-After`, pagination at 100 rows; `<Info>` "Reference data never feeds the live
  path, only historical marts."

### 5.4 `data/data-quality` — checks, severity tiers, expected gaps
- **Purpose**: the DQ engine's four checks, the gate-races/warn-quali tiering, and
  what "expected gaps" (SC/pit-out telemetry, red-flagged sessions) mean.
- **Source**: `data_quality.py` (all four checks + required/lap-key columns), `ingest.py`
  `_run_quality_checks`, DESIGN.md §"Warn-don't-fail" + resilience table.
- **Mintlify**:
  - `<Tabs>` "Blocks the write" (schema-fail-on-race) vs "Warns only" (low rows /
    high nulls / quali).
  - `<AccordionGroup>` one `<Accordion>` per check: `validate_bronze_schema` (missing
    required columns), `assert_row_count` (min 50), `check_null_rates` (5% threshold),
    `check_lap_key_duplicates` (corruption marker) — each with the logic.
  - `<Warning>` schema failure on race laps records `status=error` and **skips the
    write**.
  - severity-tier table from DESIGN.md.
  - `<Note>` on expected gaps: telemetry sparse during SC / pit-out / DNF — the writers
    skip these by design, not failure.
- **CONVENTIONS**: present tense; structural table, no hand-written counts.

### 5.5 `data/known-issues` — schema drift, timing gaps, phantom columns
- **Purpose**: the data the source *doesn't* give cleanly (2024 `session_time_s` null,
  Las Vegas timing flags, phantom columns), why it's acceptable, and the coverage
  table (races/datasets ingested).
- **Source**: README "Known Issues", SCHEMA.md per-dataset "phantom columns", coverage
  snippet.
- **Mintlify**:
  - **coverage table** from the gated snippet (see §7) — never hand-typed.
  - `<AccordionGroup>` one `<Accordion>` per known issue (root cause / impact /
    remediation): 2024 `session_time_s` null (FastF1 v3.8.3 regression — join via `Lap`),
    Las Vegas timing flags (under investigation).
  - `<Accordion>` "Phantom columns you might expect but don't exist" — weather
    `rainfall_mm` (boolean only), telemetry `brake_pct`/boolean `drs`, race_control
    lowercase `lap`/`time`.
  - `<Note>` "Red-flagged / short sessions are common in qualifying; the DQ engine
    warns but accepts them."
- **CONVENTIONS**: no per-season race counts in prose (lives only in the snippet).

### 5.6 `data/schemas/*` — Bronze column truth *(generated, enriched)*
- **Purpose**: per-column definitions for each dataset.
- **Source**: `gen_schema_reference.py` ← `SCHEMA.md` / `ingestion/schemas/*.schema.json`.
- **Mintlify**: enrich the generator's template to emit `<Warning>` blocks for
  phantom-column lists and `<ResponseField>` per column (type / nullable / notes).
  On-disk paths stay at `reference/schemas/*`; only the nav grouping moves into the
  Data tab (no file relocations in this pass).
- **CONVENTIONS**: do **not** render SCHEMA.md's "Version History" (v1.0/v1.1/v1.2)
  into the page — that is process history. If a changelog is wanted, drive it from
  release-please, not hand-written version notes.

---

### Ingestion how-to pages (`ingestion/*`)

### 5.7 `ingestion/quickstart` — ingest your first race
- **Purpose**: the "just ingest data" path the user emphasised. Zero → one race on
  disk → verified, in five minutes.
- **Source**: README §1–§3, §5; Makefile `ingest-recent`, `verify-bronze`.
- **Mintlify**: `<Steps>` — (1) install `pip install -r ingestion/requirements.txt`;
  (2) ingest one race with `python ingestion/src/ingest.py --season 2024 --round 1
  --session R`; (3) verify with `make verify-bronze`; (4) explore with `make simulate`.
  Each `<Step>` has a `<CodeGroup>` (single race / recent seasons / full backfill) and
  an expected-output block. End with a `<Check>` "You now have a partitioned Bronze
  race on disk" and a `<CardGroup>` of next steps (CLI, scope, data schemas).
- **CONVENTIONS**: the runtime/size figures ("~100 MB, 2–5 min") are estimates from
  code (`--dry-run` math: `races * 0.15 GB`); phrase as "approximately" and source the
  estimate from the dry-run formula rather than a hand-count.

### 5.8 `ingestion/data-scope` — choose how much to pull
- **Purpose**: pick the smallest scope for the task (fixtures → recent → full →
  single race → offline tests).
- **Source**: README §2 scope table; Makefile targets; `transform/tests/fixtures/`.
- **Mintlify**: `<Tabs>` one tab per scenario (each with the command, time, size, and
  "use when"); `<Tip>` for the default path (fixtures for SQL work, `ingest-recent` to
  scale-test); `<Warning>` that a full backfill is hours and ~2 GB.
- **CONVENTIONS**: no per-season race counts in prose here (those live only in the
  gated coverage snippet on the data/known-issues page).

### 5.9 `ingestion/cli` — the ingest command, every flag
- **Purpose**: complete CLI surface with the *why* and *when* for each flag.
- **Source**: `ingest.py` `_build_parser` + `main` validation.
- **Mintlify**: `<ParamField>` per option (`--start-season`/`-s`/`--end-season`,
  `--round`, `--session`, `--skip-telemetry`, `--telemetry-full`, `--force`,
  `--dry-run`, `--log-level`), documenting type, default, and the mutual-exclusion /
  validation rules (`--round` needs a single season; start>end errors).
  `<CodeGroup>` of canonical invocations; `<Warning>` that `--telemetry-full`
  multiplies size and time; link to the *generated* option list.
- **CONVENTIONS**: examples must not reference removed/renamed scripts; the docstring's
  `ingest_all.py`/`ingest_qualifying_remaining.py` ("replaces …") is history — omit it.

### 5.10 `ingestion/configuration` — environment & cache
- **Purpose**: the small config surface and the FastF1 cache.
- **Source**: `environment.py`; `ingest.py` cache enable.
- **Mintlify**: `<ParamField>` per env var (`FASTF1_CACHE_DIR`, `INGESTION_LOG_LEVEL`,
  `INGESTION_TIMEOUT_SECONDS`) with defaults; `<Info>` ".env is auto-discovered up the
  tree"; `<Note>` "FastF1 needs no credentials; it caches to `data/cache/`."

### 5.11 `ingestion/monitoring` — watch a long backfill
- **Purpose**: catch failures early during multi-hour runs; read the manifest.
- **Source**: README §4, `scripts/monitor_ingest.py`, `manifest_report.py`, DESIGN
  §observability.
- **Mintlify**: `<CodeGroup>` "Terminal 1 (ingest in background)" / "Terminal 2
  (monitor)"; `<Steps>` for the two-terminal pattern; a table of monitor exit
  conditions (`[DQ FAIL]`, OOM/disk/kill → non-zero; `=== COMPLETE:` → 0); `<Note>`
  the monitor is stdlib-only; `<Frame>` around a sample `make manifest-report` output.

### 5.12 `ingestion/verify` — confirm Bronze integrity
- **Purpose**: post-ingest verification; partial-season aware.
- **Source**: `verify_bronze.py`, README §5.
- **Mintlify**: `<Steps>` run `make verify-bronze`; `<Check>` callouts for each gate
  (race counts, nulls, dupes, schema); `<Note>` it checks only seasons present on disk
  (works after `ingest-recent`); `<Tip>` `verify_bronze.py --markdown` regenerates the
  coverage table so docs stay honest (ties to the §7 snippet gate).

### 5.13 `ingestion/manifest-report` — query the run manifest
- **Purpose**: understand every ingestion run — per-session status (ok/skip/error),
  and schema drift across runs.
- **Source**: `manifest_report.py`, DESIGN.md §observability.
- **Mintlify**: `<Steps>` run `make manifest-report`; a table of output columns (run_id,
  season, round, status, dq_passed, schema_fingerprint); `<Accordion>` "Schema drift
  detection" → how fingerprints catch FastF1 column changes; `<Frame>` with sample
  output (status per session + drift flags).

### 5.14 `ingestion/replay` — lap-by-lap race replay
- **Purpose**: explore one race's data lap-by-lap (demo / debugging).
- **Source**: `replay_simulator.py`, Makefile `simulate`.
- **Mintlify**: `<Steps>` run `make simulate` (or the full command); what the output
  shows (lap-by-lap delta, driver, compound, elapsed time); `<Frame>` with sample
  output; `<Note>` "useful for spot-checking ingestion results or debugging a
  specific lap."

### 5.15 `ingestion/architecture` — how ingestion works (code walkthrough)
- **Purpose**: the "explain the code" centrepiece. The full control flow and every
  resilience mechanism, readable without opening `ingest.py`.
- **Source**: `ingest.py` (all of it), DESIGN.md §pipeline + §resilience.
- **Mintlify**:
  - `<Mermaid>` flowchart of `main → ingest_season → ingest_race → load → DQ gate →
    partitioned write → manifest row`, plus the per-dataset try/except fan-out.
  - `<Mermaid>` state diagram of `_with_retry` (attempt → backoff 1/2/4/8s → raise).
  - `<Steps>` narrating one race's lifecycle (skip-if-exists → retry-load → DQ gate →
    write laps → write each companion dataset → manifest row).
  - `<AccordionGroup>` with one `<Accordion>` per writer function, each showing the
    real snippet and what it tolerates (e.g. `_write_telemetry` silently skips SC /
    pit-out laps — *expected*, not an error).
  - `<Note>` on idempotency (append-only, skip-unless-`--force`); `<Note>` on Hive
    partitioning and why it makes one-race queries cheap; `<Tip>` on the FastF1
    on-disk cache making `--force` re-pulls cheap.
- **CONVENTIONS**: replace any `KI-001`-style label from the source comments with the
  decision stated inline. No internal label survives into the page.

---

## 6. Mintlify component coverage ("use every feature")

The user asked for the full toolbox. Mapping each component to where it earns its place
(so the Ingestion tab is the showcase, not a wall of prose):

| Component | Where it's used |
|---|---|
| `<Steps>`/`<Step>` | quickstart, verify, monitoring (two-terminal), architecture lifecycle |
| `<Tabs>`/`<Tab>` | data-scope scenarios; DQ "blocks vs warns" |
| `<Accordion>`/`<AccordionGroup>` | per-writer-function, per-DQ-check, per-known-issue |
| `<CodeGroup>` | multi-command invocations; terminal-1/terminal-2 |
| `<ParamField>` | CLI flags (ingest, jolpica), env vars |
| `<ResponseField>`/`<Expandable>` | schema columns; nested manifest-row fields |
| `<Card>`/`<CardGroup>`/`<Columns>` | dataset catalogue, next-step nav |
| `<Note>`/`<Warning>`/`<Tip>`/`<Info>`/`<Check>` | callouts (phantom cols = Warning, defaults = Tip, no-creds = Info, verified = Check) |
| `<Mermaid>` | pipeline flow, per-race lifecycle, retry state machine |
| `<Frame>` | manifest-report / replay-simulator output |
| `<Snippet>` (reusable, `docs/snippets/`) | gated coverage table; shared command blocks reused across pages |
| `<Tooltip>` | inline glossary terms (slug, stint, compound, Bronze) |
| `<Icon>` | dataset cards, group icons |

Deliberately **not** used: `<Update>` / changelog for schema "version history" — that
is the process framing CONVENTIONS bans. A real changelog (if wanted) comes from
release-please, not hand-authored version notes.

---

## 7. CONVENTIONS.md conformance — baked in, not bolted on

The new docs must *pass* the rules the current README/SCHEMA partly violate. Concretely:

1. **Present tense, no process framing.** Rewrite README's "Follow steps 1–5 in order",
   "(v0.2)", "fixes KI-001", "replaces ingest_all.py" into capability descriptions.
   The ingest/verify *instructions* stay as Steps (genuine how-to); the stage labels go.
2. **Every reference resolves in a clone.** Strip `KI-001`, internal phase labels, and
   any pointer to `SYSTEM_DESIGN_AUDIT.md` / `_roadmap/**` from anything rendered. State
   the decision inline instead. (Audit the source comments listed in CONVENTIONS §
   "Dangling references" before quoting them into docs.)
3. **Counts live behind a gate.** Add a Mintlify snippet `docs/snippets/bronze-coverage.mdx`
   generated by `ingestion/verify_bronze.py --markdown`, and a CI gate that fails if the
   committed snippet drifts from a fresh regeneration. Every coverage/race count renders
   *from that snippet only*; prose elsewhere describes shape, not literals. Extend
   `scripts/docs_facts.py` (or add `scripts/ingestion_docs_facts.py`) to assert the
   snippet is current, mirroring the existing headline-count gates.
4. **One vocabulary.** Tab/group headings reuse the contract names ("Get Started",
   "How It Works", "Quality & Operations", "Sources") so all four layer tabs read the
   same. No "Architecture" here / "Layout" there.
5. **Comments → inline reasons.** Where a page quotes a source comment that offloads its
   "why" to an uncommitted doc, replace it with the reason itself.

---

## 8. Generated vs authored — and the gates

| Artifact | Generated? | Command | Gate |
|---|---|---|---|
| `reference/schemas/*` | yes | `scripts/gen_schema_reference.py` (`make docs-reference`) | `make docs-audit` |
| `reference/cli/ingest` | yes | `scripts/gen_cli_reference.py` | `make docs-audit` |
| `docs/snippets/bronze-coverage.mdx` | **new, yes** | `verify_bronze.py --markdown` → snippet | **new** drift check (§7) |
| `ingestion/*` narrative pages | no (authored) | — | `make docs-audit` (headers, links), `mintlify` build |
| `docs.json` nav | no (authored) | — | `mintlify` broken-link / build |

Pre-flight before authoring: the `reference/schemas/*` enrichment edits the
*generator*, not the `.mdx` (which the drift gate would otherwise overwrite). Confirm
`gen_schema_reference.py`'s template is where the `<Warning>`/`<ResponseField>` markup
is injected.

---

## 9. Build sequence

1. **Nav skeleton.** Restructure `docs.json` with five tabs (Overview / Data /
   Transform / ML / App). Overview is lightened to app-centric. Data is detailed
   (eight groups: four data-layer + four ingestion how-to, in that sidebar order);
   Transform/ML/App are stubbed (title + "coming soon" page). Move `Bronze Schemas`
   group and the `ingest` CLI from Reference into Data. Remove the old Reference tab.
   There is no separate Ingestion tab — its groups live inside Data.
2. **Overview tab rewrite.** Lighten the Overview tab: drop the deep decomposition
   math; focus on what the *app* does (home-page features, use cases, case studies).
   Reconcile with the new Overview pages (index, introduction, key-concepts). Make the
   landing page recruiter-grade per §3: hero `<Frame>`, the layer-flow `<Mermaid>`
   diagram, the tech-stack `<CardGroup>` (with logos/icons), and a by-the-numbers strip
   driven by the coverage/docs-facts gate (no hand-typed figures).
3. **Coverage snippet + gate.** Generate `docs/snippets/bronze-coverage.mdx` from
   `verify_bronze.py --markdown`; wire the drift check into `make docs-facts` (or a new
   target) and a CI step. Land this first so every Data/Ingestion page can `<Snippet>` it.
4. **Data tab — core pages.** Author `data/overview` (sources, Bronze, flow),
   `data/source-fastf1`, `data/source-jolpica`. Cross-check every API detail against
   the source code.
5. **Data tab — quality & coverage.** Author `data/data-quality` (DQ checks, severity
   tiers), `data/known-issues` (schema drift, phantom columns, expected gaps, coverage
   snippet). This is the "data exceptions" payload.
6. **Data tab (ingestion half) — Get Started.** Author `ingestion/quickstart`,
   `ingestion/data-scope`. Verify the five-minute path end-to-end against a real
   `--season 2024 --round 1 --session R`.
7. **Data tab (ingestion half) — How to Ingest.** Author `ingestion/cli`,
   `ingestion/configuration`, `ingestion/monitoring`. Cross-check every flag/behaviour
   against `ingest.py`.
8. **Data tab (ingestion half) — Operations & Deep Dive.** Author `ingestion/verify`,
   `ingestion/manifest-report`, `ingestion/replay` (ops group), and `ingestion/architecture`
   (the code walkthrough with Mermaid + accordions). This is the "code exceptions" payload.
9. **Schema enrichment.** Extend `gen_schema_reference.py` to emit
   `<Warning>`/`<ResponseField>`; regenerate; confirm pages render in the Data tab nav
   (file paths stay at `reference/schemas/*`; only nav moves in this pass).
10. **CONVENTIONS sweep.** Run the §7 checklist over every new page; remove any
    surviving label/process framing/version history; confirm all counts come from the
    snippet.
11. **Validate.** `make docs-site` (local render), `make docs-audit`, the new coverage
    gate, and a Mintlify broken-link pass. Fix orphans/dead links.
12. **Reconcile the layer READMEs.** Update `ingestion/README.md` so its narrative
    matches the new docs vocabulary, and point its "Full docs" link at the Ingestion
    tab. Same for later layers (transform/ml/app) once those tabs are built.

---

## 10. Definition of done (Data tab — data layer + ingestion how-to)

- [x] Five-tab nav live (Overview / Data / Transform / ML / App); Data fully populated;
      Transform/ML/App stubbed. No separate Ingestion tab.
- [x] Overview tab is lightweight and app-centric (features, use cases, case studies)
      *and* recruiter-impressive: a layer-flow diagram, light visuals, and a high-level
      tech-stack overview (see §3).
- [x] Data tab owns all data-layer content (sources, Bronze schemas, flow, quality,
      known issues, coverage) **and** the ingestion how-to (quickstart, scope selection,
      CLI, configuration, monitoring, ops, architecture deep-dive), as eight sidebar
      groups in two halves.
- [x] A cold reader can ingest one race in five minutes from `ingestion/quickstart`.
- [x] Every public function and flag in `ingestion/src/` and both client APIs
      (`jolpica_client.py`, FastF1 via `ingest.py`) is explained on some page.
- [x] Both exception classes covered: code (DQ raises, try/except, retry, 429,
      `_with_retry` state) and data (known issues, expected gaps, phantom columns,
      schema drift detection).
- [x] Every Mintlify component in §6 appears at least once, each pulling its weight.
- [x] Zero hand-written counts in prose; all coverage/race counts render from the
      gated snippet.
- [x] Zero dangling references (no `KI-001`, no `SYSTEM_DESIGN_AUDIT.md`, no `_roadmap`,
      no version history in schema pages).
- [x] `make docs-audit` + coverage gate + Mintlify build all green; no broken links.
- [x] `ingestion/README.md` reconciled to the same vocabulary and tab-aware (cross-links
      to Data and Ingestion tabs, not a duplicate).
- [x] Schema pages (`reference/schemas/*`) render in the Data tab's nav (file paths
      unchanged; nav-only move in this pass).
```
