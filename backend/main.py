from dotenv import load_dotenv
load_dotenv()  # Must be first — before any meal_planner imports

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)

from backend.database import create_tables
from backend.routers import (
    calendar,
    diagnostics,
    grocery,
    meals,
    pantry,
    planning,
    profile,
    weight_log,
)
from meal_planner.tracing import setup_tracing

setup_tracing()

app = FastAPI(title="mise-en-place", version="2.0.0")

cors_origins = os.getenv("CORS_ORIGIN", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    create_tables()
    # Pre-warm the LangGraph graph singleton
    from backend.services.planning_service import get_graph
    get_graph()


# All API routes live under /api so the frontend (which calls a relative /api) can
# be served from this same origin in production — no CORS, no second deploy.
app.include_router(profile.router, prefix="/api/profile")
app.include_router(pantry.router, prefix="/api/pantry")
app.include_router(calendar.router, prefix="/api/calendar")
app.include_router(meals.router, prefix="/api/days")
app.include_router(grocery.router, prefix="/api/grocery")
app.include_router(planning.router, prefix="/api/plan")
app.include_router(weight_log.router, prefix="/api/weight-log")
app.include_router(diagnostics.router, prefix="/api")


# ---- Serve the built React app (same-origin SPA) ----
# In production the multi-stage Docker build drops the Vite output at frontend/dist.
# In local dev this dir won't exist (Vite serves the app), so we skip it.
_DIST = Path(
    os.getenv("FRONTEND_DIST", str(Path(__file__).resolve().parent.parent / "frontend" / "dist"))
)

if _DIST.is_dir():
    _assets = _DIST / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        # API routes are registered above and match first. Anything else is a
        # client-side route (BrowserRouter) → serve the SPA entry, or a real file.
        if full_path.startswith("api/"):
            return FileResponse(_DIST / "index.html", status_code=404)
        candidate = _DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")
