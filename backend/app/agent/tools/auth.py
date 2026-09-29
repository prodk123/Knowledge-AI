"""Tool Authorization Engine."""

import logging
from typing import Any

from app.agent.tools.base import RequestContext, BaseTool, ToolCapability

logger = logging.getLogger(__name__)

class ToolAuthorizationPolicy:
    """Manages explicit authorization policies for tool access."""
    
    def __init__(self):
        # A simple mock matrix for Stage 8.2. In a real system, this would be DB-backed.
        # Key: tool_name, Value: list of allowed roles. (An empty list or missing key means all roles allowed).
        self._policy_matrix: dict[str, list[str]] = {
            "enterprise_search": [], # all authenticated users
            "calculator": [], # all authenticated users
            "document_lookup": [], # all authenticated users (tool enforces row-level auth)
            "conversation_search": [], # all authenticated users (tool enforces row-level auth)
            "admin_tool": ["admin"] # Example future tool
        }

class ToolAuthorizationEngine:
    """Evaluates if a user is authorized to execute a tool."""
    
    def __init__(self, policy: ToolAuthorizationPolicy | None = None):
        self.policy = policy or ToolAuthorizationPolicy()
        
    async def authorize(self, tool: BaseTool, context: RequestContext, arguments: Any) -> bool:
        """
        Determine if the execution is authorized.
        1. Checks global framework policies (e.g. role -> tool matrix).
        2. Delegates to the tool's specific authorization logic for row-level access.
        """
        # Global Matrix Check
        allowed_roles = self.policy._policy_matrix.get(tool.name, [])
        if allowed_roles:
            has_role = any(role in allowed_roles for role in context.roles)
            if not has_role:
                logger.warning("Auth Denied: User %s lacks role for tool %s", context.user_id, tool.name)
                return False
                
        # Tool-Specific Check
        try:
            tool_auth = await tool.authorize(context, arguments)
            if not tool_auth:
                logger.warning("Auth Denied: Tool %s rejected authorization for user %s", tool.name, context.user_id)
                return False
        except Exception as e:
            logger.error("Auth Error during tool %s authorization: %s", tool.name, e)
            return False
            
        return True
