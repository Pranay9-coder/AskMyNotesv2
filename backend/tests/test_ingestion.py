"""
Tests — ingestion service.
Covers: text normalisation, chunking, page metadata, file content hash.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.services.ingestion import (
    RawChunk,
    chunk_pages,
    extract_pages,
    file_content_hash,
    normalise_text,
    PageText,
)


# ── Normalisation ─────────────────────────────────────────────

def test_normalise_strips_control_chars():
    dirty = "Hello\x00World\x0bTest"
    result = normalise_text(dirty)
    assert "\x00" not in result
    assert "\x0b" not in result
    assert "Hello" in result


def test_normalise_collapses_whitespace():
    result = normalise_text("a   b\t\tc")
    assert "  " not in result
    assert "a b c" == result


def test_normalise_collapses_extra_newlines():
    result = normalise_text("a\n\n\n\nb")
    assert result.count("\n") <= 2


# ── Chunking ──────────────────────────────────────────────────

def test_chunk_empty_pages():
    assert chunk_pages([]) == []


def test_chunk_single_short_page():
    pages = [PageText(page_number=1, text="Short text that should fit in one chunk.")]
    chunks = chunk_pages(pages)
    assert len(chunks) >= 1
    assert all(isinstance(c, RawChunk) for c in chunks)


def test_chunk_page_metadata():
    """Each chunk must carry valid page_start and page_end."""
    pages = [
        PageText(page_number=1, text="Page one content. " * 50),
        PageText(page_number=2, text="Page two content. " * 50),
    ]
    chunks = chunk_pages(pages)
    for c in chunks:
        assert c.page_start >= 1
        assert c.page_end >= c.page_start


def test_chunk_token_count_positive():
    pages = [PageText(page_number=1, text="Token count must be positive. " * 20)]
    chunks = chunk_pages(pages)
    for c in chunks:
        assert c.token_count > 0


def test_chunk_respects_max_limit(monkeypatch):
    """chunk_pages should stop at MAX_CHUNKS_PER_FILE."""
    from app.core import config
    monkeypatch.setattr(config.settings, "max_chunks_per_file", 3)
    pages = [PageText(page_number=i, text="x " * 2000) for i in range(1, 11)]
    chunks = chunk_pages(pages)
    assert len(chunks) <= 3


# ── TXT extraction ────────────────────────────────────────────

def test_extract_txt_file():
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False, encoding="utf-8") as f:
        f.write("Hello world. This is a test note.\nSecond line here.")
        tmp = Path(f.name)
    try:
        pages = extract_pages(tmp)
        assert len(pages) == 1
        assert "Hello world" in pages[0].text
    finally:
        tmp.unlink()


def test_extract_unsupported_type():
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        tmp = Path(f.name)
    try:
        with pytest.raises(ValueError, match="Unsupported"):
            extract_pages(tmp)
    finally:
        tmp.unlink()


# ── Content hash ──────────────────────────────────────────────

def test_content_hash_deterministic():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"deterministic content")
        tmp = Path(f.name)
    try:
        h1 = file_content_hash(tmp)
        h2 = file_content_hash(tmp)
        assert h1 == h2
        assert len(h1) == 64  # sha256 hex
    finally:
        tmp.unlink()


def test_content_hash_differs_for_different_content():
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False) as f1, tempfile.NamedTemporaryFile(delete=False) as f2:
        f1.write(b"content A")
        f2.write(b"content B")
        p1, p2 = Path(f1.name), Path(f2.name)
    try:
        assert file_content_hash(p1) != file_content_hash(p2)
    finally:
        p1.unlink()
        p2.unlink()
