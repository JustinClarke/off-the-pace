# AI-14 — Honesty rules: record the EXCLUDE ruling on the chance number

**Status:** SPEC (nothing run). **Group:** 2 assistant · **Depends on:** none · **Ruling:** `AD5` (RESOLVED 2026-10-22: EXCLUDE). Raised 2026-10-23 on the owner's answer. This is AI-02's remaining step, split out; AI-02 depends on it.

**Sources:** `app/src/assistant/honesty/policy.json`, `app/src/assistant/honesty/`.

## Problem

`policy.json` still marks `CHANCE_LINE_QUOTABLE` as `pending_ruling` (watch W13). The owner ruled AD5: the assistant does not quote the experimental chance-to-make-the-flag number; the line stays on the simulator only (CD11).

## Method

1. Change `CHANCE_LINE_QUOTABLE` from pending to the exclude ruling, citing AD5.
2. Re-run the honesty and nav tests (`vitest src/assistant/honesty src/nav`, from `app/`).
3. Record the result on AI-14 and move AI-02 to LANDED.

## Definition of done

The rule carries the EXCLUDE ruling, the honesty and nav tests pass, and AI-02 is LANDED. Do not commit.
