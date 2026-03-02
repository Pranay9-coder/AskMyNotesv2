"""
Integration tests — full /ask pipeline with mocked LLM and embeddings.

These tests assert:
  1. Refusal phrase returned when similarity is below threshold.
  2. Valid JSON returned when evidence is present and verified.
  3. Adversarial: correct answer in real world but not in notes → refusal.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.main import app
from app.services.storage import init_db


@pytest_asyncio.fixture(autouse=True)
async def setup_db(tmp_path, monkeypatch):
    """Use temp SQLite for each test."""
    from app.core import config
    monkeypatch.setattr(config.settings, "database_url", f"sqlite+aiosqlite:///{tmp_path}/test.db")
    monkeypatch.setattr(config.settings, "storage_path", tmp_path / "uploads")
    monkeypatch.setattr(config.settings, "faiss_path", tmp_path / "faiss")
    config.settings.ensure_dirs()
    await init_db()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


# ── Helpers ───────────────────────────────────────────────────

async def _create_subject(client: AsyncClient, name: str = "Biology") -> str:
    resp = await client.post("/api/subjects", json={"name": name})
    assert resp.status_code == 201
    return resp.json()["id"]


# ── Tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_ask_refusal_when_no_evidence(client: AsyncClient):
    """When FAISS index is empty, ask should return refusal phrase."""
    subject_id = await _create_subject(client, "EmptySubject")
    with patch("app.routes.chat.embed_query", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.0] * 3072
        with patch("app.services.retriever.search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []  # no chunks found
            resp = await client.post("/api/ask", json={"subject_id": subject_id, "question": "What is ATP?"})
    assert resp.status_code == 200
    body = resp.json()
    assert "Not found in your notes" in body


@pytest.mark.asyncio
async def test_ask_refusal_below_similarity_threshold(client: AsyncClient):
    """Similarity below MIN_SIMILARITY_FOR_CALL → refusal."""
    from app.services.retriever import RetrievedChunk

    subject_id = await _create_subject(client, "Physics")
    low_score_chunk = RetrievedChunk(chunk_id="c1", faiss_id=0, score=0.10)  # below 0.35

    with patch("app.routes.chat.embed_query", new_callable=AsyncMock, return_value=[0.0] * 3072):
        with patch("app.services.retriever.search", new_callable=AsyncMock, return_value=[low_score_chunk]):
            resp = await client.post("/api/ask", json={"subject_id": subject_id, "question": "What is gravity?"})

    body = resp.json()
    assert "Not found in your notes" in body


@pytest.mark.asyncio
async def test_ask_returns_valid_json_when_evidence_found(client: AsyncClient):
    """When evidence is present and verified, expect full AskResponse JSON."""
    from app.models.schema import Chunk
    from app.services import storage
    from app.services.retriever import RetrievedChunk

    subject_id = await _create_subject(client, "Chemistry")

    # Seed a fake chunk in DB
    async with storage.AsyncSessionLocal() as session:
        # Create a fake file record first
        from app.models.schema import File
        fake_file = File(
            subject_id=subject_id,
            original_name="chem.txt",
            stored_name="chem.txt",
            mime_type="text/plain",
        )
        session.add(fake_file)
        await session.commit()
        await session.refresh(fake_file)

        fake_chunk = Chunk(
            file_id=fake_file.id,
            subject_id=subject_id,
            page_start=1,
            page_end=1,
            text="Water is composed of two hydrogen atoms and one oxygen atom.",
            token_count=12,
        )
        session.add(fake_chunk)
        await session.commit()
        await session.refresh(fake_chunk)
        chunk_id = fake_chunk.id

    retrieved_chunk = RetrievedChunk(chunk_id=chunk_id, faiss_id=0, score=0.92)
    llm_draft: dict[str, Any] = {
        "answer": "Water is composed of two hydrogen atoms and one oxygen atom.",
        "citations": [{"file": "chem.txt", "page_start": 1, "page_end": 1, "chunk_id": chunk_id, "score": 0.92}],
        "evidence_snippets": ["Water is composed of two hydrogen atoms and one oxygen atom."],
        "confidence": "High",
    }

    with (
        patch("app.routes.chat.embed_query", new_callable=AsyncMock, return_value=[0.0] * 3072),
        patch("app.services.retriever.search", new_callable=AsyncMock, return_value=[retrieved_chunk]),
        patch("app.services.llm_client.generate", new_callable=AsyncMock, return_value=llm_draft),
        patch("app.services.verifier.llm_client.verify_claim", new_callable=AsyncMock, return_value=True),
    ):
        resp = await client.post("/api/ask", json={"subject_id": subject_id, "question": "What is water made of?"})

    assert resp.status_code == 200
    body = resp.json()
    assert "answer" in body
    assert "grounding_score" in body
    assert "citations" in body
    assert isinstance(body["grounding_score"], int)


@pytest.mark.asyncio
async def test_adversarial_true_fact_not_in_notes(client: AsyncClient):
    """
    A factually correct answer that has no supporting chunk must be refused.
    Simulates: LLM returns answer but verifier rejects it.
    """
    from app.models.schema import Chunk
    from app.services import storage
    from app.services.retriever import RetrievedChunk

    subject_id = await _create_subject(client, "History")

    # Seed an unrelated chunk
    async with storage.AsyncSessionLocal() as session:
        from app.models.schema import File
        fake_file = File(subject_id=subject_id, original_name="hist.txt", stored_name="hist.txt", mime_type="text/plain")
        session.add(fake_file)
        await session.commit()
        await session.refresh(fake_file)
        fake_chunk = Chunk(
            file_id=fake_file.id, subject_id=subject_id,
            page_start=1, page_end=1,
            text="The French Revolution began in 1789.",
            token_count=7,
        )
        session.add(fake_chunk)
        await session.commit()
        await session.refresh(fake_chunk)
        chunk_id = fake_chunk.id

    retrieved_chunk = RetrievedChunk(chunk_id=chunk_id, faiss_id=0, score=0.85)
    # LLM invents an answer not in notes
    hallucinated_draft: dict[str, Any] = {
        "answer": "The American Civil War ended in 1865 with General Lee's surrender.",
        "citations": [],
        "evidence_snippets": [],
        "confidence": "Low",
    }

    with (
        patch("app.routes.chat.embed_query", new_callable=AsyncMock, return_value=[0.0] * 3072),
        patch("app.services.retriever.search", new_callable=AsyncMock, return_value=[retrieved_chunk]),
        patch("app.services.llm_client.generate", new_callable=AsyncMock, return_value=hallucinated_draft),
        patch("app.services.verifier.llm_client.verify_claim", new_callable=AsyncMock, return_value=False),
    ):
        resp = await client.post("/api/ask", json={"subject_id": subject_id, "question": "When did the Civil War end?"})

    body = resp.json()
    assert "Not found in your notes" in body
