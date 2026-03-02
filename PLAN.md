# AskMyNotes — Architecture & Build Plan

## 1. Document Analysis Summary

### What the docs define
| Document | Purpose |
|---|---|
| `PRD.md` | Product goals, user stories, success metrics, feature set |
| `Instructions.md` | Technical spec: directory layout, component responsibilities, milestones |
| `README.md` | Public-facing summary for users |

### Core invariants (must never be violated)
1. **Non-hallucination guarantee** — system returns the refusal phrase `Not found in your notes for [Subject]` rather than answer that lacks supporting evidence.
2. **Subject scoping** — retrieval always scoped to the selected subject's chunks only.
3. **Verbatim or entailed evidence** — every atomic claim in the answer must pass verbatim check OR explicit entailment check against stored chunks.
4. **Grounding score always present** — every accepted answer returns a 0–100 grounding score with component breakdown.

---

## 2. Improvements & Overrides (over the provided docs)

The following changes improve correctness, performance, or developer experience without compromising the non-hallucination guarantee.

| # | Area | What docs say | My override / improvement | Reason |
|---|---|---|---|---|
| 1 | FAISS storage | In-memory only | Persist index to `{STORAGE_PATH}/faiss/{subject_id}.index` + mapping JSON | Uploads survive server restart without re-indexing |
| 2 | Subject limit | Hard-coded 3 | `MAX_SUBJECTS_PER_USER=3` env var (default 3) | Configurable for different deployments |
| 3 | Chunking | Character-based implied | Token-aware chunking using `tiktoken` (default 512 tokens, 64 overlap) | Prevents mid-sentence splits; stays within context limits |
| 4 | Async I/O | Not specified | Fully async FastAPI (async def routes + AsyncOpenAI client) | Better concurrency; critical for concurrent demo users |
| 5 | Health endpoint | Not mentioned | `GET /health` returning status + version | Required for Docker health checks and load balancers |
| 6 | CORS | Not mentioned | Configurable `ALLOWED_ORIGINS` env var | Needed for React dev server proxy |
| 7 | Embedding cache | Optional | File-level content hash → skip re-embedding identical chunks | Reduces OpenAI cost during re-uploads / re-demos |
| 8 | Grounding score | Formula given | Unchanged, but expose component breakdown as `grounding_detail` object | Judges and Study Mode UI can display per-component |
| 9 | Subject model | "hard limit 3" | DB-driven with status field per subject (active/archived) | Allows re-naming without data loss |
| 10 | Atomic claim splitter | "simple sentence splitter" | Use `spacy` `sent_tokenize` fallback to regex sentence split | More reliable for academic text |
| 11 | OCR | Tesseract fallback | Integrate OCR only when `pdfplumber` text extraction is < 50 chars/page | Faster happy path; OCR only when needed |
| 12 | Study Mode | 5 MCQs + 3 short answers | Add `difficulty` field (easy/medium/hard) and citation for each distractor | More useful for students |

---

## 3. Final Tech Stack

```
Backend  : Python 3.11 + FastAPI (async)
Frontend : React 18 + Vite 5 + Tailwind CSS
VectorDB : FAISS-cpu (persisted to disk)
LLM      : OpenAI gpt-4o-mini (gen + verify)
Embed    : OpenAI text-embedding-3-large (3072-dim, cosine)
Metadata : SQLite via SQLModel (async-compatible)
PDF      : PyMuPDF (fitz) primary, pdfplumber fallback, Tesseract OCR last resort
Chunking : tiktoken-aware sliding window
Container: Docker + Docker Compose
```

---

## 4. System Architecture

```
User Browser
     │
     ▼
React + Vite (port 5173)
     │  REST
     ▼
FastAPI (port 8000)
  ├── /upload  ──►  IngestionService ──► [PDF/TXT parsing] ──► [Chunker]
  │                        │                                       │
  │                        ▼                                       ▼
  │                  StorageService                         EmbeddingsService
  │                  (SQLite + disk)                        (OpenAI API + cache)
  │                                                               │
  ├── /ask  ──►  RetrieverService (FAISS, subject-scoped)  ◄──────┘
  │                  │  top-K chunks
  │                  ▼
  │             LLMClient.generate()
  │                  │  draft answer JSON
  │                  ▼
  │             VerifierService
  │             ├── verbatim check
  │             └── LLMClient.verify() per unsupported claim
  │                  │  PASS or FAIL
  │                  ▼
  │             GroundingService.score()
  │                  │  grounding_score 0-100
  │                  ▼
  │             Return JSON or Refusal
  │
  └── /study ──►  StudyModeService (MCQ + short-answer generation, citation-verified)
```

---

## 5. Directory Structure (final)

