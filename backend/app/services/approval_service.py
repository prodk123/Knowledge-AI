"""Approval Service for handling tool execution approvals."""

import uuid
from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.models.approval import ApprovalRequest, ApprovalStatus
from app.agent.tools.policy import PolicyEvaluationResult

logger = logging.getLogger(__name__)


class ApprovalRequiredException(Exception):
    """Raised when an execution requires approval but none exists."""
    pass


class ApprovalService:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def create_approval_request(
        self,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        agent_run_id: uuid.UUID,
        step_id: str,
        tool_name: str,
        tool_version: str,
        arguments_hash: str,
        requested_action_desc: str,
        policy_result: PolicyEvaluationResult,
        ttl_minutes: int = 5
    ) -> ApprovalRequest:
        """Create a new pending approval request."""
        request = ApprovalRequest(
            user_id=user_id,
            conversation_id=conversation_id,
            agent_run_id=agent_run_id,
            step_id=step_id,
            tool_name=tool_name,
            tool_version=tool_version,
            arguments_hash=arguments_hash,
            risk_level=policy_result.risk_level.value,
            requested_action_desc=requested_action_desc,
            status=ApprovalStatus.PENDING,
            policy_version=policy_result.policy_version,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
        )
        self.db.add(request)
        await self.db.commit()
        await self.db.refresh(request)
        return request

    async def get_pending_approval(
        self,
        user_id: uuid.UUID,
        agent_run_id: uuid.UUID,
        tool_name: str,
        arguments_hash: str
    ) -> ApprovalRequest | None:
        """Find an active, pending, or approved request matching exact constraints."""
        stmt = select(ApprovalRequest).where(
            ApprovalRequest.user_id == user_id,
            ApprovalRequest.agent_run_id == agent_run_id,
            ApprovalRequest.tool_name == tool_name,
            ApprovalRequest.arguments_hash == arguments_hash,
            ApprovalRequest.status.in_([ApprovalStatus.PENDING, ApprovalStatus.APPROVED])
        ).order_by(ApprovalRequest.created_at.desc()).limit(1)
        
        result = await self.db.execute(stmt)
        request = result.scalar_one_or_none()
        
        if request and request.expires_at < datetime.now(timezone.utc) and request.status != ApprovalStatus.EXPIRED:
            request.status = ApprovalStatus.EXPIRED
            await self.db.commit()
            return None
            
        return request

    async def approve_request(
        self,
        approval_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> ApprovalRequest:
        """Mark an approval request as APPROVED. Must be owned by the user."""
        stmt = select(ApprovalRequest).where(
            ApprovalRequest.id == approval_id,
            ApprovalRequest.user_id == user_id
        )
        result = await self.db.execute(stmt)
        request = result.scalar_one_or_none()
        
        if not request:
            raise ValueError("Approval request not found or unauthorized.")
            
        if request.status != ApprovalStatus.PENDING:
            raise ValueError(f"Cannot approve request in status: {request.status}")
            
        if request.expires_at < datetime.now(timezone.utc):
            request.status = ApprovalStatus.EXPIRED
            await self.db.commit()
            raise ValueError("Approval request has expired.")
            
        request.status = ApprovalStatus.APPROVED
        request.approved_at = datetime.now(timezone.utc)
        request.approved_by = user_id
        await self.db.commit()
        await self.db.refresh(request)
        return request

    async def reject_request(
        self,
        approval_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> ApprovalRequest:
        """Mark an approval request as REJECTED."""
        stmt = select(ApprovalRequest).where(
            ApprovalRequest.id == approval_id,
            ApprovalRequest.user_id == user_id
        )
        result = await self.db.execute(stmt)
        request = result.scalar_one_or_none()
        
        if not request:
            raise ValueError("Approval request not found or unauthorized.")
            
        if request.status != ApprovalStatus.PENDING:
            raise ValueError(f"Cannot reject request in status: {request.status}")
            
        request.status = ApprovalStatus.REJECTED
        request.rejected_at = datetime.now(timezone.utc)
        request.rejected_by = user_id
        await self.db.commit()
        await self.db.refresh(request)
        return request

    async def consume_approval(
        self,
        approval_id: uuid.UUID
    ) -> bool:
        """
        Atomically mark an APPROVED request as CONSUMED.
        Returns True if successful, False if it was already consumed or invalid.
        """
        stmt = update(ApprovalRequest).where(
            ApprovalRequest.id == approval_id,
            ApprovalRequest.status == ApprovalStatus.APPROVED,
            ApprovalRequest.expires_at > datetime.now(timezone.utc)
        ).values(
            status=ApprovalStatus.CONSUMED
        )
        
        result = await self.db.execute(stmt)
        await self.db.commit()
        
        return result.rowcount > 0
