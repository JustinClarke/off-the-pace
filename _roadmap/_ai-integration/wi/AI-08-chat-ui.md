# AI-08 — Chat drawer, behind a flag

**Group:** 3 delivery and launch · **Depends on:** `AI-04`, `AI-06` · **Blocker:** none. The launch run and switch-on moved to AI-12 (2026-10-22), which carries the freeze (AI-03), the eval (AI-07) and `AD4`.

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

## Acceptance

- Works at phone width (16px gutter, no horizontal scroll), by keyboard and with a screen reader; respects reduced motion.
- With the proxy down or paused, the drawer shows a plain message and the rest of the app is unaffected.
- No answer renders a number that lacks a card.
- Existing e2e tests and the perf budget still pass.

## Definition of done

Component tests for streaming, linking, rule notes and failure pass, with the flag off by default. The launch run and switching the flag on are AI-12.
