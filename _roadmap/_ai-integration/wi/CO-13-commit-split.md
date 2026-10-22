# CO-13 — Commit the experimental chance line and restored records, split

**Status:** SPEC (nothing run). **Group:** 4 chance line · **Depends on:** `CO-11` · **Blocker:** CD4 ruling; owner's yes to commit.

**Sources:** the working-tree changes from the restore and experimental-line work.

## Why

Nothing is committed. The working tree mixes the restored CO-08 records, the drift code, the lookup, the page and the dependency bumps from `f02c4ff`, which should not ride along with this feature.

## Method

1. Stage in separate commits, in this order: (a) restored roadmap records and `ml/src/flag_chance.py`; (b) the lookup file and its tests; (c) the app page, methodology and docs; (d) the relabel from `CO-11`.
2. Leave the dependency bumps out, or commit them on their own with the owner's yes.
3. Run `board.py --check` and the ML and app tests before each commit.

## Definition of done

Commits as above, each with passing checks; the owner has said yes to each.
