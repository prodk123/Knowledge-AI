"""Agent Orchestrator — Bounded loop execution engine."""

import json
import logging
import uuid
import time
from typing import Any

from app.agent.schemas import AgentPlan as SchemaAgentPlan
from app.agent.prompts import AGENT_PLANNER_PROMPT
from app.services.generation_service import GenerationService
from app.agent.tools.registry import ToolRegistry
from app.agent.tools.executor import ToolExecutor
from app.agent.tools.base import RequestContext
from sqlalchemy import func
from app.core.tracing import Tracer
from app.db.database import async_session_factory
from app.models.agent import AgentRun, AgentPlan, AgentPlanStep
from app.agent.validator import PlanValidator
from app.agent.workflow import WorkflowExecutor

logger = logging.getLogger(__name__)

from app.agent.memory.retriever import MemoryRetriever
from app.services.memory_service import MemoryService
from app.agent.memory.policy import MemoryProposal

class AgentOrchestrator:
    def __init__(
        self,
        generation_service: GenerationService,
        registry: ToolRegistry,
        executor: ToolExecutor,
        allowed_roles: list[str],
        memory_retriever: MemoryRetriever,
        memory_service: MemoryService
    ):
        self.generation_service = generation_service
        self.registry = registry
        self.executor = executor
        self.allowed_roles = allowed_roles
        self.memory_retriever = memory_retriever
        self.memory_service = memory_service
        self.validator = PlanValidator(registry)
        self.workflow_executor = WorkflowExecutor(executor, generation_service)

    async def run(
        self, 
        task: str, 
        request_id: str, 
        conversation_id: uuid.UUID, 
        user_id: uuid.UUID,
        history: list[dict[str, str]] = None
    ) -> str:
        """Execute the bounded DAG agent loop."""
        if history is None:
            history = []
            
        run_id = uuid.uuid4()
        
        async with async_session_factory() as session:
            run = AgentRun(
                id=run_id,
                conversation_id=conversation_id,
                request_id=request_id,
                status="PLANNING"
            )
            session.add(run)
            await session.commit()
            
        try:
            # 0. RETRIEVE RELEVANT MEMORY
            memories = await self.memory_retriever.retrieve_relevant_memory(task, str(user_id))
            memory_context = ""
            if memories:
                memory_context = "\n".join([
                    f"[{m.memory_type}] {m.content} (Trust: {m.trust_level})"
                    for m in memories
                ])

            # 1. GENERATE PLAN
            schema_plan = await self._generate_plan(task, history, memory_context)
            
            # 2. VALIDATE PLAN
            self.validator.validate(schema_plan)
            
            # 3. SAVE PLAN TO DB
            plan, steps = await self._persist_plan(run_id, schema_plan)
            
            # 4. EXECUTE WORKFLOW
            context = RequestContext(
                user_id=str(user_id),
                roles=self.allowed_roles,
                conversation_id=str(conversation_id),
                request_id=request_id
            )
            
            is_complete = await self.workflow_executor.execute_plan(run, plan, context, history)
            
            async with async_session_factory() as session:
                refreshed_plan = await session.get(AgentPlan, plan.id)
                await session.refresh(refreshed_plan, ["plan_steps"])
                steps = refreshed_plan.plan_steps
                refreshed_run = await session.get(AgentRun, run.id)
                run_error = refreshed_run.error
                run_status = refreshed_run.status
            
            if not is_complete:
                if run_status == "WAITING_FOR_APPROVAL":
                    return "This action requires human approval. Please review the pending requests."
                else:
                    return f"Workflow halted: {run_error}"
                    
            # 5. FETCH FINAL ANSWER
            final_answer = self._extract_final_answer(steps)

            # 6. EXTRACT & PROPOSE NEW MEMORY
            await self._extract_and_propose_memory(task, final_answer, str(user_id), str(conversation_id), request_id)

            return final_answer
                
        except Exception as e:
            logger.error("Agent execution failed: %s", e, exc_info=True)
            async with async_session_factory() as session:
                run = await session.get(AgentRun, run_id)
                if run:
                    run.status = "FAILED"
                    run.error = str(e)
                    await session.commit()
            return "Something went wrong while completing that task."

    async def resume(
        self,
        agent_run_id: uuid.UUID,
        history: list[dict[str, str]] = None
    ) -> str:
        """Resume a paused workflow."""
        if history is None:
            history = []
            
        async with async_session_factory() as session:
            run = await session.get(AgentRun, agent_run_id)
            if not run:
                raise ValueError("AgentRun not found")
                
            plans = await session.execute(
                f"SELECT id FROM agent_plans WHERE run_id = '{agent_run_id}' ORDER BY created_at DESC LIMIT 1"
            )
            plan_id = plans.scalar_one_or_none()
            if not plan_id:
                raise ValueError("AgentPlan not found for run")
                
            plan = await session.get(AgentPlan, plan_id)
            user_id_str = run.conversation.user_id if run.conversation else str(uuid.uuid4())
            conversation_id_str = str(run.conversation_id)
            request_id_str = run.request_id
            
        try:
            context = RequestContext(
                user_id=str(user_id_str),
                roles=self.allowed_roles,
                conversation_id=conversation_id_str,
                request_id=request_id_str
            )
            
            is_complete = await self.workflow_executor.execute_plan(run, plan, context, history)
            
            if not is_complete:
                if run.status == "WAITING_FOR_APPROVAL":
                    return "This action requires human approval. Please review the pending requests."
                else:
                    return f"Workflow halted: {run.error}"
                    
            async with async_session_factory() as session:
                await session.refresh(plan, ["plan_steps"])
                return self._extract_final_answer(plan.plan_steps)
                    
        except Exception as e:
            logger.error("Agent resume failed: %s", e, exc_info=True)
            async with async_session_factory() as session:
                session.add(run)
                run.status = "FAILED"
                run.error = str(e)
                await session.commit()
            return "Something went wrong while resuming that task."

    async def _generate_plan(self, task: str, history: list[dict[str, str]], memory_context: str = "") -> SchemaAgentPlan:
        """Invoke LLM to create a structured plan."""
        with Tracer.start_span("agent_planning") as span:
            tool_descs = "\n".join([f"{t['name']}: {t['description']}\nSchema: {json.dumps(t.get('input_schema', {}))}" for t in self.registry.get_tool_descriptions()])
            prompt = AGENT_PLANNER_PROMPT.format(tool_descriptions=tool_descs)
            messages = [{"role": "system", "content": prompt}]
            if history:
                messages.append({"role": "user", "content": f"Conversation History:\n{json.dumps(history)}"})
            
            # Inject memory context safely
            if memory_context:
                messages.append({"role": "user", "content": f"<USER_MEMORY>\n{memory_context}\n</USER_MEMORY>"})
                
            messages.append({"role": "user", "content": f"TASK: {task}"})
            
            response_json = self.generation_service.generate_json(messages)
            data = json.loads(response_json)
            plan = SchemaAgentPlan(**data)
            
            span["goal"] = plan.goal
            span["steps_count"] = len(plan.steps)
            return plan

    async def _persist_plan(self, run_id: uuid.UUID, schema_plan: SchemaAgentPlan) -> tuple[AgentPlan, list[AgentPlanStep]]:
        async with async_session_factory() as session:
            plan = AgentPlan(
                run_id=run_id,
                goal=schema_plan.goal,
                status="PENDING",
            )
            session.add(plan)
            await session.flush()
            
            steps = []
            for i, s in enumerate(schema_plan.steps):
                step = AgentPlanStep(
                    plan_id=plan.id,
                    step_id=s.step_id,
                    sequence=i,
                    action_type=s.action_type.value,
                    tool_name=s.tool_name,
                    purpose=s.purpose,
                    dependencies=s.dependencies,
                    arguments=s.arguments,
                    status="PENDING"
                )
                session.add(step)
                steps.append(step)
                
            await session.commit()
            return plan, steps

    def _extract_final_answer(self, steps: list[AgentPlanStep]) -> str:
        for s in steps[::-1]:
            if s.status == "COMPLETED" and s.output:
                if "final_answer" in s.output:
                    return s.output["final_answer"]
                if "result" in s.output:
                    return str(s.output["result"])
        return "Task completed."

    async def _extract_and_propose_memory(self, task: str, final_answer: str, user_id: str, conversation_id: str, request_id: str) -> None:
        """Extract durable facts from the conversation and propose them as memory."""
        try:
            # We use a very simple structured prompt to extract memory if any explicit facts were stated
            prompt = (
                "You are a memory extraction assistant. Analyze the User Task and Agent Answer. "
                "If the user explicitly stated a durable fact about themselves (e.g., 'I prefer concise answers', 'I am the VP of sales'), "
                "or if a significant episodic event occurred (e.g., 'I scheduled a meeting'), extract it. "
                "Return a JSON list of objects with 'memory_type' (SEMANTIC or EPISODIC), 'content', 'source_type', 'trust_level', and 'importance' (1-5). "
                "If nothing durable or significant was stated, return an empty list [].\n\n"
                f"User Task: {task}\nAgent Answer: {final_answer}"
            )
            
            messages = [{"role": "system", "content": prompt}]
            response_json = self.generation_service.generate_json(messages)
            
            data = json.loads(response_json)
            if not isinstance(data, list):
                if isinstance(data, dict) and "memories" in data:
                    data = data["memories"]
                else:
                    data = []
                    
            for item in data:
                proposal = MemoryProposal(
                    memory_type=item.get("memory_type", "SEMANTIC"),
                    content=item.get("content", ""),
                    source_type=item.get("source_type", "AGENT_INFERENCE"),
                    source_reference=conversation_id,
                    trust_level=item.get("trust_level", "inferred"),
                    importance=item.get("importance", 3)
                )
                await self.memory_service.propose_memory(proposal, user_id)
                
        except Exception as e:
            logger.warning("Failed to extract/propose memory: %s", e)
