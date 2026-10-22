# CO-07 — Stale rulings on the improvements board: D2, D9, D13, D14

**Group:** 1 data settled · **Depends on:** none · **Status:** done 2026-10-15. `CD3` ruled yes to all four and is recorded in the improvements log. D2 and D13 are RESOLVED. D9 and D14 stay OPEN until re-measured on v15 (owned by CO-03 step 6).

**Sources:** `_roadmap/_improvements/status/build-log.json` (`decisions`).

**Audit finding:** 8.

The improvements log is the authoritative home of these four decisions. This item puts them to the user with today's facts, as `CD3`, and records the answers there. It builds nothing.

---

## What changed since each was raised (checked 2026-10-15)

- **D2, production deploy.** Its premise is that production serves v6. The live CDN manifest says `model_version: v14`, built 2026-09-22, the same as `app/public/models`. The audit's "CDN serves v11" is also out of date. The next publish question is v15, after CO-03.
- **D9, may the pit-strategy cost curve read the ML predictions.** Its +3.59 s/stint and 33.9% → 53.0% realised-call reproduction were measured on v11 against the unrefit seed. The number it governs is on a public page.
- **D13, disowned e-values.** Unchanged since 2026-09-19. Until ruled, nothing may quote a campaign-level rejection.
- **D14, does a label rebuild reopen 01b's noise floor.** The label has been rebuilt twice since it was raised, and CO-02 rebuilds it again.

## Method

1. Put `CD3` to the user in plain language (options are in the board's open decisions).
2. Record each answer in the improvements log's decision (`status`, `resolved`, `resolution`) and append a history entry there.
3. Any ruling that creates work goes on a board as a new item. It is not done here.

## Definition of done

All four have a recorded ruling, or are re-put with a date. `board.py --check` passes on the improvements board.
