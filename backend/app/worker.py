"""ARQ background worker — durable async agent job execution.

Uses the same AgentOrchestrator and dependency graph as the API path.
Secrets and dependencies are resolved at worker startup from environment.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any

from arq.connections import RedisSettings
from urllib.parse import urlparse

from app.core.config import settings
from app.db.database import async_session_factory
from app.models.job import BackgroundJob, JobStatus

logger = logging.getLogger(__name__)


def _build_orchestrator_deps():
    """
    Build the same dependency graph used by the API path.
    Returns (generation_service, tool_registry, tool_executor, memory_retriever, memory_service_factory).
    """
    from app.services.generation_service import GenerationService
    from app.rag.embeddings import get_embedding_provider
    from app.rag.vector_store import QdrantVectorStore
    from app.rag.dense_retriever import DenseRetriever
    from app.rag.bm25_retriever import BM25Retriever
    from app.rag.reranker import FlashRankReranker
    from app.rag.retriever import RetrievalOrchestrator
    from app.agent.tools.registry import ToolRegistry
    from app.agent.tools.executor import ToolExecutor
    from app.agent.tools.auth import ToolAuthorizationEngine
    from app.agent.tools.policy import ToolPolicyEngine
    from app.agent.tools.impl.enterprise_search import EnterpriseSearchTool
    from app.agent.tools.impl.calculator import CalculatorTool
    from app.agent.tools.impl.document_lookup import DocumentLookupTool
    from app.agent.tools.impl.conversation_search import ConversationSearchTool
    from app.agent.tools.impl.send_email import SendEmailTool
    from app.agent.tools.impl.web_search import WebSearchTool
    from app.agent.tools.impl.web_fetch import WebFetchTool
    from app.agent.tools.impl.calendar_search import CalendarSearchTool
    from app.agent.tools.impl.calendar_create_event import CalendarCreateEventTool
    from app.agent.memory.retriever import MemoryRetriever
    from app.services.approval_service import ApprovalService
    from app.services.email.sandbox import SandboxEmailProvider
    from app.core.guardrails.engine import GuardrailEngine
    from app.core.guardrails.input.normalization import InputNormalizationGuardrail
    from app.core.guardrails.input.secrets import SecretDetectionGuardrail
    from app.core.guardrails.input.prompt_injection import PromptInjectionGuardrail
    from app.core.guardrails.context.indirect_injection import IndirectInjectionGuardrail
    from app.core.guardrails.output.secrets import OutputSecretGuardrail
    from app.core.guardrails.output.grounding import GroundingGuardrail
    from app.core.guardrails.output.citations import CitationGuardrail

    generation_service = GenerationService(settings)
    embedding_provider = get_embedding_provider(settings)
    vector_store = QdrantVectorStore(settings)
    vector_store.ensure_collection()

    dense_retriever = DenseRetriever(embedding_provider, vector_store)
    bm25_retriever = BM25Retriever(settings)
    reranker = FlashRankReranker(settings)
    retrieval_orchestrator = RetrievalOrchestrator(
        settings=settings,
        dense_retriever=dense_retriever,
        bm25_retriever=bm25_retriever,
        reranker=reranker,
    )

    guardrail_engine = GuardrailEngine(
        input_guardrails=[
            InputNormalizationGuardrail(),
            SecretDetectionGuardrail(),
            PromptInjectionGuardrail(generation_service),
        ],
        context_guardrails=[IndirectInjectionGuardrail()],
        output_guardrails=[
            OutputSecretGuardrail(),
            GroundingGuardrail(generation_service),
            CitationGuardrail(),
        ],
    )

    email_provider = SandboxEmailProvider()

    registry = ToolRegistry()
    registry.register(EnterpriseSearchTool(retrieval_orchestrator))
    registry.register(CalculatorTool())
    registry.register(DocumentLookupTool(vector_store))
    registry.register(ConversationSearchTool(async_session_factory))
    registry.register(SendEmailTool(email_provider))
    registry.register(WebSearchTool())
    registry.register(WebFetchTool())
    registry.register(CalendarSearchTool())
    registry.register(CalendarCreateEventTool())

    class _ApprovalServiceProxy:
        async def get_pending_approval(self, *args, **kwargs):
            async with async_session_factory() as session:
                return await ApprovalService(session).get_pending_approval(*args, **kwargs)

        async def create_approval_request(self, *args, **kwargs):
            async with async_session_factory() as session:
                return await ApprovalService(session).create_approval_request(*args, **kwargs)

        async def consume_approval(self, *args, **kwargs):
            async with async_session_factory() as session:
                return await ApprovalService(session).consume_approval(*args, **kwargs)

    approval_proxy = _ApprovalServiceProxy()
    executor = ToolExecutor(
        registry=registry,
        auth_engine=ToolAuthorizationEngine(),
        guardrail_engine=guardrail_engine,
        policy_engine=ToolPolicyEngine(),
        approval_service=approval_proxy,
    )
    memory_retriever = MemoryRetriever(embedding_provider)

    return generation_service, registry, executor, memory_retriever


async def startup(ctx: Dict[str, Any]) -> None:
    logger.info("ARQ Worker starting up…")
    (
        ctx["generation_service"],
        ctx["tool_registry"],
        ctx["tool_executor"],
        ctx["memory_retriever"],
    ) = _build_orchestrator_deps()
    logger.info("ARQ Worker ready.")


async def shutdown(ctx: Dict[str, Any]) -> None:
    logger.info("ARQ Worker shutting down.")


async def run_agent_workflow(ctx: Dict[str, Any], job_id: str, payload: dict) -> dict:
    """Execute an agentic workflow durably in the background.

    The payload must contain:
        task            – the user's natural-language request
        conversation_id – UUID string of the owning conversation
        user_id         – UUID string of the requesting user
        allowed_roles   – list[str] of the user's RBAC roles
        request_id      – correlation ID string
    """
    logger.info("Worker processing job %s", job_id)

    async with async_session_factory() as session:
        job = await session.get(BackgroundJob, job_id)
        if not job:
            logger.error("Job %s not found in DB.", job_id)
            return {}

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        job.attempts += 1
        await session.commit()

    try:
        from app.agent.orchestrator import AgentOrchestrator
        from app.services.memory_service import MemoryService

        allowed_roles: list[str] = payload.get("allowed_roles", [])
        task: str = payload["task"]
        conversation_id = uuid.UUID(payload["conversation_id"])
        user_id = uuid.UUID(payload["user_id"])
        request_id: str = payload.get("request_id", str(uuid.uuid4()))

        # Build a fresh memory service scoped to this job's DB session
        async with async_session_factory() as mem_session:
            from app.rag.embeddings import get_embedding_provider
            memory_service = MemoryService(mem_session, get_embedding_provider(settings))

            orchestrator = AgentOrchestrator(
                generation_service=ctx["generation_service"],
                registry=ctx["tool_registry"],
                executor=ctx["tool_executor"],
                allowed_roles=allowed_roles,
                memory_retriever=ctx["memory_retriever"],
                memory_service=memory_service,
            )

            result = await orchestrator.run(
                task=task,
                request_id=request_id,
                conversation_id=conversation_id,
                user_id=user_id,
                history=[],
            )

        async with async_session_factory() as session:
            job = await session.get(BackgroundJob, job_id)
            if job:
                job.status = JobStatus.COMPLETED
                job.result = {"answer": result}
                job.completed_at = datetime.now(timezone.utc)
                await session.commit()

        logger.info("Job %s completed.", job_id)
        return {"answer": result}

    except Exception as exc:
        logger.error("Job %s failed: %s", job_id, exc, exc_info=True)
        async with async_session_factory() as session:
            job = await session.get(BackgroundJob, job_id)
            if job:
                job.status = JobStatus.FAILED
                job.error = str(exc)
                job.completed_at = datetime.now(timezone.utc)
                await session.commit()
        raise


# Redis connection from settings
_parsed = urlparse(settings.redis_url)
_redis_host = _parsed.hostname or "localhost"
_redis_port = _parsed.port or 6379


class WorkerSettings:
    """ARQ worker settings."""
    functions = [run_agent_workflow]
    redis_settings = RedisSettings(host=_redis_host, port=_redis_port)
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 5           # conservative concurrency \u2014 LLM calls are expensive
    job_timeout = 600      # 10 minutes max per agent job
    keep_result = 3600     # keep job results for 1 hour
