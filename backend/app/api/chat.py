"""API routes for RAG chat."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_rag_pipeline, get_current_user
from app.models.auth import User
from app.models.chat import ChatRequest, ChatResponse
from app.rag.pipeline import RAGPipeline

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def ask_question(
    request: ChatRequest,
    pipeline: Annotated[RAGPipeline, Depends(get_rag_pipeline)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Ask a question against the embedded enterprise documents.

    Uses vector retrieval to find relevant context, then asks the LLM
    to generate a grounded answer with source citations.
    """
    try:
        allowed_roles = [role.name for role in current_user.roles]
        response = pipeline.answer_question(request.question, allowed_roles=allowed_roles)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")
