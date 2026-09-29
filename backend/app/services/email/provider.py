"""Email Provider Interface."""

from typing import Protocol
from pydantic import BaseModel
from datetime import datetime

class EmailExecutionResult(BaseModel):
    status: str
    message_id: str | None
    provider: str
    recipient_count: int
    timestamp: datetime
    error: str | None = None

class EmailProvider(Protocol):
    """Abstract interface for sending emails."""
    
    async def send_email(
        self,
        recipients: list[str],
        subject: str,
        body: str,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        reply_to: str | None = None,
        idempotency_key: str | None = None
    ) -> EmailExecutionResult:
        """Send an email."""
        ...
        
    async def health_check(self) -> bool:
        """Verify the provider is healthy and configured."""
        ...
