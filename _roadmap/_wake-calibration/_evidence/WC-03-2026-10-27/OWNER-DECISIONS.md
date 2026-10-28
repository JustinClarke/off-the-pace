# WC-03 pre-registration: owner decisions before signing (2026-10-28)

The draft `wi/WC-03-preregistration-DRAFT.md` is DRAFT FOR SIGNATURE: unsigned, uncommitted, no box ticked. Nothing has been fitted, gated or scored. Four decisions are open. Each option is followed by its consequence in one line.

## (a) G3 check 4: bronze input files (`AMENDMENT-G3-bronze-hash.md`)
Check 4: 1,214 bronze parquet files (863 read by the warehouse build, 351 extra read by the WC-01 builder), combined SHA-256 `aed1c27da1cc00fb80eea470bb0c5c4879ee09556c81ff35bc17ad4aff1690b4`. The digest was recomputed from the scratchpad lists on 2026-10-28 and matches.
- **Accept:** G3 also fails if any bronze input file the build or the pass-table builder reads is changed, added or removed; "All four must hold" stands.
- **Amend** (e.g. drop the 351 builder extras, or add the qualifying files): the count and digest must be recomputed and written into §0 and §12a before signing; any rehash is a new read of `data/bronze`.
- **Reject:** strike check 4 in §0, §12a and §17b before signing; G3 is checks 1-3 only, which do not cover the bronze files (the gap flagged in `FINALISE-LOG.md`).

Evidence limits: the hash records bronze as of 2026-10-28, not as of the 2026-10-26 warehouse build; the 863 build files have modification times from 2026-06-12 to 2026-10-03 (all before that build), and the 351 extras' times were not recorded. The panel query reads only base tables in `dev.duckdb`, so check 4 guards the pass-table builder (G2) and the warehouse's provenance, not the panel itself.

## (b) Pooled-slope tolerance in G3 check 3 (and §0)
Current text: 0.4777453471 within 1e-9 (d1's own Gate 1 tolerance). The earlier branch B text used 1e-6.
- **Keep 1e-9:** matches d1's Gate 1; a run whose slope differs by more than 1e-9 for any reason, including numerical differences on rerun, gives no verdict. Whether the fingerprint repeats to 1e-9 on a second run has not been tested.
- **Change to 1e-6:** both places (§0 and §12a check 3) are edited before signing; differences below 1e-6 pass check 3, while the observed data shift (|d| 0.026) would still fail it, and checks 1-2 are unchanged.

## (c) Commit the component file lists beside the amendment note?
Files (session scratchpad, temporary): `hashes.txt` (863 lines), `hashes-extra.txt` (351 lines), `combined-sorted.txt` (1,214 lines, about 160 KB; hashes and relative paths only, no data) in `/private/tmp/claude-501/-Users-justin-github-off-the-pace/85d402b9-a9fd-45a9-8afb-88ae76cc358e/scratchpad/`.
- **Commit them** (copied into `_evidence/WC-03-2026-10-27/`): if check 4 fails, the run can diff against them and name the changed files; they go in a separate commit, since §17b says the pre-registration is committed alone.
- **Do not commit:** they are lost when the scratchpad is cleared; a check 4 failure would show only that the digest differs, not which file changed (the recipe would have to be rerun on an older bronze state, which may not exist).
- Only relevant if (a) is accept or amend.

## (d) Sign and commit now, or after further review?
- **Sign now:** after (a)-(c) are settled and any edits made in the file, follow §17b (status line, commit the file alone, record its SHA-256 on WC-03 in `build-log.json`, `board.py --check` and `--write-order`); the thresholds are then fixed, and later changes need a signed pre-result amendment.
- **After further review:** nothing is fitted until signing (§17b step 5); the bronze and `dev.duckdb` states could change in the meantime, and if they do, the recorded values in G3 no longer match and must be re-derived before signing.

Note for either option: the whole `_evidence/WC-03-2026-10-27/` folder (including `FINALISE-LOG.md` and `AMENDMENT-G3-bronze-hash.md`, which the draft cites) and `_evidence/WC-02-2026-10-27/` are also uncommitted.
