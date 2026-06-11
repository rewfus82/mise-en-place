# syntax=docker/dockerfile:1

# ---- Stage 1: build the React/Vite frontend to static files ----
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build           # -> /app/frontend/dist

# ---- Stage 2: Python backend that also serves the built frontend ----
FROM python:3.11-slim AS runtime
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FRONTEND_DIST=/app/frontend/dist

# Install Python deps. meal_planner/ must be present for hatchling to build the wheel.
COPY pyproject.toml ./
COPY meal_planner/ ./meal_planner/
RUN pip install .

# App code + built frontend
COPY backend/ ./backend/
COPY --from=frontend /app/frontend/dist ./frontend/dist

# Prebuilt retrieval corpora (committed): the Coach, plan grounding, and recipe
# anchors all read these. Runtime DBs (calendar/pantry/checkpoints) are created in
# this same dir at startup — it's ephemeral on free hosts, fine for a demo.
COPY data/knowledge.db data/recipes.db ./data/

# Bake the local embedding model into the image so retrieval needs no network or
# download at runtime — keeps cold starts fast and reliable on the free tier.
RUN python -c "from model2vec import StaticModel; StaticModel.from_pretrained('minishlab/potion-base-8M').save_pretrained('/app/data/embed-model')"
ENV RAG_EMBED_MODEL_PATH=/app/data/embed-model

EXPOSE 8000
# Hosts inject $PORT; default to 8000 locally.
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
