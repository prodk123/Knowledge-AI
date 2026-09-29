"""Red-team tests for Workflow Engine."""

import json
import asyncio
import logging
from app.agent.schemas import AgentPlan
from app.agent.validator import PlanValidator, PlanValidationError
from app.agent.tools.registry import ToolRegistry
from app.agent.tools.impl.calculator import CalculatorTool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_redteam_tests():
    logger.info("Initializing Workflow Red-Team Tests")
    
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    
    validator = PlanValidator(registry)
    
    with open("scripts/workflow_redteam_dataset.json") as f:
        dataset = json.load(f)
        
    for case in dataset:
        logger.info(f"Testing Scenario: {case['scenario']} - {case['description']}")
        
        plan = AgentPlan(**case['plan'])
        
        try:
            validator.validate(plan)
            logger.error(f"Test Failed: Expected error '{case['expected_error']}' but validation passed.")
        except PlanValidationError as e:
            if case['expected_error'] in str(e).lower() or case['expected_error'].replace(" ", "") in str(e).lower():
                logger.info(f"Test Passed: Caught expected error '{str(e)}'")
            else:
                # Basic string inclusion match
                parts = case['expected_error'].split()
                if all(p.lower() in str(e).lower() for p in parts):
                    logger.info(f"Test Passed: Caught expected error '{str(e)}'")
                else:
                    logger.warning(f"Test Warning: Caught error '{str(e)}', expected something like '{case['expected_error']}'")
                    
    logger.info("Workflow Red-Team Tests Completed")

if __name__ == "__main__":
    asyncio.run(run_redteam_tests())
