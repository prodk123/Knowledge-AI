"""Controlled Tool Executor Boundary."""

import time
import logging
from typing import Any

from pydantic import BaseModel, ValidationError

from app.agent.tools.base import RequestContext, BaseTool, ToolObservation
from app.agent.tools.registry import ToolRegistry
from app.agent.tools.auth import ToolAuthorizationEngine
from app.core.tracing import Tracer
from app.core.guardrails.engine import GuardrailEngine

logger = logging.getLogger(__name__)

class ToolExecutor:
    """The controlled boundary for executing tools."""
    
    def __init__(
        self,
        registry: ToolRegistry,
        auth_engine: ToolAuthorizationEngine,
        guardrail_engine: GuardrailEngine | None = None,
        policy_engine: Any = None,
        approval_service: Any = None
    ):
        self.registry = registry
        self.auth_engine = auth_engine
        self.guardrail_engine = guardrail_engine
        self.policy_engine = policy_engine
        self.approval_service = approval_service
        
    def _emit_telemetry(self, event: str, tool_name: str, details: str = ""):
        if tool_name == "send_email":
            logger.info("SECURITY_TELEMETRY: %s - %s", event, details)

        
    async def execute(
        self, 
        tool_name: str, 
        arguments: dict[str, Any], 
        context: RequestContext,
        tool_call_id: str,
        agent_run_id: str = ""
    ) -> ToolObservation:
        """Execute a tool with full validation, authorization, and guardrails."""
        start_time = time.time()
        obs = ToolObservation(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            status="PENDING",
            result_summary="",
            duration_ms=0.0
        )
        
        with Tracer.start_span("tool_execution") as span:
            span["tool_name"] = tool_name
            span["tool_call_id"] = tool_call_id
            
            try:
                self._emit_telemetry("EMAIL_ACTION_PROPOSED", tool_name)
                # 1. Registry Lookup
                tool = self.registry.get_tool(tool_name)
                if not tool:
                    self._emit_telemetry("EMAIL_FAILED", tool_name, "Tool not registered")
                    obs.status = "UNKNOWN_TOOL"
                    obs.result_summary = f"Tool {tool_name} is not registered."
                    return obs
                    
                if not tool.is_enabled:
                    self._emit_telemetry("EMAIL_FAILED", tool_name, "Tool disabled")
                    obs.status = "TOOL_DISABLED"
                    obs.result_summary = f"Tool {tool_name} is disabled."
                    return obs

                # 2. Schema Validation (Input)
                try:
                    typed_args = tool.input_schema(**arguments)
                except ValidationError as e:
                    obs.status = "INVALID_TOOL_INPUT"
                    obs.result_summary = f"Input validation failed: {str(e)}"
                    return obs
                    
                # 2.5 Policy & Risk Evaluation
                if self.policy_engine and self.approval_service:
                    import uuid
                    policy_result = self.policy_engine.evaluate(context, tool, typed_args)
                    if policy_result.decision == "BLOCKED":
                        self._emit_telemetry("EMAIL_BLOCKED", tool_name, policy_result.reason_code)
                        obs.status = "TOOL_BLOCKED_BY_POLICY"
                        obs.result_summary = f"Blocked: {policy_result.reason_code}"
                        return obs
                    elif policy_result.decision == "REQUIRES_APPROVAL":
                        args_hash = tool.hash_arguments(typed_args)
                        
                        run_id_uuid = uuid.UUID(agent_run_id) if agent_run_id else uuid.uuid4()
                        user_id_uuid = uuid.UUID(context.user_id)
                        
                        existing_approval = await self.approval_service.get_pending_approval(
                            user_id=user_id_uuid,
                            agent_run_id=run_id_uuid,
                            tool_name=tool_name,
                            arguments_hash=args_hash
                        )
                        
                        if not existing_approval:
                            # Create a new approval request
                            self._emit_telemetry("EMAIL_APPROVAL_REQUIRED", tool_name)
                            await self.approval_service.create_approval_request(
                                user_id=user_id_uuid,
                                conversation_id=uuid.UUID(context.conversation_id),
                                agent_run_id=run_id_uuid,
                                step_id=tool_call_id,
                                tool_name=tool_name,
                                tool_version=tool.version,
                                arguments_hash=args_hash,
                                requested_action_desc=f"Execute {tool_name}",
                                policy_result=policy_result
                            )
                            obs.status = "APPROVAL_REQUIRED"
                            obs.result_summary = "Approval requested."
                            return obs
                            
                        elif existing_approval.status == "PENDING":
                            obs.status = "APPROVAL_REQUIRED"
                            obs.result_summary = "Still waiting for approval."
                            return obs
                            
                        elif existing_approval.status == "APPROVED":
                            # Attempt to consume the approval
                            consumed = await self.approval_service.consume_approval(existing_approval.id)
                            if not consumed:
                                self._emit_telemetry("EMAIL_REPLAY_BLOCKED", tool_name)
                                obs.status = "APPROVAL_EXPIRED_OR_CONSUMED"
                                obs.result_summary = "Approval is no longer valid."
                                return obs
                            # Successfully consumed, proceed to execution
                            self._emit_telemetry("EMAIL_APPROVED", tool_name)
                            
                        elif existing_approval.status == "REJECTED":
                            self._emit_telemetry("EMAIL_REJECTED", tool_name)
                            obs.status = f"APPROVAL_{existing_approval.status}"
                            obs.result_summary = f"Approval status is {existing_approval.status}"
                            return obs
                        else:
                            obs.status = f"APPROVAL_{existing_approval.status}"
                            obs.result_summary = f"Approval status is {existing_approval.status}"
                            return obs

                # 3. Input Guardrails
                if self.guardrail_engine:
                    # Very basic injection check on text inputs
                    for key, val in arguments.items():
                        if isinstance(val, str):
                            input_check = await self.guardrail_engine.check_input(val)
                            if input_check.status in ["BLOCK", "SANITIZE"]:
                                obs.status = "TOOL_INPUT_BLOCKED"
                                obs.result_summary = "Tool input blocked by security guardrails."
                                return obs

                # 4. Authorization
                is_authorized = await self.auth_engine.authorize(tool, context, typed_args)
                if not is_authorized:
                    obs.status = "TOOL_UNAUTHORIZED"
                    obs.result_summary = "Authorization denied for this action."
                    return obs
                    
                # 5. Execution (with CircuitBreaker and Retry)
                from app.core.reliability import get_circuit_breaker, CircuitBreakerError, with_retry
                import asyncio
                
                cb = get_circuit_breaker(tool_name)
                is_external_read = "EXTERNAL_READ" in [c.value for c in tool.capabilities]
                
                async def _exec():
                    return await asyncio.wait_for(tool.execute(context, typed_args), timeout=30.0)
                    
                # Apply retry decorator only if it is a read tool (idempotent)
                if is_external_read:
                    _exec = with_retry(max_retries=2, delay=1.0)(_exec)
                
                try:
                    result = await cb.call(_exec)
                except CircuitBreakerError:
                    obs.status = "TOOL_CIRCUIT_OPEN"
                    obs.result_summary = f"Circuit breaker OPEN for {tool_name}."
                    return obs
                except asyncio.TimeoutError:
                    obs.status = "TOOL_TIMEOUT"
                    obs.result_summary = "Execution timed out."
                    return obs
                    
                # 6. Schema Validation (Output)
                if not isinstance(result, tool.output_schema):
                    obs.status = "INVALID_TOOL_OUTPUT"
                    obs.result_summary = "Tool returned invalid output format."
                    return obs
                    
                # 7. Output Guardrails & Trust Boundary
                is_external = "EXTERNAL_READ" in [c.value for c in tool.capabilities]
                obs.trust_level = "untrusted" if is_external else "trusted"
                obs.source = "external" if is_external else "internal"
                
                if self.guardrail_engine:
                    result_str = result.model_dump_json()
                    
                    if is_external:
                        # Scan for prompt injection but don't strictly block unless critical
                        from app.core.guardrails.impl.external_content import ExternalContentGuardrail
                        ext_guardrail = ExternalContentGuardrail()
                        ext_check = ext_guardrail.check(result_str)
                        if ext_check.status == "WARN":
                            obs.is_safe = False
                            logger.warning(f"External content injection detected in tool {tool_name}")
                    else:
                        # Standard context check for internal tools (e.g. secret leakage)
                        context_check = await self.guardrail_engine.check_context(result_str)
                        if context_check.status == "BLOCK":
                            obs.status = "TOOL_OUTPUT_BLOCKED"
                            obs.result_summary = "Tool output blocked by security guardrails (e.g. secret leakage)."
                            obs.is_safe = False
                            return obs
                
                # Success
                obs.status = "SUCCESS"
                obs.result_summary = result.model_dump_json()
                self._emit_telemetry("TOOL_EXECUTED", tool_name)
                
            except Exception as e:
                logger.error("Tool execution failed: %s", e, exc_info=True)
                self._emit_telemetry("EMAIL_FAILED", tool_name, str(e))
                obs.status = "TOOL_FAILED"
                obs.result_summary = "An internal error occurred during tool execution."
                obs.error = str(e)
                
            finally:
                obs.duration_ms = (time.time() - start_time) * 1000
                span["status"] = obs.status
                span["duration_ms"] = obs.duration_ms
                
        return obs
