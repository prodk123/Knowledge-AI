"""Direct LLM Service — handles conversations without RAG retrieval."""

import logging

from app.services.generation_service import GenerationService

logger = logging.getLogger(__name__)


class DirectLLMService:
    """Handles direct conversational responses bypassing the vector store."""

    SYSTEM_PROMPT = """You are a helpful and professional enterprise AI assistant.
Answer the user's question directly and concisely based on your general knowledge.
Do NOT invent company policies or proprietary data. If the user asks for company-specific information that you don't know, state clearly that you don't have access to that information in this mode.
"""

    def __init__(self, generation_service: GenerationService, guardrail_engine=None):
        self.generation_service = generation_service
        self.guardrail_engine = guardrail_engine

    def build_messages(self, question: str, history: list[dict[str, str]] = None) -> list[dict[str, str]]:
        """Build the message list for direct generation (used by both sync and streaming callers)."""
        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]

        if history:
            for msg in history[-10:]:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                })

        messages.append({"role": "user", "content": question})
        return messages

    def answer_question(self, question: str, history: list[dict[str, str]] = None) -> str:
        """Generate a response using the LLM directly with conversation history."""
        messages = self.build_messages(question, history)
        logger.info("Direct LLM service generating response")
        answer = self.generation_service.generate(messages)
        # Note: Output guardrail checks are now handled in the async caller
        # (conversations.py) to avoid nested event loop issues with uvloop.
        return answer
