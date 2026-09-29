"""Workflow plan validation engine."""

import logging
from collections import defaultdict
from app.agent.schemas import AgentPlan, AgentPlanStepSchema
from app.core.config import settings

logger = logging.getLogger(__name__)


class PlanValidationError(Exception):
    pass


class PlanValidator:
    """Validates AgentPlans (DAG structure, cycles, limits, tool existence)."""

    def __init__(self, registry):
        self.registry = registry

    def validate(self, plan: AgentPlan) -> None:
        """
        Validates the entire plan.
        Raises PlanValidationError on any failure.
        """
        if not plan.steps:
            raise PlanValidationError("Plan must contain at least one step.")

        if len(plan.steps) > settings.max_plan_steps:
            raise PlanValidationError(f"Plan exceeds max steps ({settings.max_plan_steps}).")

        step_map: dict[str, AgentPlanStepSchema] = {}
        for step in plan.steps:
            if step.step_id in step_map:
                raise PlanValidationError(f"Duplicate step ID found: {step.step_id}")
            step_map[step.step_id] = step
            
            # Validate tool existence if TOOL_CALL
            if step.action_type == "TOOL_CALL":
                if not step.tool_name:
                    raise PlanValidationError(f"Step {step.step_id} is a TOOL_CALL but missing tool_name.")
                tool = self.registry.get_tool(step.tool_name)
                if not tool:
                    raise PlanValidationError(f"Step {step.step_id} requests unknown tool: {step.tool_name}")
                if not tool.is_enabled:
                    raise PlanValidationError(f"Step {step.step_id} requests disabled tool: {step.tool_name}")

        # Validate dependencies exist
        for step in plan.steps:
            for dep in step.dependencies:
                if dep not in step_map:
                    raise PlanValidationError(f"Step {step.step_id} depends on unknown step: {dep}")

        # Cycle detection and Depth calculation using topological sort
        in_degree = {s: 0 for s in step_map}
        adj = defaultdict(list)
        for step in plan.steps:
            for dep in step.dependencies:
                adj[dep].append(step.step_id)
                in_degree[step.step_id] += 1

        queue = [s for s in in_degree if in_degree[s] == 0]
        visited_count = 0
        depths = {s: 1 for s in in_degree if in_degree[s] == 0}
        
        # Initial depth for non-zero in-degree is 0 to be updated
        for s in in_degree:
            if in_degree[s] > 0:
                depths[s] = 0

        while queue:
            current = queue.pop(0)
            visited_count += 1
            
            for neighbor in adj[current]:
                in_degree[neighbor] -= 1
                depths[neighbor] = max(depths[neighbor], depths[current] + 1)
                
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited_count != len(step_map):
            logger.warning("SECURITY_TELEMETRY: PLAN_VALIDATION_FAILED - Cycle detected")
            raise PlanValidationError("Plan dependency graph contains cycles.")

        max_depth = max(depths.values()) if depths else 0
        if max_depth > settings.max_plan_depth:
            logger.warning("SECURITY_TELEMETRY: PLAN_VALIDATION_FAILED - Depth exceeded")
            raise PlanValidationError(f"Plan dependency depth ({max_depth}) exceeds max depth ({settings.max_plan_depth}).")

        logger.info("SECURITY_TELEMETRY: WORKFLOW_CREATED - Steps: %d, Max Depth: %d", len(plan.steps), max_depth)
