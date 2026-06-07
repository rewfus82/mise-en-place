from dotenv import load_dotenv
load_dotenv()  # Must be first — before any meal_planner imports

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


app.include_router(profile.router, prefix="/profile")
app.include_router(pantry.router, prefix="/pantry")
app.include_router(calendar.router, prefix="/calendar")
app.include_router(meals.router, prefix="/days")
app.include_router(grocery.router, prefix="/grocery")
app.include_router(planning.router, prefix="/plan")
app.include_router(weight_log.router, prefix="/weight-log")
app.include_router(diagnostics.router)
