"""Swarm Orchestrator — the Supervisor for the Multi-Agent System."""

import json
import logging
import uuid
import time
from typing import Any

from app.agent.schemas import AgentPlan as SchemaAgentPlan, AgentPlanStepSchema as SchemaAgentPlanStep
from app.services.generation_service import GenerationService
from app.agent.tools.registry import ToolRegistry
from app.agent.tools.executor import ToolExecutor
from app.agent.tools.base import RequestContext
from app.core.tracing import Tracer
from app.db.database import async_session_factory
from app.models.agent import AgentRun, AgentPlan, AgentPlanStep
from app.agent.workflow import WorkflowExecutor
from app.agent.memory.retriever import MemoryRetriever
from app.services.memory_service import MemoryService
from app.agent.memory.policy import MemoryProposal
from app.agent.swarm.registry import AgentRegistry
from app.agent.swarm.policy import AgentPolicyEngine, AgentAuthorizationService

logger = logging.getLogger(__name__)

SWARM_PLANNER_PROMPT = """You are the Supervisor Agent of a Multi-Agent Swarm.
Your task is to break down the user's complex request into a DAG of sub-tasks, and delegate each sub-task to a specialized agent.

Available Specialized Agents:
{agent_descriptions}

You MUST output your plan as a JSON object matching this schema:
{{
  "goal": "Description of what we are achieving",
  "reasoning_summary": "Brief summary of the reasoning for this plan.",
  "completion_condition": "What constitutes completion of this plan.",
  "steps": [
    {{
      "step_id": "step_1",
      "action_type": "TOOL_CALL",
      "tool_name": "specialized_agent",
      "agent_id": "research_agent",
      "purpose": "What this agent needs to do",
      "dependencies": [],
      "arguments": {{
         "task": "Find latest Q3 earnings for ACME Corp"
      }}
    }},
    {{
      "step_id": "step_2",
      "action_type": "TOOL_CALL",
      "tool_name": "specialized_agent",
      "agent_id": "synthesis_agent",
      "purpose": "Summarize the findings",
      "dependencies": ["step_1"],
      "arguments": {{
         "task": "Synthesize the findings into a report."
      }}
    }}
  ]
}}

Rules:
1. Every step must have an 'agent_id' corresponding to one of the available agents.
2. The final step should usually be delegated to 'synthesis_agent' to combine the results.
3. If multiple agents can work in parallel, do NOT list them as dependencies of each other.
4. Set 'tool_name' to "specialized_agent".
5. Set 'action_type' to "TOOL_CALL".
"""

