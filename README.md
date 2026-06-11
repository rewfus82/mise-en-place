# mise-en-place

An AI meal planner for athletes and bodybuilders. Set a goal and your body
metrics, and it computes your TDEE and macro targets, then a **multi-agent
LangGraph system** generates a multi-day meal plan you review and approve before
it lands on a rolling calendar. As you log what you eat it depletes your pantry
and computes a grocery deficit list, and it back-calculates your *real*
maintenance calories from logged weight plus actual intake over time. A built-in
**Nutrition Coach** answers questions with cited, evidence-grounded responses, and
the same retrieval grounds the meal plans themselves.

> Built as a demonstration of production-shaped AI engineering: agent
> orchestration, hybrid retrieval (RAG) with an evaluation harness, human-in-the-loop
> control, structured LLM output, streaming, checkpointing, and a custom MCP
> server — not a single-prompt wrapper.

---

## Live demo

**▶ [mise-en-place-rwdy.onrender.com](https://mise-en-place-rwdy.onrender.com)** —
deployed on Render's free tier (first load may take ~30s to wake).
The demo is **BYOK (bring-your-own-key)** and provider-agnostic:
click **Connect AI** in the sidebar and pick **Claude (Anthropic)** or
**ChatGPT (OpenAI)**, then paste a key for that provider. The key is stored only
in your browser and sent only to the demo's backend, which uses it in-memory for
your requests and **never stores or logs it**. (Demo data is shared and resets
periodically.)

---

## Architecture

```
 React + Vite + TS            FastAPI (HTTP + SSE)             LangGraph agents
┌──────────────────┐  /api   ┌─────────────────────┐  stream ┌────────────────────────────┐
│ Calendar / Plan  │ ──────▶ │ routers/             │ ──────▶ │ orchestrator (router)        │
│ review / Pantry  │ ◀────── │  profile pantry plan │ ◀────── │   → meal_planner (Claude/GPT)    │
│ Grocery / Profile│  JSON   │  calendar grocery    │  events │   → nutrition (pure Python)  │
└──────────────────┘         │  weight diagnostics  │         │   → human_review (interrupt) │
                             └─────────┬───────────┘         └──────────────┬─────────────┘
                                       │                                     │
                          SQLite: calendar.db                  SqliteSaver checkpoints.db
                          pantry.db (via MCP server)           typed structured output
```

**The planning graph** is a state machine with an orchestrator that routes based
on accumulated state: no plan yet → `meal_planner`; plan but no nutrition →
`nutrition`; both done → `human_review`. The review node calls LangGraph's
`interrupt()` to **pause the graph** and hand control back to the user; the UI
then resumes it with `Command(resume="approve")` (commit to DB) or revision
feedback (re-plan). Graph state survives between the two HTTP requests via a
SQLite checkpointer.

## Retrieval-augmented nutrition (RAG)

A **Nutrition Coach** answers free-text questions ("how much protein per kg to
build muscle?") with **cited answers grounded in peer-reviewed sports-nutrition
literature**, and the same retrieval layer **grounds meal generation** — plans are
built against goal-appropriate evidence and the review panel shows the sources and
a generated rationale for *why* the plan looks the way it does.

```
 question ─▶ hybrid retrieve ─────────────▶ grounded prompt ─▶ LLM (BYOK) ─▶ cited answer (SSE)
              │                                   ▲
              ├─ dense:  sqlite-vec  (KNN) ─┐      │ "answer only from these
              ├─ sparse: FTS5 BM25         ├─ RRF ─┘  numbered sources, cite [n]"
              └─ embed:  model2vec (local, no API key)
```

**Hybrid retrieval, all in SQLite.** Dense vector search (`sqlite-vec`) and BM25
keyword search (FTS5) run against one `knowledge.db`, and their ranked lists are
combined with **Reciprocal Rank Fusion** — which fuses *ranks*, so the incomparable
vector-distance and BM25 scales never have to be reconciled. No separate vector
service.

**Free, provider-independent embeddings.** Query embeddings come from a small
**static** model (`model2vec`, ~30 MB, sub-millisecond CPU) that runs in-process
with **no API key** — so retrieval costs nothing and works regardless of which LLM
the visitor brought. Only the final answer generation uses their BYOK key. The
corpus is embedded offline (`scripts/ingest_kb.py`) and the resulting `knowledge.db`
is committed, so the deployed app needs no ingestion step and no key at startup.

**Grounding = anti-hallucination.** The model is instructed to answer only from the
retrieved sources, cite each claim `[n]`, and refuse when the sources don't cover
the question — so answers are attributable to open-access ISSN position stands
(CC BY), not invented.

**Real-recipe anchors.** A second corpus (`recipes.db`, ~530 dishes from the free
[TheMealDB](https://www.themealdb.com) API) feeds the *same* hybrid retriever: when
generating a plan, the planner pulls real dishes matching each day's
protein/cuisine as inspiration, so meals are varied and grounded in real cooking
rather than invented from scratch (the LLM still sizes portions and estimates
macros). **One retrieval engine, three jobs:** Coach Q&A, evidence grounding, and
recipe selection.

### Retrieval evaluation

A gold set of 23 questions labeled at **(document, section)** granularity — the
chunk that actually feeds the prompt — scores the strategies. Run it with
`python -m eval.rag_eval`; it's deterministic and runs in CI as a regression guard.

| Method | Hit@1 | Hit@3 | Hit@5 | MRR |
|---|---|---|---|---|
| Dense (sqlite-vec) | 0.652 | 0.913 | 0.957 | 0.791 |
| Sparse (BM25) | 0.565 | 0.870 | 0.913 | 0.733 |
| **Hybrid (RRF)** | 0.609 | **0.957** | 0.957 | 0.782 |

The interesting part is the **trade-off**: hybrid gives the best top-3 recall
(fusion rescues questions where dense's #1 is wrong but a relevant chunk sits high
in BM25), while pure dense edges it on Hit@1/MRR (blending the weaker lexical list
can displace a correct top hit). Because the app retrieves **k=5** chunks into the
prompt, Hit@3/@5 matter more than Hit@1 — so hybrid optimizes the metric that
actually affects answer quality. *(Source-level scoring saturated at ~1.0 and
couldn't tell the methods apart, which is why evaluation is done at chunk level.)*

## Key features

- **TDEE-based targets** — Mifflin-St Jeor, or Katch-McArdle when body-fat % is
  known; goal-adjusted calorie/protein/carb/fat recommendations.
- **Multi-agent plan generation** with typed structured output (Pydantic), and
  **per-day parallel generation** to keep multi-day plans fast.
- **Nutrition Coach (RAG)** — cited, streamed answers grounded in sports-nutrition
  literature; the same retrieval also grounds meal plans (with visible sources).
- **Recipe-anchored variety** — real dishes (TheMealDB) seed each day with a
  rotating protein/cuisine/method, and 3-meal days are planned as Breakfast / Lunch
  / Dinner.
- **Multimodal pantry input** — add items by typing, **snapping a photo** (LLM
  vision reads your groceries/fridge/receipt), or **speaking** (Whisper transcribes
  *in your browser* — no key, no upload).
- **Background generation** — plans and single-day regens keep running when you
  navigate away; a global status pill brings you back to review.
- **Human-in-the-loop review** before anything is persisted.
- **Live progress streaming** (SSE) during generation.
- **Custom MCP pantry server** (FastMCP) for inventory CRUD.
- **Pantry depletion + grocery deficit** with unit normalization and fuzzy
  ingredient matching.
- **Measured maintenance** — true TDEE back-calculated from weight trend + logged calories.
- **Recipe instructions, bulk-prep batching, historical calendar, dark/light themes.**

## Engineering highlights

- **Hybrid retrieval + evaluation** — dense (`sqlite-vec`) + BM25 (FTS5) fused with
  RRF, embedded by a local static model (no API key), measured by a committed
  recall@k / MRR harness that runs as a CI regression guard. Chosen the metric
  granularity (chunk-level) that actually discriminates the strategies. The same
  engine serves the Coach, plan grounding, and recipe selection.
- **Multimodal input, one pipeline** — text, image (LLM vision), and audio all feed
  the *same* structured pantry extractor by swapping only the message content.
  Audio transcription runs **fully client-side** (Whisper via transformers.js in a
  Web Worker) — free and provider-agnostic, mirroring the local-embeddings choice.
- **Navigation-proof background jobs** — generation/regeneration state lives in an
  app-level provider that owns the SSE loops, so leaving the page never orphans a
  run; a global pill reflects status and an `AbortController` powers true cancel.
- **Async/sync bridge** — LangGraph's `graph.stream()` is synchronous; it runs in
  a worker thread and feeds an `asyncio.Queue` that the FastAPI SSE handler drains.
- **Latency optimization** — collapsed one large serial generation call into N
  concurrent per-day calls (`ThreadPoolExecutor`), roughly halving wall-clock time
  for a week-long plan, with a documented variety trade-off.
- **Shared food-unit logic** — quantity parsing (incl. fractions), unit
  normalization, and fuzzy name matching live in one module used by both the
  grocery and pantry-depletion services.
- **Testing a nondeterministic system** — the LLM boundary is mocked so the graph
  routing, nutrition aggregation, and persistence are tested deterministically
  (`pytest`), alongside frontend unit tests (`Vitest`).

## Tech stack

| Layer | Tech |
|---|---|
| Frontend | React 19, Vite, TypeScript, Tailwind, TanStack Query, React Router |
| Backend | FastAPI, Uvicorn, Pydantic v2, SSE |
| AI | LangGraph, LangChain, Claude (Anthropic) **or** OpenAI (BYOK), LangSmith tracing |
| Retrieval | sqlite-vec (dense), FTS5 (BM25), RRF fusion, model2vec static embeddings |
| On-device | LLM vision (photo pantry), Whisper via transformers.js (in-browser voice) |
| Tools | FastMCP (custom pantry MCP server), TheMealDB (recipe corpus) |
| Storage | SQLite (calendar, pantry, knowledge base, recipes, LangGraph checkpoints) |
| Tests | pytest, Vitest, retrieval eval harness (recall@k / MRR) |

## Getting started

**Prerequisites:** Python 3.11+, Node 18+, and a Claude (Anthropic) **or** OpenAI
API key — entered in the app, not in a file (BYOK).

```bash
# 1. Backend deps
pip install -e ".[dev]"

# 2. (Optional) Environment — only needed for LangSmith tracing
cp .env.example .env       # LLM keys are NOT read from here (BYOK)

# 2b. (Optional) Rebuild the corpora — knowledge.db and recipes.db are committed,
#     so this is only needed to refresh them (recipes fetches from TheMealDB)
python -m scripts.ingest_kb        # ISSN literature → knowledge.db
python -m scripts.ingest_recipes   # TheMealDB recipes → recipes.db (needs network)

# 3. Run the API (http://localhost:8000)
uvicorn backend.main:app --reload

# 4. Run the frontend (separate terminal, http://localhost:5173)
cd frontend
npm install
npm run dev
```

Then click **Connect AI** in the sidebar and paste your Claude or OpenAI key.
Vite proxies `/api` → `http://localhost:8000`, so the frontend talks to the
backend with no CORS fuss in dev.

## Tests

```bash
pytest -q                       # backend: services, routers, agents (mocked LLM), retrieval
python -m eval.rag_eval         # retrieval quality: recall@k / MRR table
cd frontend && npm test         # frontend: unit tests (Vitest)
```

## Project layout

```
backend/      FastAPI app — routers/ (incl. coach), services/, schemas/, database.py
frontend/     React app — components/, pages/ (incl. CoachPage), api/, hooks/, lib/
meal_planner/ LangGraph agents/, graph.py, state.py, mcp_servers/ (pantry MCP), rag/
data/         kb_sources/ (ISSN markdown) + committed knowledge.db & recipes.db
scripts/      ingest_kb.py (knowledge base) · ingest_recipes.py (TheMealDB)
eval/         retrieval eval harness (gold.py, rag_eval.py) + RESULTS.md
tests/        pytest suite
```

## Diagnostics

`GET /api/health` is a fast liveness probe; `GET /api/health/detailed` reports DB
tables, checkpoint DB, graph compilation, and the LangGraph version.

## Deployment

One Docker image builds the React frontend and serves it from FastAPI on the
**same origin** as the API (the frontend calls a relative `/api`, so there's no
CORS and no second deploy). The included `render.yaml` deploys it to Render's free
tier. Because the demo is **BYOK**, there are **no server-side LLM secrets** to
configure — visitors supply their own keys at runtime.

```bash
docker build -t mise-en-place .
docker run -p 8000:8000 mise-en-place   # http://localhost:8000
```

> Free-tier hosts use an ephemeral filesystem, so the SQLite databases reset on
> restart and are shared across visitors — intentional for a demo sandbox. For
> durable, per-user data use a persistent volume or Postgres.

Model IDs default to current Claude/OpenAI models and are overridable via env
(`ANTHROPIC_PLANNER_MODEL`, `OPENAI_PLANNER_MODEL`, `*_LIGHT_MODEL`).

---

*Built by Ryan McLaughlin.*
