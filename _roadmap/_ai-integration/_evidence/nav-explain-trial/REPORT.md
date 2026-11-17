# Navigate / explain / combine trial with the local model (2026-11-10)

Question: can gpt-oss-20b (Ollama) pick the right shipped page, explain a page from its summary, and combine fact-card numbers? Source design: `wi/AX-10.md` (real-model behaviour was not measured there), `wi/AX-03.md` (navigate v2).

## Setup (what was checked)
- Ollama up: `curl localhost:11434/api/tags` lists `gpt-oss:20b-f1`, `gpt-oss:20b`, `gemma4:26b`. Used `gpt-oss:20b-f1` (Modelfile has `num_ctx 20480`, `num_predict 8192`, temperature 1). Nothing downloaded.
- `app/public/data/_manifest.json` present.
- Tests: `cd app && npx vitest run src/assistant src/nav` -> 57 files passed, 8 skipped, 801 tests passed, 126 skipped (before my change). After: `npx vitest run src/assistant/drawer` 36 passed; `npx tsc --noEmit -p tsconfig.app.json` clean.
- Cards: no cards.json is shipped (published cards are parquet). Built one read-only from published files into a scratch folder, not into public/data: `node scripts/build-cards.mjs --data public/data --limit 40 --out <scratch>` (34,968 cards; only 8 kinds are active, the rest held).
- Product change: the drawer now shows "Go to page: <title>" for ok navigate results (`AnswerView.tsx` `pageLinksOf` + `Link`, wired through `ChatDrawer.tsx`; tests in `AnswerView.test.tsx`). Only paths in `shippedPaths`; external and `//` URLs ignored. Flag untouched (VITE_ASSISTANT_ENABLED still defaults off). Title = `explainPage(path).title` (these are question-style titles from pageSummaries).
- Not fixed, by instruction: AX-03 race-level deep-link bugs (12 pages drop `race` on mount; pit page reads `race_id`). All trial navigate questions are season-level/no params.

## Command
`app/` cwd: `_roadmap/_ai-integration/_evidence/nav-explain-trial/run.sh <cards.json>` = `node scripts/assistant-cli.mjs --data public/data --cards <cards.json> --protocol openai --endpoint http://127.0.0.1:11434/v1/chat/completions --model gpt-oss:20b-f1 --file questions.json --out raw-run.json --text-out raw-run.txt`. Score: `python3 score.py` (writes `scored.json`). 10 questions x 3 runs = 30 runs, about 20 minutes. Files here: `questions.json`, `expected.json`, `raw-run.json`, `raw-run.txt`, `scored.json`.

## Results (strict, mechanical scoring)
| Group | Measure | Count |
|---|---|---|
| navigate (4 q x 3 = 12) | called navigate | 10/12 |
| | ended with an ok shipped route | 7/12 |
| | **right route** | **4/12** (N1 2/3, N2 1/3, N3 1/3, N4 0/3) |
| explain (3 x 3 = 9) | called explain_page ok on the right page | 5/9 |
| | gave a wrong/invented description | 1/9 (E1.r2) |
| | said "no summary / no card" (refusal) | 3/9 |
| combine (3 x 3 = 9) | get_fact_cards ever returned ok cards | **0/9** |
| | answers with numbers not backed by any card, surviving the repair turn | 2/9 (C1.r1, C2.r2) |
| | first drafts with invented numbers (caught by grounding, repair used) | 3/9 |
| | empty answer / tool-limit / raw tool-call JSON as the answer | 6/9 |
| | honest "no data" | 1/9 (C1.r3) |

Grounded answers with real numbers: 0/9. Explain faithfulness to the summary was spot-read only (E1.r1, E3.r1 looked consistent), not line-checked.

Why navigate failed: the model guesses route names (`tyre_degradation`, `era-ratings`, `drivers/era-translator`) and the validator rejects them; it usually recovers on retry because the error lists the shipped routes, but 2 of 12 gave up with "page isn't in the app". N4 (3/3) landed on `/drivers/era-translator`, which is arguably defensible, but scored wrong against `/drivers/ratings-timeline`. N3.r2 used explain_page and named the page in prose with no navigate link.
Why combine failed: every `get_fact_cards` call was rejected (`bundle is not an allowed value`, `scope_incomplete`, `scopes[0] must be object`); the model guesses bundle names and scope shapes. The system prompt and tool schema do not make these easy; this is partly a prompt/schema problem, not only a model one.

## Three failures, verbatim
1. N1.r1 "Take me to the tyre degradation page." -> `navigate({"params":{},"route":"tyre_degradation"}) -> error`, answer: "I'm sorry, but the "tyre degradation" page isn't part of this app's current content." (the page `/tyre-strategy/degradation` is shipped)
2. E1.r2 "What does the cliff survival profile show?" -> after a rejected get_fact_cards, called `get_fact_cards({"bundle":"safety_car_rate"})` and answered: "The cliff survival profile is a visual depiction of the safety-car frequency across the season. It shows the probability that a race will see a safety-car by a given point in the event." (wrong; it never called explain_page)
3. C1.r1 "For Alexander Albon in 2020, how did his gap to his teammate compare with his season results?" -> zero tool calls, answer: "Alexander Albon's median lap-time gap to teammate Pierre Gasly on paired laps over the 2020 season was 0.28 s (measured) [teammate_paired_median:2020_ALB]. Albon finished 2020 in 22nd place with 0 points..." Invented numbers and invented card ids; grounding flagged 0.28, 22, 0 and the single repair turn did not fix it. Also seen: N4.r3 said "The page ... is now open", which is untrue (the CLI opens nothing).

## Recommendation
- Navigate: not good enough as-is (4/12 right route). Likely fixable cheaply by putting the route list (with plain names) in the prompt or tool description, but that was not tested. The deterministic validator keeps wrong answers from becoming bad URLs, which is the safety that worked.
- Explain: borderline. When it calls explain_page on the right slug it summarised sensibly, but it fails to find the slug about half the time and can substitute a wrong answer from another tool (E1.r2). Needs the page-id list available to the model; untested.
- Combine: not usable. No grounded answer in 9 runs, and 2 of 9 shipped invented numbers past the repair turn (the render-time strike-through would show them, but that is the last line of defence).

## NOT measured
Gemma or any other model; prompt or schema changes; the Worker path and the 20k budget under the Worker; race-level navigate; browser rendering of the new button (unit tests only, no Playwright); temperature effects; faithfulness of explain text beyond a spot read; combine questions on any kind other than season/race teammate gap and caution/pooled rate; page-context pre-load (no `--page` given). Cards were built with `--limit 40` per kind, which may have left some scopes absent; combine failures occurred at the tool-argument stage, before any card lookup, so this does not explain them.
