## Overview
Implement a closed-book QA system whose only knowledge source is user-uploaded notes. The system must enforce grounding, allow paraphrase verification, and provide a grounding score. Implementation must be modular, object-oriented, and minimal-junk. Break work into phases and micro-tasks; tests and validation are mandatory.

## Directory layout (ideal)
/askmynotes
├── backend
│ ├── app
│ │ ├── main.py # FastAPI app entry
│ │ ├── routes
│ │ │ ├── chat.py
│ │ │ ├── files.py
│ │ │ └── study.py
│ │ ├── services
│ │ │ ├── ingestion.py # file parsing + chunking
│ │ │ ├── embeddings.py # embedding API wrappers
│ │ │ ├── retriever.py # vector DB wrapper (FAISS)
│ │ │ ├── llm_client.py # generation + verification prompts
│ │ │ ├── verifier.py # entailment & snippet verification
│ │ │ ├── grounding.py # scoring logic
│ │ │ └── storage.py # file metadata, chunk index
│ │ └── models
│ │ └── schema.py # Pydantic schemas & JSON schema
│ ├── tests
│ │ ├── test_ingestion.py
│ │ ├── test_retrieval.py
│ │ └── test_verifier.py
│ └── Dockerfile
├── frontend
│ ├── src
│ │ ├── App.jsx
│ │ ├── components
│ │ │ ├── Chat.jsx
│ │ │ ├── EvidencePanel.jsx
│ │ │ └── StudyMode.jsx
│ │ └── services
│ │ └── api.js
│ └── package.json
├── infra
│ └── docker-compose.yml
├── docs
│ ├── PROMPTS.md # system & verify prompts
│ └── QA_PLAN.md
├── scripts
│ └── gen_sample_data.py
├── .env.example
└── README.md


## Coding constraints and style
- Use Python 3.11+ and FastAPI.
- Use Pydantic for all request/response models.
- Keep modules single-responsibility and dependency-injected.
- No large monolithic files. Each service must expose a clean interface.
- Add unit tests for every key module.
- Logging: structured JSON logs at info/debug/warn.
- No secrets in code; use env variables only.
- Minimal external packages; prefer standard libraries plus:
  - `fastapi`, `uvicorn`, `pydantic`, `faiss-cpu`, `sqlmodel` or `sqlite3`, `openai`, `pdfplumber`, `pymupdf`, `python-multipart`, `requests`, `pytest`.

## Environment variables (must be predecided)
Place copies in `.env` (do not commit).

OPENAI_API_KEY=...
OPENAI_API_BASE=https://api.openai.com/v1
 # optional
OPENAI_EMBED_MODEL=text-embedding-3-large
OPENAI_GEN_MODEL=gpt-4o-mini
VECTOR_DB=faiss
DATABASE_URL=sqlite:///./data/metadata.db
STORAGE_PATH=./data/uploads
MAX_CHUNKS_PER_FILE=2000
RETRIEVAL_TOP_K=5
SIMILARITY_THRESHOLD_HIGH=0.8
SIMILARITY_THRESHOLD_MED=0.6
MIN_SIMILARITY_FOR_CALL=0.35
REFUSAL_PHRASE=Not found in your notes for {subject}


## High-level components and responsibilities
1. **Ingestion Service** (`services/ingestion.py`)
   - Extract pages and text from PDF/TXT.
   - Produce chunks with metadata: `chunk_id`, `file_name`, `page_start`, `page_end`, `text`.
   - Normalization: whitespace, unicode normalization.
   - Save raw files to `STORAGE_PATH`, store metadata in DB.

2. **Embeddings Service** (`services/embeddings.py`)
   - Wrapper around OpenAI embeddings.
   - Batch embeddings, retry logic, rate-limit handling.
   - Optionally cache embeddings for identical chunks.

3. **Vector Retriever** (`services/retriever.py`)
   - Index chunks in FAISS, store mapping `faiss_id -> chunk_id`.
   - Retrieval request MUST be subject-scoped. Implement index per subject or store subject_id in metadata filter.
   - Return top-K chunks with similarity scores.

4. **LLM Client** (`services/llm_client.py`)
   - Two calls:
     - **Generate**: Answer drafting using system prompt (strict JSON schema).
     - **Verify**: Claim entailment and unsupported statements listing. Prompt must return only `YES`/`NO` or a JSON list.
   - Do not allow the model to return free text outside expected schema. Validate in code.

5. **Verifier** (`services/verifier.py`)
   - Two layers:
     - **String-level check**: evidence snippets must appear verbatim in stored chunks (allow minimal trimming).
     - **Entailment check**: For paraphrase, use `LLM Client` to run entailment prompts for atomic claims.
   - If any atomic claim fails -> mark answer as `rejected`.

6. **Grounding Score** (`services/grounding.py`)
   - Inputs: top similarity scores, evidence overlap percentage, unsupported claim count.
   - Output: 0..100 integer with breakdown for UI.

7. **API Routes**
   - `POST /upload` — upload files into a subject.
   - `POST /ask` — subject_id + question -> returns JSON or refusal phrase.
   - `POST /study` — generate MCQs and short answers.
   - `GET /file/:id` — returns file or page-level view with highlight anchors.

