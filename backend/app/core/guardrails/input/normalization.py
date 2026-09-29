import re
import unicodedata

from app.core.guardrails.base import BaseGuardrail, GuardrailResult

class InputNormalizationGuardrail(BaseGuardrail):
    """
    Normalizes the input query to prevent basic evasion techniques.
    Removes excessive whitespace and normalizes unicode characters.
    Does not block, but may transform (though currently our engine expects check() to just return a status).
    For now, we just validate the input length and basic characteristics.
    """
    
    MAX_LENGTH = 4000
    
    def check(self, text: str, **kwargs) -> GuardrailResult:
        if not text or not text.strip():
            return GuardrailResult(status="ALLOW", guardrail_name=self.name, message="Input is empty.")
            
        if len(text) > self.MAX_LENGTH:
            return GuardrailResult(
                status="BLOCK", 
                guardrail_name=self.name, 
                message=f"Input is too long. Maximum allowed is {self.MAX_LENGTH} characters."
            )
            
        # We could technically return a "TRANSFORM" status here with the normalized text,
        # but to keep it simple, we just allow normal text.
        return GuardrailResult(status="ALLOW", guardrail_name=self.name)
