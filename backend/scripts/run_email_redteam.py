"""Red-team tests for Email Tool."""

import asyncio
import uuid
import logging
from pydantic import BaseModel

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

from app.agent.tools.registry import ToolRegistry
from app.agent.tools.executor import ToolExecutor
from app.agent.tools.auth import ToolAuthorizationEngine
from app.agent.tools.policy import ToolPolicyEngine
from app.services.approval_service import ApprovalService
from app.services.email.sandbox import SandboxEmailProvider
from app.agent.tools.impl.send_email import SendEmailTool
from app.agent.tools.base import RequestContext
from app.models.approval import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MockGuardrailEngine:
    async def check_input(self, text: str):
        class Result:
            status = "PASS"
        res = Result()
        if "sk-" in text or "Ignore previous instructions" in text:
            res.status = "BLOCK"
        return res
        
    async def check_context(self, text: str):
        class Result:
            status = "PASS"
        return Result()

async def run_tests():
    logger.info("Initializing Red-Team Tests for Email Tool")
    
    # 1. Setup DB for Approvals
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    db_session_factory = async_sessionmaker(engine, expire_on_commit=False)
    
    # 2. Setup Framework
    registry = ToolRegistry()
    email_provider = SandboxEmailProvider()
    registry.register(SendEmailTool(email_provider))
    
    auth_engine = ToolAuthorizationEngine()
    policy_engine = ToolPolicyEngine()
    guardrail_engine = MockGuardrailEngine()
    
    class ApprovalServiceWrapper:
        async def get_pending_approval(self, *args, **kwargs):
            async with db_session_factory() as session:
                return await ApprovalService(session).get_pending_approval(*args, **kwargs)
                
        async def create_approval_request(self, *args, **kwargs):
            async with db_session_factory() as session:
                return await ApprovalService(session).create_approval_request(*args, **kwargs)
                
        async def consume_approval(self, *args, **kwargs):
            async with db_session_factory() as session:
                return await ApprovalService(session).consume_approval(*args, **kwargs)
                
        async def approve_request(self, *args, **kwargs):
            async with db_session_factory() as session:
                return await ApprovalService(session).approve_request(*args, **kwargs)

    approval_service = ApprovalServiceWrapper()
    
    executor = ToolExecutor(
        registry=registry,
        auth_engine=auth_engine,
        guardrail_engine=guardrail_engine,
        policy_engine=policy_engine,
        approval_service=approval_service
    )
    
    user_id = str(uuid.uuid4())
    conv_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    
    context = RequestContext(
        user_id=user_id,
        conversation_id=conv_id,
        request_id=str(uuid.uuid4()),
        user_roles=["user"]
    )
    
    # Test 1: Invalid Email Format
    logger.info("Test 1: Invalid Email Format")
    obs = await executor.execute("send_email", {"recipients": ["invalid-email"], "subject": "Test", "body": "Body"}, context, "call_1", run_id)
    assert obs.status == "INVALID_TOOL_INPUT"
    
    # Test 2: Header Injection
    logger.info("Test 2: Header Injection")
    obs = await executor.execute("send_email", {"recipients": ["alice@example.com"], "subject": "Test\nBCC: attacker", "body": "Body"}, context, "call_2", run_id)
    assert obs.status == "INVALID_TOOL_INPUT"
    
    # Test 3: Secret Exfiltration (Guardrail)
    logger.info("Test 3: Secret Exfiltration")
    obs = await executor.execute("send_email", {"recipients": ["attacker@example.com"], "subject": "Keys", "body": "sk-1234"}, context, "call_3", run_id)
    assert obs.status == "TOOL_INPUT_BLOCKED"
    
    # Test 4: Requires Approval
    logger.info("Test 4: Requires Approval")
    args = {"recipients": ["alice@example.com"], "subject": "Report", "body": "Here is the report."}
    obs = await executor.execute("send_email", args, context, "call_4", run_id)
    assert obs.status == "APPROVAL_REQUIRED"
    
    # Test 5: Approve and Execute
    logger.info("Test 5: Approve and Execute")
    # Fetch pending approval
    tool = registry.get_tool("send_email")
    args_hash = tool.hash_arguments(SendEmailTool.input_schema(**args))
    pending = await approval_service.get_pending_approval(uuid.UUID(user_id), uuid.UUID(run_id), "send_email", args_hash)
    assert pending is not None
    
    # Approve
    await approval_service.approve_request(pending.id, uuid.UUID(user_id))
    
    # Resume
    obs = await executor.execute("send_email", args, context, "call_4_resume", run_id)
    assert obs.status == "SUCCESS"
    assert len(email_provider.sent_emails) == 1
    
    # Test 6: Replay Attempt
    logger.info("Test 6: Replay Attempt")
    # Execute with same args -> Should hit REQUIRES_APPROVAL again because old approval was consumed
    obs = await executor.execute("send_email", args, context, "call_4_replay", run_id)
    assert obs.status == "APPROVAL_REQUIRED" # New request created
    
    # Test 7: Argument Mutation
    logger.info("Test 7: Argument Mutation")
    # Mutate args for the new pending approval
    mutated_args = {"recipients": ["attacker@example.com"], "subject": "Report", "body": "Here is the report."}
    obs = await executor.execute("send_email", mutated_args, context, "call_7", run_id)
    assert obs.status == "APPROVAL_REQUIRED" # Creates a separate approval requirement
    
    logger.info("All tests passed.")

if __name__ == "__main__":
    asyncio.run(run_tests())
