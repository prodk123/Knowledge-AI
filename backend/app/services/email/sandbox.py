"""Sandbox Email Provider (Mock execution without real side effects)."""

import uuid
import logging
import hashlib
from datetime import datetime

from app.services.email.provider import EmailProvider, EmailExecutionResult

logger = logging.getLogger(__name__)

class SandboxEmailProvider(EmailProvider):
    """Mocks email sending for safe development/testing."""
    
    def __init__(self):
        self.sent_emails = [] # In-memory store for audit/tests
        
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
        """Simulates sending an email."""
        
        # Deduplication check for idempotency
        if idempotency_key:
            for email in self.sent_emails:
                if email.get("idempotency_key") == idempotency_key:
                    logger.info("SandboxEmailProvider: Replay detected for %s, skipping.", idempotency_key)
                    return EmailExecutionResult(
                        status="sent_idempotent",
                        message_id=email["message_id"],
                        provider="sandbox",
                        recipient_count=email["recipient_count"],
                        timestamp=datetime.utcnow()
                    )
        
        # Mocking network delay
        import asyncio
        await asyncio.sleep(0.1)
        
        message_id = f"sandbox-{uuid.uuid4()}"
        
        # Hash the body for safe auditing without logging full content
        body_hash = hashlib.sha256(body.encode('utf-8')).hexdigest()
        
        audit_record = {
            "message_id": message_id,
            "recipients": recipients,
            "cc": cc or [],
            "bcc": bcc or [],
            "subject": subject,
            "body_hash": body_hash,
            "reply_to": reply_to,
            "idempotency_key": idempotency_key,
            "recipient_count": len(recipients) + len(cc or []) + len(bcc or []),
            "timestamp": datetime.utcnow()
        }
        
        self.sent_emails.append(audit_record)
        logger.info("SandboxEmailProvider: Simulated email %s to %d recipients (subject: '%s')", 
                    message_id, audit_record["recipient_count"], subject)
                    
        return EmailExecutionResult(
            status="sent",
            message_id=message_id,
            provider="sandbox",
            recipient_count=audit_record["recipient_count"],
            timestamp=audit_record["timestamp"]
        )
        
    async def health_check(self) -> bool:
        """Always healthy in sandbox mode."""
        return True
