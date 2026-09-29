"""Query router — decides whether to use direct generation or RAG."""

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from app.services.generation_service import GenerationService
from app.core.tracing import Tracer

logger = logging.getLogger(__name__)


class RouteDecision(BaseModel):
    """The structured decision returned by the router."""
    route: str = Field(description="'direct', 'rag', or 'agent'")
    reason: str = Field(description="Explanation of the routing decision")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")


class QueryRouter:
    """Intelligently routes queries based on conversation history and the new message."""

    SYSTEM_PROMPT = """You are an intelligent routing assistant for an Enterprise AI Platform.
Your sole job is to determine how to route the user's latest request.

You must output a JSON object exactly matching this schema:
{
  "route": "direct" | "rag" | "agent_single" | "agent_swarm",
  "reason": "Brief explanation",
  "confidence": 0.95
}

Rules:
1. Output ONLY valid JSON.
2. Route to 'direct' if the user is asking a general knowledge question (e.g., "What is the capital of France?", "Who wrote Hamlet?"), a conversational question ("Hi", "How are you?"), or asking for code ("Write a python script"). These DO NOT need enterprise documents.
3. Route to 'direct' if the user asks a purely conversational, meta, or general follow-up question that clearly does NOT require searching company documents (e.g. "Alright, what else can you do?", "Thanks!", "Tell me more about yourself").
4. Route to 'rag' if the user is asking a straightforward question about company policies, internal documents, reimbursement limits, employee handbooks, or specific enterprise knowledge that requires a single retrieval step.
5. Route to 'agent_single' if the user is asking a complex, multi-step question that requires a sequence of tool calls (like lookup calendar then send an email) but does NOT require parallel research or extensive synthesis.
6. Route to 'agent_swarm' if the user is asking a highly complex question that requires multiple parallel lines of research, cross-domain synthesis, or heavy reasoning over multiple sources (e.g. "Research ACME Corp earnings, compare them with our internal guidelines, and summarize").
7. If the user asks a follow-up question that implicitly refers to enterprise knowledge discussed recently in the conversation, default to 'rag' unless it requires multi-step reasoning, in which case use 'agent_single' or 'agent_swarm'.
8. If uncertain, default to 'rag'.

Examples:
- User: "What is the capital of France?" -> {"route": "direct", "reason": "General knowledge question", "confidence": 0.99}
- User: "How many days of leave do I get?" -> {"route": "rag", "reason": "Requires employee handbook lookup", "confidence": 0.95}
- User: "Hi there" -> {"route": "direct", "reason": "Conversational greeting", "confidence": 0.99}
"""

    def __init__(self, generation_service: GenerationService):
        self.generation_service = generation_service

    def route(self, current_message: str, history: list[dict[str, str]] = None) -> RouteDecision:
        """Route the user's query."""
        if history is None:
            history = []

        # Format history for the prompt
        history_text = ""
        if history:
            history_text = "Recent Conversation History:\n"
            for msg in history:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                history_text += f"{role.upper()}: {content}\n"
        
        user_prompt = f"""{history_text}
LATEST USER MESSAGE: {current_message}

Determine the route for the latest user message. Provide your answer in JSON format."""

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        try:
            with Tracer.start_span("query_router") as span:
                response_json = self.generation_service.generate_json(messages)
                data = json.loads(response_json)
                
                # Validate output, default to rag if something is missing
                route = data.get("route", "rag").lower()
                if route not in ["direct", "rag", "agent_single", "agent_swarm"]:
                    # Fallback for old models that might output 'agent'
                    if route == "agent":
                        route = "agent_single"
                    else:
                        route = "rag"
                
                decision = RouteDecision(
                    route=route,
                    reason=data.get("reason", "Fallback/Parsed reason"),
                    confidence=float(data.get("confidence", 0.5))
                )
                span["route"] = decision.route
                span["confidence"] = decision.confidence
                logger.info("Router decision: %s (confidence: %.2f)", decision.route, decision.confidence)
                return decision

        except json.JSONDecodeError as e:
            logger.warning("Router JSON parse failed: %s. Output was: %s. Falling back to 'direct' for short conversational messages.", e, response_json)
            # If it's a short message, it's likely conversational and we should default to direct to avoid unnecessary RAG
            fallback_route = "direct" if len(current_message) < 50 else "rag"
            return RouteDecision(route=fallback_route, reason="JSON parse failure fallback", confidence=0.0)
        except Exception as e:
            logger.error("Router failed: %s, falling back to 'rag'", e)
            return RouteDecision(route="rag", reason="Router failure fallback", confidence=0.0)
