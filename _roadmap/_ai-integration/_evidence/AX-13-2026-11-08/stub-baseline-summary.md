# AX-13 STUB baseline (harness measurement, not a model) - 2026-11-08

STUB: deterministic scripted model. Measures the harness (dispatcher, loop, budget meter, checker, grounding, grader), NOT a model.

Question file hash 901ed60e1060afbd860636ff79830e40ada0a188cc43e04bdfbff7b869b9d6a7 (bar recorded 2026-11-08T09:59:33.404Z). Cards: /private/tmp/claude-501/-Users-justin-github-off-the-pace/bf41f451-ffc1-4ccc-bc71-e73e8a654460/scratchpad/laneR/cards-07b/cards.json (64123). Data: /private/tmp/claude-501/-Users-justin-github-off-the-pace/bf41f451-ffc1-4ccc-bc71-e73e8a654460/scratchpad/laneK/out. Repeats: 5.

## Verdict: INCOMPLETE

| bar item (fixed before the first run) | measured | threshold | pass |
| :--- | ---: | ---: | :--- |
| numbers grounded | 100.0% | 100% | yes |
| refusal / hedge cases correct | 100.0% | 100% | yes |
| right tool | 100.0% | >= 95% | yes |
| max tokens in one run | 7918 (0 over) | <= 18000 | yes |
| human read (10 answers) | not_applicable | pass | - |
| repeats per question | 5 | 5 | yes |

Runs 395 over 79 questions; endpoint errors 0.

## Checks

| check | pass | fail | n/a | rate |
| :--- | ---: | ---: | ---: | ---: |
| grounded | 395 | 0 | 0 | 100.0% |
| expected_value | 80 | 0 | 315 | 100.0% |
| honesty | 395 | 0 | 0 | 100.0% |
| rules_fired | 260 | 10 | 125 | 96.3% |
| refusal | 150 | 0 | 245 | 100.0% |
| must_not | 395 | 0 | 0 | 100.0% |
| right_tool | 395 | 0 | 0 | 100.0% |
| all_tools | 380 | 0 | 15 | 100.0% |
| budget | 395 | 0 | 0 | 100.0% |
| limits | 395 | 0 | 0 | 100.0% |
| answered | 395 | 0 | 0 | 100.0% |

### By class

| group | runs | all checks pass | rate | failed checks |
| :--- | ---: | ---: | ---: | :--- |
| ML | 15 | 15 | 100.0% | - |
| T | 180 | 170 | 94.4% | rules_fired 10 |
| T* | 50 | 50 | 100.0% | - |
| WC | 10 | 10 | 100.0% | - |
| X | 45 | 45 | 100.0% | - |
| nav | 85 | 85 | 100.0% | - |
| whatif | 10 | 10 | 100.0% | - |

### By family

| group | runs | all checks pass | rate | failed checks |
| :--- | ---: | ---: | ---: | :--- |
| aero-conditions | 15 | 15 | 100.0% | - |
| constructors | 15 | 15 | 100.0% | - |
| data-validation | 5 | 5 | 100.0% | - |
| drivers | 115 | 115 | 100.0% | - |
| ghost-car | 15 | 15 | 100.0% | - |
| lap-decomposition | 25 | 25 | 100.0% | - |
| race-craft | 110 | 100 | 90.9% | rules_fired 10 |
| the-machine | 30 | 30 | 100.0% | - |
| tyre-strategy | 65 | 65 | 100.0% | - |

### By playbook type

| group | runs | all checks pass | rate | failed checks |
| :--- | ---: | ---: | ---: | :--- |
| corner_phase | 10 | 10 | 100.0% | - |
| held_class | 65 | 65 | 100.0% | - |
| lookup_navigate | 95 | 95 | 100.0% | - |
| observed_count | 90 | 80 | 88.9% | rules_fired 10 |
| safety_car_rate | 15 | 15 | 100.0% | - |
| season_standing | 30 | 30 | 100.0% | - |
| stint_describe | 10 | 10 | 100.0% | - |
| teammate_race | 35 | 35 | 100.0% | - |
| tyre_life | 15 | 15 | 100.0% | - |
| what_if | 15 | 15 | 100.0% | - |
| why_slow | 15 | 15 | 100.0% | - |

