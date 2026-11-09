# AX-25 — Commit the race-control clock fix once a test covers it (D3)

**Decision:** hold the commit of `ingestion/src/ingest.py` until a unit test covers the datetime branch (the 139 existing tests never exercise it). Then commit it, without waiting for the re-ingest (AX-22).
**Record:** experiments/13-app-reliability-decisions/decisions.md (in the f1-chat repo: /Users/justin/github/_misc/_chat/f1-chat/experiments/13-app-reliability-decisions/decisions.md)
**Status:** decided. The test comes first.
**Done when:** the datetime branch has a test that fails on the old code and passes on the fix, and the commit is made by the owner.
