# AX-23 — Take dirty-air cost off the product surface (D1)

**Decision:** `/aero/dirty-air` and the flat 0.331 s tax are removed from what users see. The warehouse keeps the tax as an internal input, labelled unvalidated (see AX-26).
**Why:** the pilots and probes found no credible penalty. The page carries no unvalidated label today.
**Record:** experiments/13-app-reliability-decisions/decisions.md (in the f1-chat repo: /Users/justin/github/_misc/_chat/f1-chat/experiments/13-app-reliability-decisions/decisions.md)
**Status:** decided. Implementation needs the owner's go.
**Done when:** the route is gone from the nav and the router, the page has no entry in the feature list, and a test checks that no route renders the dirty-air leaderboard.