### By group (AX-13 method step 2)

| group | runs | all checks pass | rate | failed checks |
| :--- | ---: | ---: | ---: | :--- |
| a | 20 | 20 | 100.0% | - |
| b | 130 | 125 | 96.2% | rules_fired 5 |
| c | 55 | 55 | 100.0% | - |
| d | 60 | 60 | 100.0% | - |
| e | 130 | 125 | 96.2% | rules_fired 5 |

## Cost and capacity

- Tokens per run (prompt + completion over all rounds): mean 4786, p50 4652, p90 5124, max 7918; mean peak context 2472; runs on the chars/4 estimate: 395.
- Neurons per answer: mean 88.4, p90 94, max 146 (ESTIMATED from chars/4, not a measurement).
- Answers per day at the 10000-neuron cap: 113 (estimate only).
- Rounds per run: mean 2.04, max 3; runs with 2+ model rounds: 380, of which answered after a tool result: 365.
- Tool calls per run: mean 1.04, max 2.
- Repair turns: 0 runs (0.0%); repair skipped (no round left): 0; first-draft failures: none.
- Questions no tool could answer (no ok tool result in any run): oc-wins-VER-2023, ch-wins-2023, h-ml-band-2024_1-VER (3.9%).
- Reasoning tokens: 0 of 805 usage rounds report a reasoning-token field (total 0); rounds whose completion reached MAX_OUTPUT_TOKENS (2500): 0.
- Hidden output: in rounds with endpoint usage, completion_tokens total 0 against 0 estimated (chars/4) for the visible reply; 0 rounds bill more than twice their visible text (reasoning tokens counted as output, so against MAX_OUTPUT_TOKENS). No endpoint usage = not measured.

## Per question

