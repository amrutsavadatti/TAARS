# Career AI Assistant

An embeddable chatbot widget for portfolio websites. Hiring managers and visitors ask questions about the owner's career, skills, projects, and education. Answers are grounded exclusively in uploaded documents using RAG — the LLM cannot make up information not in the corpus.

**One script tag to embed. Fully self-hosted. Only the LLM API costs money.**

---

## Table of Contents

1. [How It Works](#1-how-it-works)
2. [Architecture](#2-architecture)
3. [Tech Stack](#3-tech-stack)
4. [Project Structure](#4-project-structure)
5. [Getting Started](#5-getting-started)
6. [Embed on Your Website](#6-embed-on-your-website)
7. [Configuration Reference](#7-configuration-reference)
8. [API Endpoints](#8-api-endpoints)
9. [Code Flow](#9-code-flow)
10. [Module Reference](#10-module-reference)
11. [Valkey Key Reference](#11-valkey-key-reference)
12. [Design Decisions](#12-design-decisions)
13. [Adding Documents](#13-adding-documents)
14. [Widget Development](#14-widget-development)
15. [What's Built vs What's Coming](#15-whats-built-vs-whats-coming)

---

## 1. How It Works

```
Visitor asks: "What companies has Amrut worked at?"
      ↓
Widget sends question to FastAPI backend via SSE
      ↓
Backend embeds question → searches ChromaDB → retrieves top chunks
      ↓
Chunks injected into system prompt → LLM streams answer back
      ↓
Widget renders tokens in real time as they arrive
```

Three things keep it from hallucinating:
1. **Similarity threshold** — if no chunk scores above 0.60, the LLM is never called. A canned "I don't know" response goes back instantly.
2. **System prompt guardrails** — LLM is explicitly told to only use the provided context and say so if it can't answer.
3. **Resume-aware chunking** — each job, project, and education entry is its own chunk, so retrieval is precise.

---

## 2. Architecture

```
┌────────────────────────────────────────────────────────┐
│  Embeddable Widget  (widget/dist/widget.iife.js)       │
│                                                        │
│  Shadow DOM · SSE streaming · localStorage session     │
│  Screens: Chat · Identity Gate · Rate Limit            │
└──────────────────────┬─────────────────────────────────┘
                       │ HTTPS  (SSE for chat, REST for leads)
┌──────────────────────▼─────────────────────────────────┐
│  FastAPI Backend  (backend/)                           │
│                                                        │
│  Middleware: rate_limiter · API key auth · CORS        │
│                                                        │
│  Endpoints:                                            │
│   GET  /api/v1/chat/stream   ← SSE token stream       │
│   POST /api/v1/ingest        ← upload documents        │
│   GET  /api/v1/documents     ← list documents          │
│   DELETE /api/v1/documents/:id                         │
│   POST /api/v1/visitor/lead  ← email capture           │
│                                                        │
│  Core RAG:  retriever → prompt_builder → llm_client   │
│  Ingestion: parser → chunker → embedder → vector_store│
└──────┬───────────────────────────┬─────────────────────┘
       │                           │
  ┌────▼────┐                 ┌────▼────┐
  │ChromaDB │                 │ Valkey  │
  │ vectors │                 │sessions │
  │ chunks  │                 │rate lmt │
  └─────────┘                 │ leads   │
                               └─────────┘
```

---

## 3. Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| API | FastAPI (Python, async) | Native SSE, auto Swagger |
| RAG orchestration | LangChain | Embedding provider abstraction |
| Vector DB | ChromaDB (embedded) | Free, no infra for MVP |
| Cache / sessions | Valkey (Redis fork, Linux Foundation) | Open-source Redis, same protocol |
| LLM | OpenAI or Anthropic — configurable via `.env` | Swap without code changes |
| Embeddings | OpenAI `text-embedding-3-small` (default) or HuggingFace local | HuggingFace = fully free fallback |
| Reranking | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Local, free — off by default |
| PDF parsing | PyMuPDF | Fast, accurate |
| Image parsing | Vision LLM (GPT-4o / Claude) | Captions certificates and screenshots |
| Text/DOCX | python-docx, built-in | Markdown, plain text, Word |
| Chat widget | React 18, Vite, TypeScript | Shadow DOM, single IIFE bundle |

---

## 4. Project Structure

```
career-ai-assistant/
├── backend/
│   ├── main.py                  # FastAPI app, startup, routers, CORS
│   ├── config.py                # All config via Pydantic Settings from .env
│   │
│   ├── api/
│   │   ├── chat.py              # GET /api/v1/chat/stream (SSE)
│   │   ├── ingest.py            # POST /api/v1/ingest (file upload)
│   │   ├── documents.py         # GET/DELETE /api/v1/documents
│   │   └── leads.py             # POST /api/v1/visitor/lead (email capture)
│   │
│   ├── core/
│   │   ├── rag_engine.py        # Orchestrator: retriever → prompt → LLM → stream
│   │   ├── retriever.py         # Two-stage retrieval: vector search + reranking
│   │   ├── prompt_builder.py    # System prompt + all hallucination guardrails
│   │   ├── llm_client.py        # OpenAI/Anthropic streaming client
│   │   ├── embeddings.py        # Embedding generation (OpenAI or HuggingFace)
│   │   └── chunker.py           # Resume-aware + prose chunking strategies
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
│       └── rate_limiter.py      # IP/email rate limiting + identity gate events
│
├── widget/
│   ├── src/
│   │   ├── index.tsx            # Web component entry, Shadow DOM setup, data-* config
│   │   ├── ChatWidget.tsx       # Main UI — all screens, SSE state, message list
│   │   ├── components/
│   │   │   ├── MessageList.tsx        # Chat bubbles + typing indicator
│   │   │   ├── SuggestedQuestions.tsx # Starter question chips
│   │   │   ├── IdentityGateScreen.tsx # Name/email/company form
│   │   │   └── RateLimitScreen.tsx    # Cal.com + email capture on limit hit
│   │   ├── hooks/
│   │   │   ├── useSSE.ts        # EventSource wrapper, handles named events
│   │   │   └── useSession.ts    # Session ID + visitor info in localStorage
│   │   └── styles/
│   │       └── widget.css       # All styles injected into Shadow DOM
│   ├── dist/                    # Built bundle (git-ignored, run npm run build)
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts           # IIFE output, process.env.NODE_ENV fix
│
├── scripts/
│   └── ingest_all.py            # Bulk ingest everything in raw_user_files/
│
├── raw_user_files/              # Drop your documents here (git-ignored)
├── data/
│   ├── chroma/                  # ChromaDB persistence (git-ignored)
│   └── uploads/                 # Raw uploaded files (git-ignored)
│
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env                         # Your config (git-ignored)
└── .env.example                 # Config template (committed)
```

---

## 5. Getting Started

### Prerequisites
- Python 3.11 (`uv` recommended)
- Node.js 18+ (for widget build)
- Docker (for Valkey)
- OpenAI or Anthropic API key

### Backend setup

```bash
# 1. Create Python 3.11 virtual environment
uv venv --python 3.11 .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# 2. Install dependencies
uv pip install -r requirements.txt

# 3. Copy config and fill in your values
cp .env.example .env
# Open .env and set at minimum:
#   LLM_API_KEY, OWNER_NAME, OWNER_CONTACT_EMAIL

# 4. Start Valkey (Redis-compatible cache)
docker run -d --name valkey -p 6379:6379 valkey/valkey:7-alpine

# 5. Start the API server
uvicorn backend.main:app --reload --port 8000

# 6. Add your documents and ingest
# Drop Resume.pdf, projects.md, etc. into raw_user_files/
python scripts/ingest_all.py
```

### Verify it's working

```bash
# Health check
curl http://localhost:8000/health

# Ask a question
curl -N \
  -H "X-API-Key: dev-key" \
  "http://localhost:8000/api/v1/chat/stream?q=What+is+your+tech+stack&session_id=test-1"

# Interactive API docs
open http://localhost:8000/docs
```

### Run everything with Docker Compose

```bash
docker-compose up --build
# FastAPI → localhost:8000
# Valkey  → localhost:6379
```

---

## 6. Embed on Your Website

The widget ships as a single JavaScript file. Add one `<script>` tag to any webpage — no npm, no build step, no React dependency required on the host page.

### Basic embed

```html
<script
  src="https://your-domain.com/widget/widget.iife.js"
  data-api-key="your_api_key_here"
  async
></script>
```

The chat bubble appears automatically in the bottom-right corner.

### Full embed with all options

```html
<script
  src="https://your-domain.com/widget/widget.iife.js"
  data-api-key="your_api_key_here"
  data-base-url="https://your-domain.com"
  data-owner-name="Amrut"
  data-theme-primary="#2563eb"
  data-greeting="Hi! I'm Amrut's career assistant. Ask me anything about his experience, skills, or projects."
  data-suggested-qs="What is Amrut's tech stack?,Tell me about his recent projects,What's his education background?"
  async
></script>
```

### `data-*` attribute reference

| Attribute | Required | Default | Description |
|-----------|----------|---------|-------------|
| `data-api-key` | Yes | — | Your API key (any string while auth is stubbed) |
| `data-base-url` | No | Same origin as the script | Backend URL, e.g. `https://api.yourdomain.com` |
| `data-owner-name` | No | `the owner` | Used in the header and greeting |
| `data-theme-primary` | No | `#2563eb` | Primary colour for bubble, header, buttons |
| `data-greeting` | No | Auto-generated from owner name | Opening message shown in the chat panel |
| `data-suggested-qs` | No | Empty | Comma-separated starter questions shown before first message |

### Works on

- Plain HTML pages
- React / Next.js apps (just add the script tag to `<head>` or `<body>`)
- WordPress (paste into footer scripts)
- GitHub Pages
- Any site where you can add a `<script>` tag

### How the widget is isolated

The widget renders inside a [Shadow DOM](https://developer.mozilla.org/en-US/docs/Web/API/Web_components/Using_shadow_DOM). This means:
- **No CSS conflicts** — host page styles don't affect the widget, widget styles don't affect the host page
- **No JS conflicts** — widget React instance is fully contained
- The widget appends itself to `<body>` automatically — no extra HTML element needed

### Rate limiting and visitor flow

When a visitor hits the daily question limit, the widget shows a screen with:
1. **Book a meeting** — links to your Cal.com page (`CAL_COM_BOOKING_URL` in `.env`)
2. **Email capture** — input field where visitor leaves their email; stored in Valkey for follow-up

Default limits: 10 questions per IP per day (configurable via `RATE_LIMIT_PER_IP_PER_DAY`).

---

## 7. Configuration Reference

All config is in `.env`, loaded via `backend/config.py` (Pydantic Settings).

### LLM

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openai` | `openai` or `anthropic` |
| `LLM_MODEL` | `gpt-4o-mini` | Model string. For Anthropic: `claude-sonnet-4-6` |
| `LLM_API_KEY` | — | Your OpenAI or Anthropic key |
| `EMBEDDING_PROVIDER` | `openai` | `openai` or `huggingface` (runs locally, free) |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | For HuggingFace: `all-MiniLM-L6-v2` |

> **Switching providers:** Change `LLM_PROVIDER` and `LLM_MODEL` in `.env`, restart the server. No code changes needed.

### Retrieval

| Variable | Default | Description |
|----------|---------|-------------|
| `RETRIEVAL_TOP_K` | `5` | Candidates pulled from ChromaDB |
| `ENABLE_RERANKING` | `false` | Cross-encoder reranking (disable for small corpora) |
| `RERANK_TOP_N` | `3` | Chunks kept after reranking |
| `SIMILARITY_THRESHOLD` | `0.60` | Min cosine similarity to answer. Below = "I don't know". |

> **Tuning the threshold:** With OpenAI embeddings, career questions score 0.65–0.80, off-topic questions score 0.40–0.55. Default 0.60 cleanly separates them. Lower it if the bot is too conservative; raise it if it's answering off-topic questions.

### Rate limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_PER_IP_PER_DAY` | `10` | Questions per IP (OTP gate off) |
| `RATE_LIMIT_PER_EMAIL_PER_DAY` | `20` | Questions per email (OTP gate on) |

### Identity gate (optional)

When `ENABLE_OTP_GATE=true`, the widget shows a form to collect name, email, and optional company before the visitor can continue chatting after N questions. Enables email-based rate limiting and agentic follow-up.

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_OTP_GATE` | `false` | Enable visitor identity collection |
| `OTP_GATE_MODE` | `after_n` | `upfront` = before first message, `after_n` = after N questions |
| `OTP_GATE_AFTER_N_QUESTIONS` | `1` | How many questions before the gate fires |

### Session

| Variable | Default | Description |
|----------|---------|-------------|
| `SESSION_TTL_MINUTES` | `30` | Session expires after N min of inactivity |
| `SESSION_CONTEXT_WINDOW` | `5` | Last N conversation turns injected into the prompt |

### Owner

| Variable | Default | Description |
|----------|---------|-------------|
| `OWNER_NAME` | `Amrut` | Used in the system prompt and canned responses |
| `OWNER_CONTACT_EMAIL` | — | Shown in "I don't know" responses |
| `CAL_COM_BOOKING_URL` | — | Cal.com link shown on rate limit screen |

### Widget appearance

| Variable | Default | Description |
|----------|---------|-------------|
| `WIDGET_GREETING` | — | Opening message shown when widget opens |
| `WIDGET_THEME_PRIMARY` | `#2563eb` | Primary colour (overridable per-embed via `data-theme-primary`) |
| `SUGGESTED_QUESTIONS` | — | Comma-separated starter questions |

---

## 8. API Endpoints

Interactive docs at `http://localhost:8000/docs` (Swagger UI).

---

### `GET /health`
No auth required.

```json
{ "status": "ok", "owner": "Amrut", "llm_provider": "openai", "otp_gate_enabled": false }
```

---

### `GET /api/v1/chat/stream`

Stream a RAG answer via Server-Sent Events.

**Headers:** `X-API-Key: {key}` or query param `?api_key={key}` (needed for EventSource which can't send headers)

**Query params:**

| Param | Required | Description |
|-------|----------|-------------|
| `q` | Yes | Visitor's question (max 1000 chars) |
| `session_id` | No | UUID for conversation continuity. Auto-generated if omitted. |
| `visitor_email` | No | Set by widget after identity gate completes |
| `visitor_name` | No | Set by widget after identity gate completes |

**Response:** `text/event-stream`

Normal stream:
```
data: "Amrut"
data: " has worked"
data: " at Media.net"
data: [DONE]
```

Rate limit hit:
```
event: rate_limit
data: {"message": "...", "cal_url": "http://...", "contact_email": "...", "owner_name": "Amrut"}
data: [DONE]
```

Identity gate triggered:
```
event: identity_gate
data: {"message": "...", "fields": {...}}
data: [DONE]
```

---

### `POST /api/v1/ingest`

Upload documents into the vector store.

**Headers:** `X-API-Key: {key}`
**Body:** `multipart/form-data` with one or more `files` fields
**Supported:** `pdf, png, jpg, jpeg, txt, md, docx`
**Max size:** 10 MB per file

```json
{
  "status": "ok",
  "files": [
    {"filename": "Resume.pdf", "doc_id": "abc-123", "chunks_created": 9, "size_mb": 0.09}
  ],
  "total_chunks": 9
}
```

Re-uploading the same file is safe — chunks are upserted, no duplicates.

---

### `GET /api/v1/documents`

List all ingested documents.

```json
{
  "total_documents": 4,
  "total_chunks": 33,
  "documents": [
    {"source_file": "Resume.pdf", "source_type": "pdf", "chunk_count": 9, "ingested_at": "..."}
  ]
}
```

---

### `DELETE /api/v1/documents/{doc_id}`

Remove a document and all its chunks.

```json
{ "status": "ok", "doc_id": "abc-123", "chunks_deleted": 9 }
```

---

### `POST /api/v1/visitor/lead`

Store a visitor's email for follow-up. Called by the widget when the visitor submits their email on the rate limit screen.

**Body:**
```json
{ "email": "visitor@example.com", "session_id": "optional-session-uuid" }
```

**Response:**
```json
{ "status": "ok", "message": "Thanks! We'll be in touch." }
```

Emails are stored in Valkey as a deduplicated set under `leads:{owner_id}`. See captured leads:
```bash
redis-cli -p 6379 smembers leads:amrut
```

---

## 9. Code Flow

### Happy path — question answered

```
GET /api/v1/chat/stream?q=What+is+Amrut's+tech+stack

api/chat.py
  ├── Validate API key
  ├── Load session history from Valkey
  ├── Check rate limit → allowed
  └── stream_answer(question, history, owner_id)

core/rag_engine.py
  ├── retriever.retrieve(question)
  │     ├── embedder.embed_query(question)   → [0.23, -0.11, ...]
  │     ├── ChromaDB.similarity_search()     → top 5 chunks
  │     └── Filter by threshold (0.60)       → 3 chunks pass
  │
  ├── build_prompt(chunks, history, question)
  │     → system_prompt (with <context> block + guardrails)
  │
  └── llm_client.stream_response()
        → yield "Amrut"
        → yield " uses React..."

api/chat.py wraps each token → SSE frame → browser
After [DONE]: append_turn() + increment rate counter
```

### Off-topic — no LLM call

```
GET /api/v1/chat/stream?q=What+is+the+capital+of+France

retriever.retrieve() → all chunks score ~0.45 → below threshold → []

rag_engine: chunks empty → yield no_context_response()
  → "I don't have information about that in Amrut's documents..."

LLM never called. Zero API cost.
```

### Rate limit hit

```
GET /api/v1/chat/stream  (11th question today, limit is 10)

rate_limiter.check() → count=10, limit=10 → blocked

yield 'event: rate_limit\ndata: {"cal_url":"...","contact_email":"..."}\n\n'
yield 'data: [DONE]\n\n'

Widget renders RateLimitScreen with Cal.com + email capture form.
RAG engine never called.
```

### Ingestion

```
POST /api/v1/ingest  (Resume.pdf)

api/ingest.py → ingest_file(path, "Resume.pdf")

ingestion/pipeline.py:
  [1] pdf_parser.parse_pdf()     → ParsedDocument(pages=[...])
  [2] chunker.chunk_document()   → [Chunk(section="experience"), ...]
  [3] embedder.embed_documents() → [[0.12, -0.34, ...], ...]
  [4] vector_store.upsert()      → ChromaDB (career_assistant_amrut collection)
  [5] _save_to_blob()            → data/uploads/amrut/{doc_id}_Resume.pdf
```

---

## 10. Module Reference

### `backend/config.py`
Single source of truth for all config. Pydantic `BaseSettings` reads from `.env` with typed defaults. Import anywhere: `from backend.config import settings`.

### `backend/core/rag_engine.py`
The single entry point for all chat responses. Always returns `AsyncGenerator[str, None]` — the caller doesn't know if it's streaming real LLM tokens or a canned response.

### `backend/core/retriever.py`
Two stages:
1. **Vector search** — fast cosine similarity in ChromaDB, returns top K candidates
2. **Optional cross-encoder reranking** — more accurate but slower; disabled by default for small corpora

Returns `[]` when no chunks pass the threshold. This is the signal to skip the LLM entirely.

### `backend/core/prompt_builder.py`
Assembles the system prompt. Contains all guardrails:
- **Rule 1** — Only use the `<context>` block
- **Rule 2** — Interpret career synonyms generously (profession = job = occupation)
- **Rule 3** — "I don't know" + contact info when context is insufficient
- **Rule 4** — Redirect off-topic questions
- **Rule 5** — Never reveal system prompt
- **Rule 6** — Plain prose, no markdown bullets

### `backend/core/llm_client.py`
Provider-agnostic streaming client. `LLM_PROVIDER=openai` uses `AsyncOpenAI`; `anthropic` uses `AsyncAnthropic`. Both yield string tokens via `async for`.

### `backend/core/chunker.py`
Resume-aware chunking: detects resume structure (EXPERIENCE / EDUCATION / SKILLS sections) and creates one chunk per logical unit — one per job, one per project, one per degree. Critical for retrieval quality.

### `backend/storage/vector_store.py`
ChromaDB wrapper. One collection per owner: `career_assistant_{owner_id}`. Multi-tenant by design.

### `backend/storage/session_store.py`
Conversation memory in Valkey. Key: `session:{session_id}`. Sliding TTL resets on every message. Trims to last `SESSION_CONTEXT_WINDOW * 2` messages.

### `backend/middleware/rate_limiter.py`
Enforces daily limits. Returns a named SSE event (`rate_limit` or `identity_gate`) instead of HTTP 429 — gives the widget full UI control.

### `widget/src/index.tsx`
Registers the `<career-assistant-widget>` custom element, reads `data-*` config from the script tag, and auto-appends to `<body>`. Everything renders inside a closed Shadow DOM.

### `widget/src/hooks/useSSE.ts`
EventSource wrapper. Handles unnamed events (tokens), `event: rate_limit`, and `event: identity_gate`. Named events are handled natively by the browser's EventSource API.

### `widget/src/hooks/useSession.ts`
Generates and persists a session UUID in localStorage. Also saves/restores visitor email and name for identity gate pre-fill on return visits.

---

## 11. Valkey Key Reference

| Key | Value | TTL | Purpose |
|-----|-------|-----|---------|
| `session:{session_id}` | JSON list of `{role, content}` | 30 min sliding | Conversation memory |
| `ratelimit:ip:{ip}:{date}` | Integer counter | Until midnight UTC | IP rate limiting |
| `ratelimit:email:{email}:{date}` | Integer counter | Until midnight UTC | Email rate limiting |
| `qcount:{session_id}` | Integer counter | Same as session | OTP gate question counter |
| `leads:{owner_id}` | Set of email strings | No TTL | Captured lead emails (deduped) |
| `leads:meta:{email}` | Hash: `session_id, captured_at, owner_id` | No TTL | Lead metadata |

---

## 12. Design Decisions

### SSE over WebSockets
SSE is one-directional HTTP — same streaming UX with no connection management, reconnection logic, or load balancer complications. WebSockets only if we ever need bidirectional real-time features.

### Rate limit returns SSE event, not HTTP 429
A 429 would crash the EventSource stream with no useful data. A named `event: rate_limit` gives the widget full control to render the Cal.com button and email capture form while the stream closes gracefully.

### Two hallucination prevention layers
1. **Threshold gate (code)** — below 0.60 similarity, LLM is never called. Zero cost, zero hallucination risk.
2. **System prompt (model)** — LLM instructed to only use provided context.

The first layer catches factually off-topic questions ("capital of France"). The second layer handles edge cases where chunks are retrieved but the LLM might extrapolate.

### Cross-encoder reranking disabled by default
`ms-marco-MiniLM-L-6-v2` is trained on web search data and scores resume text poorly (all negative logits). For a small corpus, vector similarity alone retrieves well. Enable with a domain-appropriate model when corpus grows.

### Fail open on infrastructure errors
Valkey down → session store returns empty history → rate limiter allows request → chat still works. Losing session memory or rate limiting temporarily is better than taking the whole chatbot offline.

### Multi-tenant by design
Every ChromaDB collection, every Valkey key, and every chunk metadata field is namespaced by `owner_id`. Scaling from single portfolio to SaaS requires no data migration.

---

## 13. Adding Documents

### Via bulk script (recommended for initial setup)

```bash
# Drop files into raw_user_files/
cp Resume.pdf raw_user_files/
cp projects.md raw_user_files/
cp certifications/ raw_user_files/

# Ingest all
source .venv/bin/activate
python scripts/ingest_all.py
```

### Via API

```bash
curl -X POST \
  -H "X-API-Key: your-key" \
  -F "files=@Resume.pdf" \
  -F "files=@projects.md" \
  http://localhost:8000/api/v1/ingest
```

### Supported types and chunking strategy

| Type | Parser | Chunking |
|------|--------|----------|
| PDF (resume) | PyMuPDF | Resume-aware: one chunk per job/project/education |
| PDF (generic) | PyMuPDF | Page-based with 80-token overlap |
| Markdown | Built-in | Heading-based sections |
| Plain text | Built-in | Double-newline paragraphs |
| DOCX | python-docx | Heading style sections |
| Images | Vision LLM | Single caption chunk |

Re-ingesting the same file is safe (upsert — no duplicates). Retrieval works immediately after ingestion; no server restart needed.

### After ingesting — verify retrieval

```bash
source .venv/bin/activate
python - <<'EOF'
from backend.core.retriever import Retriever
r = Retriever()
chunks = r.retrieve("What is your tech stack?")
for c in chunks:
    print(f"score={c.score:.3f}  {c.text[:100]}...")
EOF
```

---

## 14. Widget Development

### Build

```bash
cd widget
npm install
npm run build
# Output: widget/dist/widget.iife.js
```

### Dev server (with hot reload)

```bash
cd widget
npm run dev
# Widget dev server on localhost:5173
# Proxies /api/* to localhost:8000
# Open localhost:5173 directly for component development
```

### Test the embed locally

```bash
# Serve the widget directory
npx serve widget -l 5173
# Open http://localhost:5173/test.html
# The test page embeds widget/dist/widget.iife.js pointing at localhost:8000
```

### Widget config flow

```
<script data-api-key="..." data-theme-primary="#2563eb">
    ↓
index.tsx: readConfig()        reads data-* attributes from script tag
    ↓
index.tsx: connectedCallback() creates Shadow DOM, mounts React
    ↓
ChatWidget receives WidgetConfig props
    ↓
useSSE sends: GET /api/v1/chat/stream?q=...&api_key=...
(api_key as query param because EventSource can't send headers)
```

### Adding a new screen

1. Create `widget/src/components/NewScreen.tsx`
2. Add new screen name to the `Screen` type in `ChatWidget.tsx`
3. Add the SSE event or condition that triggers it
4. Render it in the `{screen === "new_screen" && <NewScreen />}` block
5. Add any new styles to `widget/src/styles/widget.css`
6. Run `npm run build`

---

## 15. What's Built vs What's Coming

### Backend ✅

| Component | File |
|-----------|------|
| FastAPI app, CORS, startup | `main.py`, `config.py` |
| PDF parser | `ingestion/pdf_parser.py` |
| Image parser (vision LLM) | `ingestion/image_parser.py` |
| Text / Markdown / DOCX parser | `ingestion/text_parser.py` |
| Resume-aware chunker | `core/chunker.py` |
| OpenAI / HuggingFace embeddings | `core/embeddings.py` |
| ChromaDB vector store | `storage/vector_store.py` |
| Full ingestion pipeline | `ingestion/pipeline.py` |
| Two-stage retriever | `core/retriever.py` |
| Prompt builder + guardrails | `core/prompt_builder.py` |
| OpenAI + Anthropic streaming LLM | `core/llm_client.py` |
| RAG engine orchestrator | `core/rag_engine.py` |
| Chat SSE endpoint | `api/chat.py` |
| Ingest endpoint | `api/ingest.py` |
| Document management | `api/documents.py` |
| Visitor lead capture | `api/leads.py` |
| Session store (Valkey) | `storage/session_store.py` |
| Rate limiter + identity gate | `middleware/rate_limiter.py` |

### Widget ✅

| Component | File |
|-----------|------|
| Shadow DOM web component | `src/index.tsx` |
| Main chat UI | `src/ChatWidget.tsx` |
| Message list + typing indicator | `src/components/MessageList.tsx` |
| Suggested starter questions | `src/components/SuggestedQuestions.tsx` |
| Identity gate (name/email/company) | `src/components/IdentityGateScreen.tsx` |
| Rate limit screen + email capture | `src/components/RateLimitScreen.tsx` |
| SSE hook (tokens + named events) | `src/hooks/useSSE.ts` |
| Session + visitor persistence | `src/hooks/useSession.ts` |
| Shadow DOM scoped styles | `src/styles/widget.css` |

### Coming Next

| Phase | Component | Description |
|-------|-----------|-------------|
| Phase 3 | Conversation logging (SQLite) | Persist all chats for analysis and agents |
| Phase 3 | Intent classifier agent | Label visitor as recruiter / hiring manager / developer after session ends |
| Phase 3 | Owner notification agent | Ping owner when a high-intent visitor finishes chatting |
| Phase 3 | Follow-up email agent | Send warm email from owner to high-intent visitors 1–2 hours later |
| Phase 3 | Content gap detection | Find questions the bot couldn't answer — tell owner what to add |
| Phase 4 | Admin dashboard | Upload docs, view leads, configure settings — no CLI needed |
| Phase 4 | Response caching | Cache common question answers in Valkey — instant responses, zero LLM cost |
| Phase 4 | Weekly digest agent | Email owner every Monday: visitors, intents, top questions |
