"""
Ingestion service — file parsing, chunking, and storage.

Supports:
- PDF via PyMuPDF (primary) / pdfplumber (fallback)
- TXT files
- Tesseract OCR fallback when PDF text is sparse
- tiktoken-aware sliding-window chunking
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path
from typing import NamedTuple
from uuid import uuid4

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Optional imports (graceful degradation) ───────────────────
try:
    import fitz  # PyMuPDF

    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    logger.warning("PyMuPDF not installed — PDF extraction unavailable")

try:
    import pdfplumber

    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    import tiktoken

    HAS_TIKTOKEN = True
    _enc = tiktoken.get_encoding("cl100k_base")
except ImportError:
    HAS_TIKTOKEN = False
    logger.warning("tiktoken not installed — falling back to character-based chunking")


# ── Data structures ───────────────────────────────────────────


class PageText(NamedTuple):
    page_number: int  # 1-based
    text: str


class RawChunk(NamedTuple):
    text: str
    page_start: int
    page_end: int
    token_count: int


# ── Normalisation ─────────────────────────────────────────────

def normalise_text(text: str) -> str:
    """Unicode-normalise, collapse whitespace, strip control chars."""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── PDF extraction ────────────────────────────────────────────

def _extract_with_pymupdf(path: Path) -> list[PageText]:
    doc = fitz.open(str(path))  # type: ignore[attr-defined]
    pages: list[PageText] = []
    for i, page in enumerate(doc, start=1):
        text = page.get_text("text")
        pages.append(PageText(page_number=i, text=normalise_text(text)))
    doc.close()
    return pages


def _extract_with_pdfplumber(path: Path) -> list[PageText]:
    pages: list[PageText] = []
    with pdfplumber.open(str(path)) as pdf:  # type: ignore[attr-defined]
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages.append(PageText(page_number=i, text=normalise_text(text)))
    return pages


def _needs_ocr(pages: list[PageText], min_chars_per_page: int = 50) -> bool:
    if not pages:
        return True
    avg = sum(len(p.text) for p in pages) / len(pages)
    return avg < min_chars_per_page


def extract_pages(path: Path) -> list[PageText]:
    """Return list of (page_number, text) for a PDF or TXT file."""
    suffix = path.suffix.lower()

    if suffix == ".txt":
        text = normalise_text(path.read_text(encoding="utf-8", errors="replace"))
        return [PageText(page_number=1, text=text)]

    if suffix != ".pdf":
        raise ValueError(f"Unsupported file type: {suffix}")

    # Try PyMuPDF first
    if HAS_PYMUPDF:
        try:
            pages = _extract_with_pymupdf(path)
            if not _needs_ocr(pages):
                return pages
            logger.info("PyMuPDF yielded sparse text, trying pdfplumber", extra={"path": str(path)})
        except Exception as exc:
            logger.warning("PyMuPDF extraction failed", extra={"error": str(exc)})

    # Fall back to pdfplumber
    if HAS_PDFPLUMBER:
        try:
            pages = _extract_with_pdfplumber(path)
            if not _needs_ocr(pages):
                return pages
        except Exception as exc:
            logger.warning("pdfplumber extraction failed", extra={"error": str(exc)})

    # OCR fallback (optional — requires pytesseract + poppler)
    try:
        from app.services._ocr import ocr_pdf  # lazy import

        logger.info("Falling back to OCR", extra={"path": str(path)})
        return ocr_pdf(path)
    except ImportError:
        logger.warning("OCR fallback not available (pytesseract not installed)")

    return []  # nothing extractable


# ── Token counting ────────────────────────────────────────────

def _token_count(text: str) -> int:
    if HAS_TIKTOKEN:
        return len(_enc.encode(text))
    return len(text) // 4  # rough approximation


def _token_chunks(text: str) -> list[str]:
    """Split text into token windows using tiktoken if available."""
    if not HAS_TIKTOKEN:
        # character fallback: 4 chars ≈ 1 token
        size = settings.chunk_size_tokens * 4
        overlap = settings.chunk_overlap_tokens * 4
        chunks = []
        start = 0
        while start < len(text):
            chunks.append(text[start : start + size])
            start += size - overlap
        return chunks

    tokens = _enc.encode(text)
    size = settings.chunk_size_tokens
    overlap = settings.chunk_overlap_tokens
    chunks = []
    start = 0
    while start < len(tokens):
        window = tokens[start : start + size]
        chunks.append(_enc.decode(window))
        start += size - overlap
    return chunks


# ── Chunker ───────────────────────────────────────────────────

def chunk_pages(pages: list[PageText]) -> list[RawChunk]:
    """
    Produce overlapping token-aware chunks from extracted pages.
    Each chunk carries the page range it originated from.
    """
    if not pages:
        return []

    # Join all page text, tracking character offsets → page numbers
    full_text = ""
    page_offsets: list[tuple[int, int]] = []  # (start_char, page_number)
    for pt in pages:
        page_offsets.append((len(full_text), pt.page_number))
        full_text += pt.text + "\n"

    def _char_to_page(char_idx: int) -> int:
        page = 1
        for start, pnum in page_offsets:
            if char_idx >= start:
                page = pnum
            else:
                break
        return page

    raw_chunks = _token_chunks(full_text)
    result: list[RawChunk] = []
    char_pos = 0
    for chunk_text in raw_chunks:
        if len(result) >= settings.max_chunks_per_file:
            logger.warning("Reached MAX_CHUNKS_PER_FILE limit", extra={"limit": settings.max_chunks_per_file})
            break
        cleaned = normalise_text(chunk_text)
        if not cleaned:
            char_pos += len(chunk_text)
            continue
        page_start = _char_to_page(char_pos)
        page_end = _char_to_page(char_pos + len(chunk_text) - 1)
        tc = _token_count(cleaned)
        result.append(RawChunk(text=cleaned, page_start=page_start, page_end=page_end, token_count=tc))
        # advance by chunk size minus overlap (in chars)
        advance_chars = max(len(chunk_text) - settings.chunk_overlap_tokens * 4, 1)
        char_pos += advance_chars

    return result


# ── Content hash ──────────────────────────────────────────────

def file_content_hash(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            sha.update(block)
    return sha.hexdigest()


# ── Disk save ─────────────────────────────────────────────────

def save_upload(file_bytes: bytes, original_name: str) -> tuple[Path, str]:
    """
    Save raw bytes to STORAGE_PATH with a sanitized unique filename.
    Returns (absolute_path, stored_name).
    """
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", original_name)
    unique = f"{uuid4().hex}_{safe}"
    dest: Path = settings.storage_path / unique
    dest.write_bytes(file_bytes)
    return dest, unique
