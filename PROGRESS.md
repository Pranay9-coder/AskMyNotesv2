# AskMyNotes — Build Progress Tracker

> Last updated: 2026-02-26  
> Status key: ✅ Done | 🔄 In Progress | ⬜ Not Started | ❌ Blocked

---

## Current Focus
**Phase 7 — Tests, Adversarial Demo & Polish** (remaining)

---

## Phase 1 — Project Scaffold (Foundation)

| Task | Status | Notes |
|---|---|---|
| P1-T1 | ✅ | Full directory tree created |
| P1-T2 | ✅ | `requirements.txt` with pinned versions |
| P1-T3 | ✅ | `core/config.py` pydantic-settings |
| P1-T4 | ✅ | `core/logging.py` structured JSON logger |
| P1-T5 | ✅ | `main.py` CORS + lifespan + health endpoint |
| P1-T6 | ✅ | `models/schema.py` all Pydantic + SQLModel models |
| P1-T7 | ✅ | `.env.example` |
| P1-T8 | ✅ | `infra/docker-compose.yml` + backend/frontend Dockerfiles |
| P1-T9 | ✅ | `docs/PROMPTS.md` canonical prompt templates |
| P1-T10 | ✅ | Frontend Vite + React + Tailwind scaffold |

---

## Phase 2 — Ingestion Pipeline

| Task | Status | Notes |
|---|---|---|
| P2-T1 | ✅ | `storage.py` SQLite tables: Subject, File, Chunk |
| P2-T2 | ✅ | `ingestion.py` PyMuPDF extractor with page metadata |
| P2-T3 | ✅ | `ingestion.py` tiktoken-aware chunker with overlap |
| P2-T4 | ✅ | `routes/files.py` POST /upload endpoint + `/subjects` |
| P2-T5 | ✅ | `tests/test_ingestion.py` |

---

## Phase 3 — Embeddings & Retrieval

| Task | Status | Notes |
|---|---|---|
| P3-T1 | ✅ | `embeddings.py` async OpenAI embed + content-hash cache |
| P3-T2 | ✅ | `retriever.py` FAISS per-subject, persisted to disk |
| P3-T3 | ✅ | `retriever.py` add/search + subject isolation |
| P3-T4 | ✅ | `tests/test_retrieval.py` |

---

## Phase 4 — Generation & Verification (Core)

| Task | Status | Notes |
|---|---|---|
| P4-T1 | ✅ | `llm_client.py` generate() strict JSON |
| P4-T2 | ✅ | `llm_client.py` verify() YES/NO entailment |
| P4-T3 | ✅ | `verifier.py` verbatim snippet checker |
| P4-T4 | ✅ | `verifier.py` atomic claim splitter + pipeline |
| P4-T5 | ✅ | `grounding.py` score formula |
| P4-T6 | ✅ | `routes/chat.py` POST /ask orchestration |
| P4-T7 | ✅ | `tests/test_verifier.py` |
| P4-T8 | ✅ | `tests/test_ask_integration.py` (inc. 3 adversarial) |

---

## Phase 5 — Study Mode

| Task | Status | Notes |
|---|---|---|
| P5-T1 | ✅ | `study_mode.py` MCQ generation + citation validator |
| P5-T2 | ✅ | `study_mode.py` short answer + citation validator |
| P5-T3 | ✅ | `routes/study.py` POST /study |
| P5-T4 | ⬜ | Live citation audit against real API (needs OPENAI_API_KEY) |

---

## Phase 6 — Frontend

| Task | Status | Notes |
|---|---|---|
| P6-T1 | ✅ | Subject selector (max 3 enforced) — `App.jsx` + `useSubject.js` |
| P6-T2 | ✅ | `FileUpload.jsx` with progress bar |
| P6-T3 | ✅ | `Chat.jsx`: question + answer + citations |
| P6-T4 | ✅ | `GroundingMeter.jsx`: visual 0-100 + breakdown |
| P6-T5 | ✅ | `EvidencePanel.jsx`: citations + snippets |
| P6-T6 | ✅ | `StudyMode.jsx`: MCQ + short answer cards |
| P6-T7 | ✅ | `useSubject.js` hook + global state in `App.jsx` |

---

## Phase 7 — Tests, Adversarial Demo & Polish

| Task | Status | Notes |
|---|---|---|
| P7-T1 | ✅ | `scripts/gen_sample_data.py` + adversarial test file |
| P7-T2 | ✅ | Adversarial cases in `test_ask_integration.py` |
| P7-T3 | ⬜ | README final polish (run after real API smoke test) |
| P7-T4 | ⬜ | Docker compose smoke test (needs OPENAI_API_KEY) |
| P7-T5 | ⬜ | Study Mode citation audit: 4/5 auto pass (needs real API) |

---

## Completed Items Log

| Date | Task | What was done |
|---|---|---|
| 2026-02-26 | Planning | Read PRD.md, Instructions.md, README.md |
| 2026-02-26 | Planning | Created PLAN.md with arch decisions, overrides, schemas |
| 2026-02-26 | Planning | Created PROGRESS.md (this file) |
| 2026-02-26 | Phase 1 | Full backend scaffold: config, logging, main, schema |
| 2026-02-26 | Phase 2 | Ingestion: storage.py, ingestion.py, routes/files.py |
| 2026-02-26 | Phase 3 | embeddings.py, retriever.py (FAISS persisted) |
| 2026-02-26 | Phase 4 | llm_client.py, verifier.py, grounding.py, routes/chat.py |
| 2026-02-26 | Phase 5 | study_mode.py, routes/study.py |
| 2026-02-26 | Phase 6 | Full frontend: App, Chat, EvidencePanel, GroundingMeter, StudyMode, FileUpload, useSubject |
| 2026-02-26 | Phase 7 | gen_sample_data.py, 4 test files (ingestion/retrieval/verifier/grounding/integration) |

---

## Blocked / Risks

| Item | Risk | Mitigation |
|---|---|---|
| OpenAI API key | Required for embeddings + generation | Use `.env.example`, mock in tests |
| FAISS persistence | Windows path handling | Use `pathlib.Path` throughout |
| Tesseract OCR | Binary must be installed | Detect and skip if absent; log warning |
| spaCy model download | Needs `en_core_web_sm` | Include in Dockerfile + requirements note |

---

## Next Action
Start **Phase 1** — run project scaffold tasks P1-T1 through P1-T10.
