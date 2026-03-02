"""
Chat route — POST /api/ask

Full pipeline:
  1. Validate subject.
  2. Embed question.
  3. Retrieve top-K chunks (subject-scoped).
  4. Similarity gate.
  5. LLM generate.
  6. Claim verification.
  7. Grounding score.
  8. Return JSON or refusal.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schema import AskRequest, AskResponse, Citation, GroundingDetail
from app.services import grounding, llm_client, retriever, verifier
from app.services.embeddings import embed_query
from app.services.storage import AsyncSessionLocal, get_chunks_by_ids, get_file, get_subject

logger = get_logger(__name__)
router = APIRouter()


async def _db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


@router.post("/ask")
async def ask(body: AskRequest, session: AsyncSession = Depends(_db)) -> JSONResponse:
    # 1. Validate subject
    subject = await get_subject(session, body.subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    # 2. Embed question
    q_vector = await embed_query(body.question)

    # 3. Retrieve top-K chunks
    retrieved = await retriever.search(
        subject_id=body.subject_id,
        query_vector=q_vector,
        top_k=settings.retrieval_top_k,
        min_score=0.0,  # get scores first; gate manually below
    )

    # 4. Similarity gate
    top_sim = max((r.score for r in retrieved), default=0.0)
    if top_sim < settings.min_similarity_for_call or not retrieved:
        refusal = settings.refusal(subject.name)
        logger.info("Similarity below threshold — refusal", extra={"top_sim": top_sim})
        return JSONResponse(content=refusal, status_code=200)

    # 5. Load chunk texts from DB
    chunk_ids = [r.chunk_id for r in retrieved]
    db_chunks = await get_chunks_by_ids(session, chunk_ids)
    chunk_map: dict[str, Any] = {}
    for chunk in db_chunks:
        db_file = await get_file(session, chunk.file_id)
        chunk_map[chunk.id] = {
            "chunk_id": chunk.id,
            "text": chunk.text,
            "file": db_file.original_name if db_file else "unknown",
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
        }

    chunks_payload = [chunk_map[cid] for cid in chunk_ids if cid in chunk_map]

    # 6. LLM generate
    llm_result = await llm_client.generate(
        question=body.question,
        chunks=chunks_payload,
        subject=subject.name,
    )

    if isinstance(llm_result, str):
        # LLM returned refusal phrase
        return JSONResponse(content=llm_result, status_code=200)

    answer_text: str = llm_result.get("answer", "")
    if not answer_text:
        return JSONResponse(content=settings.refusal(subject.name), status_code=200)

    # 7. Claim verification
    ver_result = await verifier.verify_answer(answer=answer_text, chunks=chunks_payload)

    if not ver_result.accepted:
        refusal = settings.refusal(subject.name)
        logger.info(
            "Answer rejected — unsupported claims",
            extra={"unsupported": ver_result.unsupported_claims},
        )
        return JSONResponse(content=refusal, status_code=200)

    # 8. Grounding score
    evidence_snippets: list[str] = [
        r.evidence_snippet
        for r in ver_result.claim_results
        if r.evidence_snippet
    ]
    # Also include snippets from LLM response
    llm_snippets: list[str] = llm_result.get("evidence_snippets", [])
    all_snippets = list(dict.fromkeys(evidence_snippets + llm_snippets))

    ev_overlap = verifier.compute_evidence_overlap(answer_text, all_snippets)
    score, confidence = grounding.compute_score(
        top_similarity=top_sim,
        support_ratio=ver_result.support_ratio,
        evidence_overlap=ev_overlap,
    )
    grounding_detail = grounding.build_grounding_detail(top_sim, ver_result.support_ratio, ev_overlap)

    # Build citations
    citations = []
    for rc in retrieved:
        info = chunk_map.get(rc.chunk_id, {})
        if info:
            citations.append(
                Citation(
                    file=info["file"],
                    page_start=info["page_start"],
                    page_end=info["page_end"],
                    chunk_id=rc.chunk_id,
                    score=round(rc.score, 4),
                )
            )

    response = AskResponse(
        answer=answer_text,
        citations=citations,
        evidence_snippets=all_snippets,
        confidence=confidence,
        grounding_score=score,
        grounding_detail=grounding_detail,
    )
    return JSONResponse(content=response.model_dump(), status_code=200)
