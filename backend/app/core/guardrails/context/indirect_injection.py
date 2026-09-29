import re
import logging

from app.core.guardrails.base import BaseGuardrail, GuardrailResult
from app.models.chat import RetrievalResult

logger = logging.getLogger(__name__)

class IndirectInjectionGuardrail(BaseGuardrail):
    """
    Checks retrieved document chunks for potential indirect prompt injections
    (e.g., a document containing 'Ignore all previous instructions...').
    """
    
    SUSPICIOUS_PATTERNS = [
        r"(?i)ignore\s+(all\s+)?(previous\s+)?instructions",
        r"(?i)you\s+are\s+now\s+",
        r"(?i)act\s+as\s+(an?\s+)?administrator",
        r"(?i)reveal\s+your\s+system\s+prompt"
    ]

    def check(self, contexts: list[RetrievalResult], **kwargs) -> GuardrailResult:
        if not contexts:
            return GuardrailResult(status="ALLOW", guardrail_name=self.name)
            
        detected_in_chunks = []
        
        for chunk in contexts:
            for pattern in self.SUSPICIOUS_PATTERNS:
                if re.search(pattern, chunk.text):
                    detected_in_chunks.append({
                        "chunk_id": chunk.chunk_id,
                        "document_id": chunk.document_id,
                        "pattern_matched": pattern
                    })
                    break # Stop checking patterns for this chunk if one matched
                    
        if detected_in_chunks:
            # We fail closed (BLOCK) if we think a document is poisoned.
            logger.warning(f"Indirect injection detected in {len(detected_in_chunks)} chunks.")
            return GuardrailResult(
                status="BLOCK",
                guardrail_name=self.name,
                message="Unable to safely process this request using the available documents.",
                reason="Detected potential indirect prompt injection in retrieved context.",
                metadata={"poisoned_chunks": detected_in_chunks}
            )
            
        return GuardrailResult(status="ALLOW", guardrail_name=self.name)
