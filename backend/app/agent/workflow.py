"""Workflow Execution Engine."""

import re
import json
import logging
from typing import Any
import uuid

from app.models.agent import AgentRun, AgentPlan, AgentPlanStep
from app.agent.tools.executor import ToolExecutor
from app.agent.schemas import AgentSynthesizeOutput
from app.agent.prompts import AGENT_SYNTHESIZE_PROMPT
from app.core.tracing import Tracer
from app.db.database import async_session_factory

logger = logging.getLogger(__name__)

REFERENCE_REGEX = re.compile(r"\$([a-zA-Z0-9_]+)(?:\.([a-zA-Z0-9_.]+))?")

class WorkflowExecutionError(Exception):
    pass

class WorkflowExecutor:
    """Executes a validated DAG AgentPlan."""
    
    def __init__(self, executor: ToolExecutor, generation_service, agent_registry=None, policy_engine=None):
        self.executor = executor
        self.generation_service = generation_service
        self.agent_registry = agent_registry
        self.policy_engine = policy_engine

    async def _resolve_references(self, arguments: dict[str, Any], completed_steps: dict[str, dict[str, Any]]) -> dict[str, Any]:
        # (same as before)
        resolved = {}
        for k, v in arguments.items():
            if isinstance(v, str):
                match = REFERENCE_REGEX.search(v)
                if match and match.group(0) == v:
                    step_id = match.group(1)
                    key_path = match.group(2)
                    if step_id not in completed_steps:
                        raise WorkflowExecutionError(f"Reference to unresolved step: {step_id}")
                    data = completed_steps[step_id]
                    if key_path:
                        for p in key_path.split("."):
                            data = data.get(p, {}) if isinstance(data, dict) else {}
                    resolved[k] = data
                elif match:
                    def replace_ref(m):
                        s_id = m.group(1)
                        k_p = m.group(2)
                        if s_id not in completed_steps:
                            return m.group(0)
                        d = completed_steps[s_id]
                        if k_p:
                            for p in k_p.split("."):
                                d = d.get(p, {}) if isinstance(d, dict) else {}
                        return str(d) if not isinstance(d, (dict, list)) else json.dumps(d)
                    resolved[k] = REFERENCE_REGEX.sub(replace_ref, v)
                else:
                    resolved[k] = v
            elif isinstance(v, dict):
                resolved[k] = await self._resolve_references(v, completed_steps)
            elif isinstance(v, list):
                resolved[k] = [(await self._resolve_references({"_": item}, completed_steps))["_"] for item in v]
            else:
                resolved[k] = v
        return resolved

    async def execute_plan(
        self, 
        agent_run: AgentRun, 
        plan: AgentPlan, 
        context, 
        history: list[dict[str, str]]
    ) -> bool:
        from sqlalchemy import select
        from sqlalchemy.exc import DBAPIError
        import asyncio

        async with async_session_factory() as session:
            try:
                stmt = select(AgentRun).where(AgentRun.id == agent_run.id).with_for_update(nowait=True)
                locked_run = (await session.execute(stmt)).scalars().first()
                if not locked_run:
                    raise WorkflowExecutionError("AgentRun not found")
                
                stmt_plan = select(AgentPlan).where(AgentPlan.id == plan.id).with_for_update(nowait=True)
                locked_plan = (await session.execute(stmt_plan)).scalars().first()
                await session.refresh(locked_plan, ["plan_steps"])
                
                agent_run = locked_run
                plan = locked_plan
                steps = plan.plan_steps
                
                for s in steps:
                    if s.status == "RUNNING":
                        logger.warning("SECURITY_TELEMETRY: WORKFLOW_RECOVERY - Step %s was left RUNNING. Marking FAILED.", s.step_id)
                        s.status = "FAILED"
                        s.error = "Step stuck in RUNNING state (process crashed). Marking FAILED for safety."
                        plan.status = "FAILED"
                        agent_run.status = "FAILED"
                        agent_run.error = "Workflow recovery halted execution due to unsafe stale state."
                        await session.commit()
                        return False

            except DBAPIError as e:
                logger.warning("SECURITY_TELEMETRY: WORKFLOW_CONCURRENCY_LOCKED - Run %s is already being executed.", agent_run.id)
                return False
            
            while True:
                ready_steps = [
                    s for s in steps 
                    if s.status in ["PENDING", "WAITING_FOR_APPROVAL"]
                    and all(ds.status == "COMPLETED" for ds in steps if ds.step_id in s.dependencies)
                ]
                
                if not ready_steps:
                    pending = [s for s in steps if s.status in ["PENDING", "WAITING_FOR_APPROVAL"]]
                    if pending:
                        waiting = [s for s in steps if s.status == "WAITING_FOR_APPROVAL"]
                        if waiting:
                            logger.info("SECURITY_TELEMETRY: WORKFLOW_PAUSED - Waiting for approval")
                            plan.status = "WAITING_FOR_APPROVAL"
                            agent_run.status = "WAITING_FOR_APPROVAL"
                            await session.commit()
                            return False
                        
                        logger.error("SECURITY_TELEMETRY: WORKFLOW_BLOCKED - Deadlock detected")
                        plan.status = "FAILED"
                        agent_run.status = "FAILED"
                        agent_run.error = "Workflow deadlock."
                        await session.commit()
                        return False
                    
                    logger.info("SECURITY_TELEMETRY: WORKFLOW_COMPLETED")
                    plan.status = "COMPLETED"
                    agent_run.status = "COMPLETED"
                    await session.commit()
                    return True
                
                completed_outputs = {s.step_id: s.output for s in steps if s.status == "COMPLETED"}
                
                # Pre-process arguments synchronously to avoid async context issues
                for step in ready_steps:
                    step.status = "RUNNING"
                await session.commit()

                # Execute ready steps concurrently
                tasks = [
                    self._execute_step(step, completed_outputs, context, history, str(agent_run.id))
                    for step in ready_steps
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Apply results
                any_failed = False
                any_waiting = False
                
                for step, result in zip(ready_steps, results):
                    if isinstance(result, Exception):
                        logger.error("Step execution exception: %s", result)
                        step.status = "FAILED"
                        step.error = str(result)
                        any_failed = True
                    elif result == "WAITING_FOR_APPROVAL":
                        any_waiting = True
                    elif result == "FAILED":
                        any_failed = True
                
                if any_waiting:
                    plan.status = "WAITING_FOR_APPROVAL"
                    agent_run.status = "WAITING_FOR_APPROVAL"
                    await session.commit()
                    return False
                    
                if any_failed:
                    plan.status = "FAILED"
                    agent_run.status = "FAILED"
                    failed_steps = [s for s in ready_steps if s.status == "FAILED"]
                    if failed_steps:
                        agent_run.error = f"Step failed: {failed_steps[0].error}"
                    await session.commit()
                    return False
                    
                await session.commit()
                
                # If there's a FINALIZE or a step explicitly returning is_complete
                if any(s.action_type == "FINALIZE" or (s.output and s.output.get("is_complete")) for s in ready_steps if s.status == "COMPLETED"):
                    agent_run.status = "COMPLETED"
                    plan.status = "COMPLETED"
                    await session.commit()
                    return True

    async def _execute_step(self, step, completed_outputs, context, history, agent_run_id: str) -> str:
        """Executes a single step and returns its new status. Updates step attributes."""
        try:
            resolved_args = await self._resolve_references(step.arguments or {}, completed_outputs)
            
            # Swarm Agent Delegation
            if hasattr(step, "agent_id") and step.agent_id:
                if not self.agent_registry or not self.policy_engine:
                    raise WorkflowExecutionError("Swarm features not configured in WorkflowExecutor")
                
                if not self.policy_engine.validate_delegation("supervisor", step.agent_id):
                    raise WorkflowExecutionError(f"Policy Engine denied delegation to {step.agent_id}")
                    
                agent = self.agent_registry.get_agent(step.agent_id)
                from app.agent.swarm.schemas import AgentDelegationRequest
                req = AgentDelegationRequest(
                    agent_id=step.agent_id,
                    task=resolved_args.get("task", step.purpose),
                    context=completed_outputs
                )
                
                with Tracer.start_span(f"swarm_agent_{step.agent_id}") as span:
                    obs = await agent.execute(req, context)
                
                if obs.status == "COMPLETED":
                    step.status = "COMPLETED"
                    step.output = {"final_answer": obs.output} if isinstance(obs.output, str) else obs.output
                    return "COMPLETED"
                else:
                    step.status = "FAILED"
                    step.error = obs.error
                    return "FAILED"
            
            # Normal Tool Execution
            if step.action_type == "TOOL_CALL":
                with Tracer.start_span(f"step_{step.step_id}") as span:
                    obs = await self.executor.execute(
                        tool_name=step.tool_name,
                        arguments=resolved_args,
                        context=context,
                        tool_call_id=str(step.id),
                        agent_run_id=agent_run_id
                    )
                
                if obs.status == "SUCCESS":
                    step.status = "COMPLETED"
                    try:
                        step.output = json.loads(obs.result_summary)
                    except json.JSONDecodeError:
                        step.output = {"result": obs.result_summary}
                    return "COMPLETED"
                        
                elif obs.status in ["APPROVAL_REQUIRED", "WAITING_FOR_APPROVAL"]:
                    logger.info("SECURITY_TELEMETRY: STEP_APPROVAL_REQUIRED - %s", step.tool_name)
                    step.status = "WAITING_FOR_APPROVAL"
                    return "WAITING_FOR_APPROVAL"
                    
                else:
                    logger.warning("SECURITY_TELEMETRY: STEP_POLICY_DENIED - %s: %s", step.tool_name, obs.status)
                    step.status = "FAILED"
                    step.error = obs.error or obs.result_summary
                    return "FAILED"
                    
            elif step.action_type in ["SYNTHESIZE", "FINALIZE"]:
                context_str = json.dumps(completed_outputs, indent=2)
                prompt = AGENT_SYNTHESIZE_PROMPT.format(context=context_str)
                messages = [{"role": "system", "content": prompt}]
                if history:
                    messages.append({"role": "user", "content": f"History:\n{json.dumps(history)}"})
                
                resp_json = self.generation_service.generate_json(messages)
                data = json.loads(resp_json)
                
                step.status = "COMPLETED"
                step.output = data
                return "COMPLETED"
                
            else:
                step.status = "FAILED"
                step.error = f"Unknown action type {step.action_type}"
                return "FAILED"
                
        except Exception as e:
            logger.error("Workflow step execution failed: %s", e, exc_info=True)
            step.status = "FAILED"
            step.error = str(e)
            return "FAILED"
