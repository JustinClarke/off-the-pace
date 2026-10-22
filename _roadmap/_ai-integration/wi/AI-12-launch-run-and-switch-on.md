# AI-12 — Launch run and switch-on

**Group:** 3 delivery and launch · **Depends on:** `AI-03` (data freeze), `AI-06`, `AI-07`, `AI-08` · **Blocker:** `AD4` (launch cost and access).

**Sources:** `wi/AI-07-analyst-eval-set.md` (set, grader, bar), `wi/AI-03-carry-over-closeout.md` (snapshot), `app/src/ui/layout/AppShell.tsx`, `firebase.json`.

Split from AI-08 on 2026-10-22. The drawer can be built before the data is frozen; the launch run cannot.

---

## Method

1. Check that the AI-03 snapshot still holds: row counts and checksums per card source, and the model version. If anything moved, stop and reopen AI-03 (watch W2).
2. Run AI-07's set, 5 repeats per question, through the real drawer (AI-08) and the Worker (AI-06) on the production endpoint, on the frozen snapshot.
3. Score against the bar AI-07 recorded before its first run. Do not change the bar.
4. Record tokens and cost per answer. That is the number AD4 is ruled from.
5. After AD4 is ruled, set the Worker's real cap and confirm the paused state still works. Turning the flag on is the owner's call.

## Acceptance

AI-07's recorded bar: 100% of numbers grounded, 100% of refusals correct, the right tool 95% of the time or more, no run over 18,000 tokens, and the human read passes.

## Definition of done

The launch run is saved as evidence and passes the bar. AD4 is ruled and its cap is in the Worker. The owner's yes to switch on is recorded. Do not deploy or commit without it.
