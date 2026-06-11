"""Retrieval-quality evaluation for the knowledge base.

Scores three retrieval strategies — dense (sqlite-vec), sparse (FTS5 BM25), and the
hybrid RRF fusion the app actually uses — on the gold set, reporting Hit@k and MRR.
The point is twofold: (1) prove the retriever is good, and (2) show *why* hybrid was
chosen by putting it next to each half on the same questions.

Run:  python -m eval.rag_eval            # prints a markdown table
      python -m eval.rag_eval --write    # also writes eval/RESULTS.md

Deterministic and API-key-free (retrieval only). Answer faithfulness — does the
generated answer stay within the cited sources — needs an LLM judge and is a
documented extension, not run here so the harness stays free and CI-friendly.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.gold import GOLD  # noqa: E402
from meal_planner.rag import retriever, store  # noqa: E402

_K_VALUES = (1, 3, 5)
_POOL = 20  # candidate depth per retriever before scoring


def _ranked_chunks(conn, method: str, query: str) -> list[int]:
    """Ranked chunk ids (best first) for a method."""
    if method == "dense":
        return retriever._dense(conn, query, _POOL)
    if method == "sparse":
        return retriever._sparse(conn, query, _POOL)
    # hybrid: the production retriever, in fused order
    return [h.chunk_id for h in retriever.retrieve(query, k=_POOL, pool=_POOL, conn=conn)]


def _first_relevant_rank(
    ranked: list[int], relevant: set[tuple], id2meta: dict[int, tuple]
) -> int | None:
    for i, cid in enumerate(ranked, start=1):
        if id2meta.get(cid) in relevant:
            return i
    return None


def run_eval() -> dict[str, dict[str, float]]:
    """Return {method: {metric: score}} averaged over the gold set.

    Scored at (source_id, section) granularity — the section a chunk belongs to,
    which is what actually gets retrieved into the prompt.
    """
    conn = store.connect()
    id2meta = {
        r["id"]: (r["source_id"], r["section"])
        for r in conn.execute("SELECT id, source_id, section FROM chunks")
    }

    methods = ("dense", "sparse", "hybrid")
    results: dict[str, dict[str, float]] = {}

    for method in methods:
        hits_at = {k: 0 for k in _K_VALUES}
        rr_sum = 0.0
        for item in GOLD:
            ranked = _ranked_chunks(conn, method, item["q"])
            rank = _first_relevant_rank(ranked, item["relevant"], id2meta)
            if rank is not None:
                rr_sum += 1.0 / rank
                for k in _K_VALUES:
                    if rank <= k:
                        hits_at[k] += 1
        n = len(GOLD)
        scores = {f"Hit@{k}": hits_at[k] / n for k in _K_VALUES}
        scores["MRR"] = rr_sum / n
        results[method] = scores

    conn.close()
    return results


def format_markdown(results: dict[str, dict[str, float]]) -> str:
    metrics = [f"Hit@{k}" for k in _K_VALUES] + ["MRR"]
    labels = {"dense": "Dense (sqlite-vec)", "sparse": "Sparse (BM25)", "hybrid": "**Hybrid (RRF)**"}
    lines = [
        f"# Retrieval evaluation ({len(GOLD)} gold questions)",
        "",
        "| Method | " + " | ".join(metrics) + " |",
        "|" + "---|" * (len(metrics) + 1),
    ]
    for method in ("dense", "sparse", "hybrid"):
        cells = [f"{results[method][m]:.3f}" for m in metrics]
        lines.append(f"| {labels[method]} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append(
        "Scored at (document, section) granularity — the chunk that feeds the prompt. "
        "Hit@k = share of questions with a correct chunk in the top k; "
        "MRR = mean reciprocal rank of the first correct chunk."
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    results = run_eval()
    table = format_markdown(results)
    print(table)
    if "--write" in argv:
        out = Path(__file__).resolve().parent / "RESULTS.md"
        out.write_text(table + "\n", encoding="utf-8")
        print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
