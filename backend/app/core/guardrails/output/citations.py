import re
import logging

from app.core.guardrails.base import BaseGuardrail, GuardrailResult
from app.models.chat import RetrievalResult

logger = logging.getLogger(__name__)

class CitationGuardrail(BaseGuardrail):
    """
    Validates that the LLM only cites sources that were actually provided in the context.
    This prevents hallucinated citations and unauthorized document leakage.
    """

    def check(self, response: str, contexts: list[RetrievalResult] = None, **kwargs) -> GuardrailResult:
        if not response:
            return GuardrailResult(status="ALLOW", guardrail_name=self.name)
            
        # The prompt instructed the LLM to use "Source N". We might look for [Source N] or Source N.
        # This regex looks for common citation formats like [1], [Source 1], Source 1
        citation_matches = re.finditer(r"(?:\[?Source\s+(\d+)\]?|\[(\d+)\])", response, re.IGNORECASE)
        
        max_valid_index = len(contexts) if contexts else 0
        
        invalid_citations = []
        for match in citation_matches:
            # group 1 is from Source N, group 2 is from [N]
            idx_str = match.group(1) or match.group(2)
            try:
                idx = int(idx_str)
                if idx < 1 or idx > max_valid_index:
                    invalid_citations.append(idx)
            except ValueError:
                continue
                
        if invalid_citations:
            logger.warning(f"Invalid citations detected: {invalid_citations}. Max valid: {max_valid_index}")
            # Policy says: "CITATION: REMOVE INVALID CITATION / ABSTAIN"
            # For simplicity in this implementation, we ABSTAIN so we don't return hallucinated citations.
            return GuardrailResult(
                status="ABSTAIN",
                guardrail_name=self.name,
                message="I cannot provide a reliable answer as some generated citations were invalid.",
                reason=f"Hallucinated citations detected: {invalid_citations}",
                metadata={"invalid_citations": invalid_citations, "max_valid": max_valid_index}
            )
            
        return GuardrailResult(status="ALLOW", guardrail_name=self.name)
