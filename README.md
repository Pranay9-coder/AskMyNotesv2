# README.md

```markdown
# AskMyNotes — README (MVP)

## What it is
AskMyNotes is a closed-book Q&A assistant that answers only from user-uploaded notes. It enforces verifiable grounding, returns evidence snippets with page-level citations, and rejects questions unsupported by the notes with a deterministic refusal.

## Quick features
- Exactly 3 subjects per user.
- Upload PDFs/TXTs as subject notes.
- Subject-scoped retrieval and answer generation.
- Strict refusal phrase: `Not found in your notes for [Subject]`.
- Grounding Score and component metrics.
- Evidence highlight: click a citation to view the exact sentence in the source file.
- Study Mode: 5 MCQs + 3 short answers with citations.
- Adversarial demo mode to show non-hallucination.

## Tech stack (MVP)
- Backend: FastAPI (Python)
- Frontend: React + Vite
- Vector DB: FAISS (in-memory)
- Embeddings and LLM: OpenAI (`text-embedding-3-large`, `gpt-4o-mini`)
- PDF/Text parsing: PyMuPDF, pdfplumber, Tesseract OCR fallback
- DB: SQLite
- Deployment: Docker (dev/demo)

## Installation (dev)
1. Clone repo
```bash
git clone <repo>
cd askmynotes
