"""Send Email Tool."""

import logging
import re
from typing import Any
from pydantic import BaseModel, Field, field_validator, model_validator

from app.agent.tools.base import BaseTool, RequestContext, ToolRiskLevel, ToolCapability
from app.services.email.provider import EmailProvider

logger = logging.getLogger(__name__)


def validate_no_newlines(value: str) -> str:
    """Ensure no newlines to prevent header injection."""
    if "\n" in value or "\r" in value:
        raise ValueError("Newlines are not permitted in this field.")
    return value.strip()


def validate_email_address(email: str) -> str:
    """Basic deterministic email validation and normalization."""
    email = validate_no_newlines(email).lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise ValueError(f"Invalid email address format: {email}")
    return email


class SendEmailInput(BaseModel):
    recipients: list[str] = Field(..., description="List of primary email recipients.", max_items=5)
    subject: str = Field(..., description="Email subject line.", max_length=255)
    body: str = Field(..., description="Email body content.", max_length=10000)
    cc: list[str] = Field(default_factory=list, description="CC recipients.", max_items=5)
    bcc: list[str] = Field(default_factory=list, description="BCC recipients.", max_items=5)
    reply_to: str | None = Field(default=None, description="Reply-to email address.")

    @field_validator("recipients", "cc", "bcc", mode="before")
    @classmethod
    def validate_emails_list(cls, emails: Any) -> list[str]:
        if isinstance(emails, str):
            emails = [emails]
        if not isinstance(emails, list):
            raise ValueError("Must be a list of strings")
        return [validate_email_address(e) for e in emails]

    @field_validator("reply_to", mode="before")
    @classmethod
    def validate_reply_to(cls, reply_to: str | None) -> str | None:
        if reply_to:
            return validate_email_address(reply_to)
        return reply_to

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, subject: str) -> str:
        return validate_no_newlines(subject)


class SendEmailOutput(BaseModel):
    status: str
    message_id: str | None
    provider: str
    recipient_count: int


class SendEmailTool(BaseTool):
    """Tool to send an email externally."""
    
    name = "send_email"
    description = "Send an email to external or internal recipients."
    version = "1.0.0"
    risk_level = ToolRiskLevel.HIGH
    capabilities = [ToolCapability.EXTERNAL_ACTION]
    
    input_schema = SendEmailInput
    output_schema = SendEmailOutput
    
    def __init__(self, provider: EmailProvider):
        super().__init__()
        self.provider = provider
        
    def describe_action(self, arguments: BaseModel | dict[str, Any]) -> str:
        """Provide a human-readable deterministic string mapping exactly what will be sent."""
        if isinstance(arguments, dict):
            args = SendEmailInput(**arguments)
        else:
            args = arguments
            
        desc = f"Send an email to {', '.join(args.recipients)}"
        if args.cc:
            desc += f" (CC: {', '.join(args.cc)})"
        if args.bcc:
            desc += f" (BCC: {', '.join(args.bcc)})"
        desc += f" with subject '{args.subject}'."
        return desc

    async def execute(self, context: RequestContext, arguments: SendEmailInput) -> SendEmailOutput:
        """Execute the email send."""
        # Derive idempotency key directly from the context request_id + tool name + args hash
        # The approval_id isn't directly passed here natively by BaseTool, but we can derive safety
        # from the exact args and the original request ID. 
        # For Stage 8.4 we'll just pass a standard key based on run context.
        idempotency_key = f"{context.request_id}_{self.hash_arguments(arguments)}"
        
        try:
            result = await self.provider.send_email(
                recipients=arguments.recipients,
                subject=arguments.subject,
                body=arguments.body,
                cc=arguments.cc,
                bcc=arguments.bcc,
                reply_to=arguments.reply_to,
                idempotency_key=idempotency_key
            )
            return SendEmailOutput(
                status=result.status,
                message_id=result.message_id,
                provider=result.provider,
                recipient_count=result.recipient_count
            )
        except Exception as e:
            logger.error("EmailProvider failed: %s", e, exc_info=True)
            # Safe structured error, do not leak provider specifics
            return SendEmailOutput(
                status="failed",
                message_id=None,
                provider="unknown",
                recipient_count=0
            )
