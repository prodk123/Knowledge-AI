"""FastAPI dependency injection providers."""

from collections.abc import AsyncGenerator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings, Settings
from app.db.database import async_session_factory
from app.models.auth import User
from app.services.auth_service import AuthService
from app.rag.embeddings import EmbeddingProvider, get_embedding_provider, OpenAICompatibleEmbeddingProvider
from app.rag.retriever import RetrievalOrchestrator
from app.rag.dense_retriever import DenseRetriever
from app.rag.bm25_retriever import BM25Retriever
from app.rag.reranker import FlashRankReranker
from app.rag.vector_store import QdrantVectorStore
from app.rag.prompt import ContextBuilder
from app.services.generation_service import GenerationService
from app.services.ingestion_service import IngestionService
from app.rag.pipeline import RAGPipeline


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session per request."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_auth_service(db: AsyncSession = Depends(get_db_session)) -> AuthService:
    return AuthService(db)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    """Validate JWT and fetch the current user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    import uuid
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    user = await auth_service.get_user_by_id(user_id)
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
        
    return user


def get_settings() -> Settings:
    return settings


# --- Singleton-style component providers ---
# These are created once and reused across requests.

_embedding_provider = None
_vector_store = None
_dense_retriever = None
_bm25_retriever = None
_reranker = None
_retrieval_orchestrator = None
_context_builder = None
_generation_service = None
_rag_pipeline = None
_ingestion_service = None


def get_embedding_provider_dep() -> EmbeddingProvider:
    global _embedding_provider
    if _embedding_provider is None:
        _embedding_provider = get_embedding_provider(settings)
    return _embedding_provider


def get_vector_store(settings: Settings = Depends(get_settings)) -> QdrantVectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = QdrantVectorStore(settings)
        _vector_store.ensure_collection()
    return _vector_store


def get_dense_retriever(
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider_dep),
    vector_store: QdrantVectorStore = Depends(get_vector_store),
) -> DenseRetriever:
    global _dense_retriever
    if _dense_retriever is None:
        _dense_retriever = DenseRetriever(embedding_provider, vector_store)
    return _dense_retriever


def get_bm25_retriever(
    settings: Settings = Depends(get_settings),
) -> BM25Retriever:
    global _bm25_retriever
    if _bm25_retriever is None:
        _bm25_retriever = BM25Retriever(settings)
    return _bm25_retriever


def get_reranker(
    settings: Settings = Depends(get_settings),
) -> FlashRankReranker:
    global _reranker
    if _reranker is None:
        _reranker = FlashRankReranker(settings)
    return _reranker


def get_retrieval_orchestrator(
    settings: Settings = Depends(get_settings),
    dense_retriever: DenseRetriever = Depends(get_dense_retriever),
    bm25_retriever: BM25Retriever = Depends(get_bm25_retriever),
    reranker: FlashRankReranker = Depends(get_reranker),
) -> RetrievalOrchestrator:
    global _retrieval_orchestrator
    if _retrieval_orchestrator is None:
        _retrieval_orchestrator = RetrievalOrchestrator(
            settings=settings,
            dense_retriever=dense_retriever,
            bm25_retriever=bm25_retriever,
            reranker=reranker,
        )
    return _retrieval_orchestrator


def get_context_builder() -> ContextBuilder:
    global _context_builder
    if _context_builder is None:
        _context_builder = ContextBuilder()
    return _context_builder


def get_generation_service() -> GenerationService:
    global _generation_service
    if _generation_service is None:
        _generation_service = GenerationService(settings)
    return _generation_service


_guardrail_engine = None

def get_guardrail_engine(generation_service: GenerationService = Depends(get_generation_service)):
    from app.core.guardrails.engine import GuardrailEngine
    from app.core.guardrails.input.normalization import InputNormalizationGuardrail
    from app.core.guardrails.input.secrets import SecretDetectionGuardrail
    from app.core.guardrails.input.prompt_injection import PromptInjectionGuardrail
    from app.core.guardrails.context.indirect_injection import IndirectInjectionGuardrail
    from app.core.guardrails.output.secrets import OutputSecretGuardrail
    from app.core.guardrails.output.grounding import GroundingGuardrail
    from app.core.guardrails.output.citations import CitationGuardrail
    
    global _guardrail_engine
    if _guardrail_engine is None:
        input_guardrails = [
            InputNormalizationGuardrail(),
            SecretDetectionGuardrail(),
            PromptInjectionGuardrail(generation_service)
        ]
        context_guardrails = [
            IndirectInjectionGuardrail()
        ]
        output_guardrails = [
            OutputSecretGuardrail(),
            GroundingGuardrail(generation_service),
            CitationGuardrail()
        ]
        _guardrail_engine = GuardrailEngine(
            input_guardrails=input_guardrails,
            context_guardrails=context_guardrails,
            output_guardrails=output_guardrails
        )
    return _guardrail_engine


def get_rag_pipeline(
    retrieval_orchestrator: RetrievalOrchestrator = Depends(get_retrieval_orchestrator),
    context_builder: ContextBuilder = Depends(get_context_builder),
    generation_service: GenerationService = Depends(get_generation_service),
    guardrail_engine = Depends(get_guardrail_engine)
) -> RAGPipeline:
    global _rag_pipeline
    if _rag_pipeline is None:
        _rag_pipeline = RAGPipeline(
            retriever=retrieval_orchestrator,
            context_builder=context_builder,
            generation_service=generation_service,
            guardrail_engine=guardrail_engine
        )
    return _rag_pipeline


_query_router = None
_query_rewriter = None
_direct_llm_service = None

def get_query_router(generation_service: GenerationService = Depends(get_generation_service)):
    from app.rag.router import QueryRouter
    global _query_router
    if _query_router is None:
        _query_router = QueryRouter(generation_service)
    return _query_router

def get_query_rewriter(generation_service: GenerationService = Depends(get_generation_service)):
    from app.rag.rewriter import ContextualQueryRewriter
    global _query_rewriter
    if _query_rewriter is None:
        _query_rewriter = ContextualQueryRewriter(generation_service)
    return _query_rewriter

def get_direct_llm_service(
    generation_service: GenerationService = Depends(get_generation_service),
    guardrail_engine = Depends(get_guardrail_engine)
):
    from app.services.direct_llm_service import DirectLLMService
    global _direct_llm_service
    if _direct_llm_service is None:
        _direct_llm_service = DirectLLMService(generation_service, guardrail_engine)
    return _direct_llm_service

_tool_registry = None
_tool_executor = None

def get_email_provider(settings: Settings = Depends(get_settings)):
    if settings.email_provider_mode == "sandbox":
        from app.services.email.sandbox import SandboxEmailProvider
        return SandboxEmailProvider()
    else:
        # Fallback to sandbox if misconfigured or unknown
        from app.services.email.sandbox import SandboxEmailProvider
        return SandboxEmailProvider()


def get_tool_registry(
    retrieval_orchestrator = Depends(get_retrieval_orchestrator),
    email_provider = Depends(get_email_provider),
    vector_store = Depends(get_vector_store)
):
    global _tool_registry
    if _tool_registry is None:
        from app.agent.tools.registry import ToolRegistry
        from app.agent.tools.impl.enterprise_search import EnterpriseSearchTool
        from app.agent.tools.impl.calculator import CalculatorTool
        from app.agent.tools.impl.document_lookup import DocumentLookupTool
        from app.agent.tools.impl.conversation_search import ConversationSearchTool
        from app.agent.tools.impl.send_email import SendEmailTool
        from app.agent.tools.impl.web_search import WebSearchTool
        from app.agent.tools.impl.web_fetch import WebFetchTool
        from app.agent.tools.impl.calendar_search import CalendarSearchTool
        from app.agent.tools.impl.calendar_create_event import CalendarCreateEventTool
        from app.db.database import async_session_factory
        
        _tool_registry = ToolRegistry()
        
        # Register Tools
        _tool_registry.register(EnterpriseSearchTool(retrieval_orchestrator))
        _tool_registry.register(CalculatorTool())
        _tool_registry.register(DocumentLookupTool(vector_store))
        _tool_registry.register(ConversationSearchTool(async_session_factory))
        _tool_registry.register(SendEmailTool(email_provider))
        _tool_registry.register(WebSearchTool())
        _tool_registry.register(WebFetchTool())
        _tool_registry.register(CalendarSearchTool())
        _tool_registry.register(CalendarCreateEventTool())
        
    return _tool_registry


def get_tool_executor(
    registry = Depends(get_tool_registry),
    guardrail_engine = Depends(get_guardrail_engine)
):
    global _tool_executor
    if _tool_executor is None:
        from app.agent.tools.executor import ToolExecutor
        from app.agent.tools.auth import ToolAuthorizationEngine
        from app.agent.tools.policy import ToolPolicyEngine
        from app.services.approval_service import ApprovalService
        from app.db.database import async_session_factory
        
        # Note: In a real async setup we'd pass a session generator, 
        # but the tool executor is a long-lived object here, so we instantiate 
        # a lightweight proxy or let the executor create temporary sessions.
        # For this setup, we'll initialize the service on-demand in the executor
        # or pass the factory. Let's pass an ApprovalService wrapper or pass the factory.
        class ApprovalServiceWrapper:
            async def get_pending_approval(self, *args, **kwargs):
                async with async_session_factory() as session:
                    service = ApprovalService(session)
                    return await service.get_pending_approval(*args, **kwargs)
                    
            async def create_approval_request(self, *args, **kwargs):
                async with async_session_factory() as session:
                    service = ApprovalService(session)
                    return await service.create_approval_request(*args, **kwargs)
                    
            async def consume_approval(self, *args, **kwargs):
                async with async_session_factory() as session:
                    service = ApprovalService(session)
                    return await service.consume_approval(*args, **kwargs)
                    
        approval_service = ApprovalServiceWrapper()
        policy_engine = ToolPolicyEngine()
        auth_engine = ToolAuthorizationEngine()
        
        _tool_executor = ToolExecutor(
            registry=registry,
            auth_engine=auth_engine,
            guardrail_engine=guardrail_engine,
            policy_engine=policy_engine,
            approval_service=approval_service
        )
    return _tool_executor
_memory_retriever = None

def get_memory_retriever(
    embedding_provider = Depends(get_embedding_provider_dep)
):
    from app.agent.memory.retriever import MemoryRetriever
    global _memory_retriever
    if _memory_retriever is None:
        _memory_retriever = MemoryRetriever(embedding_provider)
    return _memory_retriever

def get_memory_service(
    session = Depends(get_db_session),
    embedding_provider = Depends(get_embedding_provider_dep)
):
    from app.services.memory_service import MemoryService
    return MemoryService(session, embedding_provider)


def get_agent_orchestrator(
    generation_service: GenerationService = Depends(get_generation_service),
    registry = Depends(get_tool_registry),
    executor = Depends(get_tool_executor),
    memory_retriever = Depends(get_memory_retriever),
    memory_service = Depends(get_memory_service)
):
    from app.agent.orchestrator import AgentOrchestrator
    def orchestrator_factory(allowed_roles: list[str]) -> AgentOrchestrator:
        return AgentOrchestrator(
            generation_service=generation_service,
            registry=registry,
            executor=executor,
            allowed_roles=allowed_roles,
            memory_retriever=memory_retriever,
            memory_service=memory_service
        )
    return orchestrator_factory


def get_ingestion_service(
    settings: Settings = Depends(get_settings),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider_dep),
    vector_store: QdrantVectorStore = Depends(get_vector_store),
    bm25_retriever: BM25Retriever = Depends(get_bm25_retriever),
) -> IngestionService:
    global _ingestion_service
    if _ingestion_service is None:
        _ingestion_service = IngestionService(
            settings=settings,
            embedding_provider=embedding_provider,
            vector_store=vector_store,
            bm25_retriever=bm25_retriever,
        )
    return _ingestion_service
