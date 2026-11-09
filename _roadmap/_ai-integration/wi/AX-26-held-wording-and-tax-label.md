# AX-26 — Held-card wording and the unvalidated label on the flat tax (D4 and D5)

**Decision:** held-card wording becomes "no validated measure of time lost behind another car exists", with no promised date. The regex in `policy.json`'s held-card rule is updated to match. The 0.331 value stays in the warehouse as an internal input, labelled unvalidated. Retiring it is deferred (AX-22 family).
**Record:** experiments/13-app-reliability-decisions/decisions.md (in the f1-chat repo: /Users/justin/github/_misc/_chat/f1-chat/experiments/13-app-reliability-decisions/decisions.md)
**Status:** decided. Safe to apply now (wording and labels only, no data change).
**Done when:** `heldStubs.ts` and `policy.json` carry the new wording, the tests that pin the old wording are updated, and the tests pass.
