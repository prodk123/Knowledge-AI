"""Functional Tests for Multi-Agent Swarm Execution."""

import asyncio
import json
import logging
import uuid
import sys

from app.api.conversations import get_query_router
from app.rag.router import QueryRouter
from app.services.generation_service import GenerationService
from app.agent.swarm.orchestrator import SwarmOrchestrator
from app.agent.swarm.registry import AgentRegistry
from app.agent.swarm.policy import AgentPolicyEngine, AgentAuthorizationService
from app.agent.swarm.agents.specialized import create_specialized_agents
from app.agent.tools.executor import ToolExecutor
from app.agent.tools.registry import ToolRegistry
from app.agent.memory.retriever import MemoryRetriever
from app.services.memory_service import MemoryService
from app.db.database import async_session_factory
from app.models.agent import AgentRun, AgentPlan, AgentPlanStep
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

async def main():
    logger.info("Initializing Swarm Components for Functional Testing...")
    
    from app.services.generation_service import GenerationService
    from app.core.config import settings
    generation_service = GenerationService(settings)
    
    # Mock for testing without API keys
    def mock_generate_json(messages):
        return json.dumps({
            "goal": "Test goal",
            "reasoning_summary": "Testing mock",
            "completion_condition": "Done",
            "steps": [
                {
                    "step_id": "step_1",
                    "action_type": "TOOL_CALL",
                    "tool_name": "specialized_agent",
                    "agent_id": "research_agent",
                    "purpose": "Do research",
                    "dependencies": [],
                    "arguments": {"task": "Search ACME"}
                }
            ]
        })
    generation_service.generate_json = mock_generate_json
    
    agent_registry = AgentRegistry()
    tool_registry = ToolRegistry()
    from app.agent.tools.policy import ToolPolicyEngine
    tool_executor = ToolExecutor(tool_registry, ToolPolicyEngine())
    
    for agent in create_specialized_agents(generation_service, tool_executor):
        agent_registry.register(agent)
    
    policy_engine = AgentPolicyEngine()
    auth_service = AgentAuthorizationService()
    
    # Mock Memory
    class MockMemoryRetriever:
        async def retrieve_relevant_memory(self, task: str, user_id: str):
            return []
            
    class MockMemoryService:
        async def propose_memory(self, proposal, user_id):
            pass
            
    orchestrator = SwarmOrchestrator(
        generation_service=generation_service,
        registry=tool_registry,
        executor=tool_executor,
        agent_registry=agent_registry,
        policy_engine=policy_engine,
        auth_service=auth_service,
        allowed_roles=["employee"],
        memory_retriever=MockMemoryRetriever(),
        memory_service=MockMemoryService()
    )
    
    passed = 0
    total = 3
    
    try:
        # TEST 1: Agent Registration
        logger.info("\n--- TEST 1: Agent Registration ---")
        agents = agent_registry.get_all_agents()
        assert len(agents) >= 4
        logger.info("PASS: Agents registered.")
        passed += 1
        
        # TEST 2: Delegation Validation
        logger.info("\n--- TEST 2: Delegation Validation ---")
        assert policy_engine.validate_delegation("supervisor", "research_agent") == True
        assert policy_engine.validate_delegation("research_agent", "rag_agent") == False
        logger.info("PASS: Policy engine enforces delegation rules.")
        passed += 1
        
        # TEST 3: Swarm DAG Structure (Mock)
        logger.info("\n--- TEST 3: Swarm DAG Structure ---")
        # In a real scenario with database configured, we'd run a full orchestrator task.
        # But for this functional test script that runs without dropping/creating tables,
        # we'll just test the planner prompt output loosely using the generation service directly
        # to ensure the Supervisor generates valid JSON with agent_id.
        plan = await orchestrator._generate_plan("Research ACME corp and summarize.", [], "")
        assert len(plan.steps) > 0
        
        has_agent_id = any(s.arguments.get("__agent_id__") for s in plan.steps)
        assert has_agent_id, "Supervisor failed to include agent_id in plan steps"
        logger.info("PASS: Supervisor planner generates valid Swarm plan.")
        passed += 1
        
    except AssertionError as e:
        logger.error(f"FAIL: {e}")
    except Exception as e:
        logger.error(f"FAIL: Unexpected error: {e}")
        
    logger.info(f"\nFunctional Test Results: {passed}/{total} Passed")
    if passed < total:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
