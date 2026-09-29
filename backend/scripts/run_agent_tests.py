"""Agent Foundation unit testing and limit verifications."""

import asyncio
import uuid
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.agent.state import AgentState
from app.agent.schemas import AgentPlan, AgentStatus, AgentStepSchema

def test_iteration_limit():
    """Verify that the agent state blocks execution if iterations are exceeded."""
    state = AgentState(
        run_id=uuid.uuid4(),
        request_id="test",
        conversation_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        task="Do a complex task",
        max_iterations=2
    )
    
    state.iteration_count = 1
    state.check_limits() # Should pass
    
    state.iteration_count = 2
    try:
        state.check_limits()
        assert False, "Should have raised ValueError for iterations."
    except ValueError as e:
        print(f"Passed: {e}")
        assert state.status == AgentStatus.FAILED


def test_token_limit():
    """Verify token budgets."""
    state = AgentState(
        run_id=uuid.uuid4(),
        request_id="test",
        conversation_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        task="Task",
        max_tokens=100
    )
    
    state.token_usage = 101
    try:
        state.check_limits()
        assert False, "Should have raised ValueError for tokens."
    except ValueError as e:
        print(f"Passed: {e}")


def test_timeout_limit():
    """Verify timeout budget."""
    state = AgentState(
        run_id=uuid.uuid4(),
        request_id="test",
        conversation_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        task="Task",
        max_time_seconds=1 # 1 second
    )
    import time
    time.sleep(1.1)
    
    try:
        state.check_limits()
        assert False, "Should have raised TimeoutError."
    except TimeoutError as e:
        print(f"Passed: {e}")


if __name__ == "__main__":
    print("Running Agent Limits Tests...")
    test_iteration_limit()
    test_token_limit()
    test_timeout_limit()
    print("All Agent Logic Limits Passed!")
