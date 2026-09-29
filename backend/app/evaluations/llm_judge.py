"""LLM-as-a-judge for subjective agent evaluations."""

import json
import logging
from typing import Any

from app.services.generation_service import GenerationService

logger = logging.getLogger(__name__)

JUDGE_PROMPT = """You are an objective evaluation judge for an Enterprise AI Agent.
You will evaluate the agent's performance on a task.
DO NOT MODIFY ANY STATE OR APPROVE ANY ACTIONS. You are read-only.

You must output a JSON object with the following schema:
{{
  "correctness": 0.0,
  "groundedness": 0.0,
  "relevance": 0.0,
  "completeness": 0.0,
  "citation_quality": 0.0,
  "reason": "Detailed explanation of your scores."
}}
Scores must be between 0.0 (worst) and 1.0 (best).

Here is the data for evaluation:

USER INPUT:
{user_input}

EXPECTED ANSWER/GROUND TRUTH:
{ground_truth}

AGENT ACTUAL ANSWER:
{actual_answer}

EVIDENCE/CONTEXT USED BY AGENT:
{evidence}
"""

class LLMJudge:
    def __init__(self, generation_service: GenerationService):
        self.generation_service = generation_service

    def evaluate(
        self,
        user_input: str,
        actual_answer: str,
        ground_truth: str = "",
        evidence: str = ""
    ) -> dict[str, Any]:
        """Evaluate the agent's answer using the LLM judge."""
        prompt = JUDGE_PROMPT.format(
            user_input=user_input,
            ground_truth=ground_truth or "None provided.",
            actual_answer=actual_answer or "No answer provided.",
            evidence=evidence or "No evidence provided."
        )

        messages = [{"role": "system", "content": prompt}]
        
        try:
            # We enforce fallback_allowed=False for the judge if we want strict models,
            # but letting it fallback to a cheaper model is also fine.
            response_str = self.generation_service.generate_json(messages)
            result = json.loads(response_str)
            
            # Basic validation
            for key in ["correctness", "groundedness", "relevance", "completeness", "citation_quality"]:
                if key not in result or not isinstance(result[key], (int, float)):
                    result[key] = 0.0
                    
            if "reason" not in result:
                result["reason"] = "No reason provided by LLM judge."
                
            return result
        except Exception as e:
            logger.error("LLM Judge evaluation failed: %s", e)
            return {
                "correctness": 0.0,
                "groundedness": 0.0,
                "relevance": 0.0,
                "completeness": 0.0,
                "citation_quality": 0.0,
                "reason": f"LLM Judge failed: {e}"
            }
