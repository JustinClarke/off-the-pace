# ARCHIVED 2026-11-07: AI-integration build order v1

`status/` here is a snapshot of `_roadmap/_ai-integration/status/` as it stood at `updated: 2026-10-26T12:54:24+04:00`
(18 live items, 16 parked by PK1, pointer on CO-32). Do not run its `board.py`; it reads its own copy of the log.

**Why archived.** The pointer sat on CO-32, the micro-sector dirty-air method that was archived on 2026-10-27
(`../_dirty-air/ARCHIVED.md`). The cards the assistant needs were never defined against the data the app serves,
and an audit (2026-11-07) found transform honesty gaps that cards would have quoted. The replacement is
`../../_ai-integration/` (items TX-, AP-, AX-), built from `_evidence/ax-audit-2026-11-07/`.

**What stayed in place.** `_ai-integration/wi/` (the v1 work-item docs) and `_ai-integration/_evidence/` are still
there, because `app/src/assistant/honesty/policy.json`, `ml/README.md` and several build logs cite them by path.

**Proposed verdicts on the old live items** (the design agent's, for the owner to confirm; see the design doc §1):
- Rewritten into the new order: AI-01, AI-03, AI-04, AI-07, AI-09.
- Kept with additions: AI-02, AI-06 (Worker code kept), AI-08, AI-10, AI-11, AI-12, AI-14.
- Moved: AI-13 (real-data CI job) into TX-08 on the transform side.
- Superseded by the ML reset plan: CO-14, CO-18, CO-19.
- Out of assistant scope (AD5 excludes the chance number): CO-08, CO-10, CO-20.
- Superseded by `_wake-calibration`: CO-32 and watch W11.
- AI-05 stays closed.
