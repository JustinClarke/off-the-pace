# Fixes build order — rules, and the ordered task list

**State lives in [`build-log.json`](build-log.json), and only there.** This file holds the
rules that govern it, plus one **generated** task list spliced in at the bottom.

This is the same mechanism as [`../../_improvements/status/BUILD-ORDER.md`](../../_improvements/status/BUILD-ORDER.md),
applied to the audit fixes in [`../`](../README.md). The differences are listed at the end.

A hand-written checklist in this file is a defect. The task list below is *derived* from the
JSON by `board.py --write-order`, sits between two markers, and `--check` fails if it has
fallen out of sync with the log. Edit the JSON, then regenerate. Never type into the block.

```bash
python3 _roadmap/_fixes/status/board.py                # the board, open decisions, next command
python3 _roadmap/_fixes/status/board.py --check        # invariants only; exit 1 on failure
python3 _roadmap/_fixes/status/board.py --order        # the ordered task list, to stdout
python3 _roadmap/_fixes/status/board.py --write-order  # ...and spliced into this file
python3 _roadmap/_fixes/status/board.py --watch        # the watch list in full
python3 _roadmap/_fixes/status/board.py --ship         # exit 1 while a ship-blocker is open
```

**Quick start:** say `proceed` to spawn an agent on the current pointer item and skip all
explanation. Two exceptions, both from the improvements tree's experience:

1. **A decision blocks the pointer item.** If the item is `BLOCKED` on an open `FD*` decision,
   stop and put the decision to the human first, in plain language with the options
   translated. Spawning blind spends the item's full cost against the wrong premise.
2. **The pointer item is already `MEASURED`.** Don't respawn it: read the last history
   entry's `next_action`, and let the user pick the next item.

`board.py` never writes to the log — a malformed edit surfaces as a failed check, not as silent
drift. `--write-order` writes only to this file and refuses to run while the log is invalid.
Run `--check` after every edit to the JSON.

## What the log holds

