"""
FAISS retriever — per-subject persisted vector index.

Each subject gets its own .index file and a JSON mapping
{faiss_int_id -> chunk_db_id}.

Thread/async safety: FAISS operations are CPU-bound; we wrap
in asyncio.to_thread() to avoid blocking the event loop.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import numpy as np

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

try:
    import faiss  # type: ignore

    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False
    logger.error("faiss-cpu not installed — vector retrieval unavailable")


# ─────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────

def _index_path(subject_id: str) -> Path:
    return settings.faiss_path / f"{subject_id}.index"


def _mapping_path(subject_id: str) -> Path:
    return settings.faiss_path / f"{subject_id}_mapping.json"


def _load_mapping(subject_id: str) -> dict[int, str]:
    p = _mapping_path(subject_id)
    if p.exists():
        data = json.loads(p.read_text())
        return {int(k): v for k, v in data.items()}
    return {}


def _save_mapping(subject_id: str, mapping: dict[int, str]) -> None:
    _mapping_path(subject_id).write_text(json.dumps({str(k): v for k, v in mapping.items()}))


def _load_or_create_index(subject_id: str, dim: int = 3072) -> "faiss.Index":
    p = _index_path(subject_id)
    if p.exists():
        return faiss.read_index(str(p))  # type: ignore[attr-defined]
    index = faiss.IndexFlatIP(dim)  # Inner-product == cosine on unit vectors
    return index


def _normalise_vectors(vecs: np.ndarray) -> np.ndarray:
    """L2-normalise so inner product equals cosine similarity."""
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1e-10, norms)
    return (vecs / norms).astype(np.float32)


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

async def add_vectors(
    subject_id: str,
    chunk_ids: list[str],
    vectors: list[list[float]],
) -> list[int]:
    """
    Add vectors to the subject FAISS index.
    Returns the list of FAISS integer IDs assigned.
    """
    if not HAS_FAISS:
        raise RuntimeError("faiss-cpu is required")

    def _sync() -> list[int]:
        dim = len(vectors[0])
        index = _load_or_create_index(subject_id, dim)
        mapping = _load_mapping(subject_id)
        base_id = index.ntotal
        mat = _normalise_vectors(np.array(vectors, dtype=np.float32))
        index.add(mat)  # type: ignore[attr-defined]
        new_ids = list(range(base_id, base_id + len(vectors)))
        for faiss_id, chunk_id in zip(new_ids, chunk_ids):
            mapping[faiss_id] = chunk_id
        faiss.write_index(index, str(_index_path(subject_id)))  # type: ignore[attr-defined]
        _save_mapping(subject_id, mapping)
        logger.info("Vectors added to FAISS", extra={"subject_id": subject_id, "count": len(vectors)})
        return new_ids

    return await asyncio.to_thread(_sync)


class RetrievedChunk:
    __slots__ = ("chunk_id", "faiss_id", "score")

    def __init__(self, chunk_id: str, faiss_id: int, score: float) -> None:
        self.chunk_id = chunk_id
        self.faiss_id = faiss_id
        self.score = score


async def search(
    subject_id: str,
    query_vector: list[float],
    top_k: int | None = None,
    min_score: float | None = None,
) -> list[RetrievedChunk]:
    """
    Search the subject FAISS index.
    Returns up to top_k results above min_score, sorted by descending score.
    """
    if not HAS_FAISS:
        raise RuntimeError("faiss-cpu is required")

    top_k = top_k or settings.retrieval_top_k
    min_score = min_score if min_score is not None else settings.min_similarity_for_call

    def _sync() -> list[RetrievedChunk]:
        p = _index_path(subject_id)
        if not p.exists():
            return []
        index = faiss.read_index(str(p))  # type: ignore[attr-defined]
        if index.ntotal == 0:
            return []
        mapping = _load_mapping(subject_id)
        q = _normalise_vectors(np.array([query_vector], dtype=np.float32))
        k = min(top_k, index.ntotal)
        scores, ids = index.search(q, k)  # type: ignore[attr-defined]
        results: list[RetrievedChunk] = []
        for score, fid in zip(scores[0], ids[0]):
            if fid == -1:
                continue
            if float(score) < min_score:
                continue
            chunk_id = mapping.get(int(fid))
            if chunk_id:
                results.append(RetrievedChunk(chunk_id=chunk_id, faiss_id=int(fid), score=float(score)))
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    return await asyncio.to_thread(_sync)


async def delete_subject_index(subject_id: str) -> None:
    """Remove persisted index files for a subject."""
    for p in (_index_path(subject_id), _mapping_path(subject_id)):
        if p.exists():
            p.unlink()
    logger.info("Subject index deleted", extra={"subject_id": subject_id})
