"""
Tests — FAISS retriever (mocked vectors, no real embeddings).
Covers: add vectors, search, subject isolation, score threshold.
"""
from __future__ import annotations

import pytest

# Skip entire module if faiss is not installed
pytest.importorskip("faiss")

import numpy as np
import pytest_asyncio

from app.services import retriever


@pytest.fixture(autouse=True)
def tmp_faiss_dir(tmp_path, monkeypatch):
    """Redirect FAISS index to a temp directory."""
    from app.core import config
    monkeypatch.setattr(config.settings, "faiss_path", tmp_path)
    yield


def _rand_vec(dim: int = 3072) -> list[float]:
    v = np.random.randn(dim).astype(np.float32)
    v /= np.linalg.norm(v)
    return v.tolist()


@pytest.mark.asyncio
async def test_add_and_search_basic():
    vecs = [_rand_vec() for _ in range(5)]
    chunk_ids = [f"chunk-{i}" for i in range(5)]
    faiss_ids = await retriever.add_vectors("subj1", chunk_ids, vecs)
    assert len(faiss_ids) == 5

    results = await retriever.search("subj1", vecs[0], top_k=3, min_score=0.0)
    assert len(results) > 0
    # The query is identical to vecs[0], so top result should be chunk-0
    assert results[0].chunk_id == "chunk-0"
    assert results[0].score > 0.99


@pytest.mark.asyncio
async def test_subject_isolation():
    """Vectors indexed under subj1 must not appear in subj2 search."""
    v = _rand_vec()
    await retriever.add_vectors("subj1", ["chunk-A"], [v])
    results = await retriever.search("subj2", v, top_k=5, min_score=0.0)
    assert results == []


@pytest.mark.asyncio
async def test_min_score_filter():
    vecs = [_rand_vec() for _ in range(10)]
    chunk_ids = [f"c{i}" for i in range(10)]
    await retriever.add_vectors("subj3", chunk_ids, vecs)
    # Use a very high threshold — should filter out most results
    results = await retriever.search("subj3", vecs[0], top_k=10, min_score=0.99)
    # Only the identical vector should pass
    assert len(results) <= 1


@pytest.mark.asyncio
async def test_empty_index_returns_empty():
    results = await retriever.search("nonexistent_subject", _rand_vec(), top_k=5, min_score=0.0)
    assert results == []


@pytest.mark.asyncio
async def test_delete_subject_index():
    v = _rand_vec()
    await retriever.add_vectors("subj4", ["del-chunk"], [v])
    await retriever.delete_subject_index("subj4")
    results = await retriever.search("subj4", v, top_k=1, min_score=0.0)
    assert results == []
