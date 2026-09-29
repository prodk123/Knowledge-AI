"""Specialized Agents for the Swarm."""

import json
import logging
import time

from app.agent.swarm.agents.base import BaseSpecializedAgent
from app.agent.swarm.schemas import AgentDelegationRequest, AgentObservation
from app.agent.tools.base import RequestContext
from app.agent.tools.executor import ToolExecutor
from app.services.generation_service import GenerationService
from app.agent.prompts import AGENT_PLANNER_PROMPT # We could use a specialized prompt

logger = logging.getLogger(__name__)

class GenericSpecializedAgent(BaseSpecializedAgent):
    """A generic implementation for specialized agents that use LLM and tools."""
    
    def __init__(
        self,
        agent_id: str,
        description: str,
        capabilities: list[str],
        allowed_tools: list[str],
        generation_service: GenerationService,
        tool_executor: ToolExecutor,
        system_prompt: str
    ):
        self.agent_id = agent_id
        self.description = description
        self.capabilities = capabilities
        self.allowed_tools = allowed_tools
        self.generation_service = generation_service
        self.tool_executor = tool_executor
        self.system_prompt = system_prompt

    async def execute(self, request: AgentDelegationRequest, context: RequestContext) -> AgentObservation:
        start_time = time.time()
        
        try:
            # 1. Ask LLM to solve the task using allowed tools
            # We use a simple ReAct loop or just single-shot if tools are simple.
            # To keep it robust, we will do a single generation that can request tool calls,
            # execute them, and then generate the final answer.
            
            tool_descs = "\n".join([
                f"{t['name']}: {t['description']}" 
                for t in self.tool_executor.registry.get_tool_descriptions()
                if t['name'] in self.allowed_tools
            ])
            
            prompt = f"{self.system_prompt}\n\nYou have access to the following tools:\n{tool_descs}\n\n"
            prompt += "If you need to use a tool, output a JSON object with 'tool_name' and 'arguments'.\n"
            prompt += "If you can answer the task directly or have finished using tools, output a JSON object with 'final_answer'.\n"
            
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Task: {request.task}\nContext: {json.dumps(request.context)}"}
            ]
            
            # Simple max 3 iterations
            for _ in range(3):
                response_json = self.generation_service.generate_json(messages)
                try:
                    data = json.loads(response_json)
                except json.JSONDecodeError:
                    messages.append({"role": "user", "content": "Invalid JSON. Please output valid JSON."})
                    continue
                
                if "final_answer" in data:
                    return AgentObservation(
                        agent_id=self.agent_id,
                        status="COMPLETED",
                        output=data["final_answer"],
                        latency_ms=(time.time() - start_time) * 1000
                    )
                
                if "tool_name" in data:
                    tool_name = data["tool_name"]
                    if tool_name not in self.allowed_tools:
                        messages.append({"role": "user", "content": f"Tool '{tool_name}' is not allowed for this agent."})
                        continue
                        
                    tool_args = data.get("arguments", {})
                    # Execute tool
                    tool_result = await self.tool_executor.execute(tool_name, tool_args, context)
                    messages.append({"role": "assistant", "content": response_json})
                    messages.append({"role": "user", "content": f"Tool Result:\n{json.dumps(tool_result)}"})
                else:
                    messages.append({"role": "user", "content": "Please output either 'tool_name' or 'final_answer'."})
            
            return AgentObservation(
                agent_id=self.agent_id,
                status="FAILED",
                output=None,
                error="Agent exceeded maximum iterations without a final answer.",
                latency_ms=(time.time() - start_time) * 1000
            )

        except Exception as e:
            logger.error("Agent %s failed: %s", self.agent_id, e)
            return AgentObservation(
                agent_id=self.agent_id,
                status="FAILED",
                output=None,
                error=str(e),
                latency_ms=(time.time() - start_time) * 1000
            )


def create_specialized_agents(generation_service: GenerationService, tool_executor: ToolExecutor) -> list[BaseSpecializedAgent]:
    """Factory to create all specialized agents for the registry."""
    
    research_agent = GenericSpecializedAgent(
        agent_id="research_agent",
        description="Gathers external information via web search and enterprise search.",
        capabilities=["web_search", "web_fetch", "enterprise_search"],
        allowed_tools=["web_search", "web_fetch", "enterprise_search"],
        generation_service=generation_service,
        tool_executor=tool_executor,
        system_prompt="You are a Research Agent. Your job is to find accurate information using your tools."
    )
    
    rag_agent = GenericSpecializedAgent(
        agent_id="rag_agent",
        description="Searches the internal knowledge base using hybrid retrieval.",
        capabilities=["document_lookup", "enterprise_search"],
        allowed_tools=["document_lookup", "enterprise_search"],
        generation_service=generation_service,
        tool_executor=tool_executor,
        system_prompt="You are a RAG Agent. Your job is to lookup specific documents and answer based on internal knowledge."
    )
    
    analysis_agent = GenericSpecializedAgent(
        agent_id="analysis_agent",
        description="Performs calculations and logic analysis.",
        capabilities=["calculator"],
        allowed_tools=["calculator"],
        generation_service=generation_service,
        tool_executor=tool_executor,
        system_prompt="You are an Analysis Agent. Your job is to perform accurate calculations and logic."
    )
    
    synthesis_agent = GenericSpecializedAgent(
        agent_id="synthesis_agent",
        description="Synthesizes information into a final formatted report. Has no tools.",
        capabilities=["summarization", "formatting"],
        allowed_tools=[],
        generation_service=generation_service,
        tool_executor=tool_executor,
        system_prompt="You are a Synthesis Agent. Your job is to combine the context provided into a clear, comprehensive final answer. Do NOT guess facts."
    )
    
    return [research_agent, rag_agent, analysis_agent, synthesis_agent]
