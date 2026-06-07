# Mise-en-Place — Model Handoff Document

## Project Overview

React + FastAPI + LangGraph meal planning app for athletes/bodybuilders.
**Stack:** Vite/React/TypeScript frontend, FastAPI backend, LangGraph multi-agent planner, SQLite DBs.

> **Session 2026-06-07 (cont.) summary** — fixed a batch of UX/correctness bugs and added features.
> Tests: `python -m pytest tests/ -q` (87 pass) · `cd frontend && npm test` (11) · `cd frontend && npx tsc --noEmit`.
>
> - **Planning speed**: per-day parallel generation (`meal_planner_node`), 70s→33s for 7 days. Bulk prep still uses one coordinated call.
> - **Grocery list rewrite**: was reading units from the wrong column + exact-name matching. New shared `backend/services/food_units.py` (parse fractions, `unit` column, fuzzy name match); owned items now suppressed.
> - **Pantry depletion** (`pantry_service.compute_depletion`): same unit bug + it wrote `UPDATE pantry` to the wrong DB (calendar.db). Fixed via shared helpers + new `pantry_server.update_quantity`.
> - **Recipe instructions**: new `instructions` field end-to-end (`_Meal` schema, prompt, `day_meals.instructions` column + migration in `database.py`, `_persist_plan`, `DayMealOut`, `DayMeal` type, MealRow renders numbered steps).
> - **MealRow**: expanded view now shows full name + description + steps + ingredients (was truncated).
> - **Calendar selection**: planned days no longer selectable for a new plan (DayCell + CalendarView).
> - **Delete/skip day were broken**: frontend hit `/days/{date}` but routes live at `/calendar/{date}`. Fixed in `api/calendar.ts`.
> - **Regenerate a day**: `POST /plan/day` (`planning_service.regenerate_day`) + button in DayPanel.
> - **Diagnostics**: `/health/detailed`, logging, ErrorBoundary (from earlier in session).
>
> Known/remaining: cross-day meal repetition in parallel gen; review panel (PlanSidePanel) still shows a summarized preview (full recipes visible after saving); `datetime.utcnow()` + FastAPI `on_event` deprecations; `_range_locks` grows unbounded.

```
mise-en-place/
├── backend/              ← FastAPI (main.py, routers/, services/, schemas/, database.py)
├── frontend/src/         ← React (components/calendar/, components/profile/, pages/, api/, types/)
├── meal_planner/         ← LangGraph agents (agents/, graph.py, state.py)
├── data/                 ← SQLite: calendar.db, pantry.db, checkpoints.db
```

---

## Critical Bug — ✅ RESOLVED (2026-06-07)

Both `_run_sync` loops fixed (iterate `chunk.items()` instead of unpacking the dict as a
tuple), stream exceptions now forwarded to the frontend, `__interrupt__` chunk filtered.
Verified end-to-end with a live 2-day plan (6 meals, paused at review) and a revision
resume (day 1 correctly made vegetarian). Root cause confirmed below.

**Symptom:** Planning always fails with: "The AI returned 0 day(s) with 0 meals — the structured output may have failed."

**Root cause identified:** `backend/services/planning_service.py` — both `_run_sync` closures (in `stream_plan` and `resume_plan`) iterate the LangGraph stream like this:

```python
for node_name, state_update in graph.stream(initial_state, config, stream_mode="updates"):
```

In LangGraph 0.2+, `stream_mode="updates"` yields **dicts** like `{"node_name": update_dict}`, NOT tuples. Unpacking a single-key dict as a 2-tuple throws `ValueError: not enough values to unpack` immediately. The exception is caught silently, no nodes run, `planned_days` stays `[]`, but `snapshot.next` is truthy (from the initial checkpoint) → the guard triggers the error message.

**Fix:** Change BOTH `_run_sync` functions (lines ~176 and ~247) from:

```python
for node_name, state_update in graph.stream(..., stream_mode="updates"):
    msg = ""
    if "messages" in state_update:
```

To:

```python
for chunk in graph.stream(..., stream_mode="updates"):
    for node_name, state_update in chunk.items():
        msg = ""
        if "messages" in state_update:
```

Apply this fix in both the `stream_plan` function AND the `resume_plan` function. The indentation of the body stays the same — just wrap in the extra `for ... in chunk.items()`.

Also: the `Field(min_length=1)` added to `_DayPlan.meals` in `meal_planner/agents/meal_planner.py` line 84 is correct and should stay — it enforces the LLM returns at least one meal per day.

---

## What Was Built (Recent Session Work)

All of these changes are already in the codebase — they were implemented but the stream bug above prevented testing them:

### Auto-save profile forms
- `frontend/src/components/profile/ProfileForm.tsx` — debounced auto-save (600ms text, instant selects), `pendingRef` batching, spinner/checkmark status indicator, `useEffect` uses specific primitive deps (not `profile` object) to avoid resetting on background refetch
- `frontend/src/components/profile/MacroTargets.tsx` — same pattern, 700ms debounce, lock/unlock carbs/fat override preserved

### Weight logging + Measured TDEE
- `backend/database.py` — added `weight_log` table (id, date UNIQUE, weight_kg, notes) with index
- `backend/schemas/weight_log.py` — `WeightEntryOut`, `WeightEntryIn`, `MeasuredTdeeOut` schemas
- `backend/routers/weight_log.py` — GET list, POST upsert (INSERT OR REPLACE), DELETE by date, GET /measured-tdee (formula: `avg_calories - (weight_change_kg * 7700 / days)`, requires 2+ weigh-ins 7+ days apart and 7+ tracked meal days)
- `backend/main.py` — weight_log router included at `/weight-log`
- `frontend/src/types/index.ts` — `WeightEntry` and `MeasuredTdee` interfaces added
- `frontend/src/api/weightLog.ts` — `weightLogApi.list()`, `.upsert()`, `.remove()`, `.getMeasuredTdee()`
- `frontend/src/components/profile/TdeeWidget.tsx` — queries measured-tdee, shows "Measured Maintenance" (emerald) when available vs "Estimated", expandable detail panel
- `frontend/src/pages/CalendarPage.tsx` — fetches `['weight-log']`, builds `weightByDate: Map<string, number>`, passes to CalendarView

