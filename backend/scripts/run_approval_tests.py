import asyncio
import logging
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

from app.models.approval import Base
from app.services.approval_service import ApprovalService
from app.agent.tools.policy import ToolPolicyEngine, PolicyEvaluationResult, PolicyDecision
from app.agent.tools.base import ToolRiskLevel, ToolCapability, BaseTool, RequestContext
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockArgs(BaseModel):
    query: str
    amount: int

class MockHighRiskTool(BaseTool):
    name = "mock_high_risk"
    description = "A mock tool for testing."
    risk_level = ToolRiskLevel.HIGH
    input_schema = MockArgs
    output_schema = MockArgs

async def run_tests():
    logger.info("Starting Stage 8.3 Approval Tests...")
    
    engine = ToolPolicyEngine()
    tool = MockHighRiskTool()
    
    context = RequestContext(
        user_id=str(uuid.uuid4()),
        roles=["user"],
        conversation_id=str(uuid.uuid4()),
        request_id=str(uuid.uuid4())
    )
    
    args = MockArgs(query="delete everything", amount=999)
    
    # 1. Test Policy Engine
    result = engine.evaluate(context, tool, args)
    assert result.decision == PolicyDecision.REQUIRES_APPROVAL, "High risk tool should require approval."
    logger.info("Test 1 Passed: Policy Engine blocks HIGH risk tools.")
    
    # 2. Test Argument Hashing
    hash1 = tool.hash_arguments(args)
    hash2 = tool.hash_arguments({"amount": 999, "query": "delete everything"})
    assert hash1 == hash2, "Argument hashes should be deterministic regardless of order."
    logger.info("Test 2 Passed: Canonical Argument Hashing works.")
    
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    db_session_factory = async_sessionmaker(engine, expire_on_commit=False)
    
    # 3. Test DB Service
    async with db_session_factory() as session:
        service = ApprovalService(session)
        user_id = uuid.UUID(context.user_id)
        run_id = uuid.uuid4()
        
        # Create
        req = await service.create_approval_request(
            user_id=user_id,
            conversation_id=uuid.UUID(context.conversation_id),
            agent_run_id=run_id,
            step_id="step-123",
            tool_name=tool.name,
            tool_version=tool.version,
            arguments_hash=hash1,
            requested_action_desc="Execute HIGH risk",
            policy_result=result
        )
        assert req.status == "PENDING"
        logger.info("Test 3a Passed: Create Approval Request.")
        
        # Retrieve
        pending = await service.get_pending_approval(user_id, run_id, tool.name, hash1)
        assert pending is not None
        assert pending.id == req.id
        logger.info("Test 3b Passed: Retrieve Pending Approval.")
        
        # Tampered Retrieve
        tampered_hash = tool.hash_arguments({"amount": 1, "query": "delete everything"})
        missing = await service.get_pending_approval(user_id, run_id, tool.name, tampered_hash)
        assert missing is None, "Tampered arguments should not match any pending approval."
        logger.info("Test 3c Passed: Argument Tampering Prevented.")
        
        # Approve
        approved = await service.approve_request(req.id, user_id)
        assert approved.status == "APPROVED"
        logger.info("Test 3d Passed: Approve Request.")
        
        # Consume
        consumed = await service.consume_approval(approved.id)
        assert consumed is True
        logger.info("Test 3e Passed: Consume Approval.")
        
        # Replay Attack
        consumed_again = await service.consume_approval(approved.id)
        assert consumed_again is False, "Should not be able to consume twice."
        logger.info("Test 3f Passed: Replay Attacks Prevented.")
        
    logger.info("All Stage 8.3 tests passed successfully!")

if __name__ == "__main__":
    asyncio.run(run_tests())
