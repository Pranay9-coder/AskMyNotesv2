"""
Storage service — SQLite via SQLModel (async with aiosqlite).
Provides CRUD helpers for Subject, File, Chunk.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schema import Chunk, File, Subject

logger = get_logger(__name__)

# ── Engine ────────────────────────────────────────────────────
engine = create_async_engine(settings.database_url, echo=False, future=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)  # type: ignore[call-overload]


async def init_db() -> None:
    """Create all tables (idempotent)."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    logger.info("Database tables initialised")


async def get_session() -> AsyncSession:  # pragma: no cover
    async with AsyncSessionLocal() as session:
        yield session


# ── Subject helpers ───────────────────────────────────────────

async def create_subject(session: AsyncSession, name: str, user_id: str = "default") -> Subject:
    active_count = await count_active_subjects(session, user_id)
    if active_count >= settings.max_subjects_per_user:
        raise ValueError(
            f"Maximum of {settings.max_subjects_per_user} subjects per user reached."
        )
    subject = Subject(name=name, user_id=user_id)
    session.add(subject)
    await session.commit()
    await session.refresh(subject)
    logger.info("Subject created", extra={"subject_id": subject.id, "subject_name": name})
    return subject


async def get_subject(session: AsyncSession, subject_id: str) -> Optional[Subject]:
    result = await session.exec(select(Subject).where(Subject.id == subject_id))
    return result.first()


async def count_active_subjects(session: AsyncSession, user_id: str = "default") -> int:
    result = await session.exec(
        select(Subject).where(Subject.user_id == user_id, Subject.status == "active")
    )
    return len(result.all())


async def list_subjects(session: AsyncSession, user_id: str = "default") -> list[Subject]:
    result = await session.exec(
        select(Subject).where(Subject.user_id == user_id).order_by(Subject.created_at)  # type: ignore[arg-type]
    )
    return result.all()


# ── File helpers ──────────────────────────────────────────────

async def create_file(
    session: AsyncSession,
    subject_id: str,
    original_name: str,
    stored_name: str,
    mime_type: str,
    content_hash: str,
) -> File:
    f = File(
        subject_id=subject_id,
        original_name=original_name,
        stored_name=stored_name,
        mime_type=mime_type,
        content_hash=content_hash,
    )
    session.add(f)
    await session.commit()
    await session.refresh(f)
    return f


async def get_file(session: AsyncSession, file_id: str) -> Optional[File]:
    result = await session.exec(select(File).where(File.id == file_id))
    return result.first()


async def update_file_stats(
    session: AsyncSession, file_id: str, page_count: int, chunk_count: int
) -> None:
    f = await get_file(session, file_id)
    if f:
        f.page_count = page_count
        f.chunk_count = chunk_count
        session.add(f)
        await session.commit()


# ── Chunk helpers ─────────────────────────────────────────────

async def bulk_create_chunks(session: AsyncSession, chunks: list[Chunk]) -> None:
    for c in chunks:
        session.add(c)
    await session.commit()
    logger.info("Chunks stored", extra={"count": len(chunks)})


async def get_chunks_by_ids(session: AsyncSession, chunk_ids: list[str]) -> list[Chunk]:
    if not chunk_ids:
        return []
    result = await session.exec(select(Chunk).where(Chunk.id.in_(chunk_ids)))  # type: ignore[attr-defined]
    return result.all()


async def get_chunks_for_subject(session: AsyncSession, subject_id: str) -> list[Chunk]:
    result = await session.exec(select(Chunk).where(Chunk.subject_id == subject_id))
    return result.all()