```
/askmynotes
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app + CORS + lifespan
│   │   ├── routes/
│   │   │   ├── chat.py              # POST /ask
│   │   │   ├── files.py             # POST /upload, GET /file/{id}
│   │   │   └── study.py             # POST /study
│   │   ├── services/
│   │   │   ├── ingestion.py         # parse + chunk + normalize
│   │   │   ├── embeddings.py        # OpenAI embed wrapper + cache
│   │   │   ├── retriever.py         # FAISS per-subject, persisted
│   │   │   ├── llm_client.py        # generate + verify prompts
│   │   │   ├── verifier.py          # verbatim + entailment pipeline
│   │   │   ├── grounding.py         # score formula
│   │   │   ├── study_mode.py        # MCQ/short-answer generation
│   │   │   └── storage.py           # SQLite CRUD via SQLModel
│   │   ├── models/
│   │   │   └── schema.py            # Pydantic request/response + SQLModel tables
│   │   └── core/
│   │       ├── config.py            # Settings (pydantic-settings, reads .env)
│   │       └── logging.py           # Structured JSON logger
│   ├── tests/
│   │   ├── test_ingestion.py
│   │   ├── test_retrieval.py
│   │   ├── test_verifier.py
│   │   ├── test_grounding.py
│   │   └── test_ask_integration.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── Chat.jsx
│   │   │   ├── EvidencePanel.jsx
│   │   │   ├── StudyMode.jsx
│   │   │   ├── FileUpload.jsx
│   │   │   └── GroundingMeter.jsx   # visual score component
│   │   ├── services/
│   │   │   └── api.js
│   │   └── hooks/
│   │       └── useSubject.js
│   ├── package.json
│   └── Dockerfile
├── infra/
│   └── docker-compose.yml
├── docs/
│   ├── PROMPTS.md                   # All system/verify prompt templates
│   └── ARCHITECTURE.md
├── scripts/
│   └── gen_sample_data.py           # generate sample PDFs for demo
├── data/
│   ├── uploads/                     # raw uploaded files
│   ├── faiss/                       # persisted FAISS indexes
│   └── metadata.db                  # SQLite
├── .env.example
├── PLAN.md                          # this file
├── PROGRESS.md                      # live build tracker
└── README.md
```

---

## 6. Pydantic Schemas (key shapes)

```python
# Request
class AskRequest(BaseModel):
    subject_id: str
    question: str

class UploadResponse(BaseModel):
    file_id: str
    subject_id: str
    chunk_count: int

# Core Response
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

class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    evidence_snippets: list[str]
    confidence: Literal["High", "Medium", "Low"]
    grounding_score: int       # 0-100
    grounding_detail: GroundingDetail

# Study Mode
class MCQOption(BaseModel):
    label: str     # A/B/C/D
    text: str
    is_correct: bool
    citation: Citation | None

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
```

---

## 7. Environment Variables

```ini
# LLM
OPENAI_API_KEY=
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_EMBED_MODEL=text-embedding-3-large
OPENAI_GEN_MODEL=gpt-4o-mini

# Storage
VECTOR_DB=faiss
DATABASE_URL=sqlite+aiosqlite:///./data/metadata.db
STORAGE_PATH=./data/uploads
FAISS_PATH=./data/faiss

# Retrieval tuning
MAX_CHUNKS_PER_FILE=2000
RETRIEVAL_TOP_K=5
CHUNK_SIZE_TOKENS=512
CHUNK_OVERLAP_TOKENS=64
SIMILARITY_THRESHOLD_HIGH=0.80
SIMILARITY_THRESHOLD_MED=0.60
MIN_SIMILARITY_FOR_CALL=0.35

# Subject limits
MAX_SUBJECTS_PER_USER=3

# API
ALLOWED_ORIGINS=http://localhost:5173
REFUSAL_PHRASE=Not found in your notes for {subject}
APP_VERSION=0.1.0
```

---

## 8. Grounding Score Formula

```
top_similarity    = best cosine score among retrieved chunks  (0..1)
support_ratio     = supported_atomic_claims / total_atomic_claims  (0..1)
evidence_overlap  = fraction of answer tokens present in evidence snippets  (0..1)

grounding_score   = round((0.5 × top_sim + 0.3 × support_ratio + 0.2 × ev_overlap) × 100)

confidence thresholds:
  High   : grounding_score >= 75
  Medium : grounding_score >= 50
  Low    : grounding_score < 50  (still returned if all claims pass verification)
```

---

## 9. Build Phases

### Phase 1 — Project Scaffold (Foundation)
Priority: Must complete before any feature work.

| Task | Description |
|---|---|
| P1-T1 | Create full directory tree |
| P1-T2 | `requirements.txt` with pinned versions |
| P1-T3 | `core/config.py` with pydantic-settings |
| P1-T4 | `core/logging.py` structured JSON logger |
| P1-T5 | `main.py` with CORS, lifespan, health endpoint |
| P1-T6 | `models/schema.py` all Pydantic + SQLModel models |
| P1-T7 | `.env.example` |
| P1-T8 | `docker-compose.yml` and Dockerfiles |
| P1-T9 | `docs/PROMPTS.md` with canonical prompt templates |
| P1-T10 | `frontend/` Vite + React + Tailwind scaffold |

