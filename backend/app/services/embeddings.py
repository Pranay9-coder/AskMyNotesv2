"""
Embeddings service — async OpenAI embedding wrapper.
Features: batched requests, retry with exponential back-off, content-hash cache.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Optional

import openai
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_client: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base,
        )
    return _client


# ── Disk embedding cache ──────────────────────────────────────
# Cache: {content_hash: [float, ...]} stored as JSON per subject.
# Lives at {FAISS_PATH}/{subject_id}_embed_cache.json

def _cache_path(subject_id: str) -> Path:
    return settings.faiss_path / f"{subject_id}_embed_cache.json"


def _load_cache(subject_id: str) -> dict[str, list[float]]:
    p = _cache_path(subject_id)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}
    return {}


def _save_cache(subject_id: str, cache: dict[str, list[float]]) -> None:
    p = _cache_path(subject_id)
    p.write_text(json.dumps(cache))


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# ── Core embedding call ───────────────────────────────────────

async def _embed_batch_with_retry(texts: list[str], max_retries: int = 4) -> list[list[float]]:
    client = _get_client()
    delay = 1.0
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = await client.embeddings.create(
                model=settings.openai_embed_model,
                input=texts,
            )
            return [item.embedding for item in response.data]
        except openai.RateLimitError as exc:
            logger.warning("Rate limit hit, retrying", extra={"attempt": attempt, "delay": delay})
            last_exc = exc
            await asyncio.sleep(delay)
            delay *= 2
        except openai.APIError as exc:
            logger.error("OpenAI API error", extra={"error": str(exc)})
            raise
    raise RuntimeError(f"Embedding failed after {max_retries} retries") from last_exc


async def embed_texts(
    texts: list[str],
    subject_id: str,
    batch_size: int = 100,
) -> list[list[float]]:
    """
    Embed a list of texts with caching and batching.
    Returns list of float vectors in the same order as input.
    """
    cache = _load_cache(subject_id)
    results: list[list[float] | None] = [None] * len(texts)
    uncached_indices: list[int] = []
    uncached_texts: list[str] = []

    # Resolve from cache
    for i, text in enumerate(texts):
        h = _text_hash(text)
        if h in cache:
            results[i] = cache[h]
        else:
            uncached_indices.append(i)
            uncached_texts.append(text)

    if uncached_texts:
        logger.info("Embedding uncached texts", extra={"count": len(uncached_texts)})
        all_vectors: list[list[float]] = []
        for start in range(0, len(uncached_texts), batch_size):
            batch = uncached_texts[start : start + batch_size]
            vectors = await _embed_batch_with_retry(batch)
            all_vectors.extend(vectors)

        for idx, vec in zip(uncached_indices, all_vectors):
            h = _text_hash(texts[idx])
            cache[h] = vec
            results[idx] = vec

        _save_cache(subject_id, cache)

    return results  # type: ignore[return-value]


async def embed_query(query: str) -> list[float]:
    """Embed a single query string (no caching — queries are volatile)."""
    vectors = await _embed_batch_with_retry([query])
    return vectors[0]
