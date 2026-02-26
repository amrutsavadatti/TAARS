from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialise shared resources
    from backend.storage.cache import get_valkey
    from backend.storage.vector_store import get_vector_store

    app.state.valkey = await get_valkey()
    app.state.vector_store = await get_vector_store()
    yield
    # Shutdown: clean up
    await app.state.valkey.aclose()


app = FastAPI(
    title="Career AI Assistant",
    description="RAG-powered portfolio chatbot API",
    version="0.1.0",
    lifespan=lifespan,
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
