"""
Files routes — upload endpoint and file viewer.
POST /api/upload
GET  /api/file/{file_id}
POST /api/subjects
GET  /api/subjects
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schema import Chunk, SubjectCreate, SubjectRead, UploadResponse
from app.services import ingestion
from app.services import retriever as ret
from app.services import storage
from app.services.embeddings import embed_texts

logger = get_logger(__name__)
router = APIRouter()

ALLOWED_MIME = {"application/pdf", "text/plain"}
ALLOWED_SUFFIXES = {".pdf", ".txt"}


async def _db() -> AsyncSession:  # dependency
    async with storage.AsyncSessionLocal() as session:
        yield session


# ── Subjects ──────────────────────────────────────────────────

@router.post("/subjects", response_model=SubjectRead, status_code=201)
async def create_subject(body: SubjectCreate, session: AsyncSession = Depends(_db)) -> SubjectRead:
    try:
        subject = await storage.create_subject(session, name=body.name, user_id=body.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return SubjectRead(
        id=subject.id,
        name=subject.name,
        user_id=subject.user_id,
        created_at=subject.created_at,
        status=subject.status,
    )


@router.get("/subjects", response_model=list[SubjectRead])
async def list_subjects(user_id: str = "default", session: AsyncSession = Depends(_db)) -> list[SubjectRead]:
    subjects = await storage.list_subjects(session, user_id=user_id)
    return [SubjectRead(id=s.id, name=s.name, user_id=s.user_id, created_at=s.created_at, status=s.status) for s in subjects]


# ── Upload ────────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_file(
    subject_id: str,
    file: UploadFile,
    session: AsyncSession = Depends(_db),
) -> UploadResponse:
    # Validate subject
    subject = await storage.get_subject(session, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    # Validate file type
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {suffix}")

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    # Save to disk
    saved_path, stored_name = ingestion.save_upload(file_bytes, file.filename or "upload")
    content_hash = ingestion.file_content_hash(saved_path)

    # Create file DB record
    mime = file.content_type or ("application/pdf" if suffix == ".pdf" else "text/plain")
    db_file = await storage.create_file(
        session,
        subject_id=subject_id,
        original_name=file.filename or stored_name,
        stored_name=stored_name,
        mime_type=mime,
        content_hash=content_hash,
    )

    # Extract pages & chunk
    pages = ingestion.extract_pages(saved_path)
    raw_chunks = ingestion.chunk_pages(pages)

    if not raw_chunks:
        raise HTTPException(status_code=422, detail="Could not extract any text from the file.")

    # Store chunk records (no FAISS yet — embed asynchronously)
    chunk_texts = [rc.text for rc in raw_chunks]
    vectors = await embed_texts(chunk_texts, subject_id=subject_id)

    chunk_records: list[Chunk] = []
    for rc in raw_chunks:
        chunk_records.append(
            Chunk(
                file_id=db_file.id,
                subject_id=subject_id,
                page_start=rc.page_start,
                page_end=rc.page_end,
                text=rc.text,
                token_count=rc.token_count,
                embedding_cached=True,
            )
        )

    await storage.bulk_create_chunks(session, chunk_records)
    chunk_ids = [c.id for c in chunk_records]

    # Add to FAISS index
    await ret.add_vectors(subject_id=subject_id, chunk_ids=chunk_ids, vectors=vectors)

    # Update file stats
    await storage.update_file_stats(session, db_file.id, page_count=len(pages), chunk_count=len(raw_chunks))

    logger.info(
        "File ingested",
        extra={"file_id": db_file.id, "chunks": len(raw_chunks), "pages": len(pages)},
    )
    return UploadResponse(
        file_id=db_file.id,
        subject_id=subject_id,
        original_name=db_file.original_name,
        chunk_count=len(raw_chunks),
        page_count=len(pages),
    )


# ── File viewer ───────────────────────────────────────────────

@router.get("/file/{file_id}")
async def get_file(file_id: str, session: AsyncSession = Depends(_db)) -> FileResponse:
    db_file = await storage.get_file(session, file_id)
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    path = settings.storage_path / db_file.stored_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(
        path=str(path),
        media_type=db_file.mime_type,
        filename=db_file.original_name,
    )
