"""
All Pydantic request/response schemas and SQLModel ORM tables.
Single source of truth for data shapes.
"""
from datetime import datetime
from typing import List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlmodel import Column, DateTime, Field as SQLField, Relationship, SQLModel


# ─────────────────────────────────────────────────────────────
# SQLModel ORM tables
# ─────────────────────────────────────────────────────────────

class Subject(SQLModel, table=True):
    __tablename__ = "subjects"

    id: str = SQLField(default_factory=lambda: str(uuid4()), primary_key=True)
    name: str
    user_id: str = SQLField(default="default")  # extend for auth later
    created_at: datetime = SQLField(default_factory=datetime.utcnow, sa_column=Column(DateTime))
    status: str = SQLField(default="active")  # active | archived

    files: List["File"] = Relationship(back_populates="subject")


class File(SQLModel, table=True):
    __tablename__ = "files"

    id: str = SQLField(default_factory=lambda: str(uuid4()), primary_key=True)
    subject_id: str = SQLField(foreign_key="subjects.id")
    original_name: str
    stored_name: str  # sanitized filename on disk
    mime_type: str
    page_count: int = 0
    chunk_count: int = 0
    content_hash: str = ""  # sha256 of file bytes for dedup
    created_at: datetime = SQLField(default_factory=datetime.utcnow, sa_column=Column(DateTime))

    subject: Optional[Subject] = Relationship(back_populates="files")
    chunks: List["Chunk"] = Relationship(back_populates="file")


class Chunk(SQLModel, table=True):
    __tablename__ = "chunks"

    id: str = SQLField(default_factory=lambda: str(uuid4()), primary_key=True)
    file_id: str = SQLField(foreign_key="files.id")
    subject_id: str  # denormalized for fast filter
    faiss_index_id: int = -1  # index inside the per-subject FAISS index
    page_start: int
    page_end: int
    text: str
    token_count: int = 0
    embedding_cached: bool = False

    file: Optional[File] = Relationship(back_populates="chunks")


# ─────────────────────────────────────────────────────────────
# API request / response Pydantic schemas
# ─────────────────────────────────────────────────────────────

class SubjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    user_id: str = "default"


class SubjectRead(BaseModel):
    id: str
    name: str
    user_id: str
    created_at: datetime
    status: str


class UploadResponse(BaseModel):
    file_id: str
    subject_id: str
    original_name: str
    chunk_count: int
    page_count: int


class Citation(BaseModel):
    file: str
    page_start: int
    page_end: int
    chunk_id: str
    score: float


class GroundingDetail(BaseModel):
    top_similarity: float
    support_ratio: float
    evidence_overlap: float


class AskRequest(BaseModel):
    subject_id: str
    question: str = Field(..., min_length=3, max_length=2000)


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    evidence_snippets: list[str]
    confidence: Literal["High", "Medium", "Low"]
    grounding_score: int = Field(..., ge=0, le=100)
    grounding_detail: GroundingDetail


class RefusalResponse(BaseModel):
    refusal: str


# Study Mode schemas

class MCQOption(BaseModel):
    label: str  # A / B / C / D
    text: str
    is_correct: bool
    citation: Optional[Citation] = None


class MCQItem(BaseModel):
    question: str
    options: list[MCQOption]
    explanation: str
    difficulty: Literal["easy", "medium", "hard"]
    citation: Citation


class ShortAnswerItem(BaseModel):
    question: str
    answer: str
    citation: Citation


class StudyRequest(BaseModel):
    subject_id: str
    topic: Optional[str] = None  # optional focus topic
    mcq_count: int = Field(default=5, ge=1, le=10)
    short_answer_count: int = Field(default=3, ge=1, le=10)


class StudyResponse(BaseModel):
    mcqs: list[MCQItem]
    short_answers: list[ShortAnswerItem]


class HealthResponse(BaseModel):
    status: str
    version: str
