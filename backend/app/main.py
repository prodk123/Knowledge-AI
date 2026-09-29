"""FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, chat, documents, conversations, observability, approvals, memory, evaluations, users
from app.core.config import settings
from app.core.dependencies import get_vector_store
from app.db.database import check_db_connection, init_db

# Configure structured logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Starting up %s (env: %s)", settings.app_name, settings.app_env)

    # 0. Fail fast if SECRET_KEY is not explicitly set in staging/production
    if not settings.app_env == "development" and len(settings.secret_key) < 32:
        raise RuntimeError(
            "SECRET_KEY must be set via environment variable in staging/production. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )

    # 1. Automatic schema migrations disabled in production
    # In production, schemas must be migrated using `alembic upgrade head`
    logger.info("Skipping automatic init_db(); ensure 'alembic upgrade head' has been run.")
    
    # 2. Ensure Qdrant collection exists
    try:
        vector_store = get_vector_store(settings=settings)
        vector_store.ensure_collection()
    except Exception as e:
        logger.error("Failed to initialize vector store during startup: %s", e)
        # We don't crash here; let the health check report it.

    # 3. Initialize ARQ Redis Pool
    try:
        from arq import create_pool
        from arq.connections import RedisSettings
        from urllib.parse import urlparse
        
        parsed_url = urlparse(settings.redis_url)
        host = parsed_url.hostname or "localhost"
        port = parsed_url.port or 6379
        
        app.state.arq_pool = await create_pool(RedisSettings(host=host, port=port))
        logger.info("ARQ Redis pool initialized")
    except Exception as e:
        logger.warning(f"Failed to initialize ARQ Redis pool (expected in some tests/local runs): {e}")

    yield
    
    if hasattr(app.state, "arq_pool"):
        await app.state.arq_pool.close()
        
    try:
        from app.db.database import engine
        await engine.dispose()
        logger.info("Database engine disposed cleanly")
    except Exception as e:
        logger.error(f"Error disposing database engine: {e}")
    
    logger.info("Shutting down %s", settings.app_name)


# Initialize FastAPI
app = FastAPI(
    title="Enterprise RAG API",
    description="Stage 5: Persistent Conversations and Query Routing",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — driven by settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(observability.router)
app.include_router(approvals.router)
app.include_router(memory.router, prefix="/api/memory", tags=["memory"])
app.include_router(evaluations.router, prefix="/api/evaluations", tags=["evaluations"])


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint. Verifies connectivity to dependencies."""
    db_ok = await check_db_connection()
    
    try:
        vector_store = get_vector_store(settings=settings)
        # Ping Qdrant
        vector_store.client.get_collections()
        qdrant_ok = True
    except Exception:
        qdrant_ok = False

    status = "ok" if db_ok and qdrant_ok else "degraded"
    
    return {
        "status": status,
        "database": "connected" if db_ok else "disconnected",
        "qdrant": "connected" if qdrant_ok else "disconnected",
    }
