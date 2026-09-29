"""Approval API Routes."""

import uuid
import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.dependencies import get_db_session as get_db, get_current_user, get_agent_orchestrator
from app.models.approval import ApprovalRequest, ApprovalStatus
from app.models.conversation import Message
from app.services.approval_service import ApprovalService
from app.models.auth import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/approvals", tags=["approvals"])

class ApprovalResponse(BaseModel):
    id: uuid.UUID
    agent_run_id: uuid.UUID
    tool_name: str
    risk_level: str
    requested_action_desc: str
    status: str
    created_at: Any
    expires_at: Any
    
    class Config:
        from_attributes = True

@router.get("/pending", response_model=list[ApprovalResponse])
async def get_pending_approvals(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all pending approvals for the current user."""
    stmt = select(ApprovalRequest).where(
        ApprovalRequest.user_id == current_user.id,
        ApprovalRequest.status == ApprovalStatus.PENDING
    ).order_by(ApprovalRequest.created_at.desc())
    
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
async def approve_request(
    approval_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    agent_orchestrator_factory=Depends(get_agent_orchestrator),
):
    """Approve a pending request, then resume the agent workflow in the background."""
    service = ApprovalService(db)
    try:
        req = await service.approve_request(approval_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Retrieve the original task from the conversation's last user message
    # so we can re-run the orchestrator, which will now find the APPROVED record
    # and proceed to execute the tool.
    try:
        stmt = (
            select(Message)
            .where(
                Message.conversation_id == req.conversation_id,
                Message.role == "user",
            )
            .order_by(Message.sequence_number.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        last_user_msg = result.scalars().first()
        original_task = last_user_msg.content if last_user_msg else None

        if original_task:
            allowed_roles = [role.name for role in current_user.roles]
            orchestrator = agent_orchestrator_factory(allowed_roles=allowed_roles)
            agent_run_id = req.agent_run_id

            conversation_id = req.conversation_id

            async def resume_workflow():
                try:
                    result = await orchestrator.resume(
                        agent_run_id=agent_run_id,
                        history=[],
                    )
                    logger.info("Approval resume completed for run %s: %s", agent_run_id, result[:100] if result else "no result")
                    
                    if result:
                        from app.db.database import async_session_factory
                        async with async_session_factory() as session:
                            stmt = select(Message).where(Message.conversation_id == conversation_id).order_by(Message.sequence_number.desc()).limit(1)
                            res = await session.execute(stmt)
                            last_msg = res.scalars().first()
                            seq = last_msg.sequence_number + 1 if last_msg else 1
                            
                            new_msg = Message(
                                conversation_id=conversation_id,
                                role="assistant",
                                content=result,
                                sequence_number=seq,
                                metadata_={"is_approval_resume_result": True}
                            )
                            session.add(new_msg)
                            await session.commit()
                            
                except Exception as exc:
                    logger.error("Approval resume failed: %s", exc, exc_info=True)

            background_tasks.add_task(resume_workflow)

    except Exception as exc:
        logger.error("Could not schedule approval resume: %s", exc, exc_info=True)

    return req


@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
async def reject_request(
    approval_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Reject a pending request."""
    service = ApprovalService(db)
    try:
        req = await service.reject_request(approval_id, current_user.id)
        return req
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
