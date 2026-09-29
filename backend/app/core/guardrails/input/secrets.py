import re

from app.core.guardrails.base import BaseGuardrail, GuardrailResult

class SecretDetectionGuardrail(BaseGuardrail):
    """
    Detects API keys, tokens, and common credential formats using Regex.
    """
    
    # Very basic regexes for demonstration. A real enterprise system would use a robust library like TruffleHog or AWS Macie.
    SECRET_PATTERNS = {
        "aws_access_key": r"(?i)AKIA[0-9A-Z]{16}",
        "jwt_token": r"eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*",
        "private_key": r"-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----",
        "generic_api_key": r"(?i)(api[_-]?key|secret|token)[\s:=]+[\"']?[a-zA-Z0-9\-_]{20,}[\"']?"
    }

    def check(self, text: str, **kwargs) -> GuardrailResult:
        detected_secrets = []
        for secret_type, pattern in self.SECRET_PATTERNS.items():
            if re.search(pattern, text):
                detected_secrets.append(secret_type)
                
        if detected_secrets:
            # We fail closed (BLOCK) for secrets in input.
            return GuardrailResult(
                status="BLOCK",
                guardrail_name=self.name,
                message="I cannot process sensitive credentials or secrets. Please remove them and try again.",
                reason="Detected potential secrets.",
                metadata={"detected_secret_types": detected_secrets}
            )
            
        return GuardrailResult(status="ALLOW", guardrail_name=self.name)
