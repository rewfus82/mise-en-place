"""Tests for knowledge-base chunking and frontmatter parsing (no model/DB)."""
from meal_planner.rag.chunking import chunk_document, parse_frontmatter

_DOC = """---
id: demo-2020
title: "A Demo Position Stand"
authors: "Smith J, Doe A, Roe B"
year: 2020
doi: "10.0000/demo"
url: "https://example.org/demo"
license: "CC BY 4.0"
---

## First Section

Some introductory content about protein and training adaptations.

## Second Section

More content here about creatine and recovery.
"""


def test_parse_frontmatter_extracts_metadata():
    meta, body = parse_frontmatter(_DOC)
    assert meta["id"] == "demo-2020"
    assert meta["title"] == "A Demo Position Stand"
    assert meta["year"] == 2020  # coerced to int
    assert isinstance(meta["year"], int)
    assert body.strip().startswith("## First Section")


def test_parse_frontmatter_absent():
    meta, body = parse_frontmatter("no frontmatter here")
    assert meta == {}
    assert body == "no frontmatter here"


def test_chunk_document_carries_citation_and_sections():
    chunks = chunk_document(_DOC)
    assert len(chunks) == 2
    sections = {c.section for c in chunks}
    assert sections == {"First Section", "Second Section"}
    for c in chunks:
        assert c.source_id == "demo-2020"
        assert c.meta["doi"] == "10.0000/demo"
        assert c.meta["year"] == 2020
    # Ordinals are unique and sequential.
    assert sorted(c.ord for c in chunks) == [0, 1]


def test_chunk_document_windows_long_sections():
    body = "## Big\n\n" + " ".join(f"word{i}" for i in range(500))
    doc = '---\nid: long\n---\n' + body
    chunks = chunk_document(doc)
    # 500 words at target 180 / overlap 40 (step 140) -> multiple overlapping windows.
    assert len(chunks) >= 3
    assert all(c.section == "Big" for c in chunks)


def test_chunk_document_fallback_id():
    chunks = chunk_document("## S\n\nbody text", fallback_id="from-filename")
    assert chunks[0].source_id == "from-filename"
