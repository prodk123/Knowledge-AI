"""Base Guardrail Abstraction and Types."""

from typing import Literal, Any
from pydantic import BaseModel, Field

class GuardrailResult(BaseModel):
    """Standardized internal result from a guardrail execution."""
    
    status: Literal["ALLOW", "BLOCK", "WARN", "SANITIZE", "ABSTAIN", "REGENERATE"] = Field(
        description="The action the engine should take based on this guardrail."
    )
    guardrail_name: str = Field(
        description="The name of the guardrail that generated this result."
    )
    message: str | None = Field(
        default=None,
        description="Optional safe user-facing message to return (e.g., 'I can't process sensitive credentials.')."
    )
    reason: str | None = Field(
        default=None,
        description="Internal machine-readable reason for the result."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional structured data (confidence scores, model used, latency)."
    )

class BaseGuardrail:
    """Abstract interface for all guardrails."""
    
    @property
    def name(self) -> str:
        return self.__class__.__name__

    def check(self, *args, **kwargs) -> GuardrailResult:
        """Execute the guardrail logic and return a GuardrailResult."""
        raise NotImplementedError("Guardrails must implement the check method.")
