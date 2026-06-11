"""Nutrition Coach: grounded, cited Q&A over the sports-nutrition knowledge base.

Flow: hybrid-retrieve the most relevant chunks -> build a prompt that forces the
model to answer ONLY from those numbered sources and cite them -> stream the answer
token-by-token over SSE, with the source list emitted up front so the UI can render
citations before the text arrives.

Retrieval is local and free; only the final generation uses the visitor's BYOK key
(`make_llm`). The model is told to refuse when the sources don't cover the question,
which is the whole anti-hallucination point of grounding.
"""
from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from meal_planner.llm import LLMConfigError, coerce_text, make_llm, normalize_provider
from meal_planner.rag.retriever import RetrievedChunk, retrieve

logger = logging.getLogger(__name__)

_TOP_K = 5

_SYSTEM = """You are a sports-nutrition coach for athletes and bodybuilders.

Answer the user's question using ONLY the numbered sources below. Every factual
claim must cite the source it came from, using square brackets like [1] or [2].
Prefer concrete numbers (grams per kilogram, milligrams, timing) when the sources
provide them.

If the sources do not contain the answer, say so plainly and do not answer from
outside knowledge. Never invent facts, numbers, or citations. Keep the answer
concise and practical.

Sources:
{sources}"""


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _source_payload(chunks: list[RetrievedChunk]) -> list[dict]:
    """UI-facing citation list, 1-indexed to match the [n] markers in the prompt."""
    out = []
    for i, c in enumerate(chunks, start=1):
        out.append(
            {
                "n": i,
                "citation": c.citation(),
                "title": c.title,
                "section": c.section,
                "journal": c.journal,
                "url": c.url,
                "doi": c.doi,
                "source_id": c.source_id,
            }
        )
    return out


def _context_block(chunks: list[RetrievedChunk]) -> str:
    """The numbered source block injected into the system prompt."""
    lines = []
    for i, c in enumerate(chunks, start=1):
        header = f"[{i}] ({c.citation()} — {c.section})"
        lines.append(f"{header}\n{c.text}")
    return "\n\n".join(lines)




async def ask_stream(question: str, provider: str, api_key: str):
    """Async generator of SSE strings: sources, then answer tokens, then done."""
    try:
        norm_provider = normalize_provider(provider)
        if not api_key or not api_key.strip():
            raise LLMConfigError("No API key provided for the selected AI provider.")
    except LLMConfigError as exc:
        yield _sse({"type": "error", "message": str(exc)})
        return

    question = (question or "").strip()
    if not question:
        yield _sse({"type": "error", "message": "Ask a nutrition question to get started."})
        return

    chunks = retrieve(question, k=_TOP_K)
    if not chunks:
        yield _sse({"type": "sources", "sources": []})
        yield _sse(
            {
                "type": "token",
                "text": (
                    "I don't have sourced information on that in my nutrition library "
                    "yet. Try asking about protein intake, creatine, caffeine, nutrient "
                    "timing, dieting and body composition, beta-alanine, or meal frequency."
                ),
            }
        )
        yield _sse({"type": "done"})
        return

    yield _sse({"type": "sources", "sources": _source_payload(chunks)})

    messages = [
        SystemMessage(content=_SYSTEM.format(sources=_context_block(chunks))),
        HumanMessage(content=question),
    ]
    llm = make_llm(norm_provider, api_key, role="light")

    try:
        async for part in llm.astream(messages):
            text = coerce_text(part.content)
            if text:
                yield _sse({"type": "token", "text": text})
    except Exception as exc:  # noqa: BLE001 — surface any provider error to the client
        logger.exception("Coach generation failed")
        yield _sse({"type": "error", "message": f"Answer generation failed: {exc}"})
        return

    yield _sse({"type": "done"})
