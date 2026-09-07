# ContextLab — Project Plan

### chat-with-your-docs(add this feature)

A client-side tool that turns your own PDFs and Markdown into **clean, pipeline-ready
context** for a local LLM. The chunking is the product; the LLM is downstream and not
required to run the app.

> **Teaching context.** This is a small, shippable project designed to build the exact
> skills behind Off The Pace's app layer — zero-backend, in-browser SQL over DuckDB-WASM
> (`otp-05`) — plus the "measure against a baseline, don't trust the demo" discipline from
> its ML evaluation (`otp-03`). It's a few evenings of work, not a horizontal rewrite of
> the whole stack.

---

## 1. The problem it solves

Ask questions grounded in your own documents via a local LLM (Ollama, or anyone's),
with **nothing leaving your machine**. Every RAG tutorial skips the part that actually
determines answer quality — *chunking* — by jumping straight to an embeddings API call.
This tool makes chunking the visible, measurable centerpiece and outputs context that
downstream tools actually want.

**Key reframe:** the LLM is not needed to *build* the context. Parsing, chunking,
metadata, and retrieval are all deterministic/local. The LLM only consumes the output.
That means the whole generator can run **100% client-side in the browser**.

---

## 2. Why this project (skill map)

| This project's step            | Off The Pace analogue                          |
|--------------------------------|------------------------------------------------|
| Files → chunks → SQL in browser | Zero-backend DuckDB-WASM app (`otp-05`)        |
| Retrieval as a SQL query (VSS) | Analytical SQL in-browser at sub-10ms          |
| Chunk-strategy hit-rate@k eval | Beats-baseline gating, calibration (`otp-03`)  |
| JSONL/Parquet pipeline exports | "Regenerated from a single source" (`otp-08`)  |
| In-browser embeddings via ONNX | ONNX Runtime Web live inference (`otp-05/07`)   |

Same engine (DuckDB) as Off The Pace runs everywhere, including its browser build — so
retrieval is one SQL query, not a new vector-DB dependency.

---

## 3. Architecture (all client-side)

```
┌─────────────────────────── Browser (no server) ───────────────────────────┐
│                                                                            │
│  Upload PDFs/MDs  ──►  Parse  ──►  Chunk (3 strategies)  ──►  Metadata      │
│                        │                                        │          │
│                        ▼                                        ▼          │
│                  pdfjs-dist / MD                        DuckDB-WASM (+ VSS) │
│                  heading tree                    chunks + metadata + vector │
│                                                        │                    │
│                          Retrieval = SQL  ◄────────────┘                    │
│                          (BM25 keyword  OR  array_distance similarity)      │
│                                                        │                    │
│                          Visual explorer  ◄────────────┤                    │
│                          Export (JSONL/CSV/MD/Parquet) ◄┘                   │
└────────────────────────────────────────────────────────────────────────────┘
        │ (optional, downstream — data stays local)
        ▼
   Ollama @ localhost:11434  /  WebLLM in-browser  /  manual paste
```

**Stack:** React + TypeScript + Vite · DuckDB-WASM (+ VSS extension) · `pdfjs-dist`
for PDFs · frontmatter + heading parser for Markdown · (optional) Transformers.js /
ONNX Runtime Web for in-browser embeddings.

---

## 4. The centerpiece — chunking strategies

Build **three** and compare them side-by-side. This is the whole point; do not ship one.

1. **Naive fixed-size window + overlap** — the baseline every tutorial stops at.
2. **Structure-aware** — never split across an H2 in Markdown; paragraph/page-aware for
   PDFs; carry the heading path as metadata.
3. **Semantic (stretch)** — break at embedding-similarity valleys instead of fixed size.

For each strategy, surface:
- The chunks themselves
- Quality metrics: avg/median token count, % of chunks that cut a sentence mid-way,
  boundary-respect rate
- A **density heatmap** across the source document (where do chunks cluster vs. sparsely
  cover text)

Let the user pick the winner **for their actual docs**, not from theory.

---

## 5. The eval harness (the discipline that makes it impressive)

Hand-write **10–15 `(question, expected source doc/section)` pairs**. Then measure
**retrieval hit-rate@k** for each chunking strategy. This is the `otp-03` habit —
don't trust the demo, score it against a baseline — applied to retrieval.

Output: a small table showing hit-rate@k per strategy, so "structure-aware beats naive"
is a *measured claim*, not a vibe.

---

## 6. Metadata per chunk

Attach to every chunk (heuristics or a local embedding model, all in-browser):
- `source_file`, `heading_path`, `page`, `token_count`
- Optional: short tl;dr, key entities/terms
- Semantic similarity edges to other chunks → a small knowledge-graph view

Turns "a list of text" into "a queryable structure."

---

## 7. Exports (pipeline-ready, not "copy to clipboard")

- **JSONL** — one chunk + metadata per line, ready for LLM batch inference
- **CSV** — for spreadsheet inspection
- **Markdown** — preserving heading structure
- **Parquet / SQLite** — same formats Off The Pace already uses

---

## 8. Optional downstream LLM (data stays local either way)

Three tiers, in order of purity:
1. **Retrieval only** — return chunks; user pastes them into any LLM. Purest client-side.
2. **Ollama @ localhost** — browser calls `localhost:11434`. Zero-friction once Ollama is
   running; all data stays on the machine (technically a local server call, not pure
   browser).
3. **In-browser LLM (WebLLM)** — pure client-side, but smaller/slower models and heavier
   WASM setup.

A small **Python CLI companion** (stretch) takes the exported JSONL and runs prompt
templates ("summarize", "extract entities", "list prerequisites") against Ollama — makes
the browser app stage 1 of a real RAG workflow.

---

## 9. Test corpus

Point it at **Off The Pace's own `docs/` folder** (199 `.mdx` files, already in the repo)
— immediately useful ("chat with my project's docs"), zero data-sourcing effort.

**Gotcha to bake into testing:** don't only test on clean Markdown, or chunking will look
solved. Include at least one **ugly real-world PDF** — multi-column layout, repeated
headers/footers, a table — because that's what mangles naive text extraction.

---

## 10. Build order

1. **Parse + display** — upload a PDF and an MD, extract text, show it. (No chunking yet.)
2. **Naive chunker + DuckDB-WASM load** — chunk, store rows, query them via SQL.
3. **Structure-aware chunker** — heading tree for MD, page/paragraph for PDF.
4. **Comparison UI + quality metrics + heatmap** — the centerpiece.
5. **Retrieval** — start with BM25 keyword SQL (no model). Then add VSS vector search with
   in-browser embeddings.
6. **Eval harness** — the 10–15 pairs, hit-rate@k table.
7. **Exports** — JSONL first, then the rest.
8. **Stretch** — semantic chunking · knowledge-graph view · Ollama CLI companion · WebLLM.

Phases 1–4 are a complete, demoable artifact on their own. Everything after is depth.

---

## 11. What each peer walks away able to do

- Run analytical SQL fully in the browser (DuckDB-WASM) with no backend
- Make a quality claim *measurable* instead of asserted (hit-rate@k baseline)
- Handle real, messy input (PDFs) rather than only clean demo data
- Produce outputs the *next* tool in a pipeline can consume
- (Stretch) run a model client-side via ONNX/WebLLM

The transferable habit — same one behind Off The Pace's leakage audit and reconstruction
check — is **state the test before you build the thing.** Write the hit-rate@k eval
before tuning the chunker.


What impresses me most about your proposal
This sentence:
don't trust the demo, score it against a baseline
That's exactly the kind of engineering mindset hiring managers like to see.
Almost every RAG demo says
"It answered correctly!"
Yours says
"Here's the retrieval hit-rate@5 for three strategies."
That's engineering.
I think you can lean into local AI even more
Right now your plan is
Parse

↓

Chunk

↓

Retrieve

↓

Optional LLM
I'd almost make the LLM feel secondary.
The product becomes
A workbench for designing better context.
That's much more interesting.
If I were hiring
Imagine I open your portfolio.
I see:
Off The Pace
End-to-end data engineering
DuckDB
dbt
XGBoost
ONNX
React
Great.
Then I click
ContextLab
and see
Upload PDFs

↓

Compare chunking algorithms

↓

Run retrieval benchmarks

↓

Measure hit-rate@k

↓

Export JSONL / Parquet

↓

Use with Ollama
Now I'm seeing someone who understands
browser engineering
WASM
information retrieval
evaluation
local AI
systems architecture
That's a broader technical profile than another analytics application.
There's one thing I'd change though
I wouldn't stop at chunking.
I'd build the whole thing around the question
"Why did retrieval succeed?"
Imagine the UI.
Question

↓

Retrieved chunks

↓

Score

↓

Chunk boundaries

↓

Embedding similarity

↓

Ground truth

↓

Hit/Miss explanation
Now you've built something I haven't really seen.
Most RAG tools show answers.
Very few explain retrieval.
Long term
I actually think this could become a family of projects.
Off The Pace
↓
Analytics

ContextLab
↓
Retrieval

Future
↓
ModelLab
Where ModelLab might compare
embedding models
rerankers
quantized local LLMs
prompt templates
latency
memory
All running locally.
That creates a coherent narrative for your portfolio: building privacy-first, browser-native analytical and AI tools.

3. ContextLab → evolves into “Retrieval + Evaluation Engine”
Right now:
upload docs → chunk → embed → evaluate
That’s v0.
ContextLab v1 → Context Intelligence System
(A) Multi-source ingestion
Now accepts:
PDFs
Markdown
Context Bundles (from DataScope)
SQL outputs
structured tables
So it becomes universal:
anything → chunks
(B) Chunking is now plugin-based
Instead of 3 hardcoded methods:
structural chunker
semantic chunker
table-aware chunker (NEW, important)
Example:
Source	Chunk strategy
PDF	layout-aware
Markdown	heading tree
SQL output	row-group + semantic summarization
DataScope bundle	schema-aware chunking
(C) Retrieval engine (hybrid)
You now have:
BM25 (SQL-based)
vector search (optional)
metadata filters
schema-aware filtering
Built on:
DuckDB-Wasm + VSS
(D) Evaluation engine becomes core product
Not optional anymore.
You track:
hit-rate@k
precision@k
chunk boundary quality
semantic drift
retrieval latency
This becomes the “truth layer” of the system.
(E) Context understanding layer (new)
This is key:
ContextLab now understands:
“this chunk came from a transformation”
“this chunk is derived from SQL”
“this is a computed metric vs raw text”
So retrieval becomes:
“find derived knowledge, not just text”
ContextLab becomes:
A system for turning structured knowledge into high-quality retrieval context
4. The glue: Context Bundle (VERY IMPORTANT)
This is what makes the ecosystem real.
Context Bundle v1 structure:
/context/
    schema.json
    raw/
        table.parquet
    derived/
        features.parquet
    sql/
        queries.sql
    insights/
        insights.json
    metadata/
        profile.json
    charts/
        charts.json
Why this matters
This means:
DataScope = writer of knowledge
ContextLab = reader + evaluator of knowledge
They never tightly couple.
Any future tool can join the ecosystem.
5. The real unlock: in-browser transforms
This is where your intuition is correct.
When transforms happen in-browser:
You gain:
1. No backend dependency
everything is local
privacy-first
zero infrastructure
2. Computation becomes interactive
instant SQL
instant feature engineering
live iteration loop
3. Context becomes “manufactured”, not extracted
Instead of:
raw file → chunk
You now have:
raw file → transformations → structured knowledge → chunked intelligence
That’s a completely different pipeline.
4. LLM becomes optional, not central
This is huge.
Most RAG systems:
depend on LLM
Yours:
LLM consumes output, it does not define pipeline
That’s architecturally stronger.