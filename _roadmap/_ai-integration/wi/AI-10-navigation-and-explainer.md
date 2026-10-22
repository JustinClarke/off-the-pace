# AI-10 — Navigation and page explainer

**Group:** 2 assistant build · **Depends on:** none · **Blocker:** none.

**Sources:** `app/src/nav/`, `docs/app/` (34 pages, about 168 KB in total).

---

## Scope

Two small tools, both read-only:

1. **`navigate(route, filters?)`**: moves the app to a shipped route, with allowed filters only. The route list is built from the app's own route table, so it cannot name a page that does not exist.
2. **`explain_page(page_id)`**: returns a pre-cut summary of that page's docs, 800 tokens or less. The full docs are never sent to the model.

## Method

1. Generate the route list at build time from the route table (shipped routes only). Check it against the built app.
2. Write one summary per docs page, cut to 800 tokens or less, keeping the method notes and caveats the answer must carry (AI-02).
3. Generate the summaries from the docs at build time, so they cannot drift from the source. Fail the build if a summary is over budget.

## Acceptance

- Every shipped route resolves; no unshipped route is listed.
- Every summary is 800 tokens or less, and carries the caveats from its docs page.

## Definition of done

Both checks run in CI, and the explainer answers "how does this page work" for 5 pages in the headless loop. Do not commit.
