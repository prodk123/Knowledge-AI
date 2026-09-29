"""Tool Governance and Policy Framework."""

import logging
from enum import Enum
from typing import Any

from pydantic import BaseModel
from app.agent.tools.base import BaseTool, RequestContext, ToolRiskLevel, ToolCapability

logger = logging.getLogger(__name__)


class PolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"
    BLOCKED = "BLOCKED"


class PolicyEvaluationResult(BaseModel):
    decision: PolicyDecision
    reason_code: str
    risk_level: ToolRiskLevel
    policy_version: str = "2026-09-01-v1"


class ToolPolicyEngine:
    """Central policy evaluator for Risk-Based Tool Governance."""
    
    def __init__(self):
        self.policy_version = "2026-09-01-v1"
        
    def evaluate(
        self,
        context: RequestContext,
        tool: BaseTool,
        arguments: Any
    ) -> PolicyEvaluationResult:
        """
        Evaluate whether the tool action is allowed, blocked, or requires approval.
        This is the central deterministic gate for tool governance.
        """
        
        # 1. Evaluate Risk Level
        risk = tool.risk_level
        
        # 2. Hardcoded Stage 8.3 Matrix
        # - LOW: ALLOW
        # - MEDIUM / HIGH: REQUIRES_APPROVAL
        # - CRITICAL: BLOCKED
        
        if risk == ToolRiskLevel.CRITICAL:
            logger.warning("Policy Blocked: Tool %s has CRITICAL risk.", tool.name)
            return PolicyEvaluationResult(
                decision=PolicyDecision.BLOCKED,
                reason_code="CRITICAL_RISK_BLOCKED",
                risk_level=risk,
                policy_version=self.policy_version
            )
            
        if ToolCapability.DESTRUCTIVE in tool.capabilities:
            logger.warning("Policy Blocked: Tool %s has DESTRUCTIVE capability.", tool.name)
            return PolicyEvaluationResult(
                decision=PolicyDecision.BLOCKED,
                reason_code="DESTRUCTIVE_CAPABILITY_BLOCKED",
                risk_level=risk,
                policy_version=self.policy_version
            )
            
        if risk in [ToolRiskLevel.MEDIUM, ToolRiskLevel.HIGH]:
            return PolicyEvaluationResult(
                decision=PolicyDecision.REQUIRES_APPROVAL,
                reason_code=f"{risk.value}_RISK_REQUIRES_APPROVAL",
                risk_level=risk,
                policy_version=self.policy_version
            )
            
        # 3. Default ALLOW for LOW risk without DESTRUCTIVE flags
        return PolicyEvaluationResult(
            decision=PolicyDecision.ALLOW,
            reason_code="LOW_RISK_ALLOWED",
            risk_level=risk,
            policy_version=self.policy_version
        )
