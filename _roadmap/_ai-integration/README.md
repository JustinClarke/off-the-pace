# AI integration v2: giving the trackside-analyst assistant clean access to the data

**Goal.** An assistant that answers fan questions only with numbers that arrive as a fact card (value, n,
interval and its kind, measured / modelled / unavailable label, source, versions, page link) or as a labelled
result of a bounded query, drawn from the same code the app's pages use.

**Status: planned, nothing built under this board yet.** The v1 board is archived at
[`../_archive/_ai-integration-v1/`](../_archive/_ai-integration-v1/ARCHIVED.md); its `wi/` docs and `_evidence/`
stay here because `app/src/assistant/honesty/policy.json` and `ml/README.md` cite them.

Built from three read-only audits (2026-11-07), kept in [`_evidence/ax-audit-2026-11-07/`](_evidence/ax-audit-2026-11-07/PROVENANCE.txt):
transform layer, the 43 app features as inference sources, and the data-access design.

## Phases

| Group | Items | Needs |
| :-- | :-- | :-- |
| 1 transform honesty | TX-01..TX-11 | nothing; inside PK1's scope. TX-01..03 are P0 |
| 2 app fixes | AP-01..AP-04 | TX-03 / TX-05 for two of them |
| 3 foundations | AX-01..AX-09 | HD1 (partial lift of PK1) |
| 4 assistant | AX-10..AX-14 | HD1 |
| 5 held classes | AX-15..AX-18 | HD2 (dirty-air tax), wake calibration, the ML redo |
| 6 launch | AX-19, AX-20 | HD5 |

Run it: `python3 _roadmap/_ai-integration/status/board.py`. Work-item docs: [`wi/`](wi/) (`TX-`, `AP-`, `AX-` are v2; `AI-`, `CO-` are v1 records).
