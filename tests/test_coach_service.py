"""Tests for the Nutrition Coach service with a mocked LLM and retrieval.

The LLM boundary is faked (no API calls): we patch coach_service.make_llm to return
a fake whose .astream yields message chunks, and patch coach_service.retrieve to
control the grounded context.
"""
import json

import pytest

from backend.services import coach_service
from meal_planner.rag.retriever import RetrievedChunk


def _chunk(source_id="protein-doc", section="Daily protein intake"):
    return RetrievedChunk(
        chunk_id=1,
        source_id=source_id,
        title="Protein Stand",
        authors="Jager R, Smith A",
        year=2017,
        journal="JISSN",
        doi="10.0/x",
        url="https://example.org",
        license="CC BY 4.0",
        section=section,
        text="1.4 to 2.0 grams of protein per kilogram of body weight per day.",
        score=0.5,
    )


class _FakeChunk:
    def __init__(self, content):
        self.content = content


class _FakeLLM:
    """Stands in for a LangChain chat model; .astream yields message chunks."""

    def __init__(self, contents):
        self._contents = contents

    async def astream(self, _messages):
        for c in self._contents:
            yield _FakeChunk(c)


async def _drain(gen):
    """Collect SSE strings from an async generator into parsed event dicts."""
    events = []
    async for sse in gen:
        assert sse.startswith("data: ") and sse.endswith("\n\n")
        events.append(json.loads(sse[6:].strip()))
    return events


@pytest.fixture
def patch_llm(monkeypatch):
    def _install(contents):
        monkeypatch.setattr(coach_service, "make_llm", lambda *a, **k: _FakeLLM(contents))

    return _install


async def test_happy_path_streams_sources_then_tokens(monkeypatch, patch_llm):
    monkeypatch.setattr(coach_service, "retrieve", lambda *a, **k: [_chunk()])
    patch_llm(["Aim for ", "1.6 g/kg [1]."])

    events = await _drain(coach_service.ask_stream("how much protein?", "anthropic", "sk-ant-x"))

    types = [e["type"] for e in events]
    assert types[0] == "sources"
    assert types[-1] == "done"
    assert events[0]["sources"][0]["n"] == 1
    assert events[0]["sources"][0]["citation"] == "Jager R, et al. (2017)"
    answer = "".join(e["text"] for e in events if e["type"] == "token")
    assert answer == "Aim for 1.6 g/kg [1]."


async def test_anthropic_block_content_is_coerced(monkeypatch, patch_llm):
    monkeypatch.setattr(coach_service, "retrieve", lambda *a, **k: [_chunk()])
    # Anthropic-style list-of-blocks content.
    patch_llm([[{"type": "text", "text": "Protein "}], [{"type": "text", "text": "matters."}]])

    events = await _drain(coach_service.ask_stream("protein?", "anthropic", "sk-ant-x"))
    answer = "".join(e["text"] for e in events if e["type"] == "token")
    assert answer == "Protein matters."


async def test_missing_key_yields_error(monkeypatch):
    monkeypatch.setattr(coach_service, "retrieve", lambda *a, **k: [_chunk()])
    events = await _drain(coach_service.ask_stream("protein?", "anthropic", ""))
    assert events == [e for e in events if e["type"] == "error"]
    assert "API key" in events[0]["message"]


async def test_unknown_provider_yields_error():
    events = await _drain(coach_service.ask_stream("protein?", "llama", "key"))
    assert events[0]["type"] == "error"


async def test_retrieval_failure_yields_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("knowledge base unavailable")

    monkeypatch.setattr(coach_service, "retrieve", boom)
    events = await _drain(coach_service.ask_stream("protein?", "anthropic", "sk-ant-x"))
    assert events == [{"type": "error", "message": events[0]["message"]}]
    assert "unavailable" in events[0]["message"]


async def test_empty_question_yields_error():
    events = await _drain(coach_service.ask_stream("   ", "anthropic", "sk-ant-x"))
    assert events[0]["type"] == "error"


async def test_no_results_gives_graceful_fallback(monkeypatch):
    monkeypatch.setattr(coach_service, "retrieve", lambda *a, **k: [])
    events = await _drain(coach_service.ask_stream("how do I tango?", "anthropic", "sk-ant-x"))
    types = [e["type"] for e in events]
    assert types == ["sources", "token", "done"]
    assert events[0]["sources"] == []
    assert "don't have sourced information" in events[1]["text"]


async def test_generation_error_is_surfaced(monkeypatch):
    monkeypatch.setattr(coach_service, "retrieve", lambda *a, **k: [_chunk()])

    class _Boom:
        async def astream(self, _m):
            raise RuntimeError("provider exploded")
            yield  # pragma: no cover

    monkeypatch.setattr(coach_service, "make_llm", lambda *a, **k: _Boom())
    events = await _drain(coach_service.ask_stream("protein?", "anthropic", "sk-ant-x"))
    assert events[0]["type"] == "sources"
    assert events[-1]["type"] == "error"
    assert "generation failed" in events[-1]["message"].lower()