| question | runs | all pass | tokens (mean) | rounds (mean) | repair runs | tool calls (mean) | neurons (mean) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| tr-2024_1-VER | 5 | 5 | 4912 | 2.0 | 0 | 1.0 | 92 |
| tr-2020_14-HAM | 5 | 5 | 4906 | 2.0 | 0 | 1.0 | 92 |
| tr-2018_1-RIC | 5 | 5 | 4927 | 2.0 | 0 | 1.0 | 92 |
| tr-2021_16-HAM | 5 | 5 | 4915 | 2.0 | 0 | 1.0 | 92 |
| tr-2024_5-NOR | 5 | 5 | 4928 | 2.0 | 0 | 1.0 | 92 |
| tr-2019_1-NOR | 5 | 5 | 4922 | 2.0 | 0 | 1.0 | 92 |
| ss-2024-NOR | 5 | 5 | 4650 | 2.0 | 0 | 1.0 | 87 |
| ss-2023-ALO | 5 | 5 | 4658 | 2.0 | 0 | 1.0 | 87 |
| er-2023-ALO | 5 | 5 | 4511 | 2.0 | 0 | 1.0 | 84 |
| rr-2023_10-HAM | 5 | 5 | 4419 | 2.0 | 0 | 1.0 | 81 |
| rc-2024_8 | 5 | 5 | 4426 | 2.0 | 0 | 1.0 | 81 |
| ws-2024_8-SAI | 5 | 5 | 4996 | 2.0 | 0 | 1.0 | 94 |
| ws-2023_10-HAM | 5 | 5 | 5007 | 2.0 | 0 | 1.0 | 94 |
| sd-2024_1-VER | 5 | 5 | 4691 | 2.0 | 0 | 1.0 | 87 |
| sd-2024_5-NOR | 5 | 5 | 4692 | 2.0 | 0 | 1.0 | 87 |
| sc-all | 5 | 5 | 4588 | 2.0 | 0 | 1.0 | 85 |
| sc-2018 | 5 | 5 | 4815 | 2.0 | 0 | 1.0 | 89 |
| x-sc-monaco | 5 | 5 | 4606 | 2.0 | 0 | 1.0 | 85 |
| tl-2024_1-SOFT | 5 | 5 | 4531 | 2.0 | 0 | 1.0 | 84 |
| tl-2023_10-HARD | 5 | 5 | 4538 | 2.0 | 0 | 1.0 | 84 |
| cp-2024-NOR | 5 | 5 | 4652 | 2.0 | 0 | 1.0 | 87 |
| cp-2024-VER | 5 | 5 | 4659 | 2.0 | 0 | 1.0 | 87 |
| oc-pits-VER-2024 | 5 | 5 | 4636 | 2.0 | 0 | 1.0 | 86 |
| oc-pits-top3-2024 | 5 | 5 | 4670 | 2.0 | 0 | 1.0 | 86 |
| oc-wins-VER-2023 | 5 | 0 | 4675 | 2.0 | 0 | 1.0 | 86 |
| oc-sc-laps-2024 | 5 | 5 | 4577 | 2.0 | 0 | 1.0 | 84 |
| oc-soft-stint-2024 | 5 | 5 | 4653 | 2.0 | 0 | 1.0 | 86 |
| oc-dnf-LEC-2022 | 5 | 5 | 7024 | 3.0 | 0 | 2.0 | 129 |
| oc-gained-2021 | 5 | 5 | 4716 | 2.0 | 0 | 1.0 | 87 |
| oc-quickest-2024_1 | 5 | 5 | 4704 | 2.0 | 0 | 1.0 | 87 |
| oc-corners | 5 | 5 | 4623 | 2.0 | 0 | 1.0 | 85 |
| oc-monaco-sc-history | 5 | 5 | 4626 | 2.0 | 0 | 1.0 | 85 |
| oc-stints-HAM-2024_1 | 5 | 5 | 4699 | 2.0 | 0 | 1.0 | 87 |
| oc-braking-2024_8 | 5 | 5 | 4708 | 2.0 | 0 | 1.0 | 87 |
| ch-pits-per-race-2024 | 5 | 5 | 7614 | 3.0 | 0 | 2.0 | 140 |
| ch-sc-laps-season | 5 | 5 | 7073 | 3.0 | 0 | 2.0 | 130 |
| ch-stint-compound-2023 | 5 | 5 | 7243 | 3.0 | 0 | 2.0 | 134 |
| ch-laps-VER-2024_1 | 5 | 5 | 7918 | 3.0 | 0 | 2.0 | 146 |
| ch-wins-2023 | 5 | 0 | 7248 | 3.0 | 0 | 2.0 | 133 |
| cmp-2024_1-VER-PER | 5 | 5 | 4412 | 2.0 | 0 | 1.0 | 81 |
| cmp-2024_5-NOR-PIA | 5 | 5 | 4409 | 2.0 | 0 | 1.0 | 81 |
| cmp-2023_10-HAM-RUS | 5 | 5 | 4414 | 2.0 | 0 | 1.0 | 81 |
| cmp-2022_1-LEC-SAI | 5 | 5 | 4413 | 2.0 | 0 | 1.0 | 81 |
| cmp-2019_1-NOR-SAI | 5 | 5 | 4408 | 2.0 | 0 | 1.0 | 81 |
| ex-race-lost | 5 | 5 | 5076 | 2.0 | 0 | 1.0 | 93 |
| ex-pit-gantt | 5 | 5 | 5072 | 2.0 | 0 | 1.0 | 93 |
| ex-survival | 5 | 5 | 5079 | 2.0 | 0 | 1.0 | 93 |
| ex-ratings | 5 | 5 | 5088 | 2.0 | 0 | 1.0 | 93 |
| x-lap-map-grey | 5 | 5 | 5124 | 2.0 | 0 | 1.0 | 94 |
| nav-pit-gantt-2024_8 | 5 | 5 | 4399 | 2.0 | 0 | 1.0 | 81 |
| nav-race-control-2024_5 | 5 | 5 | 4395 | 2.0 | 0 | 1.0 | 81 |
| nav-ratings | 5 | 5 | 4361 | 2.0 | 0 | 1.0 | 80 |
| nav-corner-2024 | 5 | 5 | 4371 | 2.0 | 0 | 1.0 | 80 |
| os-cautions-2024_1 | 5 | 5 | 2242 | 1.0 | 0 | 0.0 | 42 |
| lv-checo | 5 | 5 | 4367 | 2.0 | 0 | 1.0 | 80 |
| lv-kmag | 5 | 5 | 4382 | 2.0 | 0 | 1.0 | 81 |
| lv-teams-2024 | 5 | 5 | 4589 | 2.0 | 0 | 1.0 | 84 |
| lv-spa | 5 | 5 | 4473 | 2.0 | 0 | 1.0 | 82 |
| wi-pit-lap20 | 5 | 5 | 4403 | 2.0 | 0 | 1.0 | 81 |
| x-chance-line | 5 | 5 | 4414 | 2.0 | 0 | 1.0 | 81 |
| wi-no-stop-2021 | 5 | 5 | 4411 | 2.0 | 0 | 1.0 | 81 |
| x-skill-mix-2024 | 5 | 5 | 5028 | 2.0 | 0 | 1.0 | 94 |
| x-affinity-era | 5 | 5 | 4588 | 2.0 | 0 | 1.0 | 85 |
| x-would-have-won-2022 | 5 | 5 | 5090 | 2.0 | 0 | 1.0 | 94 |
| x-blind-test | 5 | 5 | 5157 | 2.0 | 0 | 1.0 | 95 |
| x-sector-2023_10-VER | 5 | 5 | 4496 | 2.0 | 0 | 1.0 | 83 |
| x-2026 | 5 | 5 | 2164 | 1.0 | 0 | 0.0 | 40 |
| x-cross-era | 5 | 5 | 2194 | 1.0 | 0 | 0.0 | 41 |
| x-constructor-pace-2023 | 5 | 5 | 4509 | 2.0 | 0 | 1.0 | 83 |
| h-traffic-2023_10-HAM | 5 | 5 | 4475 | 2.0 | 0 | 1.0 | 83 |
| h-dirty-air-2024_1-NOR | 5 | 5 | 4475 | 2.0 | 0 | 1.0 | 83 |
| h-ml-band-2024_1-VER | 5 | 5 | 4668 | 2.0 | 0 | 1.0 | 86 |
| h-ml-cliff-2024_1 | 5 | 5 | 4546 | 2.0 | 0 | 1.0 | 84 |
| h-race-lost-2024_1-PER | 5 | 5 | 4505 | 2.0 | 0 | 1.0 | 83 |
| h-ghost-2024_1 | 5 | 5 | 5033 | 2.0 | 0 | 1.0 | 93 |
| h-ghost-champ-2021 | 5 | 5 | 5084 | 2.0 | 0 | 1.0 | 94 |
| h-consistency-2023 | 5 | 5 | 4965 | 2.0 | 0 | 1.0 | 91 |
| h-wet-2021 | 5 | 5 | 4957 | 2.0 | 0 | 1.0 | 91 |
| h-party-2020 | 5 | 5 | 4470 | 2.0 | 0 | 1.0 | 82 |

## Every failure, with its cause

- oc-wins-VER-2023 #1: rules_fired: did not fire: COMPUTED_NOT_CARD_WORDING
- ch-wins-2023 #1: rules_fired: did not fire: COMPUTED_NOT_CARD_WORDING
- oc-wins-VER-2023 #2: rules_fired: did not fire: COMPUTED_NOT_CARD_WORDING
- ch-wins-2023 #2: rules_fired: did not fire: COMPUTED_NOT_CARD_WORDING
- oc-wins-VER-2023 #3: rules_fired: did not fire: COMPUTED_NOT_CARD_WORDING
- ch-wins-2023 #3: rules_fired: did not fire: COMPUTED_NOT_CARD_WORDING
- oc-wins-VER-2023 #4: rules_fired: did not fire: COMPUTED_NOT_CARD_WORDING
- ch-wins-2023 #4: rules_fired: did not fire: COMPUTED_NOT_CARD_WORDING
- oc-wins-VER-2023 #5: rules_fired: did not fire: COMPUTED_NOT_CARD_WORDING
- ch-wins-2023 #5: rules_fired: did not fire: COMPUTED_NOT_CARD_WORDING
