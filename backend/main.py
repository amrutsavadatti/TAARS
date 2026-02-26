from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialise shared resources
    from backend.storage.cache import get_valkey
    from backend.storage.vector_store import get_vector_store
    from backend.storage.session_store import get_session_store
    from backend.middleware.rate_limiter import get_rate_limiter

    app.state.valkey = await get_valkey()
    app.state.vector_store = get_vector_store()
    app.state.session_store = await get_session_store()
    app.state.rate_limiter = get_rate_limiter(app.state.valkey)
    yield
    # Shutdown: clean up
    await app.state.valkey.aclose()


app = FastAPI(
    title="Career AI Assistant API",
    description="""
## RAG-powered portfolio chatbot backend

This API powers an embeddable career assistant widget for portfolio websites.
Visitors ask questions about the owner's career, skills, projects, and education.
Answers are grounded exclusively in uploaded documents — no hallucination.

### Key features
- **Streaming chat** via Server-Sent Events (SSE)
- **RAG pipeline**: vector search → optional reranking → LLM streaming
- **Session memory**: multi-turn conversations via Valkey
- **Rate limiting**: IP-based (OTP off) or email-based (OTP on)
- **Identity gate**: optional visitor identification before chatting
- **Document management**: ingest, list, delete

### Authentication
All endpoints require `X-API-Key` header.
Owner-only endpoints (ingest, documents) will require a JWT admin token in production.

### SSE event types (chat endpoint)
| Event | Meaning |
|-------|---------|
| *(unnamed)* `data: "token"` | Regular response token |
| `event: rate_limit` | Daily limit hit — widget shows CTA screen |
| `event: identity_gate` | OTP gate triggered — widget shows name/email form |
| `data: [DONE]` | Stream complete |
""",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS — permissive for local dev; lock down per owner domain in production
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers (imported here; implemented in later tasks)
# ---------------------------------------------------------------------------
from backend.api.chat import router as chat_router
from backend.api.ingest import router as ingest_router
from backend.api.documents import router as documents_router

app.include_router(chat_router, prefix="/api/v1")
app.include_router(ingest_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["health"])
async def health():
    return {
        "status": "ok",
        "owner": settings.owner_name,
        "llm_provider": settings.llm_provider,
        "otp_gate_enabled": settings.enable_otp_gate,
    }


@app.get("/", tags=["health"])
async def root():
    return {"message": f"Career AI Assistant for {settings.owner_name} — see /docs"}
