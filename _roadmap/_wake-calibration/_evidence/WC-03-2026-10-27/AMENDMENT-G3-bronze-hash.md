# Proposed pre-result amendment: G3 check 4 (bronze input files)

Date drafted: 2026-10-28. Status: PROPOSED, pending owner sign-off. Nothing has been fitted, gated or scored. Not signed; the pre-registration status line is unchanged (DRAFT FOR SIGNATURE).

## What changed in `wi/WC-03-preregistration-DRAFT.md`
- Section 0, G3 row: added the file count and combined digest.
- Section 12a, G3: added check 4 and changed "All three must hold" to "All four must hold".
- Section 17b: the Benchmark line and the text above it now mention check 4.

## Why
G3 checks 1-3 cover the scratch `dev.duckdb`, the panel row count and the pooled-slope fingerprint. They do not cover the bronze parquet files that the warehouse build reads, or the extra files the WC-01 builder reads (track_status, circuit_info, schedule). The earlier note to the owner (FINALISE-LOG.md) flagged this gap. Read-only checks on 2026-10-28:
- All eight objects `WI01_PANEL_SQL` reads in a copy of `data/dev.duckdb` (SHA-256 7173444b...3214f9f, identical to the original) are BASE TABLEs, not views: int_lap_fuel_state, int_field_pace_curve, int_compound_cliff_predicted, int_stint_geometry, int_lap_air_state, int_event_corrections, int_track_evolution, int_lap_residual_decomposed. So the panel itself reads no parquet at run time; the parquet hash guards the pass-table builder (G2) and the warehouse's provenance rather than the panel query.

## New value
- Files: 863 (warehouse build) + 351 (builder extras: 173 track_status, 170 circuit_info, 8 schedule) = **1,214**.
- Combined SHA-256 (over the path-sorted `<hash>  <relative path>` lines): `aed1c27da1cc00fb80eea470bb0c5c4879ee09556c81ff35bc17ad4aff1690b4`.
- Component lists (scratchpad, not committed): `.../scratchpad/hashes.txt` (list digest d29d452e...1df9e), `.../scratchpad/hashes-extra.txt` (list digest 8c4e962a...e585a), merged as `.../scratchpad/combined-sorted.txt`.
- Recipe: `cat hashes.txt hashes-extra.txt | LC_ALL=C sort -t' ' -k3 | shasum -a 256`, paths relative to `data/bronze`.

## Caveats
- The extras set is the full glob (all race folders), a superset of what a given build run touches; it also covers circuit_info files read as +/-1 season fallbacks.
- Qualifying-session parquet files (deeper `session=Q` folders) are not hashed; the builder does not read them.
- Telemetry has 171 files for 173 races (2018 Australia and Bahrain have none).
- The lists above live in the session scratchpad; if the owner accepts, commit them beside this note so the run can diff on failure.
