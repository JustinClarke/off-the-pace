# Repository conventions

How this repository is laid out and documented. The goal is a tree where any
reader human or coding agent can open a directory, understand what it does
and how it connects to its neighbours, and start debugging without prior context.

Two principles drive everything below:

1. **Describe what a thing does, not how it came to be.** Git carries history.
2. **Everything a reader needs resolves inside a fresh clone.** No pointers to
   files, plans, or labels that exist only on one machine.

---

## The pipeline

Data flows in one direction. Each stage reads the stage above and writes for the
stage below.

```
ingestion/   raw F1 telemetry → Hive-partitioned Parquet (Bronze; no business logic)
    ↓
transform/   dbt + DuckDB: clean → physics decomposition → coefficient fits → feature marts
    ↓
ml/          XGBoost on the gold marts → versioned .bst + parity-tested .onnx
    ↓
app/         React + DuckDB-Wasm + ONNX Runtime Web: queries and inference in the browser
```

Cross-cutting directories sit beside the pipeline rather than inside it:
`scripts/` (research, validation, reference generation), `docs/` (the public
Mintlify site), `infra/` (Terraform), `data/` (artifacts), `agents/`.

This order is the canonical reading order. Layer README footers link upstream and
downstream so the tree can be walked end to end.

---

## Writing rules

These apply to every committed README, MDX page, and code comment.

### Describe the present

State what the code is and does. Do not narrate the process that produced it.

- **Banned:** "Phase 5", "Sprint 0", "Wave 0", "Step 3 of", "Implements F9 of …",
  "recently added", "now complete", "newly", "deprecated alias for".
- **Fine:** ordered *instructions* for a genuine procedure ("1. ingest 2. build
  3. test") that is a how-to, not a history. The test is whether the number
  describes *what the reader does next* (keep) or *what stage the project reached*
  (delete).

A status line like "Complete and deployed" is the project talking about itself in
time. Describe the capability instead and let CI badges carry live status.

### Every reference resolves in a clone

A reader has the committed tree and nothing else. Never point at something they
cannot open.

- **Banned:** links or citations to `SYSTEM_DESIGN_AUDIT.md`, `_roadmap/**`,
  `_issue_logs/**`, or any internal label whose definition is not committed 
  `AD-3`, `Appendix C`, `R-3`, `F9`, `AD-13`, and the like.
- If a decision is worth citing, **state the decision inline.** Replace
  "self-hosted bundle so COEP doesn't block assets (AD-11)" with the reason
  itself the parenthetical adds nothing a reader can follow.
- Describing a gitignored directory *as* gitignored is allowed (e.g. repo-tour
  noting `_roadmap/` is internal and not published). The rule bans depending on
  its contents, not naming its existence.

### Counts live behind a gate or not in prose

A number written by hand rots. Cite a count in prose only when a drift gate keeps
it honest (the repo already gates several via `scripts/docs_facts.py` and
`scripts/app_docs_audit.py`). Otherwise describe the thing without the number, or
point at the generated artifact that holds the current value.

### One vocabulary

The same concept gets the same heading in every layer. Do not call the directory
map "Architecture" in one README, "Subtree map" in another, and "Layout" in a
third. Use the section names defined below.

---

## The layer README contract

Every pipeline layer (`ingestion/`, `transform/`, `ml/`, `app/`) carries a
`README.md` with these sections, in this order. Omit a section only when it is
genuinely empty; never reorder or rename.

1. **Title + purpose** `# <dir>/ <one line>`. A single sentence: what the
   layer reads and what it produces.
2. **What it does** one short paragraph. The layer's job in the pipeline, named
   upstream input and downstream consumer.
3. **Layout** the directory/file map, each entry with a one-line role. A DAG or
   data-flow diagram is a subsection here, not a separate top-level heading.
4. **Inputs and outputs** the concrete upstream source and downstream consumer,
   and the contract between them (which tables/files/columns cross the boundary).
5. **Contracts** what this layer guarantees that something downstream relies on:
   enforced schemas, numerical tolerances, determinism, invariants. Omit if none.
6. **Commands** the `make`/CLI targets to build, test, and run, one line each.
7. **Tracked vs generated** what is committed versus regenerated, and the command
   that regenerates it. Omit if the layer has no generated artifacts.
8. **Tests** what is covered and how to run it.

**Footer** upstream/downstream neighbour links phrased as data flow:
`← upstream: <dir>/ · downstream: <dir>/ →`.

---

## The layer directory contract

- A layer's own code lives under a predictable root (`src/` for Python layers,
  `src/` for the app, `models/` for dbt).
