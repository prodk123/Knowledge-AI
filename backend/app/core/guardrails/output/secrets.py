import re

from app.core.guardrails.base import BaseGuardrail, GuardrailResult

class OutputSecretGuardrail(BaseGuardrail):
    """
    Prevents the LLM from leaking generated or retrieved secrets.
    """
    
    SECRET_PATTERNS = {
        "aws_access_key": r"(?i)AKIA[0-9A-Z]{16}",
        "jwt_token": r"eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*",
        "private_key": r"-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----",
        "generic_api_key": r"(?i)(api[_-]?key|secret|token)[\s:=]+[\"']?[a-zA-Z0-9\-_]{20,}[\"']?",
        "system_prompt_leak": r"(?i)(You are an Enterprise AI assistant|You must base your answer strictly on the provided|Your primary role is to act as a secure|system instruction|developer instruction|hidden instruction|developer prompt|system prompt|You are a security classifier)"
    }

    def check(self, response: str, contexts: list = None, **kwargs) -> GuardrailResult:
        if not response:
            return GuardrailResult(status="ALLOW", guardrail_name=self.name)
            
        detected_secrets = []
        for secret_type, pattern in self.SECRET_PATTERNS.items():
            if re.search(pattern, response):
                detected_secrets.append(secret_type)
                
        if detected_secrets:
            # We fail closed (BLOCK) for output secrets. We could REDACT, but BLOCK is safer for enterprise.
            return GuardrailResult(
                status="BLOCK",
                guardrail_name=self.name,
                message="The generated response contained sensitive information and was blocked.",
                reason="Detected potential secrets in output.",
                metadata={"detected_secret_types": detected_secrets}
            )
            
        return GuardrailResult(status="ALLOW", guardrail_name=self.name)
