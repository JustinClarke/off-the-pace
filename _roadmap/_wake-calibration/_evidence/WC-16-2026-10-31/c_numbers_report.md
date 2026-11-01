# Pirelli dry-compound nominations as absolute C-numbers, 2018-2025

Table: `c_numbers.csv` (same folder). 173 rows, one per race in `transform/seeds/race_scheduled_laps.csv` joined to `race_to_track.csv` (race_id -> circuit_key). Columns: race_id, season, round, circuit, event_name, hard_c, medium_c, soft_c, consecutive, source_url, source_type, fetched_ok, agreement_with_existing_file, existing_file_value, lead_spot_checked, evidence_quote, notes.

Method: one sonnet sub-agent per season, each blind to the existing seed's values, had to fetch a page and copy a short quote for every row. The lead then re-fetched 35 rows (`lead_spot_checked=y`), weighted toward mismatches and the weakest evidence. All 35 confirmed. Caveat: WebFetch returns a model's summary of the page, so a quote is close to verbatim but has not been checked character for character.

## Coverage

| Season | Races | Verified | Primary Pirelli | Secondary | Lead spot-checked |
|---|---|---|---|---|---|
| 2018 | 21 | 21 | 0 | 21 | 5 |
| 2019 | 21 | 21 | 21 | 0 | 1 |
| 2020 | 17 | 17 | 0 | 17 | 8 |
| 2021 | 22 | 22 | 13 | 9 | 2 |
| 2022 | 22 | 22 | 8 | 14 | 3 |
| 2023 | 22 | 22 | 10 | 12 | 3 |
| 2024 | 24 | 24 | 22 | 2 | 5 |
| 2025 | 24 | 24 | 0 | 24 | 8 |
| Total | 173 | 173 | 74 | 99 | 35 |

Unverified: none. Most "secondary" rows come from formula1.com's per-race article "What tyres will the teams and drivers have for ...", which restates Pirelli's nomination. The 2018 rows come from formula1.com, verstappen.com, crash.net, f1technical.net and motorsportweek.com. The 2020 rows come from formula1.com and a verstappen.com page that quotes Pirelli's announcement for the first eight races. Pirelli's own 2020 pages show the nomination only as an image.

Weaker rows. All are still backed by a fetched page and are flagged in `notes`:
- **2020_14 Turkey:** the page names "C1, C2 and C3" as the hardest trio. Hard/medium/soft follows the hardness order (Pirelli marks the hardest white); the page does not state it per label. Lead-checked.
- **2025_14 Hungary:** the formula1.com page gives the trio C3/C4/C5 ("same as last year"). Labels follow the hardness order. Lead-checked. The agent's first source was a blog.
- **2024_1 Bahrain:** indirect. Pirelli's 2024 Barcelona release says C1 as Hard, C2 as Medium, C3 as Soft were "the same three selected for the opening round of the year in Bahrain". Lead-checked.
- **2024_24 Abu Dhabi:** indirect. The Pirelli release says "same trio" as Las Vegas (C3/C4/C5).
- **2023_19 and 2023_20 (Mexico, São Paulo):** the agent's quote was weak, but the lead re-fetched the Pirelli release dated 28 Sep 2023, which states both explicitly.
- **2022_15 Dutch:** the formula1.com fetch mentioned a "C5 soft", which looks like a typo. Pirelli's own page and f1technical both give C1/C2/C3, and the row uses that.
- **2022_3 Australia:** C5 as soft is confirmed on Pirelli's page ("the softest C5 compound as the P Zero Red soft ... a bigger gap than normal"). Lead-checked.

## Agreement with the existing seed (`transform/seeds/tyre_allocations.csv`)