- Tests live in `tests/` beside the code they cover.
- Generated artifacts are gitignored and reproducible from a single command named
  in the README's **Tracked vs generated** section.
- File and directory names describe their contents in the project's vocabulary
  (see `docs/AGENTS.md` terminology). A new app feature directory is its canonical
  slug, reused verbatim as its docs filename.

---

## Code comments

Comments explain *what the code does and why*, in place. A comment that offloads
the "why" to an uncommitted document is not a comment it is a dangling pointer.
Write the reason; drop the label.

---

## Conformance backlog

The tree does not yet meet the rules above. These are the concrete deviations,
highest-impact first. Items in the first group break for anyone who clones the
repo and should clear before the rest.

### Dangling references to uncommitted artifacts

`SYSTEM_DESIGN_AUDIT.md` is not committed, yet committed files cite it by phase:

- `.github/workflows/README.md` "implement Phase 5 of `SYSTEM_DESIGN_AUDIT.md`"
- `app/vitest.config.ts` "Regression ratchet (Phase 5 / F9 of SYSTEM_DESIGN_AUDIT.md)"
- `scripts/publish_cdn.sh` "Staging vs prod (F2 / Phase 2 of SYSTEM_DESIGN_AUDIT.md)"

`_roadmap/` is gitignored, yet code points into it:

- `app/vite.config.ts` (two comments) "See `_roadmap/_issue_logs/…/onnxruntime_web_vite_dev_mjs_import.md`"

The `AD-N` / `Appendix C` / `R-N` labels are defined only in uncommitted planning
notes. They appear across, at least:

- `app/src/ml/featureVector.ts`, `index.ts`, `infer.ts`, `manifest.ts`,
  `session.ts`, `verifyParity.ts` `AD-3`, `AD-11`, `Appendix C`, `R-3`
- `app/src/data/duckdb/client.ts` `AD-11`
- `app/src/routes/home/index.tsx`, `home/tileViz.tsx`, `landing.tsx` `AD-12`
- `scripts/export_app_data.py` `AD-2`, `AD-12`, `AD-13`

Fix: replace each label with the decision it stands for, stated inline.

### Process framing in prose

- `ingestion/README.md` "Follow steps 1–5 in order"; the README's own narrative
  is structured as numbered process stages. The ingest/verify *instructions* are
  fine; reframe the section headings to describe what each part is.
- `scripts/export_app_data.py` "Sprint 0 F1", "Wave 0 (canary tables only)" in
  the module docstring and output.

### Status and history claims

- `app/README.md` opens "Complete and deployed." and "35 passing tests".
  Describe the app's capability; drop the status line and the hand-written count.

### Heading vocabulary divergence

The directory-map section is named differently in each layer: "Architecture"
(`app`), "Model DAG" + "Directory structure" (`transform`), "Subtree map"
(`app`), "Layout" (`ml`). Normalize all to the **Layout** section in the README
contract above, and align the remaining headings to the contract's eight sections.

### Hand-written counts in prose

Counts written into README prose drift from reality (`app/README.md`: "59 route
entries", "11 pillars", "30 shipped"; `ingestion/README.md`: per-season race
counts). Either move them behind an existing drift gate or describe the structure
without the literal number.
