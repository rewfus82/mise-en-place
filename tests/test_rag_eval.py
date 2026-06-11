"""Regression guard on retrieval quality via the eval harness.

Deterministic (local embeddings + committed knowledge.db), so these thresholds are
a real floor: if a chunking/embedding/fusion change degrades retrieval, this fails.
"""
from eval.rag_eval import format_markdown, run_eval


def test_eval_reports_all_methods():
    results = run_eval()
    assert set(results) == {"dense", "sparse", "hybrid"}
    for scores in results.values():
        assert {"Hit@1", "Hit@3", "Hit@5", "MRR"} <= set(scores)


def test_retrieval_quality_floor():
    results = run_eval()
    # Hybrid is what the app uses — hold its top-3 recall and MRR to a floor.
    assert results["hybrid"]["Hit@3"] >= 0.90
    assert results["hybrid"]["MRR"] >= 0.70
    # Dense should clearly beat sparse on this corpus (semantic > lexical here).
    assert results["dense"]["MRR"] > results["sparse"]["MRR"]


def test_format_markdown_has_table():
    table = format_markdown(run_eval())
    assert "| Method |" in table
    assert "Hybrid (RRF)" in table
