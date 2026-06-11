"""Tests for evidence grounding of meal generation."""
from meal_planner.rag import guidance
from meal_planner.rag.guidance import _query, guideline_block, plan_rationale
from meal_planner.rag.retriever import RetrievedChunk


def test_query_reflects_goal_and_protein():
    q = _query("cut", 180)
    assert "deficit" in q
    assert "180" in q


def test_query_unknown_goal_falls_back_to_maintain():
    assert _query("", 150) == _query("maintain", 150)


def test_guideline_block_against_real_kb():
    block, sources = guideline_block("bulk", 190)
    assert block.startswith("Evidence-based guidelines")
    assert sources                       # at least one citation
    assert "[" in block and "]" in block  # inline citations present


def test_guideline_block_dedupes_sources(monkeypatch):
    dup = RetrievedChunk(
        chunk_id=1, source_id="s", title="t", authors="Jager R, Smith A",
        year=2017, journal="JISSN", doi="d", url="u", license="l",
        section="sec", text="some guidance", score=0.5,
    )
    monkeypatch.setattr(guidance, "retrieve", lambda *a, **k: [dup, dup])
    _block, sources = guideline_block("cut", 170)
    assert sources == [  # collapsed to one
        {"citation": "Jager R, et al. (2017)", "title": "t", "url": "u"}
    ]


def test_guideline_block_empty_when_no_hits(monkeypatch):
    monkeypatch.setattr(guidance, "retrieve", lambda *a, **k: [])
    assert guideline_block("cut", 170) == ("", [])


def test_guideline_block_degrades_on_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("kb unavailable")

    monkeypatch.setattr(guidance, "retrieve", boom)
    assert guideline_block("cut", 170) == ("", [])


# --- plan_rationale (grounded "why this plan" summary) ---

class _Resp:
    def __init__(self, content):
        self.content = content


class _FakeLLM:
    def __init__(self, content):
        self._content = content

    def invoke(self, _messages):
        return _Resp(self._content)


def test_plan_rationale_generates_summary(monkeypatch):
    monkeypatch.setattr(guidance, "make_llm", lambda *a, **k: _FakeLLM("Higher protein preserves muscle while cutting."))
    out = plan_rationale("cut", 180, 2000, "Evidence: protein 2.3-3.1 g/kg.", "anthropic", "sk-ant-x")
    assert out == "Higher protein preserves muscle while cutting."


def test_plan_rationale_coerces_anthropic_blocks(monkeypatch):
    monkeypatch.setattr(
        guidance, "make_llm",
        lambda *a, **k: _FakeLLM([{"type": "text", "text": "Eat more protein."}]),
    )
    out = plan_rationale("bulk", 190, 3000, "Evidence here.", "anthropic", "sk-ant-x")
    assert out == "Eat more protein."


def test_plan_rationale_empty_without_evidence():
    assert plan_rationale("cut", 180, 2000, "", "anthropic", "sk-ant-x") == ""


def test_plan_rationale_empty_without_creds():
    assert plan_rationale("cut", 180, 2000, "Evidence.", "", "") == ""


def test_plan_rationale_degrades_on_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("llm down")

    monkeypatch.setattr(guidance, "make_llm", boom)
    assert plan_rationale("cut", 180, 2000, "Evidence.", "anthropic", "sk-ant-x") == ""
