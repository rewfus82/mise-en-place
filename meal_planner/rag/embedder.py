"""In-process query/document embeddings via a small static model.

model2vec "potion-base-8M" produces 256-dim float32 vectors with no neural
inference at query time (static token embeddings + pooling), so it costs a few
megabytes of RAM and sub-millisecond CPU — the only embedding approach that fits
a 512MB free-tier box while staying API-key-free.

The model is loaded once (lru_cache). Set RAG_EMBED_MODEL_PATH to a vendored local
copy to avoid a Hugging Face download on cold start (preferred for deploys).
"""
from __future__ import annotations

import functools
import os

import numpy as np

# potion-base-8M is fixed at 256 dims; the sqlite-vec table is declared with this.
EMBED_DIM = 256

_MODEL_NAME = os.getenv("RAG_EMBED_MODEL", "minishlab/potion-base-8M")


@functools.lru_cache(maxsize=1)
def _model():
    from model2vec import StaticModel

    # A vendored local path wins so production never reaches out to HF at runtime.
    local = os.getenv("RAG_EMBED_MODEL_PATH")
    return StaticModel.from_pretrained(local or _MODEL_NAME)


def embed(texts: list[str]) -> np.ndarray:
    """Embed a list of strings -> (n, EMBED_DIM) float32 array."""
    if not texts:
        return np.empty((0, EMBED_DIM), dtype=np.float32)
    vecs = _model().encode(list(texts))
    return np.asarray(vecs, dtype=np.float32)


def embed_one(text: str) -> np.ndarray:
    """Embed a single string -> (EMBED_DIM,) float32 array."""
    return embed([text])[0]
