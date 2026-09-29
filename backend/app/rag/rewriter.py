"""Contextual Query Rewriter — resolves context in follow-up questions."""

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from app.services.generation_service import GenerationService

logger = logging.getLogger(__name__)


class RewriteResult(BaseModel):
    standalone_query: str = Field(description="The rewritten query suitable for vector retrieval")


class ContextualQueryRewriter:
    """Rewrites follow-up questions into standalone queries based on conversation history."""

    SYSTEM_PROMPT = """You are an expert query rewriter for an Enterprise Search System.
Your job is to look at the user's latest message and the recent conversation history, and rewrite the user's latest message into a standalone search query.
This standalone query will be used to retrieve documents from a vector database.

Rules:
1. If the latest message is a follow-up that uses pronouns (e.g., "it", "they", "those", "this policy") or implies context from the previous messages, replace those references with the specific subjects from the history.
2. If the latest message is already self-contained, return it as-is.
3. Do NOT answer the question. Only rewrite the query.
4. Output ONLY valid JSON matching this schema:
{
  "standalone_query": "The fully resolved standalone query string"
}
"""

    def __init__(self, generation_service: GenerationService):
        self.generation_service = generation_service

    def rewrite(self, current_message: str, history: list[dict[str, str]] = None) -> str:
        """Rewrite the query. If no history or history is empty, return as is."""
        if not history:
            return current_message

        history_text = "Recent Conversation History:\n"
        for msg in history:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            history_text += f"{role.upper()}: {content}\n"
        
        user_prompt = f"""{history_text}
LATEST USER MESSAGE: {current_message}

Rewrite the latest user message into a standalone query. Output JSON."""

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        try:
            response_json = self.generation_service.generate_json(messages)
            data = json.loads(response_json)
            standalone_query = data.get("standalone_query", current_message)
            logger.info("Rewrote query: '%s' -> '%s'", current_message, standalone_query)
            return standalone_query

        except Exception as e:
            logger.error("Query rewriter failed: %s, returning original query", e)
            return current_message
