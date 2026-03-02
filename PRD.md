# Product Requirements Document (PRD) — AskMyNotes MVP

## 1. Purpose
Build a closed-book question-answering system that answers only from user-provided notes. The product must enforce non-hallucination, provide verifiable citations, and surface a measurable grounding score. Target demo: hackathon judges and early users (students, tutors).

## 2. Target users
- Students who want answers strictly from their class notes.
- Tutors and exam-prep creators who want verifiable Q&A and auto-generated study materials.
- Judges and reviewers who need demonstrable, testable correctness.

## 3. Key problem
RAG systems often hallucinate. Judges want enforceable guarantees that answers are derived only from the uploaded corpus.

## 4. Core value proposition (MVP USPs)
1. **Strict Grounding Enforcement**: Answers are accepted only if claims are supported by uploaded text. Otherwise the system returns `Not found in your notes for [Subject]`.
2. **Grounding Score**: Numeric score and component metrics (top similarity, evidence overlap, unsupported claim count).
3. **Sentence-level Verification and Entailment**: Claims are validated semantically, allowing paraphrase while blocking unsupported facts.
4. **Evidence Highlight Overlay**: Click a citation and highlight the exact sentence in the source PDF/TXT.
5. **Adversarial Mode**: Demonstrable refusal behavior for queries not supported by notes.
6. **Study Mode with Guarantees**: MCQs and short answers are generated only when fully supported; distractors are not copied verbatim.

## 5. Phase 1 (MVP) — required features
- Create exactly 3 subjects per user.
- File upload for each subject (PDF, TXT). Page-aware extraction.
- Chunking, embeddings, and a subject-scoped retriever.
- Chat endpoint that:
  - Retrieves top-k chunks (subject scoped).
  - Calls LLM with strict system prompt.
  - Validates response against stored chunks.
  - Returns JSON with `answer`, `citations`, `evidence_snippets`, `confidence`.
  - If insufficient evidence: `Not found in your notes for [Subject]`.
- UI: chat, grounding score, evidence panel with highlights, Study Mode generator (5 MCQs + 3 short answers).
- Tests that assert exact refusal string and mapping from evidence to file/page.

## 6. Phase 2 (post-MVP)
- Browser voice I/O (STT/TTS).
- Multi-turn follow-up handling preserving grounding constraints.
- Conflict detection across notes (contradiction detection).
- More robust indexing (distillation, semantic compression).
- Support for larger corpora (S3 + Redis/FAISS + Postgres).

## 7. Non-functional requirements
- Response latency: aim <2s for retrieval and <3s for LLM call in demo environment (subject to model).
- Security: uploads isolated per user; no internet access in LLM prompts.
- Deterministic refusal behavior for unsupported queries.

## 8. Success metrics (for hackathon/demo)
- 0 accepted answers that contain unsupported claims in sample test-suite (automated).
- Grounding Score displayed for 100% of answered queries.
- Study Mode: at least 4 out of 5 MCQs pass citation check automatically.
- Live demo: 3 adversarial queries correctly refused.

## 9. Tech stack (MVP)
- Backend: Python + FastAPI
- Frontend: React + Vite
- Vector DB: FAISS (in-memory for hackathon)
- PDF/Text extraction: PyMuPDF (fitz) and pdfplumber, Tesseract OCR fallback
- Embeddings & LLM: OpenAI (primary). Fallback: local HuggingFace models
- DB: SQLite for metadata (hackathon); Postgres optional later
- Hosting: local / Docker for demo

## 10. Models and API providers (predecided)
- Embeddings: `text-embedding-3-large` (OpenAI)  
  Env var: `OPENAI_EMBED_MODEL` default `text-embedding-3-large`
- Generation / Verification: `gpt-4o-mini` (OpenAI) used for both answer generation and entailment checks in separate calls.  
  Env var: `OPENAI_GEN_MODEL` default `gpt-4o-mini`
- API provider: OpenAI with env var `OPENAI_API_KEY`. Optionally support `HF_API_KEY` as fallback.

> Note: choose lower-cost models if speed/cost is critical for demo. You may reuse the same model for generate/verify by changing the prompt.

## 11. Constraints & acceptance criteria
- The system must never return an answer containing an unsupported factual claim. If detection fails in rare cases, the failure count must be visible and minimized.
- The exact refusal string must be returned verbatim:  
  `Not found in your notes for [Subject]`
- Evidence snippets must be exact or minimally trimmed sentences taken from chunks.

## 12. Timeline (hackathon)
- Day 0 (planning): finalize stack, env variables, directory layout, prompts, and dataset.
- Day 1 morning: ingestion pipeline + chunking + small local vector DB.
- Day 1 afternoon: retrieval + LLM call + JSON enforcement + UI chat.
- Day 2 morning: verification module + grounding score + evidence overlay.
- Day 2 afternoon: Study Mode + adversarial tests + README + demo polish.
