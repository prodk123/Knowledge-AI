"""Generation service — abstraction over LLM calls."""

import logging

from typing import Any
from openai import OpenAI, AsyncOpenAI

from app.core.config import Settings

logger = logging.getLogger(__name__)


class GenerationService:
    """Handles communication with the LLM (OpenRouter/OpenAI API)."""

    def __init__(self, settings: Settings):
        self.client = OpenAI(
            api_key=settings.llm_api_key, base_url=settings.llm_base_url
        )
        self.async_client = AsyncOpenAI(
            api_key=settings.llm_api_key, base_url=settings.llm_base_url
        )
        self.model = settings.llm_model
        logger.info("Generation service initialized (model=%s)", self.model)

    def _record_metrics(self, response: Any, model_name: str) -> None:
        """Extract token usage and record estimated costs."""
        # Some models don't return usage
        if not hasattr(response, 'usage') or response.usage is None:
            return
            
        usage = response.usage
        from app.core.models import model_registry
        
        m_info = model_registry.get_model(model_name)
        if m_info:
            input_cost = (usage.prompt_tokens / 1000.0) * m_info.cost_per_1k_input
            output_cost = (usage.completion_tokens / 1000.0) * m_info.cost_per_1k_output
            cost = input_cost + output_cost
        else:
            cost = 0.0
            
        # Log or emit telemetry (could integrate with a global RequestContext here)
        logger.debug(f"LLM Call [{model_name}]: {usage.total_tokens} tokens, ${cost:.5f}")

    def generate(self, messages: list[dict[str, str]], fallback_allowed: bool = True) -> str:
        """Call the LLM with the provided message history."""
        try:
            logger.debug("Calling LLM API")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.0,
            )
            self._record_metrics(response, self.model)
            answer = response.choices[0].message.content
            if answer is None:
                return "Error: Received empty response from LLM."
            return answer
        except Exception as e:
            logger.error("LLM generation failed: %s", e)
            if fallback_allowed:
                from app.core.models import model_registry
                fallback = model_registry.get_fallback_model(self.model)
                if fallback:
                    logger.warning(f"Falling back to model {fallback.model_id}")
                    # Change model temporarily
                    old_model = self.model
                    self.model = fallback.model_id
                    try:
                        return self.generate(messages, fallback_allowed=False)
                    finally:
                        self.model = old_model
            raise RuntimeError(f"Failed to generate answer: {e}") from e

    def generate_json(self, messages: list[dict[str, str]], fallback_allowed: bool = True) -> str:
        """Call the LLM enforcing JSON output."""
        try:
            logger.debug("Calling LLM API (JSON mode)")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            self._record_metrics(response, self.model)
            answer = response.choices[0].message.content
            if answer is None:
                return "{}"
            
            # Strip markdown JSON blocks
            answer = answer.strip()
            if answer.startswith("```json"):
                answer = answer[7:]
            if answer.startswith("```"):
                answer = answer[3:]
            if answer.endswith("```"):
                answer = answer[:-3]
                
            return answer.strip()
        except Exception as first_err:
            logger.warning("JSON mode failed (%s), retrying without response_format", first_err)
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.0,
                )
                self._record_metrics(response, self.model)
                answer = response.choices[0].message.content
                if answer is None:
                    return "{}"
                
                # Strip markdown JSON blocks if the model ignored response_format
                answer = answer.strip()
                if answer.startswith("```json"):
                    answer = answer[7:]
                if answer.startswith("```"):
                    answer = answer[3:]
                if answer.endswith("```"):
                    answer = answer[:-3]
                    
                return answer.strip()
            except Exception as e:
                logger.error("LLM JSON generation failed: %s", e)
                if fallback_allowed:
                    from app.core.models import model_registry
                    fallback = model_registry.get_fallback_model(self.model)
                    if fallback:
                        logger.warning(f"Falling back to JSON model {fallback.model_id}")
                        old_model = self.model
                        self.model = fallback.model_id
                        try:
                            return self.generate_json(messages, fallback_allowed=False)
                        finally:
                            self.model = old_model
                raise RuntimeError(f"Failed to generate JSON answer: {e}") from e
    async def stream(
        self,
        messages: list[dict[str, str]],
    ):
        """
        Async generator that yields string chunks as they arrive from the LLM.

        Usage:
            async for chunk in generation_service.stream(messages):
                yield chunk

        Falls back to yielding the full response in one chunk if streaming fails.
        """
        try:
            response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.0,
                stream=True,
            )
            async for chunk in response:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield delta.content
        except Exception as e:
            logger.warning("Streaming failed (%s), falling back to single response.", e)
            try:
                fallback = self.generate(messages, fallback_allowed=True)
                yield fallback
            except Exception as inner_e:
                logger.error("Stream fallback also failed: %s", inner_e)
                yield "I'm sorry, I encountered an error generating a response."