- **2019-2023:** 104 of 104 rows match. The seed's values for these years are confirmed, even though most of its URLs no longer resolve. The fetched URLs in `c_numbers.csv` can replace its attributions.
- **2024:** 23 of 24 match. One mismatch:
  - **2024_16 Italy (Monza).** The seed has C2/C3/C4. The 2024 value is **C3/C4/C5**: Pirelli's release of 30 Jul 2024, "A soft September ... Monza, Baku and Singapore", says "the C3 will be the P Zero White hard, the C4 P Zero Yellow medium and C5 P Zero Red soft ... exactly the same choice as last year" (2023 Monza was also C3/C4/C5). Lead-checked.
- **2025:** 12 of 23 match, 11 mismatch, and 1 is missing (2025_6 Miami, which is C3/C4/C5). This confirms the warning in the seed's documentation that the carried-forward rows are wrong about half the time.

| race_id | Event | Seed (carried) | Verified |
|---|---|---|---|
| 2025_5 | Saudi Arabia | C2/C3/C4 | C3/C4/C5 |
| 2025_7 | Emilia Romagna | C3/C4/C5 | C4/C5/C6 |
| 2025_8 | Monaco | C3/C4/C5 | C4/C5/C6 |
| 2025_10 | Canada | C3/C4/C5 | C4/C5/C6 |
| 2025_12 | Britain | C1/C2/C3 | C2/C3/C4 |
| 2025_13 | Belgium | C2/C3/C4 | C1/C3/C4 |
| 2025_15 | Netherlands | C1/C2/C3 | C2/C3/C4 |
| 2025_16 | Italy | C2/C3/C4 | C3/C4/C5 |
| 2025_17 | Azerbaijan | C3/C4/C5 | C4/C5/C6 |
| 2025_19 | United States | C2/C3/C4 | C1/C3/C4 |
| 2025_20 | Mexico City | C3/C4/C5 | C2/C4/C5 |

The lead re-fetched 2025_5, 7, 12, 13, 19 and 20; formula1.com quotes are in the CSV. The seed's `accepted_values` test allows only C1-C5, so the 2025 C6 rows would fail it if loaded as they are.

## Non-consecutive nominations and special cases

The nominated trio skips a step at 9 races. Everywhere else it is three adjacent compounds.
- **2018**, on the 7-name ladder:
  - China, Germany and Hungary were MEDIUM/SOFT/ULTRASOFT, skipping supersoft.
  - Singapore and Russia were SOFT/ULTRASOFT/HYPERSOFT, skipping supersoft.
- **2022_3 Australia:** C2/C3/C5. The gap is between medium and soft.
- **2025_13 Belgium:** C1/C3/C4. Gap between hard and medium; Pirelli calls the hard "new for this event".
- **2025_19 United States:** C1/C3/C4. Gap between hard and medium.
- **2025_20 Mexico City:** C2/C4/C5. Gap between hard and medium.

Other special cases:
- **C6 in 2025:** Imola, Monaco, Canada and Baku, all C4/C5/C6.
- **Same venue, different nominations:** 2020 British (C1-C3) vs 70th Anniversary (C2-C4), and 2021 Styria (C2-C4) vs Austria (C3-C4-C5). 2020 Austria/Styria and Bahrain/Sakhir had the same trio.
- **2018 thinner-tread tyres:** Spain, France and Britain (f1technical news/21672). These are a different construction, not just a compound choice.
- **2023 C-scale renumbering:** for 2023 Pirelli added a new C1 and renamed the old one C0 (never nominated). Singapore, Japan and Qatar were "unchanged in name". A C-number therefore means slightly different rubber before and after 2023, and between 2019-21 and 2022+ (construction change). `compound_hardness_scale.csv` already splits by era.
- **Events with extra rules, not compound changes:** 2023 Qatar had an 18-lap cap per set (seen only in search snippets). 2025 Monaco had a mandatory two stops. 2023 Hungary/Monza used the alternative tyre allocation. Sprint weekends had 12 sets.
- **Relabelling:** every nomination is labelled hard/medium/soft in hardness order. For a skip race the relative class still holds, but the step between two labels is two C-numbers.
- **2018 vs C-numbers:** 2018 names are not on the C-scale. The repo's ordinal mapping (`compound_hardness_scale.csv`, 2018 rank 1-7) is a stated assumption.

