"""
Application configuration — reads from environment / .env file.
All settings must come from here; no hardcoded secrets anywhere else.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM / Embeddings ──────────────────────────────────────────
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openai_api_base: str = "https://api.openai.com/v1"
    openai_embed_model: str = "text-embedding-3-large"
    openai_gen_model: str = "gpt-4o-mini"

    # ── Storage ───────────────────────────────────────────────────
    vector_db: Literal["faiss"] = "faiss"
    database_url: str = "sqlite+aiosqlite:///./data/metadata.db"
    storage_path: Path = Path("./data/uploads")
    faiss_path: Path = Path("./data/faiss")

    # ── Retrieval / chunking tuning ───────────────────────────────
    max_chunks_per_file: int = 2000
    retrieval_top_k: int = 5
    chunk_size_tokens: int = 512
    chunk_overlap_tokens: int = 64
    similarity_threshold_high: float = 0.80
    similarity_threshold_med: float = 0.60
    min_similarity_for_call: float = 0.35

    # ── Subject limits ────────────────────────────────────────────
    max_subjects_per_user: int = 3

    # ── API ───────────────────────────────────────────────────────
    allowed_origins: str = "http://localhost:5173"
    refusal_phrase: str = "Not found in your notes for {subject}"
    app_version: str = "0.1.0"

    # ── Helpers ───────────────────────────────────────────────────
    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    def refusal(self, subject: str) -> str:
        return self.refusal_phrase.format(subject=subject)

    def ensure_dirs(self) -> None:
        """Create required data directories if they don't exist."""
        for p in (self.storage_path, self.faiss_path, Path("./data")):
            p.mkdir(parents=True, exist_ok=True)


settings = Settings()  # type: ignore[call-arg]  # OPENAI_API_KEY must be set in env