class SwarmOrchestrator:
    def __init__(
        self,
        generation_service: GenerationService,
        registry: ToolRegistry,
        executor: ToolExecutor,
        agent_registry: AgentRegistry,
        policy_engine: AgentPolicyEngine,
        auth_service: AgentAuthorizationService,
        allowed_roles: list[str],
        memory_retriever: MemoryRetriever,
        memory_service: MemoryService
    ):
        self.generation_service = generation_service
        self.registry = registry
        self.executor = executor
        self.agent_registry = agent_registry
        self.policy_engine = policy_engine
        self.auth_service = auth_service
        self.allowed_roles = allowed_roles
        self.memory_retriever = memory_retriever
        self.memory_service = memory_service
        
        # We reuse WorkflowExecutor but inject the agent registry and policy engine
        self.workflow_executor = WorkflowExecutor(
            executor, 
            generation_service,
            agent_registry=self.agent_registry,
            policy_engine=self.policy_engine
        )

    async def run(
        self, 
        task: str, 
        request_id: str, 
        conversation_id: uuid.UUID, 
        user_id: uuid.UUID,
        history: list[dict[str, str]] = None
    ) -> str:
        """Execute the Swarm DAG loop."""
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

            # 1. GENERATE SWARM PLAN (SUPERVISOR)
            schema_plan = await self._generate_plan(task, history, memory_context)
            
            # 2. VALIDATE SWARM PLAN
            self._validate_plan(schema_plan)
            
            # 3. SAVE PLAN TO DB
            plan, steps = await self._persist_plan(run_id, schema_plan)
            
            # 4. EXECUTE SWARM WORKFLOW
            context = RequestContext(
                user_id=str(user_id),
                roles=self.allowed_roles,
                conversation_id=str(conversation_id),
                request_id=request_id
            )
            
            # The workflow executor will handle the parallel/DAG execution and delegation
            is_complete = await self.workflow_executor.execute_plan(run, plan, context, history)
            
            if not is_complete:
                if run.status == "WAITING_FOR_APPROVAL":
                    return "This action requires human approval. Please review the pending requests."
                else:
                    return f"Workflow halted: {run.error}"
                    
            # 5. FETCH FINAL ANSWER
            final_answer = self._extract_final_answer(steps)

            # 6. EXTRACT & PROPOSE NEW MEMORY
            await self._extract_and_propose_memory(task, final_answer, str(user_id), str(conversation_id), request_id)

            return final_answer
                
        except Exception as e:
            logger.error("Swarm execution failed: %s", e, exc_info=True)
            async with async_session_factory() as session:
                run = await session.get(AgentRun, run_id)
                if run:
                    run.status = "FAILED"
                    run.error = str(e)
                    await session.commit()
            return "Something went wrong while completing that task."

    async def _generate_plan(self, task: str, history: list[dict[str, str]], memory_context: str = "") -> SchemaAgentPlan:
        """Invoke Supervisor LLM to create a structured Swarm plan."""
        with Tracer.start_span("swarm_planning") as span:
            agent_descs = "\n".join([
                f"- {a['agent_id']}: {a['description']} (Capabilities: {a['capabilities']})" 
                for a in self.agent_registry.get_agent_descriptions()
            ])
            prompt = SWARM_PLANNER_PROMPT.format(agent_descriptions=agent_descs)
            
            messages = [{"role": "system", "content": prompt}]
            if history:
                messages.append({"role": "user", "content": f"Conversation History:\n{json.dumps(history)}"})
            
            if memory_context:
                messages.append({"role": "user", "content": f"<USER_MEMORY>\n{memory_context}\n</USER_MEMORY>"})
                
            messages.append({"role": "user", "content": f"TASK: {task}"})
            
            response_json = self.generation_service.generate_json(messages)
            
            # To handle extra fields not in SchemaAgentPlan, we just map it loosely
            data = json.loads(response_json)
            
            steps = []
            for s in data.get("steps", []):
                steps.append(SchemaAgentPlanStep(
                    step_id=s["step_id"],
                    action_type=s["action_type"],
                    tool_name=s.get("tool_name", "specialized_agent"),
                    purpose=s["purpose"],
                    dependencies=s.get("dependencies", []),
                    arguments=s.get("arguments", {})
                ))
                # Store agent_id in arguments temporarily so we can pass it to persistence
                steps[-1].arguments["__agent_id__"] = s.get("agent_id")
                
            plan = SchemaAgentPlan(
                goal=data.get("goal", "Swarm Goal"),
                reasoning_summary=data.get("reasoning_summary", "Swarm reasoning"),
                completion_condition=data.get("completion_condition", "All steps complete"),
                steps=steps
            )
            
            span["goal"] = plan.goal
            span["steps_count"] = len(plan.steps)
            return plan

    def _validate_plan(self, plan: SchemaAgentPlan):
        """Validate the swarm plan."""
        step_ids = {s.step_id for s in plan.steps}
        for s in plan.steps:
            for d in s.dependencies:
                if d not in step_ids:
                    raise ValueError(f"Invalid dependency: {d} in step {s.step_id}")
            agent_id = s.arguments.get("__agent_id__")
            if not agent_id:
                 raise ValueError(f"Missing agent_id in step {s.step_id}")
            
            # Enforce Policy Engine rules
            if not self.policy_engine.validate_delegation("supervisor", agent_id):
                 raise ValueError(f"Policy Engine blocked delegation Supervisor -> {agent_id}")

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
                agent_id = s.arguments.pop("__agent_id__", None)
                
                step = AgentPlanStep(
                    plan_id=plan.id,
                    step_id=s.step_id,
                    sequence=i,
                    action_type=s.action_type.value,
                    tool_name=s.tool_name,
                    purpose=s.purpose,
                    dependencies=s.dependencies,
                    arguments=s.arguments,
                    agent_id=agent_id, # The Swarm specific field
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
        try:
            prompt = (
                "You are a memory extraction assistant. Analyze the User Task and Agent Answer. "
                "If the user explicitly stated a durable fact about themselves, extract it. "
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