## Decision summary

- **Can the model use absolute C-numbers?** Yes, for every race 2019-2025 (152 races, all verified, 0 unverified). For 2018 (21 races) the nomination is verified, but only as Pirelli names, which have no C-number.
- **Recommended source for the model:** use `c_numbers.csv` values, not the current seed, for 2024_16, 2025_6 and the 11 mismatched 2025 rows.
- **Fallback rule** (for 2018, for any future race not yet sourced, and for laps whose compound label cannot be joined):
  - Use the relative class factor (SOFT 1.10, MEDIUM 1.00, HARD 0.96), as the model does now.
  - Set a flag `compound_basis = relative_class` (versus `absolute_c`).
  - Do not carry a nomination forward from an earlier season. 11 of 23 carried 2025 rows were wrong.
  - For 2018, optionally use the ordinal 7-step ladder with `compound_basis = ordinal_2018`. The steps are not the same physical size as C steps, so keep the relative-class factor as the default for 2018.

## Proposal (not implemented): a C-number tyre factor

**Aim.** A small, bounded factor that rises monotonically with softness and keeps a race's middle compound near 1.00.

**Option B, recommended: relative class times a race-range adjustment.**
- Formula: `factor = step(rank_lap - rank_medium_of_race) x g(rank_medium_of_race)`.
- `step` reproduces today's factors for a normal race and extends them at skip races:

| rank_lap - rank_medium | step |
|---|---|
| -2 | 0.93 |
| -1 | 0.96 |
| 0 | 1.00 |
| +1 | 1.10 |
| +2 | 1.17 |

- `g` shifts the whole race's range by how soft the race's middle compound is, so a C4-medium weekend costs a little more than a C2-medium one:

| Medium compound | g |
|---|---|
| C2 | 0.97 |
| C3 | 1.00 |
| C4 | 1.03 |
| C5 | 1.06 |

- C5 is the medium only in the 2025 C4/C5/C6 races.
- Medium factors across races therefore stay within 0.97-1.06.
- Clamp the product to [0.90, 1.17]. The largest product, C5-medium x +1 = 1.166, falls just inside. The +2 step would give 1.24 but never occurs with a C5 medium.
- A consecutive C2/C3/C4 race gives exactly the current factors 0.96 / 1.00 / 1.10.

**Option A, simpler: absolute only.**

| Compound | C1 | C2 | C3 | C4 | C5 | C6 |
|---|---|---|---|---|---|---|
| Factor | 0.93 | 0.96 | 1.00 | 1.05 | 1.10 | 1.15 |

The middle compound is 1.00 only at C3-medium races (0.96-1.10 elsewhere), and it ignores the within-race softest/hardest role. Use it only if the owner wants the factor to depend on rubber alone.

**DA-03 collision check (BUILD-ORDER rule 6).**
- Done by the lead on the constants only, read-only, against all 276 distinct 3-dp numbers in `_roadmap/_archive/_dirty-air/_evidence/DA-03-2026-10-27/fit.json`.
- None of the candidate constants collides.
- None of the 20 distinct `step x g` products collides either (0.902, 0.93, 0.931, 0.958, 0.96, 0.97, 0.986, 0.989, 1.0, 1.018, 1.03, 1.06, 1.067, 1.1, 1.133, 1.135, 1.166, 1.17, 1.205, 1.24). DA-03 has no number between 0.8 and 1.3 at all.
- The real risk is in the per-race x tyre x car loss values (seconds), which `transform/tasks/wake_calibration/tests/test_wc11_placeholder.py::test_combined_value_bounded_and_off_da03` checks. The implementer must re-run it after any change. If a product lands on a DA-03 value, nudge the colliding constant by ±0.01. 0.96 was chosen over 0.95 for this reason.
- **2018 handling:** use the relative class, with flag `relative_class`.