## JSON schema for assistant responses (enforce strictly)
```json
{
  "answer": "string",
  "citations": [
    {
      "file": "string",
      "page_start": 1,
      "page_end": 1,
      "chunk_id": "string",
      "score": 0.0
    }
  ],
  "evidence_snippets": ["string"],
  "confidence": "High|Medium|Low",
  "grounding_score": 0
}

If not supported: return only the exact string: Not found in your notes for {subject}

Prompting rules (docs/PROMPTS.md)

Provide canonical system prompt for generation and verification. See docs/PROMPTS.md.

Generation prompt MUST: include only the retrieved chunks in a labeled CONTEXT field, include the QUESTION, and require strict JSON output.

Verification prompt MUST: present atomic claim list and CONTEXT and ask strictly YES/NO per claim.

Verification workflow (micro-level)

Retrieve top-K chunks for subject scope.

If top similarity < MIN_SIMILARITY_FOR_CALL OR no chunk matches simple keyword overlap -> return refusal phrase.

Call Generate to draft answer (LLM receives only retrieved chunks).

Parse generated JSON. Extract atomic claims (simple sentence splitter).

For each claim:

Check verbatim presence in retrieved chunks. If present -> supported.

Else call Verify LLM: "Claim X is supported by CONTEXT? Answer only YES or NO."

If any claim unsupported -> return refusal phrase.

If all supported -> compute grounding score and return accepted JSON.

Grounding score (recommended formula)
top_similarity = s1 (0..1)
support_ratio = supported_atomic_claims / total_atomic_claims
evidence_overlap = percent of answer phrase tokens that map to supporting snippets (0..1)

grounding_score = round( (0.5 * top_similarity + 0.3 * support_ratio + 0.2 * evidence_overlap) * 100 )

Testing checklist (must pass)

Unit tests: ingestion, chunk->page mapping, embedding wrapper, retrieval filter by subject.

Integration tests: ask endpoint returns refusal phrase when no evidence, and valid JSON when evidence present.

Adversarial tests: queries that are true in real world but absent in notes -> refusal.

Study Mode tests: each MCQ correct answer must have citation and explanation from notes.

Implementation guidance for copilot

Break every feature into small tasks before coding.

Implement interfaces first (stubs) and tests that assert behavior (TDD).

Favor clarity of code and testability over micro-optimizations.

Keep prompts in docs/PROMPTS.md and reference them by ID in code.

Avoid printing entire dataset into prompts; send only retrieved chunks.

Suggested milestones (micro-tasks)
Milestone A — Ingestion & storage
A1: File upload endpoint with disk save
A2: PDF page extraction with page numbers
A3: Chunking logic and chunk metadata storage

Milestone B — Embeddings & retrieval
B1: Embedding wrapper & batch embed
B2: FAISS index per subject + mapping table
B3: Retrieval API with subject filter

Milestone C — Generation & enforcement
C1: Implement generate call and strict JSON parser
C2: Implement refusal gating by similarity threshold
C3: Implement verifier pipeline and refusal behavior

Milestone D — Frontend & UX
D1: Chat UI + subject selection (3 subjects enforcement)
D2: Evidence panel + file viewer + highlights
D3: Study Mode UI

Milestone E — Tests & demo
E1: Unit tests for ingestion, retrieval
E2: Integration tests for the full ask pipeline
E3: Demo script & sample notes

## Security & privacy
- Do not send user files outside system except to the LLM provider for embedding/generation. - Log only metadata and hashed file names.
- Use server-side sanitized filenames.
- For PII-sensitive contexts, provide opt-out for sending full text to LLM (but the MVP assumes uploads are allowed).

**Operational notes for the agent**:
If you are asked to “improvise”, prefer conservative changes that preserve the non-hallucination guarantee.

When creating code, include explicit unit tests.

When uncertain about resource limits, implement a configurable MAX_CHUNKS_PER_FILE and pagination for retrieval.


---

API (main endpoints):
POST /upload — multipart upload of file with subject_id.
POST /ask — JSON { "subject_id": "...", "question":"..." } -> returns either:
valid JSON response: answer, citations, evidence_snippets, confidence, grounding_score
or the exact string: Not found in your notes for {Subject}
POST /study — generate MCQs and short answers. Returns structured items with citations.
GET /file/{file_id} — returns file viewer with anchors for page highlighting.

Response format (successful)
{
  "answer":"string",
  "citations":[{"file":"string","page_start":1,"page_end":1,"chunk_id":"string","score":0.86}],
  "evidence_snippets":["exact sentence from source"],
  "confidence":"High",
  "grounding_score":94
}

How the system prevents hallucination (concise):
Subject-scoped retrieval — only chunks from selected subject are retrieved.
Similarity gating — if top similarity below threshold, return refusal.
Strict LLM prompt — generation prompt instructs JSON-only output and "do not use external knowledge".
Post-generation verification — evidence snippets must appear verbatim or pass entailment checks. Any unsupported claim -> refusal.
Grounding score and logs — transparent metrics for judges.
Grounding Score breakdown
Displayed by UI with components:
Top similarity
Suppot ratio (atomic claims supported)
Evidence overlap
Formula documented in docs/PROMPTS.md.