### Historical calendar
- `frontend/src/components/calendar/CalendarView.tsx` — `isViewable = date <= today`, past dates open DayPanel even when empty, `weightByDate` prop passed to each DayCell
- `frontend/src/components/calendar/DayCell.tsx` — `weightKg?: number` prop, weight badge bottom-right, past cells clickable
- `frontend/src/components/calendar/DayPanel.tsx` — weight log section (inline input → 700ms debounce → upsert), read-only mode for completed/skipped days, `day?` is now optional

### Planning UX improvements
- `frontend/src/components/calendar/PlanSidePanel.tsx` — terminal-style activity stream (macOS dots, scrollable, blinking cursor), "Plan ready — review before saving" banner, committing spinner step, error handling (redirects back to config step on error)
- `meal_planner/state.py` — added `special_requests: str` field
- `backend/services/planning_service.py` — `_build_initial_state` forwards `special_requests`, guard sends `{"type":"error"}` when `planned_days` empty or `total_meals == 0`
- `meal_planner/agents/meal_planner.py` — `special_requests_section` wired into prompt, `Field(min_length=1)` on `_DayPlan.meals`

### Goal recalculation bug fix
- `backend/routers/profile.py` — removed `if not merged.get("calorie_target"):` guard; now always recalculates all four targets when body metrics or goal change

---

## Pending Work

### 1. Fix the stream bug — ✅ DONE
File: `backend/services/planning_service.py`. Both functions fixed and verified.

### 2. Testing — ✅ DONE (61 tests, all green)

**Backend (50):** `python -m pytest tests/ -q`
- `tests/test_tdee_service.py` — 21 tests, `calculate_tdee` / `recommended_macros` / `suggest_meals_per_day`
- `tests/test_nutrition_node.py` — 7 tests, pure-Python macro aggregation
- `tests/test_routers.py` — 15 TestClient integration tests (profile, weight-log, measured-TDEE edge cases, diagnostics)
- `tests/test_meal_planner_node.py` — 7 tests, mocked LLM (structured-output parsing, special_requests/feedback wiring, full graph flow → interrupt). Regression guard for the stream bug.
- `tests/conftest.py` — `client` fixture (temp calendar.db via monkeypatched `_DB_PATH`) + `seed_eaten_day` helper.
- Note: `pytest-asyncio` turned out unnecessary — Starlette's `TestClient` is sync and drives the async SSE routes fine. The `asyncio_mode` config warning is harmless.

**Frontend (11):** `cd frontend && npm test` (Vitest)
- `frontend/src/lib/units.ts` — extracted the duplicated inline helpers (`kgToLbs`, `lbsToKg`, `cmToFtIn`, `ftInToCm`, `deriveCarbsFat`) into one shared module; refactored ProfileForm, MacroTargets, DayPanel, DayCell to import them.
- `frontend/src/lib/units.test.ts` — 11 tests covering conversions, round-trips, and the macro formula.

### 3. Diagnostics / observability — ✅ DONE
- `backend/routers/diagnostics.py` — `GET /health` (fast liveness) + `GET /health/detailed` (DB tables, checkpoints DB, graph compile + nodes, API-key presence, langgraph version).
- `backend/main.py` — `logging.basicConfig` (level via `LOG_LEVEL` env).
- `backend/services/planning_service.py` — `logger.exception(...)` in both `_run_sync` except blocks; the `_stream_done` `exc` is now forwarded to the frontend as `{"type": "error", "message": ...}` instead of being swallowed.
- `frontend/src/components/ErrorBoundary.tsx` — app-level error boundary (wraps the tree in App.tsx) with an actionable reload screen showing the error detail.

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `backend/services/planning_service.py` | **Bug is here** — stream iteration, `stream_plan`, `resume_plan` |
| `backend/services/tdee_service.py` | TDEE formula, macro recommendations |
| `backend/routers/profile.py` | Profile CRUD, TDEE recalc on save |
| `backend/routers/weight_log.py` | Weight entries, measured TDEE endpoint |
| `backend/database.py` | SQLite init, schema |
| `meal_planner/agents/meal_planner.py` | LLM structured output, `_DayPlan`, `_RangePlan` |
| `meal_planner/graph.py` | LangGraph graph builder |
| `meal_planner/state.py` | `RangePlanState` TypedDict |
| `frontend/src/api/weightLog.ts` | Weight log API client |
| `frontend/src/components/calendar/PlanSidePanel.tsx` | Planning flow UI, SSE consumer |
| `frontend/src/components/profile/ProfileForm.tsx` | Auto-save profile |
| `frontend/src/components/profile/MacroTargets.tsx` | Auto-save macros |
| `frontend/src/components/profile/TdeeWidget.tsx` | TDEE + measured maintenance display |

---

## Running the App

```bash
# Backend
cd C:\Users\rewfu\repos\mise-en-place
uvicorn backend.main:app --reload

# Frontend (separate terminal)
cd frontend
npm run dev
```

Backend: http://localhost:8000  
Frontend: http://localhost:5173

---

## Context

User: Ryan McLaughlin, SWE II at Paychex, ~5yr full-stack, ~4mo production LangGraph. Building this as a public AI portfolio project to target senior AI eng roles. Prefers terse responses; no trailing summaries.
