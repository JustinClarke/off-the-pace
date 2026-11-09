# WC-03 pre-registration: finalise log (2026-10-28)

Edits to `_roadmap/_wake-calibration/wi/WC-03-preregistration-DRAFT.md` applying the owner's decisions of 2026-10-28. The file is **not signed** (no box ticked, signature and date blank) and **not committed**. `build-log.json` and `BUILD-ORDER.md` not edited. Nothing was fitted, scored or gated; no warehouse or bronze file was read or written for this step (only the existing scratch `rerun_theta_result.json` and the WC-01 `counts_by_season.csv` were read, to check numbers).

## Edits by owner decision

| # | Section | Edit | Decision |
|---|---|---|---|
| 1 | Header (status) | Status line now "DRAFT FOR SIGNATURE, not yet signed or committed."; one line added noting the 2026-10-28 finalisation and this log | C |
| 2 | Header | "Signing is blocked until the owner picks one branch of G3" paragraph replaced by the benchmark decision (shipped 0.331; 0.305 diagnostic only; G3 data-unchanged gate before any fit or score) | A, D |
| 3 | Changes since the first draft, item 3 | "G3 now has two branches for the owner to choose between" replaced by the decision | A, D |
| 4 | Changes, item 16 | "proposed, pending owner confirmation" replaced by "confirmed by the owner on 2026-10-28; N1 set to the refit option" | B, D |
| 5 | Changes, new item 17 | Records this finalisation | D |
| 6 | §0 fixed numbers | Flat-penalty row labelled "(the benchmark)"; new row for the G3 data-unchanged gate with its three exact values | A |
| 7 | §2d flat-now | "(Proposed, pending owner confirmation: N1.)" now "(N1.)" | B, D |
| 8 | §2d yardstick panel | Panel `d_lag1` now said to be used only in G3's pooled-slope fingerprint and the diagnostic rerun (was "G3 checks the reference fit exactly as it was run") | A |
| 9 | §2e item 2 | New paragraph "How the rerun is used": benchmark stays 0.331; rerun 0.305 (95 % interval 0.269 to 0.341, n 135,675) reported as a diagnostic only, data moved (v15, v16); its fingerprints define G3 | A |
| 10 | §2e "Which way the contest leans" | "(under branch A of G3 this goes away)" removed; now says the effect stays in and is stated on the scorecard | A |
| 11 | §4b, §6, §7, §8a, §8b, §10, §11 headings | "(proposed, pending owner confirmation: Cx)" now "(choice Cx)"; §4b also names N2 | B, D |
| 12 | §9 W1, W2, verdict scope | Pending wording removed from the N5, C12 and N5-scope tags | B, D |
| 13 | §12a G3 | Branches A and B removed. G3 is now "the input data has not changed since 2026-10-28", run before any scoring: (1) scratch `dev.duckdb` SHA-256 = `7173444b0745130769863c123fb5c04c7e5edd8be7a1fb2dbf614637d3214f9f`; (2) panel rows = 135,841 and shipped calibration n = 135,841; (3) pooled-slope fingerprint (d1 Gate 1) = 0.4777453471 within 1e-9. Any failure: stop, nothing fitted or scored, "no verdict", owner told, scorecard's first line says so | A |
| 14 | §12b | New bullet: the 0.305 reference-fit diagnostic, reported as recorded, never a verdict input | A |
| 15 | §14 prior knowledge | "G3's branches handle the second" replaced by the benchmark decision and G3 | A, D |
| 16 | §16 | Sentence about branch A's label change removed | A |
| 17 | §17a | Heading now "Confirmed choices"; "proposed, pending owner confirmation" now "confirmed by owner on 2026-10-28"; benchmark decision stated. Wording and numbers of every choice unchanged | B, D |
| 18 | §17a N1 row | Alternative "(0.331 × same-lap share, no refit)" removed; refit option kept | B |
| 19 | §17b | Pre-signing text no longer asks for a G3 branch; "G3 branch: A / B" line replaced by an unticked "Benchmark: shipped 0.331; G3 = input data unchanged since 2026-10-28" box. All boxes unticked, signature and date blank. After-signing step 1 now names "DRAFT FOR SIGNATURE" | A, C |

## Consistency check (decision E)

Checked against the body: 8 gap bins [lower, upper) (§0, §5, §6, §10); seed 20261027 (§0, §8c, §12b, C14); 1,000 resamples (§0, §8c, §12b, C14); 200-stop minimum (§0, §11, C14); 0.5 % margin and -0.5 % (§0, §9, §17b); minimums 1,000 laps and 18 races (§0, G5, C14); 60/68 and 20/24 races (§0, §8c, G5); benchmark 0.331 (§0, §2d); fit 2022-2024 (68 races), score 2025 (24 races), older cars 2018-2020 (55) on 2021 (22) (§0, §3, §6, §8c). Race counts match WC-01 `counts_by_season.csv` (19+21+15 = 55; 22; 22+22+24 = 68; 24). Stint shares 0.32/0.36/0.32/0.36 match. Every section a choice points to (C1-C14, N1-N5) exists and holds that choice.

Mismatches found and fixed:

| # | Section | Mismatch | Fix |
|---|---|---|---|
| E1 | §0 flat-now row | Said θ_now is fitted "(§8b)"; θ_now is defined in §2d and refitted per draw in §8c; §8b has no θ_now fit | Now "(§2d), refitted in every bootstrap draw (§8c)" |
| E2 | §2f | "The stint in §8b steps 3-4" — §8b step 4 is the score and uses no stint; the stint steps are §8a steps 3-4 and §8b step 3 | Now "§8a steps 3-4 and §8b step 3" |

## Note for the owner

- G3's data-source fingerprint is the SHA-256 of the `dev.duckdb` copy, the only data-file fingerprint the revision recorded. The staging views also read parquet files by relative path from `transform/`; those files are not in that hash. The panel row count and pooled-slope fingerprint cover the panel's content, so a change there would still very likely fail G3, but not with certainty.
- Tolerance on the pooled slope is 1e-9 (d1's own Gate 1 tolerance). The earlier branch B text used 1e-6. Change it before signing if 1e-6 is preferred.
