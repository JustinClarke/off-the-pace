# _roadmap/ — planning, measurement and fix tracking

Working documents for the project: what is being attempted, what has been measured, and what
is left to fix. None of it is shipped or read by `ingestion/`, `transform/`, `ml/` or `app/`. The
code describes what it does in place; this tree records why it changed and what is next.

## Layout

| Folder | What it holds | Start with |
|---|---|---|
| [`_fixes/`](_fixes/README.md) | The transform forensic audit (F1–F55), reverified and turned into work items, with a board that tracks them | `python _roadmap/_fixes/status/board.py` |
| [`_improvements/`](_improvements/README.md) | The ML/transform lab: research, evaluations and implementations, each carrying a stage rather than a checkbox | `python _roadmap/_improvements/status/board.py` |
| [`_ai-integration/`](_ai-integration/README.md) | The AI layer that lets a fan ask about a race and get a trackside-analyst answer grounded in the app's verified stats, plus the close-out (`CO-*`) of defects under the numbers it would quote. The live board as of 2026-10-15 | `python _roadmap/_ai-integration/status/board.py` |
| [`_status/`](_status/) | Project status snapshots, open issues and the maintenance / pipeline-sync checklist | `_status/STATUS.md` |
| [`_wip/`](_wip/) | Forward plans not yet started: in-product AI, streaming watch-along, a Spark rebuild | `_wip/PROJECT_PLAN.md` |
| [`_archive/`](_archive/) | Closed plans and notes kept for reference, including the docs-tab plans the Mintlify site was built from | — |

Each board reads its own `status/build-log.json`, which is the only authoritative state for that
tree. The boards only render and validate; they never write to the log.

Figures quoted in `_status/` are snapshots from when each file was written. For current counts,
use the generated snippets in [`docs/snippets/`](../docs/snippets/) or the
[docs site](https://offthepace.mintlify.app).

---

← Previous in tour: [agents/](../agents/README.md) (local only) · **End of tour: back to [README.md](../README.md) →**
