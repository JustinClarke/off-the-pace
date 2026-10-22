# AI-04 — Assistant core: seven tools and the answer loop

**Group:** 2 assistant build · **Depends on:** `AI-01`, `AI-02`, `AI-09`, `AI-10`, `AI-11` · **Blocker:** none. `AD2` and `AD3` ruled 2026-10-22.

**Sources:** the AI-01 card table and schema, `app/src/data/duckdb/client.ts`, `app/src/data/manifest.ts`, `docs/app/degradation-simulator.mdx`.

_Rewritten 2026-10-22 to the plan `AD2` records. The earlier one-tool plan is superseded. No design was changed in the rewrite._

---

## Decided (AD2, AD3)

- **Model:** gpt-oss-20b, with a 20,480-token window. The Worker (AI-06) fixes the model, the system prompt, the tool set and the output cap.
- **Tools (seven):** `get_fact_cards` (AI-01), `query_data` (the bounded query builder, AI-09), `list_values` (exact-code lookup), `compare_lap_times` and `make_chart` (AI-11), `explain_page` and `navigate` (AI-10). The model writes no SQL in v1.
- **Quoting:** rated or modelled numbers come only from fact cards. Query-builder numbers may be quoted, labelled `computed_not_card` and stated as plain counts or averages (AD3).

## Token budget (20k)

Instructions 1,500 · tool schemas 1,900 · page context 600 · query catalogue 1,200 · history 2,000 (last two turns) · tool results 6,000 (1,500 each) · output 4,000.

## Method

1. Wire the seven tools behind one dispatcher, each specified in its own item.
2. System prompt: the AI-02 rules, the card schema and the query catalogue. Every number in an answer cites a card `id` or a query result. That is what AI-07 grades and AI-08 links.
3. Loop limit: at most 4 tool calls per question (the prototype allowed 8). An empty or refused call is passed back to the model, which retries once or says it has no data.
4. "What if" tyre questions link the Degradation Simulator page. They get no computed answer in v1.
5. Runs headless from one command against a local endpoint, so AI-07 can measure it before the proxy exists. In the app it calls through the AI-06 proxy.

## Acceptance

- A question needing one card gets an answer whose numbers match that card.
- An empty result produces an answer that says there is no data, with no number.
- No answer contains a number without a card id or a labelled query result (checked by AI-02's checker).

## Tests to add

Loop limit, empty result, refused call, and number-without-source rejection, with the model call stubbed.

## Definition of done

Tests pass and the headless command answers 10 sample questions. Do not commit.
