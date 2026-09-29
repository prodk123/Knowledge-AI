"""Prompt builder — constructs grounded prompts for the LLM."""

import logging

from app.models.chat import RetrievalResult

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Builds the prompt instructing the LLM to answer using retrieved context."""

    SYSTEM_PROMPT = """You are a helpful and precise enterprise knowledge assistant.
Your task is to answer the user's question based strictly on the provided document excerpts.

Rules:
1. Use ONLY the information provided in the context below.
2. If the context does not contain enough information to answer the question, say clearly: "The available documents do not contain enough information to answer this question." Do not guess or invent answers.
3. Be concise and professional.
4. Do not mention "the provided context" or "the document excerpts" in your answer. Just answer the question.
"""

    def build_prompt(
        self, question: str, contexts: list[RetrievalResult], history: list[dict[str, str]] = None
    ) -> list[dict[str, str]]:
        """Construct the prompt messages for the OpenAI-compatible API.

        Args:
            question: The user's question.
            contexts: Retrieved document chunks.
            history: Recent conversation history.

        Returns:
            List of message dictionaries (role, content).
        """
        if not contexts:
            context_text = "No relevant documents found."
        else:
            # Format each chunk cleanly
            context_parts = []
            for i, ctx in enumerate(contexts, start=1):
                source_info = f"Source {i}: {ctx.filename}"
                if ctx.section:
                    source_info += f" (Section: {ctx.section})"
                if ctx.page_number:
                    source_info += f" (Page: {ctx.page_number})"
                
                context_parts.append(f"--- {source_info} ---\n{ctx.text}")
            
            context_text = "\n\n".join(context_parts)

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
        ]

        if history:
            for msg in history[-5:]: # Keep last 5 messages to preserve context window
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })

        # The user message contains both the context and the question
        user_message_content = f"""Here are the relevant document excerpts:

<context>
{context_text}
</context>

Question: {question}
"""

        messages.append({"role": "user", "content": user_message_content})

        return messages
