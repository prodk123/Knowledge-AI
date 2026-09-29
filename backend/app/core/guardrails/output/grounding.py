import json
import logging

from app.core.guardrails.base import BaseGuardrail, GuardrailResult
from app.models.chat import RetrievalResult
from app.services.generation_service import GenerationService

logger = logging.getLogger(__name__)

class GroundingGuardrail(BaseGuardrail):
    """
    Validates that the claims in the generated response are supported by the retrieved context.
    """
    
    SYSTEM_PROMPT = """You are a grounding evaluator. Your job is to check if the ANSWER is fully supported by the CONTEXT.
Output JSON:
{
    "is_grounded": boolean,
    "confidence": float (0.0 to 1.0),
    "unsupported_claims": ["list of claims not in context, if any"]
}"""

    def __init__(self, generation_service: GenerationService = None):
        self.generation_service = generation_service

    def check(self, response: str, contexts: list[RetrievalResult] = None, **kwargs) -> GuardrailResult:
        if not contexts:
            # If no context was provided (e.g. direct chat or empty retrieval), we can't check grounding against docs.
            return GuardrailResult(status="ALLOW", guardrail_name=self.name)
            
        if not self.generation_service:
            logger.warning("No generation service provided for GroundingGuardrail. Skipping.")
            return GuardrailResult(status="ALLOW", guardrail_name=self.name)
            
        context_text = "\n\n".join([f"Source {i+1}: {c.text}" for i, c in enumerate(contexts)])
        
        user_prompt = f"CONTEXT:\n{context_text}\n\nANSWER:\n{response}"
        
        try:
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ]
            response_json = self.generation_service.generate_json(messages)
            result = json.loads(response_json)
            
            is_grounded = result.get("is_grounded", True)
            confidence = float(result.get("confidence", 1.0))
            unsupported_claims = result.get("unsupported_claims", [])
            
            if not is_grounded:
                return GuardrailResult(
                    status="ABSTAIN", # Quality guardrails ABSTAIN rather than BLOCK
                    guardrail_name=self.name,
                    message="I couldn't find enough information in the available documents to answer that reliably.",
                    reason="Answer contains ungrounded claims.",
                    metadata={"unsupported_claims": unsupported_claims, "confidence": confidence}
                )
                
        except Exception as e:
            logger.error(f"Grounding LLM check failed: {e}")
            # If the grounding check fails to run, we should probably fail open to preserve availability, 
            # or ABSTAIN to be ultra safe. Policy says: Grounding: ABSTAIN on uncertain.
            return GuardrailResult(
                status="ABSTAIN",
                guardrail_name=self.name,
                message="I couldn't find enough information in the available documents to answer that reliably.",
                reason=f"Grounding evaluation failed: {e}"
            )
            
        return GuardrailResult(status="ALLOW", guardrail_name=self.name)
