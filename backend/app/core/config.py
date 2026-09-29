"""Centralized application configuration using Pydantic Settings."""

import secrets
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All configuration is centralized here. No module should call os.getenv() directly.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "enterprise-rag"
    app_env: str = "development"
    log_level: str = "INFO"

    # --- Security / JWT ---
    # REQUIRED in staging and production — must be set via SECRET_KEY env var.
    # In development a random key is generated per process (tokens do not survive restart).
    secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # --- CORS ---
    # Comma-separated list of allowed origins.
    # Example: http://localhost:3000,https://app.example.com
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @field_validator("secret_key", mode="after")
    @classmethod
    def _ensure_secret_key(cls, v: str) -> str:
        """Generate a random key in development; require one in staging/production."""
        if not v:
            # We cannot read app_env here (not yet available), so we always generate.
            # The startup event in main.py will raise if env != development and key is empty.
            return secrets.token_hex(32)
        return v

    # --- PostgreSQL ---
    database_url: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/enterprise_rag"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800

    # --- Redis ---
    redis_url: str = "redis://redis:6379/0"

    # --- Qdrant ---
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "enterprise_documents"

    # --- Embeddings ---
    embedding_provider: str = "openrouter"
    embedding_model: str = "liquid/lfm-2.5-embedding-350m:free"
    embedding_dimension: int = 1024

    # --- LLM (OpenRouter via OpenAI-compatible API) ---
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: str = "your-openrouter-api-key-here"
    llm_model: str = "google/gemma-3-27b-it:free"

    # --- Chunking ---
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # --- Retrieval & Reranking (Stage 2) ---
    retrieval_mode: str = "hybrid_reranked"  # dense, bm25, hybrid, hybrid_reranked
    dense_top_k: int = 20
    bm25_top_k: int = 20
    rrf_k: int = 60
    hybrid_candidate_k: int = 30
    final_top_k: int = 5
    reranker_model: str = "ms-marco-MiniLM-L-12-v2"
    reranker_device: str = "cpu"
    enable_retrieval_debug: bool = False

    # --- File Storage ---
    upload_dir: str = "data/uploads"

    # --- Email Action Settings ---
    email_provider_mode: str = "sandbox" # sandbox, smtp, etc.
    email_max_recipients: int = 5
    email_max_subject_len: int = 255
    email_max_body_len: int = 10000

    # --- Agent Workflow Settings (Stage 8.5) ---
    max_plan_steps: int = 10
    max_plan_depth: int = 10
    max_step_retries: int = 2
    max_replans: int = 2
    max_workflow_seconds: int = 300
    # --- External Tool Settings (Stage 8.6) ---
    web_provider: str = "sandbox" # sandbox, duckduckgo
    web_search_max_results: int = 5
    web_max_fetch_bytes: int = 500 * 1024 # 500 KB limit
    web_max_redirects: int = 3
    
    calendar_provider_mode: str = "sandbox"
    calendar_max_attendees: int = 10
    calendar_max_duration_hours: int = 8

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


# Singleton instance
settings = Settings()
