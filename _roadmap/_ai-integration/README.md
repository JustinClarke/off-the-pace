# _ai-integration — an AI layer that lets any fan feel like a trackside race analyst

**Goal.** A fan asks a question about a race and gets a trackside-analyst answer that is built only from this app's verified stats, with the same honest-uncertainty rules the docs already set.

## Layout

```
_ai-integration/
├── README.md               this file
├── status/                 execution state — start here to run anything
│   ├── board.py            renderer + validator (never writes to the log)
│   ├── build-log.json      AUTHORITATIVE state: items, stages, open decisions, handoff history
│   └── BUILD-ORDER.md      the rules, and the generated, ordered task list
├── wi/                     one doc per work item: what exists, method, acceptance, definition of done
└── _evidence/              per-item artefacts (diffs, probe output), one folder per item and date:
                            <item>-<date>/ with a PROVENANCE.txt, as in ../_fixes/_evidence/
```

Same mechanism as [`../_fixes/`](../_fixes/README.md) and [`../_improvements/`](../_improvements/README.md): a JSON log, a read-only board, a generated task list.

## Running it

```bash
python3 _roadmap/_ai-integration/status/board.py            # items, stages, what each waits on, open rulings, next command
python3 _roadmap/_ai-integration/status/board.py --check    # invariants; run after any edit to build-log.json
```

**State lives in `status/build-log.json` and nowhere else.** The WI docs describe the work; none of them records whether it is done. If one seems to, the log wins.

## v1 scope

The assistant quotes only fact cards (a value with its sample size, interval and source page), follows the docs' honesty rules, and uses one tool that looks cards up. It is measured headless by AI-07 before any UI exists, and it ships behind a flag only after the numbers under it are settled (AI-03).

Cut from v1, each with a measured reason to bring it back: free SQL (cards cannot be built from a model-written aggregate; reopen if AI-07 shows low card coverage) and live ONNX inference (AI-05; precomputed predictions already carry their bands).

## Work items

| Doc | Item | Group | Audit findings (2026-10-15) |
| :-- | :-- | :-- | :-- |
| [CO-01](wi/CO-01-mart-semantics.md) | `CO-01` | D carry-over | T3, T4, T5 |
| [CO-02](wi/CO-02-cliff-label-defects.md) | `CO-02` | D carry-over | 1, 2, 9 (code headers), T1, T2, T6 (check-run) |
| [CO-03](wi/CO-03-v15-gates-rerun.md) | `CO-03` | D carry-over | 3, 4 |
| [CO-04](wi/CO-04-measurement-honesty.md) | `CO-04` | D carry-over | 5, 6, T7 (check-run) |
| [CO-05](wi/CO-05-ingestion-review.md) | `CO-05` | D carry-over | 7 |
| [CO-06](wi/CO-06-docs-schema-refresh.md) | `CO-06` | D carry-over | 9 (schema and generated docs) |
| [CO-07](wi/CO-07-stale-rulings.md) | `CO-07` | D carry-over | 8 |
| [AI-03](wi/AI-03-carry-over-closeout.md) | `AI-03` | D carry-over | gate on CO-01..04, CO-06 |
| [AI-01](wi/AI-01-grounding-contract.md) | `AI-01` | A grounding | |
| [AI-02](wi/AI-02-honesty-policy.md) | `AI-02` | A grounding | |
| [AI-04](wi/AI-04-assistant-core.md) | `AI-04` | B assistant core | |
| [AI-05](wi/AI-05-model-prediction-tool.md) | `AI-05` | B assistant core | closed for v1 |
| [AI-06](wi/AI-06-proxy-and-key-safety.md) | `AI-06` | C delivery | |
| [AI-07](wi/AI-07-analyst-eval-set.md) | `AI-07` | C delivery | |
| [AI-08](wi/AI-08-chat-ui.md) | `AI-08` | C delivery | |

`CO-*` items close out defects under the numbers the assistant would quote. Each audit finding has exactly one owner. The fixes and improvements logs keep their recorded entries; AI-03 and CO-07 correct them when the work lands, so nothing is tracked twice.

The older sketch of this idea is [`../_wip/AI_PLAN.md`](../_wip/AI_PLAN.md) ("in-product AI co-strategist"). It stays as background; this folder supersedes it for tracking.
