# AI-08 — Chat UI and launch run

**Group:** C delivery · **Depends on:** `AI-03`, `AI-04`, `AI-06`, `AI-07` · **Blocker:** none beyond dependencies (`AD1` is ruled).

**Sources:** `app/src/ui/layout/AppShell.tsx`, `app/src/ui/feedback/`, `app/src/nav/`.

---

## What exists today

`AppShell` hosts the pages and `ui/feedback/` holds loading, empty and error states. There is no chat surface.

## Method

1. A drawer reachable from every page, streaming the answer from AI-04 through the AI-06 proxy.
2. Every number links to the page that explains it (the card's `source_page`) and shows its interval and sample size on hover or tap.
3. AI-02 rule hits render as a visible note on the answer, not buried text.
4. Reuse `DataBoundary`, `EmptyState` and `ErrorBoundary` for loading and failure. Use `TechTooltip` for terms.
5. Ship behind a flag, off by default.
6. **Launch run.** Re-run AI-07 against the real drawer on AI-03's frozen snapshot.

## Acceptance

- Works at phone width (16px gutter, no horizontal scroll), by keyboard and with a screen reader; respects reduced motion.
- With the proxy down or paused, the drawer shows a plain message and the rest of the app is unaffected.
- No answer renders a number that lacks a card.
- Existing e2e tests and the perf budget still pass.

## Definition of done

Component tests for streaming, linking, rule notes and failure pass, and the launch run meets AI-07's recorded bar. Turning the flag on is the user's call.
