"""
Study route — POST /api/study

Generates MCQs and short-answer questions from a subject's notes.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schema import StudyRequest, StudyResponse
from app.services import retriever
from app.services import study_mode
from app.services.embeddings import embed_query
from app.services.storage import AsyncSessionLocal, get_chunks_by_ids, get_file, get_subject

logger = get_logger(__name__)
router = APIRouter()


async def _db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


@router.post("/study", response_model=StudyResponse)
async def study(body: StudyRequest, session: AsyncSession = Depends(_db)) -> JSONResponse:
    subject = await get_subject(session, body.subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    # Use topic as query, otherwise use subject name
    query_text = body.topic or subject.name
    q_vector = await embed_query(query_text)

    # Retrieve broader set for study mode (2× top_k)
    retrieved = await retriever.search(
        subject_id=body.subject_id,
        query_vector=q_vector,
        top_k=settings.retrieval_top_k * 2,
        min_score=0.0,
    )

    if not retrieved:
        raise HTTPException(status_code=422, detail="No notes found for this subject. Upload files first.")

    # Load chunk texts
    chunk_ids = [r.chunk_id for r in retrieved]
    db_chunks = await get_chunks_by_ids(session, chunk_ids)
    chunk_texts: dict[str, Any] = {}
    for chunk in db_chunks:
        db_file = await get_file(session, chunk.file_id)
        chunk_texts[chunk.id] = {
            "text": chunk.text,
            "file": db_file.original_name if db_file else "unknown",
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
        }

    result = await study_mode.generate_study_material(
        subject_id=body.subject_id,
        subject_name=subject.name,
        retrieved_chunks=retrieved,
        chunk_texts=chunk_texts,
        topic=body.topic,
        mcq_count=body.mcq_count,
        short_answer_count=body.short_answer_count,
    )

    return JSONResponse(content=result.model_dump(), status_code=200)
