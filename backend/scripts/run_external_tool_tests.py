"""Workflow tests for External Tool Ecosystem."""

import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

import json
import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import create_async_engine
from app.db.database import async_session_factory
from app.models.agent import Base, AgentRun, AgentPlan, AgentPlanStep
from app.models.conversation import Conversation
from app.models.guardrail import GuardrailEvent

from app.agent.schemas import AgentPlan as SchemaAgentPlan
from app.agent.workflow import WorkflowExecutor
from app.agent.tools.registry import ToolRegistry
from app.agent.tools.executor import ToolExecutor
from app.agent.tools.auth import ToolAuthorizationEngine
from app.agent.tools.policy import ToolPolicyEngine
from app.agent.tools.base import RequestContext
from app.core.guardrails.engine import GuardrailEngine
from app.core.guardrails.impl.external_content import ExternalContentGuardrail
from app.agent.tools.impl.web_search import WebSearchTool
from app.agent.tools.impl.web_fetch import WebFetchTool
from app.agent.tools.impl.calendar_search import CalendarSearchTool
from app.agent.tools.impl.calendar_create_event import CalendarCreateEventTool
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

@compiles(ARRAY, "sqlite")
def compile_array_sqlite(type_, compiler, **kw):
    return "JSON"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockGenerationService:
    def generate_json(self, messages):
        return '{"final_answer": "Mocked response", "is_complete": true}'

class MockApprovalService:
    def __init__(self):
        self.approvals = {}

    async def get_pending_approval(self, user_id, agent_run_id, tool_name, arguments_hash):
        for approval in self.approvals.values():
            if approval.get("arguments_hash") == arguments_hash and approval.get("tool_name") == tool_name:
                class MockApprovalObj:
                    id = approval["id"]
                    status = approval["status"]
                return MockApprovalObj()
        return None

    async def create_approval_request(self, user_id, conversation_id, agent_run_id, step_id, tool_name, tool_version, arguments_hash, requested_action_desc, policy_result):
        approval_id = str(uuid.uuid4())
        self.approvals[approval_id] = {
            "id": approval_id,
            "arguments_hash": arguments_hash,
            "tool_name": tool_name,
            "status": "PENDING"
        }
        return approval_id

    async def consume_approval(self, approval_id):
        if approval_id in self.approvals and self.approvals[approval_id]["status"] == "APPROVED":
            self.approvals[approval_id]["status"] = "CONSUMED"
            return True
        return False
        
    def approve(self, arguments_hash):
        for approval in self.approvals.values():
            if approval["arguments_hash"] == arguments_hash:
                approval["status"] = "APPROVED"

async def run_workflow_tests():
    logger.info("Initializing External Workflow Tests")
    
    # 1. Setup DB
    from app.db.database import init_db
    await init_db()
        
    import app.agent.workflow
    app.agent.workflow.async_session_factory = async_session_factory
    import app.agent.orchestrator
    app.agent.orchestrator.async_session_factory = async_session_factory
    import app.agent.tools.executor
    app.agent.tools.executor.async_session_factory = async_session_factory
    
    # 2. Setup Framework
    registry = ToolRegistry()
    registry.register(WebSearchTool())
    registry.register(WebFetchTool())
    registry.register(CalendarSearchTool())
    registry.register(CalendarCreateEventTool())
    
    auth_engine = ToolAuthorizationEngine()
    policy_engine = ToolPolicyEngine()
    guardrail_engine = GuardrailEngine(
        input_guardrails=[],
        context_guardrails=[],
        output_guardrails=[]
    )
    
    approval_service = MockApprovalService()
    
    executor = ToolExecutor(
        registry=registry,
        auth_engine=auth_engine,
        guardrail_engine=guardrail_engine,
        policy_engine=policy_engine,
        approval_service=approval_service
    )
    
    workflow_executor = WorkflowExecutor(executor, MockGenerationService())
    
    user_id = uuid.uuid4()
    conv_id = uuid.uuid4()
    
    async with async_session_factory() as session:
        conv = Conversation(id=conv_id, user_id=user_id, title="Test")
        session.add(conv)
        await session.commit()
    
    run_id = uuid.uuid4()
    agent_run = AgentRun(id=run_id, conversation_id=conv_id, request_id="test_req", status="PLANNING")
    
    plan_dict = {
      "goal": "Search the web for Q3 dates and create a calendar event.",
      "steps": [
        {
          "step_id": "step_1",
          "action_type": "TOOL_CALL",
          "tool_name": "web_search",
          "purpose": "Find Q3 dates",
          "dependencies": [],
          "arguments": {"query": "Q3 2026 enterprise dates", "max_results": 1}
        },
        {
          "step_id": "step_2",
          "action_type": "TOOL_CALL",
          "tool_name": "calendar_create_event",
          "purpose": "Schedule Q3 review",
          "dependencies": ["step_1"],
          "arguments": {
              "title": "Q3 Review",
              "start_time": "2026-09-14T15:00:00Z",
              "end_time": "2026-09-14T16:00:00Z",
              "description": "Discussing web search results: $step_1.results",
              "location": "Virtual",
              "attendees": ["rahul@example.com"]
          }
        }
      ],
      "reasoning_summary": "Planning external integrations.",
      "completion_condition": "Event Created"
    }
    schema_plan = SchemaAgentPlan(**plan_dict)
    
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
    
    # 1. First execution pass (Web Search should complete, Calendar should pause for approval)
    logger.info("Executing Pass 1")
    is_complete = await workflow_executor.execute_plan(agent_run, plan, context, [])
    
    assert is_complete is False
    assert agent_run.status == "WAITING_FOR_APPROVAL"
    
    async with async_session_factory() as session:
        fetched_plan = await session.get(AgentPlan, plan.id)
        await session.refresh(fetched_plan, ["plan_steps"])
        
        step_1 = next(s for s in fetched_plan.plan_steps if s.step_id == "step_1")
        assert step_1.status == "COMPLETED"
        assert "results" in step_1.output
        
        step_2 = next(s for s in fetched_plan.plan_steps if s.step_id == "step_2")
        assert step_2.status == "WAITING_FOR_APPROVAL"
        
        # 2. Simulate User Approval
        logger.info("Simulating User Approval")
        # Find the arguments hash used for step_2
        # Since arguments contain $step_1.results, they were resolved in executor. 
        # We can just manually approve all pending in mock service
        for approval in approval_service.approvals.values():
            if approval["status"] == "PENDING":
                approval_service.approve(approval["arguments_hash"])

    # 3. Second execution pass (Should consume approval and create event)
    logger.info("Executing Pass 2 (Resuming)")
    agent_run.status = "EXECUTING" # Reset to executing as orchestrator would
    is_complete = await workflow_executor.execute_plan(agent_run, plan, context, [])
    
    assert is_complete is True
    assert agent_run.status == "COMPLETED"
    
    async with async_session_factory() as session:
        fetched_plan = await session.get(AgentPlan, plan.id)
        await session.refresh(fetched_plan, ["plan_steps"])
        
        step_2 = next(s for s in fetched_plan.plan_steps if s.step_id == "step_2")
        assert step_2.status == "COMPLETED"
        assert step_2.output["status"] == "CREATED"
        
    logger.info("All External Workflow Tests Passed!")

if __name__ == "__main__":
    asyncio.run(run_workflow_tests())