| Key | Holds |
| :--- | :--- |
| `pointer` | The single next item to run. Exactly one, always (or `null` when everything is terminal). |
| `stage_vocabulary` | The six legal stages and what each means. |
| `model_vocabulary` | The four Claude models an item may name, and when each is the right one. |
| `groups` | The improvements-tree group each item belongs to (`ref` points at that group's leaf doc). |
| `items` | `id`, `group`, `stage`, `depends_on`, `title`, `findings`, `doc`, `cost`, `model`, `note`, and `closed` for terminal items. |
| `decisions` | `FD*` rulings awaiting a human call. Referenced by an item's `blocked_by_decision` (one id or a list). |
| `watch_vocabulary` | The nine kinds of watch entry and what each means. |
| `watch_rules` | What is being kept an eye on that is neither an item nor a ruling: ship-blockers, standing hazards, uncommitted or unreviewed work, unverified claims, stale artifacts, gate gaps, known debt. Each has `id`, `raised`, `kind`, `title`, `detail`, `clears_when` (the prose), a `trigger` (what `board.py` evaluates), an optional `item` / `decision`, and `resolved` / `resolution` once cleared by hand. No status is stored: the watch list is computed from the triggers. |
| `history` | Append-only session records, in handoff-protocol shape. |

## Items, and how they map to the WI docs

Each item points at the WI doc in [`../wi/`](../wi/) that carries its method, acceptance, tests
and definition of done (`doc`), and lists the audit findings it fixes (`findings`). The
per-finding verdicts and the F50–F55 write-ups are in [`../reference/`](../reference/). Four WI docs are executed as
two items each, because part of the doc is blocked and part is not:

| WI doc | Item | Findings | Why split |
| :--- | :--- | :--- | :--- |
| `WI-02` | `WI-02a` | F41, F7, F39 | Provenance first; no ruling needed. |
| | `WI-02b` | F2, F9 | The refit needs `FD3`, `WI-02a` and `WI-05`. |
| `WI-09` | `WI-09` | F13, F14, F17, F18, F19, F20, F54 | Landed 2026-09-25; keeps the doc's id. |
| | `WI-09b` | F12 | Split after the build: what "cleared" means is a ruling (`FD6`). |
| `WI-14` | `WI-14a` | F50, F28, F46 | Independent of the F40 ruling. |
| | `WI-14b` | F40, F44, F45 | The chain that `FD5` gates. |
| `WI-15` | `WI-15a` | F43, F48 (coding) | `WI-01`'s θ_air re-estimate needs F48's coding first. |
| | `WI-15b` | F47, F49 | Thermal; does not feed θ_air. |

Everything else is one item per doc, id = the doc's `WI-NN`.

## Stages

- **SPEC** — reverified and specced in its WI doc. Nothing run.
- **BUILDING** — in progress.
- **MEASURED** — fix applied and its acceptance numbers exist; the orchestrator has not yet
  re-run the doc's definition of done.
- **LANDED** — definition of done re-run by the orchestrator and passing, **in the working
  tree**. Committing or publishing is the user's call and is not part of the stage.
- **BLOCKED** — waiting on an open decision (or a dependency that hit a problem). A plain unmet
  dependency is not `BLOCKED`; dependency order already handles that.
- **CLOSED** — terminal, with the reason recorded. Do not re-open without new evidence.

There is no `GATED` stage here. The improvements tree needs one because a *number* has to pass
[`gates.md`](../../_improvements/foundations/gates.md) before it can be claimed. A fix's gate is its
WI doc's definition of done — the audit's `verify_findings.py` check flipping to CLEARED plus
the new T-tests passing — and that is what `LANDED` means. The exception is a fix that moves a
feature contract or the label (`WI-01`, `WI-15a`, `WI-15b`, `WI-02b`): those also owe the gate,
and the item's `landed` history entry must say which gate steps were run.

## Rules

**Changing a stage.** Only when the WI doc's criteria for that stage are met. Stages move
forward, or back to `BLOCKED` with a logged reason — never silently sideways.

**Which model.** Every live item names one from `model_vocabulary`, and `--check` rejects a
live item without one. `opus-5` is the default; `sonnet-5` is a step down where the WI doc has
already made the judgment call; `fable-5.1` is a step up where the failure mode is a
plausible-looking number rather than an error. The choice belongs to the item, not the session.

**Running an item is a delegation, not a switch.** The interactive session orchestrates and
does not execute a live item itself. It spawns an agent at the item's own `model` to do the
work, then reviews what comes back **before touching the log**: re-reads the diff, re-runs the
WI doc's definition of done and `board.py --check`, and only then records the result. An
agent's summary describes what it intended, not necessarily what it produced. A stage only
advances once the orchestrator has checked the work independently. Expect the WI doc's own
text to need correcting where the result disproves it — see *Deviation* below.

**Order.** Dependency order. `board.py` prints unmet blockers after each item; don't start one
that shows any. Among items that are ready, the task list puts work you can run now ahead of
work waiting on one of your rulings.

**One `▶`.** `pointer` names exactly one non-terminal item. `--check` enforces it.

**Every session appends one `history` entry** with all six fields — `landed`, `verified`,
`assumed`, `gates_run`, `next_command`, `next_action`. `--check` fails if any is missing on the
latest entry. `verified` and `assumed` are the hard epistemic line from
[`epistemics.md`](../../_improvements/foundations/epistemics.md): only `verified` if the code path was
traced and the number can be cited.

**The watch list is where an exception lives.** Items say what to build and decisions say what
to rule; anything else a session leaves behind (an artifact that is now stale, work that is
uncommitted or unreviewed, a claim run in one place only, a gate that does not guard, a known
defect left on purpose, a trap someone could step on) gets a `watch_rules` entry with a
`clears_when` and a `trigger`, so it cannot fall off the board when the item that raised it lands.
Prose in `assumed` or `next_action` is not tracked by anything. The list is **computed**, like the
task list: `board.py` evaluates each rule's trigger against the items, the decisions and the other
rules on every run (see *Adding a watch rule*). A rule is never deleted; one whose trigger needs a
fact the log cannot see is cleared by recording `resolved` (a date) and `resolution`. `--check`
validates every rule and its references; `--ship` is the gate to run before publishing, and fails
while a `ship-blocker` is open. The generated task list below carries the open entries.

**Deviation from a WI doc is logged _and_ the doc corrected**, so the log never silently
diverges from the spec.

**Nothing is committed without being asked.** Standing rule for this repo. `LANDED` means the
change is in the working tree and verified; the human commits.

### What is different from an improvements item

Fixes edit production code (`transform/`, `ml/`, `app/`), so the improvements tree's
"probes never touch the warehouse or `ml/models/`" is narrowed rather than copied:

- **Ad hoc probes are still throwaway** — scratchpad only, `data/dev.duckdb` opened read-only.
- **Fix work edits the working tree.** Rebuilding the dev warehouse (`dbt build`) or a model is
  in scope only where the WI doc's definition of done requires it, and the item's `landed`
  entry says so. Never touch `data/ci.duckdb`.
- **Until `WI-07` lands, do not run `ml.src.features --check`** (it is what `Makefile:195` and
  CI call). It has no read-only mode: it rewrites the shipped `ml/models/encoders.json` from
  whatever the holdout resolver returns (F11/F53). `WI-07` adds `--persist-encoders`, default
  off.
- **`WI-04` must land before the v14 manifest is published to the CDN.** The CDN serves v11
  today; publishing v14 first breaks the Degradation Simulator for everyone.

## Adding an item

Append to `items` with a unique `id`, a `group` that exists, `stage: "SPEC"`, real `depends_on`
ids, `findings`, a `doc` that exists, a `cost` and a `model` — `--check` rejects a live item
missing any of those, and rejects a `doc` path that does not resolve. Then make sure the WI
doc has a definition of done for it.

## Adding a watch rule

Append to `watch_rules` with the next free `W<n>` id, `raised`, a `kind` from `watch_vocabulary`,
`title`, `detail`, `clears_when` (what a person reads) and a `trigger` (what `board.py` evaluates).
`trigger.clear` is required. `trigger.raise` is optional: it keeps the rule off the list until it
holds, so a follow-up can be registered before the item that owes it lands. Each is a condition:

| Condition | Holds when |
| :--- | :--- |
| `"manual"` | The rule records `resolved` and `resolution`. For facts the log cannot see: a commit, a re-export, a rebuild, a ruling given outside `decisions`. |
| `{"item": "WI-08"}` | The item is `LANDED` or `CLOSED`. Add `"stage": [...]` to name other stages. |
| `{"decision": "FD4"}` | The decision is `RESOLVED`. |
| `{"watch": "W8"}` | That watch rule is cleared. |
| `{"all": [...]}` / `{"any": [...]}` | Every / at least one of the listed conditions holds. |

Write the trigger that the `clears_when` prose describes. If the prose names something the log
can see as a precondition, put it in an `all` with `"manual"` (W19: FD4 is ruled *and* the rounds
are ingested). If it names one as an alternative, use an `any` (W37: WI-08 lands, *or* the term is
dropped). If the log can see all of it, leave `"manual"` out (W46: W8 and W45 both clear). An item
landing usually *raises* a follow-up rather than clearing one (W1: the re-export is owed because
WI-13 landed), so reach for `raise` there, not `clear`. `--check` fails on a dead reference, a
cycle, a stored `status`, a resolution the trigger has no `"manual"` to read, and a hand
resolution whose other conditions are not met. `--watch` prints each open rule's trigger, and
lists the rules that cleared by trigger alone.

---

## The ordered task list

Dependencies first, then work you can run now ahead of work waiting on a ruling, then group
order, then id. Read it top-down: it is the sequence in which the items are actually runnable.

<!-- BEGIN GENERATED TASKS -- do not hand-edit; `board.py --write-order` -->

_Generated from [`build-log.json`](build-log.json) at `updated: 2026-09-29T18:30Z`. Run `python3 _roadmap/_fixes/status/board.py --write-order` after any edit to the log._

**0 live items** (0 blocked). The pointer is on **None** — that is the one to run next; the rest of the order is what becomes runnable after it, with anything waiting on one of your rulings sorted behind the work that isn't. 20 terminal items are finished and not listed here — run `board.py` for the per-group view, or read their `closed` field in [`build-log.json`](build-log.json).

| # | Item | Group | Stage | Cost | Model | Fixes | Task | Waiting on |
| ---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |

### Which model to run it on

Recorded per item in the log, not chosen at the keyboard, so the choice is reviewable and moves with the item rather than with whoever picks it up.

- **`fable-5.1`** — claude-fable-5-1. Novel statistical construction where a wrong derivation is expensive and hard to detect from the output - estimators, identification arguments, inference machinery. Reach for it when the failure mode is a plausible-looking number, not an error.
- **`opus-5`** — claude-opus-5. The default. Anything that makes a ruling, designs an aggregation, moves the feature contract, or turns a measurement into a claim.
- **`sonnet-5`** — claude-sonnet-5. The method is already written down and the judgment call is made - ingest, enumeration, a named refit, a declared schema note. Step back up to opus-5 the moment the leaf doc leaves a choice open.
- **`haiku-4-5`** — claude-haiku-4-5. Throughput work with a mechanical check on the output. Nothing in the tree currently qualifies: every live item either writes into the contract, rules on leakage, or produces a claim.

### Watch list — kept an eye on, not tasks and not rulings

_Generated from the watch rules in [`build-log.json`](build-log.json) (`watch_rules`); watch entries update automatically as items land or decisions resolve. A rule whose trigger needs something the log cannot see (a commit, a re-export, a rebuild, your ruling) stays open until its `resolved` and `resolution` are recorded._

**19 open** (0 ship-blockers). Full detail: `python3 _roadmap/_fixes/status/board.py --watch`. `python3 _roadmap/_fixes/status/board.py --ship` exits 1 while a ship-blocker is open.

Each watch rule is tagged with the recommended model (haiku/sonnet/opus) for token efficiency (5 haiku, 10 sonnet, 4 opus). The tag is the smallest model that can work the rule to its `clears_when`; step up a tier the moment the rule turns out to leave a choice open that the tag assumed was made.

- **`haiku`** — Maps to haiku-4-5. A binary check, or recording a resolution the evidence or the user has already settled: is it committed, did the named tests pass on the rebuild, write down the accept. The output has a mechanical check (a test result, a file list, git log).
- **`sonnet`** — Maps to sonnet-5. The fix or the options are written down in the rule: pick between two named options, run a named rebuild or export and check the pages, review a diff, reconcile counts, reword text to a meaning already settled.
- **`opus`** — Maps to opus-5 (fable-5.1 if the rule turns into a new estimator). Rules on a trade-off, designs the fix, audits a decision, or turns a measurement into a claim: label-moving changes, leakage boundaries, gate runs before a promotion.

| ID | Kind | Item | Model | What | Clears when |
| :--- | :--- | :--- | :--- | :--- | :--- |
| W4 | unreviewed | — | `sonnet` | Ingestion-hardening agent's partial work is in the working tree, unread and untested | The diff is reviewed and ingestion/tests pass and the change is kept, or the changes are discarded (git checkout on the modified paths plus deleting the four new files; destructive, the user's call). |
| W5 | unverified | WI-09 | `sonnet` | WI-09's new tests and one source form have only run on the dev target | A CI-target build runs them (not done: this tree does not touch data/ci.duckdb). |
| W33 | unverified | WI-16b | `opus` | The isolation car term falls back to the global driver key in both eras; its car/driver split is unvalidated | WI-16b's V1c/V2a/V3a are run and graded, and the result is stated in its As built section. |
| W6 | stale-artifact | WI-09 | `haiku` | Dev-warehouse marts stale for WI-09's changes until rebuilt | dbt run on those three marts (or the next full dbt build). |
| W7 | stale-artifact | WI-07 | `haiku` | Drift baselines need regenerating from a CI build | Either: (1) WI-09's fixture data issues are resolved (dbt_expectations test passes on CI; assert_raw_laps_race_depth_is_race_only finds matching bronze parquets), then `dbt build --target ci` and `make lint-oracle-snapshot` complete successfully and the result is committed; OR (2) a design decision is made to pin the fixture to a pre-schema-change baseline (smaller cost, eventual debt). |
| W8 | stale-artifact | — | `sonnet` | Generated docs still carry old text | Docs are regenerated in one sweep once the landed items are committed. |
| W20 | stale-artifact | WI-15a | `haiku` | Dev warehouse stale for WI-15a: T33/T38 tests error until rebuilt | data/dev.duckdb is rebuilt with the fixed int_lap_proximity and int_lap_air_state (may defer to after WI-01's label bump, as both items move the same label rows). |
| W23 | stale-artifact | WI-15b | `haiku` | Dev warehouse holds WI-15b's first (inner-join) thermal build: T37 errors on dev until rebuilt | data/dev.duckdb's int_lap_thermal_proxy+ is rebuilt from the working tree (dbt build -s int_lap_thermal_proxy+), and T37/T39 pass on it. |
| W28 | stale-artifact | WI-15a | `sonnet` | app/public/data air-state exports pre-date WI-15a's F48 coding | The three tables are re-exported from a dev warehouse rebuilt with WI-15a. Because of W20 that is after WI-01's label bump, and theta-dependent tables move again there anyway. |
| W34 | stale-artifact | WI-16a | `haiku` | Dev warehouse and data/fits have no driver-isolation build | The orchestrator rebuilds dev (make car-fe-isolation-fit, then dbt run), which W20/W23 may defer to after WI-01. |
| W35 | stale-artifact | — | `sonnet` | Three docs-facts gates fail on pre-existing ML/app count drift | The ML and app counts are reconciled and the three scripts pass. |
| W46 | stale-artifact | WI-01 | `sonnet` | Generated docs and inventory snippets predate WI-01 | W8's single regeneration sweep runs after WI-01 is committed. |
| W54 | stale-artifact | WI-17 | `sonnet` | The Degradation Simulator's P3 basket fixtures predate the current warehouse | The fixtures are regenerated from a rebuilt envelope (and the generator restored), and accuracy.test.ts and powerLaw.test.ts re-run on them. |
| W39 | pending-ruling | WI-01 | `opus` | Honest-range floor moved to 0.920, which is looser; whether the tyre wear cap binds too often is unchecked | An audit of the cap-binding laps decides whether the cap (or the wear fit behind it) is right, and either a direct cap-binding-share check is added or the floor is set from that audit. |
| W17 | gate-gap | WI-07 | `sonnet` | The sqlfluff gate does not hold | The size limit is raised or the skip is made loud, and the failing files are fixed or excluded on purpose. |
| W15 | debt | WI-13 | `opus` | WI-13's neighbours, found and not fixed | Each is given an item or an explicit 'accept', one at a time. |
| W18 | debt | WI-09 | `sonnet` | 2020_1 (Austrian GP) lap numbering is wrong in bronze | 2020_1 is re-pulled from FastF1 and re-checked (whether a re-pull fixes it is untested). |
| W19 | debt | FD4 | `sonnet` | 2026 races are not ingested | FD4 is ruled, the seeds are filled (WI-05's gate lists what is missing) and the rounds are ingested. |
| W53 | debt | WI-17 | `opus` | No 2025 hardness ranks: WI-17's C6 leave-out (T54) and its 2025 season-forward fold cannot run | The 2025 tyre_allocations rows are re-added and checked against their source URLs, dev is rebuilt, and python -m ml.src.powerlaw re-runs T54 on real C6 cells and the <= 2024 / 2025 fold. |

<!-- END GENERATED TASKS -->
