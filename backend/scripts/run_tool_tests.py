"""Tests for Tool Registry and Execution Framework."""

import asyncio
import sys
import os
import uuid
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.agent.tools.registry import ToolRegistry
from app.agent.tools.auth import ToolAuthorizationEngine, ToolAuthorizationPolicy
from app.agent.tools.executor import ToolExecutor
from app.agent.tools.base import RequestContext
from app.agent.tools.impl.calculator import CalculatorTool, CalculatorInput

# Setup simple logger
logging.basicConfig(level=logging.INFO)


async def run_tests():
    print("--- Tool Framework Security Tests ---")
    
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    
    # Custom policy for testing
    policy = ToolAuthorizationPolicy()
    policy._policy_matrix["admin_tool"] = ["admin"]
    
    auth_engine = ToolAuthorizationEngine(policy=policy)
    executor = ToolExecutor(registry, auth_engine)
    
    context = RequestContext(
        user_id=str(uuid.uuid4()),
        roles=["employee"],
        conversation_id=str(uuid.uuid4()),
        request_id=str(uuid.uuid4())
    )
    
    # Test 1: Successful Calculator execution
    print("\n[Test 1] Valid Calculator Execution")
    obs = await executor.execute(
        "calculator", 
        {"expression": "(125 * 24) / 2"}, 
        context, 
        str(uuid.uuid4())
    )
    assert obs.status == "SUCCESS"
    print(f"Passed! Result: {obs.result_summary}")
    
    # Test 2: Malicious Calculator injection
    print("\n[Test 2] Calculator Code Injection Attempt")
    obs = await executor.execute(
        "calculator", 
        {"expression": "__import__('os').system('echo HACKED')"}, 
        context, 
        str(uuid.uuid4())
    )
    assert obs.status == "TOOL_FAILED"
    print(f"Passed! Blocked with error: {obs.error}")
    
    # Test 3: Unknown Tool
    print("\n[Test 3] Unknown Tool Invocation")
    obs = await executor.execute(
        "admin_database", 
        {"query": "DROP TABLE users"}, 
        context, 
        str(uuid.uuid4())
    )
    assert obs.status == "UNKNOWN_TOOL"
    print("Passed! Blocked unknown tool.")
    
    print("\nAll Tool Framework tests passed successfully.")

if __name__ == "__main__":
    asyncio.run(run_tests())