### Phase 2 — Ingestion Pipeline
| Task | Description |
|---|---|
| P2-T1 | `storage.py` — SQLite tables: Subject, File, Chunk |
| P2-T2 | `ingestion.py` — PyMuPDF extractor with page metadata |
| P2-T3 | `ingestion.py` — tiktoken-aware chunker with overlap |
| P2-T4 | `routes/files.py` — POST /upload endpoint |
| P2-T5 | `tests/test_ingestion.py` — chunk count, metadata, page mapping |

### Phase 3 — Embeddings & Retrieval
| Task | Description |
|---|---|
| P3-T1 | `embeddings.py` — async OpenAI embed, batch, retry, content-hash cache |
| P3-T2 | `retriever.py` — FAISS index per subject, persisted to disk |
| P3-T3 | `retriever.py` — add/search with subject filter, faiss_id→chunk_id mapping |
| P3-T4 | `tests/test_retrieval.py` — subject isolation, threshold filter |

### Phase 4 — Generation & Verification (Core)
| Task | Description |
|---|---|
| P4-T1 | `llm_client.py` — generate() with strict JSON system prompt |
| P4-T2 | `llm_client.py` — verify() with YES/NO entailment prompt |
| P4-T3 | `verifier.py` — verbatim snippet checker |
| P4-T4 | `verifier.py` — atomic claim splitter + full verification pipeline |
| P4-T5 | `grounding.py` — score formula, confidence thresholds |
| P4-T6 | `routes/chat.py` — POST /ask end-to-end orchestration |
| P4-T7 | `tests/test_verifier.py` — verbatim pass, entailment pass, refusal cases |
| P4-T8 | `tests/test_ask_integration.py` — full pipeline integration |

### Phase 5 — Study Mode
| Task | Description |
|---|---|
| P5-T1 | `study_mode.py` — MCQ generation prompt + citation validator |
| P5-T2 | `study_mode.py` — short answer generation + citation validator |
| P5-T3 | `routes/study.py` — POST /study endpoint |
| P5-T4 | Tests: 4/5 MCQs pass citation check |

### Phase 6 — Frontend
| Task | Description |
|---|---|
| P6-T1 | Subject selector (max 3, enforced) |
| P6-T2 | FileUpload component with progress indicator |
| P6-T3 | Chat component: send question, render answer + citations |
| P6-T4 | GroundingMeter component: visual 0-100 + component breakdown |
| P6-T5 | EvidencePanel: click citation → highlight in file viewer |
| P6-T6 | StudyMode UI: MCQ card + short answer card |
| P6-T7 | Global state: useSubject hook |

### Phase 7 — Tests, Adversarial Demo & Polish
| Task | Description |
|---|---|
| P7-T1 | `scripts/gen_sample_data.py` — synthetic notes PDFs |
| P7-T2 | Adversarial test suite (3 queries correctly refused) |
| P7-T3 | README final polish |
| P7-T4 | Docker compose full-stack smoke test |
| P7-T5 | Study Mode citation audit: automated 4/5 pass check |

---

## 10. Prompt Templates (reference IDs, full text in docs/PROMPTS.md)

| ID | Usage |
|---|---|
| `PROMPT_GEN_SYSTEM` | Generation system prompt — strict JSON, no external knowledge |
| `PROMPT_GEN_USER` | Generation user turn — injects CONTEXT + QUESTION |
| `PROMPT_VERIFY_CLAIM` | Entailment check — CONTEXT + CLAIM → YES or NO |
| `PROMPT_STUDY_MCQ` | MCQ generation — CONTEXT + TOPIC → structured JSON |
| `PROMPT_STUDY_SA` | Short answer generation — CONTEXT + TOPIC → structured JSON |

---

## 11. Key Decisions Log

| Date | Decision | Rationale |
|---|---|---|
| 2026-02-26 | FAISS persisted to disk | Survive restarts without re-indexing |
| 2026-02-26 | tiktoken chunking instead of char-based | Token-accurate; prevents embedding truncation |
| 2026-02-26 | Async FastAPI + aiosqlite | Concurrent users, non-blocking LLM calls |
| 2026-02-26 | SQLModel for ORM | Type-safe, compatible with both SQLite and Postgres |
| 2026-02-26 | Content-hash embedding cache | Cost reduction during demo re-runs |
| 2026-02-26 | spacy sentence tokenizer for claims | More reliable atomic claim splitting |
| 2026-02-26 | grounding_detail exposed in API | Judges can see score breakdown |
| 2026-02-26 | difficulty field on Study Mode items | Better student UX |
