"""Tests for Workflow Execution Engine."""

import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

import json
import asyncio
import logging
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models.agent import Base, AgentRun, AgentPlan, AgentPlanStep
from app.models.conversation import Conversation
from app.agent.schemas import AgentPlan as SchemaAgentPlan
from app.agent.validator import PlanValidator
from app.agent.workflow import WorkflowExecutor
from app.agent.tools.registry import ToolRegistry
from app.agent.tools.executor import ToolExecutor
from app.agent.tools.auth import ToolAuthorizationEngine
from app.agent.tools.policy import ToolPolicyEngine
from app.agent.tools.impl.calculator import CalculatorTool
from app.agent.tools.base import RequestContext
from app.db.database import async_session_factory
from app.core.guardrails.engine import GuardrailEngine
from app.core.guardrails.base import BaseGuardrail, GuardrailResult
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

class MockGuardrailProvider(BaseGuardrail):
    def check(self, *args, **kwargs) -> GuardrailResult:
        return GuardrailResult(status="ALLOW", guardrail_name="MockGuardrailProvider")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockGenerationService:
    def generate_json(self, messages):
        return '{"final_answer": "Mocked response", "is_complete": true}'

class MockApprovalService:
    async def get_pending_approval(self, *args, **kwargs):
        return None
    async def create_approval_request(self, *args, **kwargs):
        return None
    async def consume_approval(self, *args, **kwargs):
        return True
    async def approve_request(self, *args, **kwargs):
        pass

async def run_workflow_tests():
    logger.info("Initializing Workflow Tests")
    
    # 1. Setup DB
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    global async_session_factory
    async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
    
    # Needs to monkey patch async_session_factory inside modules since we use it directly
    import app.agent.workflow
    app.agent.workflow.async_session_factory = async_session_factory
    import app.agent.orchestrator
    app.agent.orchestrator.async_session_factory = async_session_factory
    import app.agent.tools.executor
    app.agent.tools.executor.async_session_factory = async_session_factory
    
    # 2. Setup Framework
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    
    auth_engine = ToolAuthorizationEngine()
    policy_engine = ToolPolicyEngine()
    guardrail_engine = GuardrailEngine(
        input_guardrails=[MockGuardrailProvider()],
        context_guardrails=[],
        output_guardrails=[]
    )
    
    executor = ToolExecutor(
        registry=registry,
        auth_engine=auth_engine,
        guardrail_engine=guardrail_engine,
        policy_engine=policy_engine,
        approval_service=MockApprovalService()
    )
    
    generation_service = MockGenerationService()
    workflow_executor = WorkflowExecutor(executor, generation_service)
    
    # We create a dummy conversation for DB integrity
    user_id = uuid.uuid4()
    conv_id = uuid.uuid4()
    
    async with async_session_factory() as session:
        conv = Conversation(id=conv_id, user_id=user_id, title="Test")
        session.add(conv)
        await session.commit()
    
    logger.info("Testing Scenario: single_tool - Calculate 125 * 24")
    
    run_id = uuid.uuid4()
    agent_run = AgentRun(id=run_id, conversation_id=conv_id, request_id="test_req", status="PLANNING")
    
    # Dummy DAG plan
    plan_dict = {
      "goal": "Calculate 125 * 24",
      "steps": [
        {
          "step_id": "step_1",
          "action_type": "TOOL_CALL",
          "tool_name": "calculator",
          "purpose": "Multiply 125 by 24",
          "dependencies": [],
          "arguments": {"expression": "125 * 24"}
        },
        {
          "step_id": "step_2",
          "action_type": "FINALIZE",
          "purpose": "Final Answer",
          "dependencies": ["step_1"],
          "arguments": {"context": "$step_1.result"}
        }
      ],
      "reasoning_summary": "Calculated.",
      "completion_condition": "Done"
    }
    schema_plan = SchemaAgentPlan(**plan_dict)
    
    # Persist the plan (mocking orchestrator's _persist_plan)
    async with async_session_factory() as session:
        session.add(agent_run)
        plan = AgentPlan(run_id=run_id, goal=schema_plan.goal, status="PENDING")
        session.add(plan)
        await session.flush()
        
        for i, s in enumerate(schema_plan.steps):
            step = AgentPlanStep(
                plan_id=plan.id, step_id=s.step_id, sequence=i, action_type=s.action_type.value,
                tool_name=s.tool_name, purpose=s.purpose, dependencies=s.dependencies,
                arguments=s.arguments, status="PENDING"
            )
            session.add(step)
        await session.commit()
        
    context = RequestContext(user_id=str(user_id), roles=["user"], conversation_id=str(conv_id), request_id="req")
    
    # Execute workflow
    is_complete = await workflow_executor.execute_plan(agent_run, plan, context, [])
    
    assert is_complete is True
    assert agent_run.status == "COMPLETED"
    assert plan.status == "COMPLETED"
    
    async with async_session_factory() as session:
        fetched_plan = await session.get(AgentPlan, plan.id)
        await session.refresh(fetched_plan, ["plan_steps"])
        assert len(fetched_plan.plan_steps) == 2
        
        step_1 = next(s for s in fetched_plan.plan_steps if s.step_id == "step_1")
        assert step_1.status == "COMPLETED"
        assert step_1.output["result"] == 3000
        
        step_2 = next(s for s in fetched_plan.plan_steps if s.step_id == "step_2")
        assert step_2.status == "COMPLETED"
        
    logger.info("Test Passed: Calculate 125 * 24 (Dependencies Resolved, Steps Completed)")
    logger.info("Workflow Tests Completed")

if __name__ == "__main__":
    asyncio.run(run_workflow_tests())
