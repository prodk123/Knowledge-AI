"""API routes for persistent conversations."""

import asyncio
import json
import logging
import uuid
from typing import Annotated, AsyncGenerator, Callable

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import (
    get_current_user,
    get_db_session,
    get_query_router,
    get_query_rewriter,
    get_direct_llm_service,
    get_rag_pipeline,
    get_generation_service,
    get_agent_orchestrator,
)
from app.models.auth import User
from app.models.chat import ChatResponse
from app.models.conversation import (
    Conversation,
    Message,
    ConversationResponse,
    ConversationDetailResponse,
    ConversationCreate,
    ConversationUpdate,
    MessageCreate,
    MessageResponse,
)
from app.models.job import BackgroundJob
from app.rag.pipeline import RAGPipeline
from app.rag.router import QueryRouter
from app.rag.rewriter import ContextualQueryRewriter
from app.services.direct_llm_service import DirectLLMService
from app.services.generation_service import GenerationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("/", response_model=ConversationResponse)
async def create_conversation(
    request: ConversationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Create a new conversation."""
    conversation = Conversation(
        user_id=current_user.id,
        title=request.title or "New conversation",
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


@router.get("/", response_model=list[ConversationResponse])
async def list_conversations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """List all conversations for the current user."""
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    )
    result = await db.scalars(stmt)
    return list(result.all())


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Get a specific conversation and its messages."""
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    result = await db.scalars(stmt)
    conversation = result.first()

    if not conversation:
        raise HTTPException(
            status_code=404, detail="Conversation not found or access denied."
        )

    return conversation


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def rename_conversation(
    conversation_id: uuid.UUID,
    request: ConversationUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Rename a conversation."""
    stmt = select(Conversation).where(
        Conversation.id == conversation_id, Conversation.user_id == current_user.id
    )
    result = await db.scalars(stmt)
    conversation = result.first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation.title = request.title
    await db.commit()
    await db.refresh(conversation)
    return conversation


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Delete a conversation. Ownership is enforced server-side."""
    stmt = select(Conversation).where(
        Conversation.id == conversation_id, Conversation.user_id == current_user.id
    )
    result = await db.scalars(stmt)
    conversation = result.first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await db.delete(conversation)
    await db.commit()
    return {"message": "Conversation deleted successfully"}


def _generate_title(generation_service: GenerationService, first_message: str) -> str:
    messages = [
        {
            "role": "system",
            "content": "Generate a concise 3-5 word title for a conversation that starts with the user's message. Do NOT use quotes.",
        },
        {"role": "user", "content": first_message},
    ]
    try:
        title = generation_service.generate(messages).strip(' "')
        return title[:50]
    except Exception as e:
        logger.error("Failed to generate title: %s", e)
        return "New conversation"


async def generate_title_task(
    conversation_id: uuid.UUID,
    first_message: str,
    generation_service: GenerationService,
    db_session_maker,
):
    """Background task to generate and update the title."""
    title = await asyncio.to_thread(
        _generate_title, generation_service, first_message
    )
    async with db_session_maker() as db:
        stmt = select(Conversation).where(Conversation.id == conversation_id)
        result = await db.scalars(stmt)
        conversation = result.first()
        if conversation and conversation.title == "New conversation":
            conversation.title = title
            await db.commit()


# ─── SSE helpers ──────────────────────────────────────────────────────────────

def _sse_event(event_type: str, data: str) -> str:
    """Format a single SSE event."""
    payload = json.dumps({"type": event_type, "content": data})
    return f"data: {payload}\n\n"


def _sse_done(sources: list = None, metadata: dict = None) -> str:
    """Final SSE event carrying sources/metadata so the frontend can attach them."""
    payload = json.dumps(
        {
            "type": "done",
            "sources": [s.model_dump() if hasattr(s, "model_dump") else s for s in (sources or [])],
            "metadata": metadata or {},
        }
    )
    return f"data: {payload}\n\n"


def _sse_error(detail: str) -> str:
    payload = json.dumps({"type": "error", "detail": detail})
    return f"data: {payload}\n\n"


async def _run_agent_and_stream(
    orchestrator,
    task: str,
    request_id: str,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    history: list,
    generation_service: GenerationService,
) -> AsyncGenerator[str, None]:
    """
    Run the agent orchestrator (which handles all AgentRun persistence, tool auth,
    policy engine, circuit breakers, memory, etc.) and then streams the synthesis
    token-by-token using generation_service.stream().

    The orchestrator returns a complete answer string. We use that string as a
    single-shot 'stream' to keep the existing orchestrator architecture intact,
    while still yielding a streamed experience for the final synthesis.
    """
    # Emit planning activity event
    yield _sse_event("activity", "Agent planning...")

    try:
        # Run the full agent lifecycle synchronously in a thread so the event loop
        # isn't blocked. This preserves all existing orchestrator logic including
        # AgentRun/Step persistence, tool execution, approval, memory, etc.
        answer = await orchestrator.run(
            task=task,
            request_id=request_id,
            conversation_id=conversation_id,
            user_id=user_id,
            history=history,
        )

        # Now stream the final answer token by token
        yield _sse_event("activity", "Synthesis...")

        # Build synthesis streaming messages
        synthesis_messages = [
            {
                "role": "system",
                "content": (
                    "You are a synthesis assistant. The following answer was produced by an "
                    "agent workflow. Present it clearly and completely to the user without "
                    "omitting any details. Do not add new facts."
                ),
            },
            {"role": "user", "content": f"Agent answer to stream:\n\n{answer}"},
        ]

        # If the answer signals waiting-for-approval, fetch and emit the approval card data
        if answer.startswith("This action requires human approval"):
            yield _sse_event("token", answer)
            # Fetch the pending approval record for this user/conversation so the
            # frontend can render Approve/Reject buttons
            try:
                from app.db.database import async_session_factory
                from app.models.approval import ApprovalRequest
                from sqlalchemy import select as sa_select
                async with async_session_factory() as session:
                    stmt = (
                        sa_select(ApprovalRequest)
                        .where(
                            ApprovalRequest.user_id == user_id,
                            ApprovalRequest.conversation_id == conversation_id,
                            ApprovalRequest.status == "PENDING",
                        )
                        .order_by(ApprovalRequest.created_at.desc())
                        .limit(1)
                    )
                    result = await session.scalars(stmt)
                    pending = result.first()
                    if pending:
                        approval_data = {
                            "id": str(pending.id),
                            "tool_name": pending.tool_name,
                            "risk_level": pending.risk_level.lower(),
                            "requested_action_desc": pending.requested_action_desc,
                            "status": pending.status.lower(),
                            "expires_at": pending.expires_at.isoformat() if pending.expires_at else None,
                        }
                        yield _sse_event("approval", json.dumps(approval_data))
            except Exception as appr_err:
                logger.warning("Could not fetch pending approval: %s", appr_err)

        elif answer.startswith("Something went wrong"):
            yield _sse_event("token", answer)
        else:
            async for chunk in generation_service.stream(synthesis_messages):
                yield _sse_event("token", chunk)

    except Exception as e:
        logger.error("Agent streaming failed: %s", e, exc_info=True)
        yield _sse_error(f"Agent execution failed: {str(e)}")



# ─── Main message endpoint ──────────────────────────────────────────────────

@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: uuid.UUID,
    request: MessageCreate,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    router_dep: Annotated[QueryRouter, Depends(get_query_router)],
    rewriter: Annotated[ContextualQueryRewriter, Depends(get_query_rewriter)],
    direct_service: Annotated[DirectLLMService, Depends(get_direct_llm_service)],
    rag_pipeline: Annotated[RAGPipeline, Depends(get_rag_pipeline)],
    generation_service: Annotated[GenerationService, Depends(get_generation_service)],
    agent_orchestrator_factory: Annotated[Callable, Depends(get_agent_orchestrator)],
    fast_api_request: Request = None,
):
    """
    Send a message to a conversation.

    Returns a StreamingResponse with SSE events:
      {"type": "activity", "content": "..."} — agent/routing activity
      {"type": "token",    "content": "..."} — a streamed text chunk
      {"type": "done",  "sources": [...], "metadata": {...}} — end-of-stream
      {"type": "error",    "detail": "..."}  — error (after which stream closes)

    For background (ARQ) jobs, returns a standard JSON body {is_async, job_id}.
    """

    # ── 1. Verify ownership ──────────────────────────────────────────────────
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    result = await db.scalars(stmt)
    conversation = result.first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    history = [{"role": msg.role, "content": msg.content} for msg in conversation.messages]

    # ── 2. Persist user message ──────────────────────────────────────────────
    sequence_number = len(conversation.messages) + 1
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=request.content,
        sequence_number=sequence_number,
    )
    db.add(user_msg)
    await db.commit()

    if sequence_number == 1:
        from app.db.database import async_session_factory

        background_tasks.add_task(
            generate_title_task,
            conversation.id,
            request.content,
            generation_service,
            async_session_factory,
        )

    # ── 3. Background ARQ path ───────────────────────────────────────────────
    if getattr(request, "run_async", False):
        if fast_api_request and hasattr(fast_api_request.app.state, "arq_pool"):
            job_id = uuid.uuid4().hex
            from app.db.database import async_session_factory

            job_record = BackgroundJob(
                id=job_id,
                job_type="agent_workflow",
                payload={
                    "query": request.content,
                    "conversation_id": str(conversation.id),
                    "user_id": str(current_user.id),
                    "tenant_id": "default",
                },
            )
            db.add(job_record)
            await db.commit()

            await fast_api_request.app.state.arq_pool.enqueue_job(
                "run_agent_workflow",
                job_id=job_id,
                payload=job_record.payload,
                _job_id=job_id,
            )

            return ChatResponse(
                answer="Job submitted to background workers. Please check job status.",
                sources=[],
                is_async=True,
                job_id=job_id,
            )
        else:
            logger.warning(
                "Requested run_async=True, but ARQ pool is not available. Falling back to sync."
            )

    # ── 4. Streaming SSE path ────────────────────────────────────────────────
    from app.core.dependencies import get_guardrail_engine
    from app.core.tracing import Tracer
    from app.db.database import async_session_factory

    request_id = str(uuid.uuid4())
    allowed_roles = [role.name for role in current_user.roles]

    async def event_generator() -> AsyncGenerator[str, None]:
        """
        Core streaming generator. Produces SSE events and persists the
        assembled answer after streaming completes.
        """
        answer_chunks: list[str] = []
        sources: list = []
        metadata: dict = {}
        error_occurred = False

        try:
            async with Tracer.start_trace(
                request_id=request_id,
                user_id=current_user.id,
                conversation_id=conversation.id,
            ) as trace:
                # ── INPUT GUARDRAILS ─────────────────────────────────────────
                engine = get_guardrail_engine(generation_service)
                input_result = await engine.check_input(request.content)

                if input_result.status in ["BLOCK", "ABSTAIN", "SANITIZE"]:
                    blocked_msg = input_result.message or "I cannot process that request."
                    yield _sse_event("token", blocked_msg)
                    yield _sse_done()
                    # Persist
                    await _persist_assistant_message(
                        db=db,
                        conversation=conversation,
                        answer=blocked_msg,
                        sequence_number=sequence_number + 1,
                        metadata={"route": "blocked_by_guardrail"},
                        async_session_factory=async_session_factory,
                    )
                    return

                # ── ROUTING ─────────────────────────────────────────────────
                decision = router_dep.route(request.content, history)
                trace["route"] = decision.route
                metadata["route"] = decision.route
                metadata["router_reason"] = decision.reason
                metadata["router_confidence"] = decision.confidence

                yield _sse_event("activity", f"Routing: {decision.route}")

                # ── DIRECT ──────────────────────────────────────────────────
                if decision.route == "direct":
                    direct_messages = direct_service.build_messages(request.content, history)
                    async for chunk in generation_service.stream(direct_messages):
                        answer_chunks.append(chunk)
                        yield _sse_event("token", chunk)

                # ── RAG ─────────────────────────────────────────────────────
                elif decision.route == "rag":
                    yield _sse_event("activity", "Retrieving context...")
                    standalone_query = rewriter.rewrite(request.content, history)
                    metadata["standalone_query"] = standalone_query

                    # Run retrieval in thread (sync operation)
                    contexts = await asyncio.to_thread(
                        rag_pipeline.retrieve_context,
                        question=request.content,
                        allowed_roles=allowed_roles,
                        retrieval_query=standalone_query,
                    )
                    sources = [ctx.to_source_reference() for ctx in contexts]
                    metadata["sources"] = [s.model_dump() for s in sources]

                    yield _sse_event("activity", "Generating answer...")
                    # Build messages then stream generation token-by-token
                    rag_messages = rag_pipeline.build_generation_messages(
                        question=request.content,
                        contexts=contexts,
                        history=history,
                    )
                    async for chunk in generation_service.stream(rag_messages):
                        answer_chunks.append(chunk)
                        yield _sse_event("token", chunk)

                # ── AGENT SINGLE ────────────────────────────────────────────
                elif decision.route == "agent_single":
                    orchestrator = agent_orchestrator_factory(allowed_roles=allowed_roles)
                    async for event in _run_agent_and_stream(
                        orchestrator=orchestrator,
                        task=request.content,
                        request_id=request_id,
                        conversation_id=conversation.id,
                        user_id=current_user.id,
                        history=history,
                        generation_service=generation_service,
                    ):
                        # Capture token chunks and approval data for persistence
                        try:
                            parsed = json.loads(event.removeprefix("data: ").strip())
                            if parsed.get("type") == "token":
                                answer_chunks.append(parsed["content"])
                            elif parsed.get("type") == "approval":
                                metadata["approval_request"] = json.loads(parsed["content"])
                        except Exception:
                            pass
                        yield event

                # ── AGENT SWARM ─────────────────────────────────────────────
                elif decision.route == "agent_swarm":
                    from app.agent.swarm.orchestrator import SwarmOrchestrator
                    from app.agent.swarm.registry import AgentRegistry
                    from app.agent.swarm.policy import AgentPolicyEngine, AgentAuthorizationService
                    from app.agent.swarm.agents.specialized import create_specialized_agents

                    # Re-use the tool registry/executor from the singleton orchestrator.
                    # This preserves auth_engine, policy_engine, approval_service,
                    # guardrails, circuit breakers and all other executor dependencies.
                    orig_orchestrator = agent_orchestrator_factory(allowed_roles=allowed_roles)

                    agent_registry = AgentRegistry()
                    for agent in create_specialized_agents(
                        generation_service, orig_orchestrator.executor
                    ):
                        agent_registry.register(agent)

                    swarm_orchestrator = SwarmOrchestrator(
                        generation_service=generation_service,
                        registry=orig_orchestrator.registry,
                        executor=orig_orchestrator.executor,   # ← fixed: reuse fully-constructed executor
                        agent_registry=agent_registry,
                        policy_engine=AgentPolicyEngine(),
                        auth_service=AgentAuthorizationService(),
                        allowed_roles=allowed_roles,
                        memory_retriever=orig_orchestrator.memory_retriever,
                        memory_service=orig_orchestrator.memory_service,
                    )

                    async for event in _run_agent_and_stream(
                        orchestrator=swarm_orchestrator,
                        task=request.content,
                        request_id=request_id,
                        conversation_id=conversation.id,
                        user_id=current_user.id,
                        history=history,
                        generation_service=generation_service,
                    ):
                        try:
                            parsed = json.loads(event.removeprefix("data: ").strip())
                            if parsed.get("type") == "token":
                                answer_chunks.append(parsed["content"])
                        except Exception:
                            pass
                        yield event

                # ── OUTPUT GUARDRAILS (Direct/RAG) ───────────────────────────
                if decision.route in ["direct", "rag"] and answer_chunks:
                    full_answer = "".join(answer_chunks)
                    if engine:
                        try:
                            output_result = await engine.check_output(full_answer)
                            if output_result.status in ["BLOCK", "ABSTAIN", "SANITIZE"]:
                                blocked_msg = (
                                    output_result.message
                                    or "The generated response was blocked by safety policies."
                                )
                                # Clear streamed chunks and replace
                                answer_chunks = [blocked_msg]
                                # We already streamed tokens; append a correction notice
                                yield _sse_event("token", f"\n\n⚠️ {blocked_msg}")
                        except Exception as guard_err:
                            logger.warning("Output guardrail check failed (non-fatal): %s", guard_err)

        except Exception as e:
            logger.error("Streaming generation failed: %s", e, exc_info=True)
            error_occurred = True
            yield _sse_error(str(e))

        # ── Yield done event ─────────────────────────────────────────────────
        if not error_occurred:
            yield _sse_done(sources=sources, metadata=metadata)

        # ── Persist assembled answer ─────────────────────────────────────────
        if answer_chunks:
            full_answer = "".join(answer_chunks)
            await _persist_assistant_message(
                db=db,
                conversation=conversation,
                answer=full_answer,
                sequence_number=sequence_number + 1,
                metadata=metadata,
                async_session_factory=async_session_factory,
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
        },
    )


async def _persist_assistant_message(
    db: AsyncSession,
    conversation: Conversation,
    answer: str,
    sequence_number: int,
    metadata: dict,
    async_session_factory,
) -> None:
    """Persist the assistant message after streaming completes."""
    try:
        # Use a fresh session because the request-scoped session may already be closed
        async with async_session_factory() as session:
            assistant_msg = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=answer,
                sequence_number=sequence_number,
                metadata_=metadata,
            )
            session.add(assistant_msg)

            # Update conversation updated_at
            stmt = select(Conversation).where(Conversation.id == conversation.id)
            result = await session.scalars(stmt)
            conv = result.first()
            if conv:
                conv.updated_at = func.now()

            await session.commit()
    except Exception as e:
        logger.error("Failed to persist assistant message: %s", e)
