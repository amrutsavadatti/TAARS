# Career AI Assistant — Developer Documentation

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Tech Stack](#3-tech-stack)
4. [Project Structure](#4-project-structure)
5. [Getting Started](#5-getting-started)
6. [Configuration Reference](#6-configuration-reference)
7. [API Endpoints](#7-api-endpoints)
8. [Code Flow — Full Request Lifecycle](#8-code-flow--full-request-lifecycle)
9. [Module Reference](#9-module-reference)
10. [Data Flow Diagrams](#10-data-flow-diagrams)
11. [Key Design Decisions](#11-key-design-decisions)
12. [Valkey Key Reference](#12-valkey-key-reference)
13. [Adding New Documents](#13-adding-new-documents)
14. [What's Built vs What's Coming](#14-whats-built-vs-whats-coming)

---

## 1. Project Overview

A plug-and-play embeddable chatbot widget for portfolio websites. Hiring managers and visitors can ask questions about the owner's career, skills, projects, and education. Answers are grounded exclusively in uploaded documents using RAG (Retrieval-Augmented Generation) — the LLM cannot fabricate information not present in the corpus.

**Design principles:**
- Retrieval quality is the #1 priority — if retrieval is bad, nothing else matters
- Never hallucinate — low confidence → canned "I don't know" response, no LLM call
- Low friction for visitors — no auth required by default, rate limit silently
- Configurable everything — LLM provider, rate limits, theme, agents — all via `.env`
- Free first, paid optional — only the LLM API costs money

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Embeddable Chat Widget (React — Phase 2)                │
│  Shadow DOM · SSE streaming · Session ID · Suggested Qs  │
└──────────────────────┬───────────────────────────────────┘
                       │ HTTPS
┌──────────────────────▼───────────────────────────────────┐
│  FastAPI Backend                                         │
│                                                          │
│  ┌─────────────────┐    ┌──────────────────────────────┐ │
│  │  Middleware      │    │  API Endpoints               │ │
│  │  - Rate limiter  │    │  GET  /api/v1/chat/stream    │ │
│  │  - API key auth  │    │  POST /api/v1/ingest         │ │
│  │  - CORS          │    │  GET  /api/v1/documents      │ │
│  └─────────────────┘    │  DELETE /api/v1/documents/:id│ │
│                          └──────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────────┐ │
│  │  Core RAG Engine                                     │ │
│  │  retriever → prompt_builder → llm_client             │ │
│  └──────────────────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────────┐ │
│  │  Ingestion Pipeline                                  │ │
│  │  parser → chunker → embedder → vector_store          │ │
│  └──────────────────────────────────────────────────────┘ │
└──────────┬───────────────────────────┬────────────────────┘
           │                           │
    ┌──────▼──────┐             ┌──────▼──────┐
    │  ChromaDB   │             │   Valkey    │
    │  Vector DB  │             │  (Redis)    │
    │  Embeddings │             │  Sessions   │
    │  + chunks   │             │  Rate limits│
    └─────────────┘             └─────────────┘
```

---

## 3. Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| API Framework | FastAPI (Python) | Async, native SSE, auto Swagger |
| RAG Orchestration | LangChain | Embedding provider abstraction |
| Vector DB | ChromaDB (embedded) | Free, zero infra for MVP |
| Cache / Sessions | Valkey (Redis fork) | Open-source Redis, same protocol |
| LLM | OpenAI or Anthropic (configurable) | Swap via `.env` |
| Embeddings | OpenAI `text-embedding-3-small` or HuggingFace local | HuggingFace = free fallback |
| Reranking | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Local, free — disabled for small corpora |
| PDF parsing | PyMuPDF (fitz) | Fast, accurate text extraction |
| Image parsing | Vision LLM (GPT-4o-mini / Claude) | Captions certificates and screenshots |
| Text/DOCX parsing | python-docx, built-in | Handles markdown, plain text, Word docs |

---

## 4. Project Structure

```
career-ai-assistant/
├── backend/
│   ├── main.py                  # FastAPI app entry, startup, routers, CORS
│   ├── config.py                # All config via Pydantic Settings from .env
│   │
│   ├── api/
│   │   ├── chat.py              # GET /api/v1/chat/stream (SSE)
│   │   ├── ingest.py            # POST /api/v1/ingest (file upload)
│   │   └── documents.py         # GET/DELETE /api/v1/documents
│   │
│   ├── core/
│   │   ├── rag_engine.py        # Orchestrator: retriever → prompt → LLM → stream
│   │   ├── retriever.py         # Two-stage retrieval: vector search + reranking
│   │   ├── prompt_builder.py    # System prompt assembly + guardrails
│   │   ├── llm_client.py        # OpenAI/Anthropic streaming client
│   │   ├── embeddings.py        # Embedding generation (OpenAI or HuggingFace)
│   │   └── chunker.py           # Resume-aware + prose document chunking
│   │
│   ├── ingestion/
│   │   ├── pipeline.py          # Full ingestion orchestrator
│   │   ├── parser.py            # File type router
│   │   ├── pdf_parser.py        # PDF → text via PyMuPDF
│   │   ├── image_parser.py      # Image → caption via vision LLM
│   │   ├── text_parser.py       # Markdown, plain text, DOCX
│   │   └── models.py            # ParsedDocument dataclass
│   │
│   ├── storage/
│   │   ├── vector_store.py      # ChromaDB abstraction (upsert, search, delete)
│   │   ├── session_store.py     # Conversation history in Valkey
│   │   └── cache.py             # Valkey async client factory
│   │
│   └── middleware/
│       └── rate_limiter.py      # IP/email rate limiting + OTP identity gate
│
├── raw_user_files/              # Drop documents here for ingestion (git-ignored)
├── data/
│   ├── chroma/                  # ChromaDB persistence (git-ignored)
│   └── uploads/                 # Raw uploaded files (git-ignored)
│
├── scripts/
│   └── ingest_all.py            # Bulk ingest everything in raw_user_files/
│
├── docker-compose.yml           # FastAPI + Valkey + ChromaDB
├── Dockerfile
├── requirements.txt
├── .env                         # Your config (git-ignored)
└── .env.example                 # Config template (committed)
```

---

## 5. Getting Started

### Prerequisites
- Python 3.11
- Docker (for Valkey)
- OpenAI or Anthropic API key (for LLM + embeddings)

### Setup

```bash
# 1. Create virtual environment with Python 3.11
uv venv --python 3.11 .venv
source .venv/bin/activate

# 2. Install dependencies
uv pip install -r requirements.txt

# 3. Copy and fill in your config
cp .env.example .env
# Edit .env — at minimum set LLM_API_KEY

# 4. Start Valkey
docker run -d --name valkey -p 6379:6379 valkey/valkey:7-alpine

# 5. Start the API server
uvicorn backend.main:app --reload --port 8000

# 6. Add your documents
# Drop PDFs, markdowns, or text files into raw_user_files/
python scripts/ingest_all.py
```

### Verify it's working

```bash
# Health check
curl http://localhost:8000/health

# Ask a question
curl -N -H "X-API-Key: your-key" \
  "http://localhost:8000/api/v1/chat/stream?q=What+is+your+tech+stack&session_id=test-1"

# View Swagger docs
open http://localhost:8000/docs
```

### Run with Docker Compose

```bash
docker-compose up --build
```

This starts FastAPI (port 8000), Valkey (port 6379), and ChromaDB (port 8001).

---

## 6. Configuration Reference

All config is loaded from `.env` via Pydantic Settings in `backend/config.py`.

### LLM

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openai` | `openai` or `anthropic` |
| `LLM_MODEL` | `gpt-4o-mini` | Model string passed to API |
| `LLM_API_KEY` | — | API key (OpenAI or Anthropic) |
| `EMBEDDING_PROVIDER` | `openai` | `openai` or `huggingface` (free local) |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | For HuggingFace: `all-MiniLM-L6-v2` |

### Retrieval

| Variable | Default | Description |
|----------|---------|-------------|
| `RETRIEVAL_TOP_K` | `5` | Candidates pulled from ChromaDB |
| `ENABLE_RERANKING` | `false` | Cross-encoder reranking (disable for small corpora) |
| `RERANK_TOP_N` | `3` | Chunks kept after reranking |
| `SIMILARITY_THRESHOLD` | `0.62` | Min cosine similarity to keep a chunk [0–1] |

> **Tuning tip:** Career questions typically score 0.65–0.72. Off-topic questions score 0.50–0.58. The default 0.62 threshold cleanly separates them.

### Rate Limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_PER_IP_PER_DAY` | `50` | Questions per IP when OTP is off |
| `RATE_LIMIT_PER_EMAIL_PER_DAY` | `20` | Questions per email when OTP is on |

### OTP Identity Gate

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_OTP_GATE` | `false` | Enable visitor identity collection |
| `OTP_GATE_MODE` | `after_n` | `after_n` = ask after N questions |
| `OTP_GATE_AFTER_N_QUESTIONS` | `1` | Ask on 1st question (0 = before first) |

When OTP gate fires, the widget collects **name** (required), **email** (required), **company** (optional).

### Session

| Variable | Default | Description |
|----------|---------|-------------|
| `SESSION_TTL_MINUTES` | `30` | Session expires after N min of inactivity |
| `SESSION_CONTEXT_WINDOW` | `5` | Last N conversation turns injected into prompt |

### Owner

| Variable | Default | Description |
|----------|---------|-------------|
| `OWNER_NAME` | `Amrut` | Used in system prompt and canned responses |
| `OWNER_CONTACT_EMAIL` | — | Shown in "I don't know" responses |
| `CAL_COM_BOOKING_URL` | — | Cal.com link shown on rate limit screen |

---

## 7. API Endpoints

Interactive docs available at `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc` (ReDoc).

---

### `GET /health`
Health check. No auth required.

**Response:**
```json
{
  "status": "ok",
  "owner": "Amrut",
  "llm_provider": "openai",
  "otp_gate_enabled": false
}
```

---

### `GET /api/v1/chat/stream`

Stream a RAG-powered answer via Server-Sent Events.

**Headers:**
```
X-API-Key: {owner_api_key}
```

**Query params:**
| Param | Required | Description |
|-------|----------|-------------|
| `q` | Yes | Visitor's question (max 1000 chars) |
| `session_id` | No | UUID for conversation continuity. Auto-generated if omitted. |

**Response:** `text/event-stream`

Normal token stream:
```
data: "Amrut"
data: " has worked"
data: " at Media.net"
data: [DONE]
```

Rate limit hit (OTP off — widget renders email capture + Cal.com):
```
event: rate_limit
data: {"message": "You've reached today's question limit!", "show_email_capture": true, "email_capture_label": "...", "cal_com_url": "...", "owner_name": "Amrut"}
data: [DONE]
```

Identity gate triggered (OTP on — widget renders name/email/company form):
```
event: identity_gate
data: {"message": "Before we continue...", "fields": {"name": {...}, "email": {...}, "company": {...}}, "submit_url": "/api/v1/visitor/identify"}
data: [DONE]
```

**Errors:**
| Code | Cause |
|------|-------|
| 401 | Missing X-API-Key header |

---

### `POST /api/v1/ingest`

Upload and ingest documents into the vector store.

**Headers:**
```
X-API-Key: {owner_api_key}
```

**Body:** `multipart/form-data`
```
files: <file>   (repeat for multiple files)
```

**Supported types:** `pdf, png, jpg, jpeg, txt, md, docx`
**Max size:** 10 MB per file (configurable via `MAX_UPLOAD_SIZE_MB`)

**Response:**
```json
{
  "status": "ok",
  "files": [
    {"filename": "Resume.pdf", "doc_id": "abc-123", "chunks_created": 9, "size_mb": 0.09}
  ],
  "total_chunks": 9
}
```

**Errors:**
| Code | Cause |
|------|-------|
| 401 | Missing API key |
| 415 | Unsupported file type |
| 422 | All files failed to ingest |

> **Re-ingestion is safe.** Uploading a file that was previously ingested upserts the chunks — no duplicates.

---

### `GET /api/v1/documents`

List all ingested documents.

**Headers:**
```
X-API-Key: {owner_api_key}
```

**Response:**
```json
{
  "total_documents": 4,
  "total_chunks": 42,
  "documents": [
    {
      "source_file": "Resume.pdf",
      "source_type": "pdf",
      "chunk_count": 9,
      "ingested_at": "2026-02-26T01:16:22.150742+00:00"
    }
  ]
}
```

---

### `DELETE /api/v1/documents/{doc_id}`

Delete a document and all its chunks from the vector store.

**Headers:**
```
X-API-Key: {owner_api_key}
```

**Response:**
```json
{
  "status": "ok",
  "doc_id": "abc-123",
  "chunks_deleted": 9
}
```

**Errors:**
| Code | Cause |
|------|-------|
| 404 | Document not found or already deleted |

---

## 8. Code Flow — Full Request Lifecycle

### Chat request (happy path)

```
Browser: GET /api/v1/chat/stream?q=What+is+your+tech+stack&session_id=abc

1. api/chat.py — chat_stream()
   ├── Validate X-API-Key header
   ├── Extract client IP
   └── Return StreamingResponse(_token_stream())

2. api/chat.py — _token_stream()  [async generator]
   ├── Load history from Valkey
   │     session_store.get_history("abc")
   │     → [{"role": "user", "content": "..."}, ...]
   │
   ├── Check rate limit
   │     rate_limiter.check(session_id, ip)
   │     → RateLimitResult(allowed=True)
   │
   └── Call RAG engine
         rag_engine.stream_answer(question, history, owner_id)

3. core/rag_engine.py — stream_answer()  [async generator]
   ├── retriever.retrieve("What is your tech stack?")
   │     ├── embedder.embed_query(question)        → [0.12, -0.34, ...]
   │     ├── vector_store.similarity_search(...)    → [SearchResult, ...]
   │     └── → [RankedChunk(section="skills", score=0.72), ...]
   │
   ├── chunks not empty → build_prompt(chunks, history, question)
   │     → (system_prompt, user_message)
   │
   └── llm_client.stream_response(system_prompt, user_message)
         → yield "Amrut"
         → yield " uses"
         → yield " React..."

4. api/chat.py — _token_stream() wraps each token:
   → yield 'data: "Amrut"\n\n'
   → yield 'data: " uses"\n\n'
   → yield 'data: [DONE]\n\n'

5. After stream complete:
   ├── session_store.append_turn(session_id, question, full_answer)
   │     → Saves to Valkey, resets 30-min TTL
   └── rate_limiter.increment(session_id, ip)
         → Increments ratelimit:ip:{ip}:{date} counter
```

### Chat request — off-topic (no LLM call)

```
Browser: GET /api/v1/chat/stream?q=What+is+the+capital+of+France

1–2. Same as above...

3. core/rag_engine.py — stream_answer()
   ├── retriever.retrieve("What is the capital of France?")
   │     ├── embed + vector search → chunks with score ~0.50 (below threshold)
   │     └── → []  (empty — no relevant content found)
   │
   └── chunks empty → yield no_context_response()
         → "I don't have information about that in Amrut's documents..."
         No LLM API call made. No cost.

4. api/chat.py wraps canned response as SSE, sends [DONE]
```

### Chat request — rate limit hit

```
Browser: GET /api/v1/chat/stream?q=...  (51st question today)

1–2. Same setup...

3. rate_limiter.check(session_id, ip)
   └── ratelimit:ip:127.0.0.1:2026-02-26 = 50  → at limit
       → RateLimitResult(allowed=False, event_type="rate_limit", payload={...})

4. api/chat.py:
   └── yield 'event: rate_limit\ndata: {...}\n\n'
       yield 'data: [DONE]\n\n'
       return  ← RAG engine never called
```

### Ingestion request

```
curl -F "files=@Resume.pdf" POST /api/v1/ingest

1. api/ingest.py
   ├── Validate API key
   ├── For each file:
   │     ├── Validate extension and size
   │     └── Write to temp file → call ingest_file()
   │
2. ingestion/pipeline.py — ingest_file()
   ├── [1] parser.py → pdf_parser.parse_pdf()
   │         → ParsedDocument(pages=["[Page 1]\nAmrut Savadatti..."], ...)
   │
   ├── [2] core/chunker.py → chunk_document()
   │         ├── Detect resume (has EXPERIENCE + EDUCATION + SKILLS)
   │         └── → [Chunk(section="header"), Chunk(section="experience"), ...]
   │
   ├── [3+4] core/embeddings.py + storage/vector_store.py
   │         ├── embedder.embed_documents([chunk.text, ...])
   │         │     → [[0.12, -0.34, ...], ...]  (one vector per chunk)
   │         └── collection.upsert(ids, documents, embeddings, metadatas)
   │
   └── [5] _save_to_blob()
           → data/uploads/amrut/{doc_id}_Resume.pdf

3. Return: {"status": "ok", "files": [...], "total_chunks": 9}
```

---

## 9. Module Reference

### `backend/config.py`
Single source of truth for all configuration. Uses Pydantic `BaseSettings` — reads from `.env`, falls back to defaults. Access anywhere with `from backend.config import settings`.

### `backend/core/rag_engine.py`
The single entry point for the chat pipeline. Always returns `AsyncGenerator[str, None]`. The chat endpoint doesn't care whether it's streaming real LLM tokens or a canned response.

```python
async for token in stream_answer(question, history, owner_id):
    yield token
```

### `backend/core/retriever.py`
Two-stage pipeline:
1. **Vector search** — fast cosine similarity in ChromaDB, returns top K candidates
2. **Cross-encoder reranking** — optional, uses local model to re-score (disabled by default for small corpora)

Returns `[]` when no chunks pass the similarity threshold — this is the signal to skip the LLM entirely.

### `backend/core/prompt_builder.py`
Assembles the final prompt sent to the LLM. Contains all three hallucination guardrails:
1. **Structural fence** — `<context>` tags, "only use what's inside"
2. **Low-confidence rule** — "say so honestly if insufficient"
3. **Off-topic redirect** — "politely redirect non-career questions"

### `backend/core/llm_client.py`
Provider-agnostic streaming client. Switch between OpenAI and Anthropic by changing `LLM_PROVIDER` in `.env`. Both yield `str` tokens via `async for`.

### `backend/core/chunker.py`
Chunking is **resume-aware**. It detects resume structure and creates one chunk per logical unit (one per job, one per project, etc.). This is critical for retrieval quality — if "Media.net experience" is one chunk, a question about that role retrieves exactly the right context.

### `backend/storage/vector_store.py`
ChromaDB wrapper namespaced by owner. Key design: **one collection per owner** (`career_assistant_{owner_id}`). Multi-tenant by design from day one.

### `backend/storage/session_store.py`
Conversation memory in Valkey. Key: `session:{session_id}`. Value: JSON list of turns. Sliding TTL resets on every message. Trims to last `SESSION_CONTEXT_WINDOW * 2` messages automatically.

### `backend/middleware/rate_limiter.py`
Enforces daily question limits. Two modes:
- **OTP off** — key: `ratelimit:ip:{ip}:{date}`, limit: 50/day
- **OTP on** — key: `ratelimit:email:{email}:{date}`, limit: 20/day

On limit hit, returns a structured `RateLimitResult` that the chat endpoint converts to a named SSE event (not a 429 HTTP error) — this gives the widget full control over the UI response.

---

## 10. Data Flow Diagrams

### Ingestion pipeline

```
raw_user_files/Resume.pdf
        │
        ▼
   parser.py          ← detects file type
        │
        ▼
  pdf_parser.py       ← extracts text page by page
        │
        ▼
ParsedDocument
  pages: ["[Page 1]\nAmrut Savadatti..."]
  source_type: "pdf"
        │
        ▼
   chunker.py         ← resume-aware splitting
        │
        ▼
[Chunk(section="header"),
 Chunk(section="experience"),   ← one per job
 Chunk(section="experience"),
 Chunk(section="skills"),
 Chunk(section="project"),      ← one per project
 Chunk(section="education")]    ← one per degree
        │
        ▼
  embeddings.py       ← vectorise each chunk text
        │
        ▼
[[0.12, -0.34, ...],            ← one 1536-dim vector per chunk
 [0.56, 0.11, ...],
 ...]
        │
        ▼
vector_store.py       ← upsert into ChromaDB
  collection: career_assistant_amrut
        │
        ▼
data/uploads/amrut/{doc_id}_Resume.pdf  ← raw file saved
```

### Retrieval pipeline (per chat message)

```
"What is Amrut's tech stack?"
        │
        ▼
embed_query()         ← embed the question
  → [0.23, -0.11, ...]
        │
        ▼
similarity_search()   ← cosine similarity in ChromaDB
  top_k=5, threshold=0.62
  → [SearchResult(section="skills", score=0.72),
     SearchResult(section="summary", score=0.70),
     SearchResult(section="experience", score=0.68)]
        │
        ▼ (if ENABLE_RERANKING=true)
cross_encoder.predict()
  score each (question, chunk) pair
  → rerank by cross-encoder score
        │
        ▼
[RankedChunk(section="skills",    score=0.72),
 RankedChunk(section="summary",   score=0.70),
 RankedChunk(section="experience",score=0.68)]
```

---

## 11. Key Design Decisions

### SSE over WebSockets
Server-Sent Events give the same token-by-token UX as WebSockets with a simple HTTP GET. No connection management, no reconnection logic, works behind standard load balancers. WebSockets are reserved for bidirectional real-time features we don't need yet.

### Two hallucination prevention layers
1. **Similarity threshold** (code-level) — if the best chunk score is below 0.62, skip the LLM entirely and return a canned response. Zero hallucination risk because the LLM is never called.
2. **System prompt instructions** (model-level) — the LLM is told explicitly to only use `<context>` content and to say so honestly if it can't answer.

### Rate limit returns SSE event, not HTTP 429
Returning `event: rate_limit\ndata: {...}` instead of a `429` response gives the widget complete control over the UI. It can display the email capture form and Cal.com button without a page reload or error state. A `429` would just break the SSE stream with no useful data.

### Cross-encoder reranking disabled by default
The `cross-encoder/ms-marco-MiniLM-L-6-v2` model is trained on MS MARCO web search data. It scores resume/career text poorly (all negative logits). For a small corpus (<100 chunks), vector similarity alone retrieves accurately. Enable reranking when using a domain-appropriate model.

### Multi-tenant from day one
Every vector store collection is named `career_assistant_{owner_id}`. Every chunk carries `owner_id` in metadata. Scaling from personal tool to SaaS requires no data migration.

### Fail open on infrastructure errors
If Valkey is down: session store returns empty history, rate limiter allows the request through. The chat still works — it just loses session memory temporarily. Losing rate limiting briefly is better than blocking all users.

---

## 12. Valkey Key Reference

| Key Pattern | Value | TTL | Purpose |
|-------------|-------|-----|---------|
| `session:{session_id}` | JSON list of `{role, content}` turns | 30 min (sliding) | Conversation memory |
| `ratelimit:ip:{ip}:{date}` | Integer counter | Until midnight UTC | IP-based rate limiting |
| `ratelimit:email:{email}:{date}` | Integer counter | Until midnight UTC | Email-based rate limiting |
| `qcount:{session_id}` | Integer counter | Same as session TTL | OTP gate question counter |

---

## 13. Adding New Documents

### Via script (bulk)
```bash
# Drop files into raw_user_files/
cp my_resume.pdf raw_user_files/
cp projects.md raw_user_files/

# Ingest all
python scripts/ingest_all.py
```

### Via HTTP API
```bash
curl -X POST \
  -H "X-API-Key: your-key" \
  -F "files=@my_resume.pdf" \
  -F "files=@projects.md" \
  http://localhost:8000/api/v1/ingest
```

### Supported file types
| Type | Parser | Chunking strategy |
|------|--------|-------------------|
| PDF (resume) | PyMuPDF | Resume-aware: one chunk per job/project/education entry |
| PDF (generic) | PyMuPDF | Page-based with 80-token overlap |
| Markdown | Built-in | Heading-based sections |
| Plain text | Built-in | Double-newline paragraph groups |
| DOCX | python-docx | Heading style sections |
| Images | Vision LLM | Single chunk (LLM-generated caption) |

### After ingesting new documents
- ChromaDB is updated immediately
- Retrieval uses new chunks on the next chat request
- No server restart required
- Re-ingesting the same file is safe (upsert — no duplicates)

---

## 14. What's Built vs What's Coming

### Built (Phase 1 — Backend) ✅

| Component | File | Status |
|-----------|------|--------|
| Project scaffolding | `main.py`, `config.py`, `docker-compose.yml` | Done |
| PDF parser | `ingestion/pdf_parser.py` | Done |
| Image parser | `ingestion/image_parser.py` | Done |
| Text/MD/DOCX parser | `ingestion/text_parser.py` | Done |
| Resume-aware chunker | `core/chunker.py` | Done |
| Embedding generation | `core/embeddings.py` | Done |
| ChromaDB vector store | `storage/vector_store.py` | Done |
| Ingestion pipeline | `ingestion/pipeline.py` | Done |
| Two-stage retriever | `core/retriever.py` | Done |
| Prompt builder + guardrails | `core/prompt_builder.py` | Done |
| LLM streaming client | `core/llm_client.py` | Done |
| RAG engine orchestrator | `core/rag_engine.py` | Done |
| Chat SSE endpoint | `api/chat.py` | Done |
| Ingest HTTP endpoint | `api/ingest.py` | Done |
| Document management | `api/documents.py` | Done |
| Session store | `storage/session_store.py` | Done |
| Rate limiter | `middleware/rate_limiter.py` | Done |

### Coming Next

| Phase | Component | Description |
|-------|-----------|-------------|
| Phase 2 | React widget | Shadow DOM chat bubble, SSE streaming, suggested questions |
| Phase 2 | OTP gate UI | Name/email/company form in widget |
| Phase 2 | Rate limit screen | Email capture + Cal.com CTA in widget |
| Phase 2 | `POST /api/v1/visitor/lead` | Anonymous email capture after rate limit |
| Phase 2 | `POST /api/v1/visitor/identify` | Visitor identity submission (OTP on) |
| Phase 3 | Intent classifier | Classify visitor as recruiter/developer/student |
| Phase 3 | Follow-up email agent | Auto email high-intent visitors |
| Phase 3 | Owner notification agent | Alert owner of high-intent visitors |
| Phase 3 | Content gap detection | Find unanswered questions weekly |
| Phase 4 | Admin dashboard | Upload docs, view analytics, configure settings |
| Phase 4 | Conversation logging | SQLite/Postgres conversation history |
| Phase 4 | Response caching | Cache common answers in Valkey |
