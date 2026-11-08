# AX-07b - the five minimum-set card kinds AX-07 did not build

**Group:** 3 foundations · **Depends on:** AX-07 · **Model/cost:** sonnet-5, 1-2d · **Blocker:** none.

**Sources:** `_evidence/AX-07-2026-11-08/PROVENANCE.txt` (what exists, how kinds are written), `_evidence/ax-07-lineage/lineage.md` (class per source), `app/src/assistant/cards/{kinds,registry,build}.ts`, `app/src/assistant/cards/sql/`, each feature's `cards.ts`.

## Kinds to build (follow the pattern of race.teammate_gap and era_rating.season)
1. `data_quality.race` - lineage says usable_laps, pct_usable and anomaly_laps are dirty-air-dependent: build the kind as HELD with the reason, not live.
2. `race_control.pooled_rate` - the pooled safety-car / VSC rate only. No per-circuit rate (the audit's forbidden chain).
3. `tyre_cliff_survival.profile` - a Kaplan-Meier lower bound; the card says so and carries n (stints).
4. `corner_phase.season` - corner skill with its `*_se_s`; transform-only with the AIR_STATE_FILTER caveat.
5. `season.teammate_gap` - the season mart's teammate gap with its SE/CI (TX-06) and the trust label; `rank_separated_from_next` travels in policy_fields.

## Method / Acceptance
Each kind needs a spec, a builder over the published files, parity with the page it mirrors on 3 parameter sets (as AX-04 did), and a refusal or held reason for every case the data cannot support. Acceptance: a full card run on a scratch export produces valid cards for every kind (counts reported), no card without n, interval kind never relabelled, and the lineage class for each kind stated in the card.

## Naming
Use the skill-measure names from AX-21's glossary (`teammate_paired_median`, `era_rating`); do not introduce new ones.

## Tests to add
Per kind: a live case, an unavailable/held case with its reason, and a parity case. Full vitest keeps only the 2 pre-existing failures. Definition of done: tests pass, typecheck and eslint clean on touched files. Do not commit.
