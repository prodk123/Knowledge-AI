import logging
import uuid
import time
from typing import List

from app.core.guardrails.base import BaseGuardrail, GuardrailResult
from app.db.database import async_session_factory
from app.models.guardrail import GuardrailEvent
from app.core.tracing import current_trace_id

logger = logging.getLogger(__name__)

class GuardrailEngine:
    """Orchestrates guardrail execution and event logging."""
    
    def __init__(self, input_guardrails: List[BaseGuardrail], context_guardrails: List[BaseGuardrail], output_guardrails: List[BaseGuardrail]):
        self.input_guardrails = input_guardrails
        self.context_guardrails = context_guardrails
        self.output_guardrails = output_guardrails
        
    async def _execute_stage(self, guardrails: List[BaseGuardrail], stage_name: str, *args, **kwargs) -> GuardrailResult:
        """Executes a list of guardrails sequentially and stops if one blocks."""
        trace_id = current_trace_id.get()
        
        for guardrail in guardrails:
            start_time = time.time()
            try:
                # Assuming check is synchronous for now. If using an async LLM call, this could be awaited.
                result = guardrail.check(*args, **kwargs)
            except Exception as e:
                logger.error(f"Guardrail {guardrail.name} failed: {e}")
                # Fail open or closed depending on policy. By default, fail closed for safety.
                result = GuardrailResult(
                    status="BLOCK", 
                    guardrail_name=guardrail.name, 
                    reason=f"Exception during check: {e}"
                )
            
            latency = (time.time() - start_time) * 1000
            
            # Log the event asynchronously to avoid blocking the critical path
            await self._log_event(stage_name, result, latency, trace_id)
            
            if result.status in ["BLOCK", "ABSTAIN", "SANITIZE"]:
                # Stop processing further guardrails in this stage on terminal states
                return result
                
        # If all passed, return an ALLOW
        return GuardrailResult(status="ALLOW", guardrail_name="Engine", message="All checks passed")
        
    async def _log_event(self, stage_name: str, result: GuardrailResult, latency: float, trace_id: uuid.UUID | None):
        """Persist the guardrail event to the database."""
        
        # Skip logging if no trace_id is available yet (trace hasn't been committed)
        # This avoids FK violations on guardrail_events.trace_id -> traces.id
        if trace_id is None:
            logger.debug("Skipping guardrail event logging: no trace_id available yet")
            return
        
        # Calculate severity based on status
        severity = "LOW"
        if result.status == "BLOCK":
            severity = "HIGH"
        elif result.status == "ABSTAIN":
            severity = "MEDIUM"
            
        try:
            async with async_session_factory() as session:
                event = GuardrailEvent(
                    trace_id=trace_id,
                    guardrail_name=result.guardrail_name,
                    category=stage_name,
                    action=result.status,
                    severity=severity,
                    latency_ms=latency,
                    metadata_json=result.metadata
                )
                session.add(event)
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to log guardrail event: {e}")

    async def check_input(self, text: str) -> GuardrailResult:
        """Execute input guardrails."""
        return await self._execute_stage(self.input_guardrails, "INPUT", text)
        
    async def check_context(self, contexts: list) -> GuardrailResult:
        """Execute context guardrails."""
        return await self._execute_stage(self.context_guardrails, "CONTEXT", contexts)
        
    async def check_output(self, response: str, contexts: list = None) -> GuardrailResult:
        """Execute output guardrails."""
        return await self._execute_stage(self.output_guardrails, "OUTPUT", response, contexts)
