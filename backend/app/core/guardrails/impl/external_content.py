"""External Content Guardrail."""

import re
from typing import Any
from app.core.guardrails.base import BaseGuardrail, GuardrailResult

class ExternalContentGuardrail(BaseGuardrail):
    """
    Scans external content for prompt injection and control instructions.
    
    Instead of blocking the entire workflow, it flags the content so that 
    the workflow engine knows it contains potentially malicious instructions
    and ensures it remains strictly treated as UNTRUSTED DATA.
    """
    
    # Common prompt injection signatures
    INJECTION_PATTERNS = [
        r"(?i)ignore\s+(all\s+)?previous\s+instructions",
        r"(?i)system\s+prompt",
        r"(?i)you\s+are\s+now\s+a\s+",
        r"(?i)new\s+rule:",
        r"(?i)forget\s+everything",
        r"(?i)bypass\s+approval",
        r"(?i)approval\s+granted",
        r"(?i)this\s+operation\s+is\s+low\s+risk"
    ]
    
    def __init__(self):
        self.compiled_patterns = [re.compile(p) for p in self.INJECTION_PATTERNS]

    def check(self, text: str, contexts: list = None, **kwargs) -> GuardrailResult:
        if not text:
            return GuardrailResult(status="ALLOW", guardrail_name=self.name)
            
        for pattern in self.compiled_patterns:
            if pattern.search(text):
                # We flag the content as containing injection, but we ALLOW it to pass 
                # through as data (untrusted). The workflow executor relies on the trust_level
                # to isolate it. 
                return GuardrailResult(
                    status="WARN", # Using WARN so it doesn't halt the pipeline
                    guardrail_name=self.name,
                    message="External content contains potential prompt injection.",
                    reason="Matched prompt injection pattern",
                    metadata={"injection_detected": True}
                )
                
        return GuardrailResult(
            status="ALLOW",
            guardrail_name=self.name,
            metadata={"injection_detected": False}
        )
