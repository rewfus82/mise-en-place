"""Structure-aware chunking for the knowledge base.

Source documents are markdown with a YAML-ish frontmatter block carrying citation
metadata. Chunking is section-aware: we split on `##` headings so every chunk
keeps a meaningful section anchor for citation, then sliding-window within long
sections so no chunk blows past the embedding model's useful context.

A tiny hand-rolled frontmatter parser avoids adding a PyYAML dependency for what
is only flat `key: value` metadata.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Citation fields carried from frontmatter onto every chunk of a document.
_META_KEYS = ("id", "title", "authors", "year", "journal", "doi", "url", "license")

_TARGET_WORDS = 180   # ~240 tokens, comfortable for potion + a focused passage
_OVERLAP_WORDS = 40   # carry context across a window boundary


@dataclass
class Chunk:
    source_id: str
    section: str
    ord: int
    text: str
    meta: dict = field(default_factory=dict)


def parse_frontmatter(raw: str) -> tuple[dict, str]:
    """Split a `---`-delimited frontmatter block from the markdown body.

    Returns (meta, body). Values are stripped of surrounding quotes; `year` is
    coerced to int when numeric. Missing frontmatter -> ({}, raw).
    """
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", raw, re.DOTALL)
    if not m:
        return {}, raw
    block, body = m.group(1), m.group(2)
    meta: dict = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key == "year" and val.isdigit():
            meta[key] = int(val)
        else:
            meta[key] = val
    return meta, body


def _split_sections(body: str) -> list[tuple[str, str]]:
    """Split body into (section_title, section_text) on `##`/`#` headings."""
    sections: list[tuple[str, str]] = []
    current_title = "Overview"
    buf: list[str] = []

    def flush():
        text = "\n".join(buf).strip()
        if text:
            sections.append((current_title, text))

    for line in body.splitlines():
        heading = re.match(r"^#{1,3}\s+(.*)$", line)
        if heading:
            flush()
            current_title = heading.group(1).strip()
            buf = []
        else:
            buf.append(line)
    flush()
    return sections or [("Overview", body.strip())]


def _window(words: list[str]) -> list[str]:
    """Sliding window over a word list with overlap; one window if it fits."""
    if len(words) <= _TARGET_WORDS:
        return [" ".join(words)] if words else []
    step = _TARGET_WORDS - _OVERLAP_WORDS
    out = []
    for start in range(0, len(words), step):
        piece = words[start : start + _TARGET_WORDS]
        if piece:
            out.append(" ".join(piece))
        if start + _TARGET_WORDS >= len(words):
            break
    return out


def chunk_document(raw: str, *, fallback_id: str = "") -> list[Chunk]:
    """Parse one source document into citation-tagged chunks."""
    meta, body = parse_frontmatter(raw)
    source_id = meta.get("id") or fallback_id
    citation = {k: meta.get(k) for k in _META_KEYS}

    chunks: list[Chunk] = []
    ordinal = 0
    for section_title, section_text in _split_sections(body):
        for window in _window(section_text.split()):
            chunks.append(
                Chunk(
                    source_id=source_id,
                    section=section_title,
                    ord=ordinal,
                    text=window,
                    meta=citation,
                )
            )
            ordinal += 1
    return chunks
