"""RAG Pipeline — orchestrates retrieval and generation."""

import logging

from app.models.chat import ChatResponse, RetrievalResult
from app.rag.prompt import ContextBuilder
from app.rag.retriever import RetrievalOrchestrator
from app.services.generation_service import GenerationService
from app.core.tracing import Tracer

logger = logging.getLogger(__name__)


class RAGPipeline:
    """End-to-end RAG pipeline orchestration.

    Coordinates retrieval, prompt building, and LLM generation.
    Maintains the mapping between the generated answer and the source chunks.
    """

    def __init__(
        self,
        retriever: RetrievalOrchestrator,
        context_builder: ContextBuilder,
        generation_service: GenerationService,
        guardrail_engine=None,
    ):
        self.retriever = retriever
        self.context_builder = context_builder
        self.generation_service = generation_service
        self.guardrail_engine = guardrail_engine

    def retrieve_context(
        self,
        question: str,
        allowed_roles: list[str] | None = None,
        retrieval_query: str = None,
    ) -> list[RetrievalResult]:
        """Run retrieval only. Used by streaming path to separate retrieval from generation."""
        search_query = retrieval_query if retrieval_query else question
        with Tracer.start_span("retrieval_orchestrator") as span:
            span["search_query"] = search_query
            contexts = self.retriever.retrieve(query=search_query, allowed_roles=allowed_roles)
            span["retrieved_count"] = len(contexts)
        return contexts

    def build_generation_messages(
        self,
        question: str,
        contexts: list[RetrievalResult],
        history: list[dict[str, str]] = None,
    ) -> list[dict[str, str]]:
        """Build the generation messages from retrieved contexts.

        Used by both sync (answer_question) and streaming callers.
        """
        with Tracer.start_span("context_builder"):
            return self.context_builder.build_prompt(
                question=question, contexts=contexts, history=history
            )

    def answer_question(
        self,
        question: str,
        allowed_roles: list[str] | None = None,
        history: list[dict[str, str]] = None,
        retrieval_query: str = None,
    ) -> ChatResponse:
        """Execute the full RAG pipeline (sync, non-streaming)."""
        logger.info("Processing question: %s", question)

        contexts = self.retrieve_context(question, allowed_roles, retrieval_query)

        # Note: Context and output guardrail checks are now handled in the async
        # caller (conversations.py) to avoid nested event loop issues with uvloop.

        messages = self.build_generation_messages(question, contexts, history)

        # 3. Generate the answer
        with Tracer.start_span("llm_generation"):
            answer = self.generation_service.generate(messages=messages)

        # 4. Map internal RetrievalResults to public SourceReferences
        sources = [ctx.to_source_reference() for ctx in contexts]

        logger.info("Generated answer with %d sources", len(sources))
        return ChatResponse(answer=answer, sources=sources)
