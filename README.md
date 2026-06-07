# mise-en-place

An AI meal planner for athletes and bodybuilders. Set a goal and your body
metrics, and it computes your TDEE and macro targets, then a **multi-agent
LangGraph system** generates a multi-day meal plan you review and approve before
it lands on a rolling calendar. As you log what you eat it depletes your pantry
and computes a grocery deficit list, and it back-calculates your *real*
maintenance calories from logged weight plus actual intake over time.

> Built as a demonstration of production-shaped AI engineering: agent
> orchestration, human-in-the-loop control, structured LLM output, streaming,
> checkpointing, and a custom MCP server — not a single-prompt wrapper.

---

## Architecture

```
 React + Vite + TS            FastAPI (HTTP + SSE)             LangGraph agents
┌──────────────────┐  /api   ┌─────────────────────┐  stream ┌────────────────────────────┐
│ Calendar / Plan  │ ──────▶ │ routers/             │ ──────▶ │ orchestrator (router)        │
│ review / Pantry  │ ◀────── │  profile pantry plan │ ◀────── │   → meal_planner (Claude)    │
│ Grocery / Profile│  JSON   │  calendar grocery    │  events │   → nutrition (pure Python)  │
└──────────────────┘         │  weight diagnostics  │         │   → human_review (interrupt) │
                             └─────────┬───────────┘         └──────────────┬─────────────┘
                                       │                                     │
                          SQLite: calendar.db                  SqliteSaver checkpoints.db
                          pantry.db (via MCP server)           Claude structured output
```

**The planning graph** is a state machine with an orchestrator that routes based
on accumulated state: no plan yet → `meal_planner`; plan but no nutrition →
`nutrition`; both done → `human_review`. The review node calls LangGraph's
`interrupt()` to **pause the graph** and hand control back to the user; the UI
then resumes it with `Command(resume="approve")` (commit to DB) or revision
feedback (re-plan). Graph state survives between the two HTTP requests via a
SQLite checkpointer.

## Key features

- **TDEE-based targets** — Mifflin-St Jeor, or Katch-McArdle when body-fat % is
  known; goal-adjusted calorie/protein/carb/fat recommendations.
- **Multi-agent plan generation** with typed structured output (Pydantic), and
  **per-day parallel generation** to keep multi-day plans fast.
- **Human-in-the-loop review** before anything is persisted.
- **Live progress streaming** (SSE) during generation.
- **Custom MCP pantry server** (FastMCP) for inventory CRUD.
- **Pantry depletion + grocery deficit** with unit normalization and fuzzy
  ingredient matching.
- **Measured maintenance** — true TDEE back-calculated from weight trend + logged calories.
- **Recipe instructions, bulk-prep batching, historical calendar, dark/light themes.**

## Engineering highlights

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
| AI | LangGraph, LangChain, Claude (Anthropic), LangSmith tracing |
| Tools | FastMCP (custom pantry MCP server) |
| Storage | SQLite (calendar, pantry, LangGraph checkpoints) |
| Tests | pytest, Vitest |

## Getting started

**Prerequisites:** Python 3.11+, Node 18+, an Anthropic API key.

```bash
# 1. Backend deps
pip install -e ".[dev]"

# 2. Environment — copy the example and fill in your key
cp .env.example .env       # then edit ANTHROPIC_API_KEY

# 3. Run the API (http://localhost:8000)
uvicorn backend.main:app --reload

# 4. Run the frontend (separate terminal, http://localhost:5173)
cd frontend
npm install
npm run dev
```

Vite proxies `/api` → `http://localhost:8000`, so the frontend talks to the
backend with no CORS fuss in dev.

## Tests

```bash
pytest -q                       # backend: services, routers, agents (mocked LLM)
cd frontend && npm test         # frontend: unit tests (Vitest)
```

## Project layout

```
backend/      FastAPI app — routers/, services/, schemas/, database.py
frontend/     React app — components/, pages/, api/, hooks/, lib/
meal_planner/ LangGraph agents/, graph.py, state.py, mcp_servers/ (pantry MCP)
data/         SQLite databases (gitignored)
tests/        pytest suite
```

## Diagnostics

`GET /health` is a fast liveness probe; `GET /health/detailed` reports DB tables,
checkpoint DB, graph compilation, API-key presence, and the LangGraph version.

---

*Built by Ryan McLaughlin.*
