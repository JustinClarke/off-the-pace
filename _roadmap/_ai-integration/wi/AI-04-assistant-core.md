# AI-04 — Assistant core: one fact-card tool and the answer loop

**Group:** B assistant core · **Depends on:** `AI-01`, `AI-02` · **Blocker:** none.

**Sources:** the AI-01 card table and schema, `app/src/data/duckdb/client.ts`, `app/src/data/manifest.ts`.

---

## Why one tool, not free SQL

The earlier plan gave the model a read-only SQL tool. A model-written aggregate has no sample size and no interval, so under AI-01 it cannot be quoted. For v1 the assistant gets one structured tool over the fact cards. A SQL tool comes back only if AI-07 shows cards cannot answer a large share of fan questions.

## Method

1. Tool `get_fact_cards(scope, driver?, race?, season?, family?)`: returns matching cards, or an explicit "no cards" with the reason. Bounded by construction, so it needs no SQL guard or row cap.
2. System prompt: the AI-02 rules and the card schema. Every number in an answer cites a card `id`. That id is what AI-07 grades and AI-08 links.
3. Loop limit: at most 4 tool calls per question. An empty or refused call is passed back to the model, which retries once or says it has no data.
4. Hypothetical "what if" tyre questions link the Degradation Simulator page. They do not get a computed answer in v1.
5. Runs headless from one command (Node, a local dev key from the environment, never bundled), so AI-07 can measure it before the proxy (AI-06) exists. In the app it calls through the AI-06 proxy.

## Acceptance

- A question needing one card gets an answer whose numbers match that card.
- An empty result produces an answer that says there is no data, with no number.
- No answer contains a number without a card id (checked by AI-02's checker).

## Tests to add

Loop limit, empty result, refused call, and number-without-id rejection, with the model call stubbed.

## Definition of done

Tests pass and the headless command answers 10 sample questions. Do not commit.
