"""Tests for hybrid retrieval (dense + sparse + RRF) against a temp knowledge base.

Uses the real static embedder (local, no API key) and a temp SQLite KB built from
inline source docs via the production pipeline, so these are true end-to-end
retrieval tests, not mocks.
"""
import pytest

from meal_planner.rag import store
from meal_planner.rag.chunking import chunk_document
from meal_planner.rag.embedder import embed
from meal_planner.rag.retriever import _fts_query, _rrf, retrieve

_DOCS = [
    """---
id: protein-doc
title: "Protein Stand"
authors: "Jager R, Smith A"
year: 2017
---
## Daily protein intake
For building and maintaining muscle, 1.4 to 2.0 grams of protein per kilogram of
body weight per day is sufficient for most exercising individuals.
""",
    """---
id: creatine-doc
title: "Creatine Stand"
authors: "Kreider R, Jones B"
year: 2017
---
## Dosing
Load with about 20 grams of creatine monohydrate per day for five to seven days,
then maintain with 3 to 5 grams per day.
""",
    """---
id: caffeine-doc
title: "Caffeine Stand"
authors: "Guest N, Lee C"
year: 2021
---
## Dosing and timing
Caffeine improves performance at 3 to 6 milligrams per kilogram of body mass taken
about 60 minutes before exercise.
""",
]


@pytest.fixture
def kb_conn(tmp_path):
    conn = store.connect(tmp_path / "knowledge.db")
    store.reset(conn)
    all_chunks = []
    for doc in _DOCS:
        all_chunks.extend(chunk_document(doc))
    vectors = embed([c.text for c in all_chunks])
    for chunk, vec in zip(all_chunks, vectors):
        store.insert_chunk(conn, chunk, vec)
    conn.commit()
    store.rebuild_fts(conn)
    yield conn
    conn.close()


def test_retrieve_finds_relevant_source(kb_conn):
    results = retrieve("how much protein per kilogram to build muscle?", k=3, conn=kb_conn)
    assert results
    assert results[0].source_id == "protein-doc"


def test_retrieve_keyword_match(kb_conn):
    # Rare exact term — sparse BM25 should pull the right doc to the top.
    results = retrieve("creatine monohydrate loading dose", k=3, conn=kb_conn)
    assert results[0].source_id == "creatine-doc"


def test_results_are_ordered_by_fused_score(kb_conn):
    results = retrieve("caffeine before exercise", k=3, conn=kb_conn)
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)
    assert results[0].source_id == "caffeine-doc"


def test_retrieved_chunk_citation_format(kb_conn):
    results = retrieve("protein intake", k=1, conn=kb_conn)
    cite = results[0].citation()
    assert "Jager R, et al." in cite
    assert "(2017)" in cite


def test_empty_query_returns_empty(kb_conn):
    assert retrieve("", k=3, conn=kb_conn) == []
    assert retrieve("   ", k=3, conn=kb_conn) == []


def test_k_limits_results(kb_conn):
    assert len(retrieve("protein creatine caffeine", k=1, conn=kb_conn)) == 1


# --- pure-function unit tests (no DB) ---

def test_rrf_rewards_agreement():
    # id 2 appears high in both lists -> should win.
    fused = _rrf([[1, 2, 3], [2, 4, 5]])
    ranked = sorted(fused, key=lambda c: fused[c], reverse=True)
    assert ranked[0] == 2


def test_rrf_empty():
    assert _rrf([[], []]) == {}


def test_fts_query_sanitizes_special_chars():
    # Must not produce raw FTS5 operators that would raise a syntax error.
    q = _fts_query("protein? (g/kg): \"timing\" *")
    assert q == '"protein" OR "g" OR "kg" OR "timing"'


def test_fts_query_empty_when_no_word_tokens():
    assert _fts_query("?!*()") == ""
