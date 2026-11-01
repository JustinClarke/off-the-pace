# Constructor wake-sensitivity evidence (WC-13 car factor)

Date: 2026-10-31. Research only; no repo file was changed.

## Recommendation

**Keep all 81 rows neutral (1.00, `neutral_default`). The evidence is not enough.** None of the 81 (season, constructor_id) rows has a fetched, citable, non-outcome source that *explicitly* links that team's design concept to how sensitive the car is to another car's wake.

Recommended: implement non-neutral factors for **0 rows**.

## Counts

| | n |
| :-- | --: |
| Seed rows (2018-2025) | 81 |
| Rows with at least one explicit, fetched, non-outcome, team-specific source | **0** |
| Rows with an "implied" team-level source (not enough) | 4 (2019 Ferrari, 2019 Alfa Romeo Racing, 2021 Red Bull Racing, 2022 Mercedes) |
| Candidate sources logged in `constructor_evidence.csv` (all fetched and resolving) | 26 |
| of which explicit on wake/following | 11, **all era-wide** (FIA, F1, Tombazis, Symonds), none team-specific |
| of which implied | 5 |
| of which no link | 10 |
| Claims verified by the lead (page opened, quote checked) | 13 |

Method: three sonnet sub-agents (2018-20, 2021-22, 2023-25), plus the lead's own searches. Anything not backed by a fetched page was dropped, including the Piola zero-pod piece (502), the Racer "what is dirty air" explainer (429), the Aston Martin AMR22 page, f1technical news/22109 and the Red Bull porpoising Tech Tuesday. WebFetch returns pages summarised by a small model, so quotes are close to verbatim but not character-checked against the raw HTML.

## Why no row qualifies

The team-level material splits into four kinds. None of them is evidence for a direction.

1. **Concept records with no wake link.** Rake and wheelbase in 2018 (F1.com Tech Tuesday: Mercedes long wheelbase, low rake; Red Bull about 1.9 deg; Ferrari high rake). The 2022 sidepod concepts (Mercedes zero-pod, Ferrari "bathtub"). These sources confirm the concepts differ, but they never say which way any concept moves wake sensitivity.
2. **"Sensitivity" that is not wake sensitivity.** High rake "too sensitive" to speed, yaw and ride height (Motorsport Magazine, 2021). The open high-rake floor letting "turbulent flow sneak in" (Autosport, 2021; generic turbulence, no mention of following). Zero-pod ride-height sensitivity (The Race, 2022). These are about the operating window in clean air, and partly inferred from performance.
3. **The wake a car creates, not the wake it receives.** The 2019 Ferrari/Alfa outwash wing (f1technical.net, a generic Perrinn CFD model, not the team cars). The 2022 Mercedes W13 endplate "more outwash potential" (Motorsport.com). Mercedes' own front-tyre wake control (RaceFans, Elliott). These would affect the *following* car, not the team's own `constructor_factor`. The model's factor applies to the car in the wake, so they do not map onto it.
4. **Outcome-based material.** Driver comments, race-pace or overtaking comparisons and forum opinion. These are excluded by rule. One is a rival team principal's view on how well the zero-pod worked (Stella), which is outcome-flavoured.

Only the **era-wide** sources are explicit: FIA AUTO #24 (2018), F1's 2022 car explainer (47% to 18% at 10 m), Hughes on 2022 outwash, Tombazis 2023 (20% to 35%, endplates, floor sides, wheel fins), and The Race's Nov 2025 FIA data (55% / 85% / 65% retained at 10 m for 2019 / 2022 / 2025). These support the existing `era_factor` (WC-12), not a car factor. FIA AUTO #24 says outright that "every car has a unique level of sensitivity to the wake" but names no team. So variation between cars is real, but nothing public says which way it goes for any car.

## Rows that do not qualify

All 81 rows, for these reasons:

- **2018 (11 rows):** Ferrari, Mercedes and Red Bull have concept records only (rake and wheelbase), no wake link. Force India, Racing Point, Haas, McLaren, Renault, Sauber, Toro Rosso and Williams: nothing found.
- **2019 (10):** Ferrari and Alfa Romeo Racing are implied only (generic-model outwash, wake created). Mercedes and Red Bull: concept only. Haas, McLaren, Racing Point, Renault, Toro Rosso, Williams: nothing found.
- **2020 (10):** Red Bull's high-rake "sensitivity" is not wake sensitivity. Racing Point's low-rake copy of Mercedes: concept only, no wake link. Others: nothing.
- **2021 (10):** Red Bull is implied only (open-floor turbulence). Mercedes and Aston Martin low rake: clean-air window, outcome-informed. Others: nothing.
- **2022 (10):** Mercedes has its own tyre wake and outwash *created* (implied or no). Ferrari: concept, no link. Red Bull: forum speculation only. Others: nothing.
- **2023 (10):** Mercedes: ride height and concept, no wake link. The floor-edge raise and regained outwash are era-wide. Others: nothing.
- **2024 (10), 2025 (10):** era-wide only. These outcomes are sealed (W8) and nothing team-specific and non-outcome surfaced. McLaren 2024-25 concept material was forum-only and is excluded.

## Recommended factor table

Empty. No row qualifies, so no value in 0.97-1.03 is proposed and the DA-03 collision check (factor x per-race value at 3 dp) does not arise. If the owner still wants a non-neutral factor, it could only be set as an assumption without a public directional source. That is the DD-WC27 "guess about a real company" case WC-13 already ruled out. The implementer would also have to run the DA-03 grep test (`test_wc11_placeholder.py`).

## Possible follow-up (low expected yield)

The sub-agents did not search the RaceCar Engineering archive, Craig Scarborough or Giorgio Piola directly for every team, and gave thin coverage to the midfield teams. A targeted pass there could be run. Given that 26 sources and three era groups turned up no explicit team link, a change in the conclusion is unlikely.
