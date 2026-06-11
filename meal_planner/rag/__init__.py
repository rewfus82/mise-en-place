"""Local, provider-independent retrieval layer for grounded nutrition answers.

The whole RAG stack runs without any API key: query embeddings come from a small
static model (model2vec) that runs in-process, and retrieval is plain SQLite
(sqlite-vec for dense KNN + FTS5 for BM25). Only the *final answer generation*
uses the visitor's BYOK key — so retrieval is free, fast, and works regardless of
which LLM provider the visitor brought.
"""
