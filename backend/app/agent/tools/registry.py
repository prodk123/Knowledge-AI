"""Tool Registry for discovering and managing tools."""

import logging
from typing import Any, Dict

from app.agent.tools.base import BaseTool

logger = logging.getLogger(__name__)

class ToolRegistry:
    """Manages the registration and discovery of tools."""
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        
    def register(self, tool: BaseTool) -> None:
        """Register a new tool. Raises ValueError on duplicate."""
        if tool.name in self._tools:
            logger.error("Attempted to register duplicate tool: %s", tool.name)
            raise ValueError(f"Tool {tool.name} is already registered.")
        self._tools[tool.name] = tool
        logger.info("Registered tool: %s (v%s)", tool.name, tool.version)
        
    def unregister(self, tool_name: str) -> None:
        """Unregister a tool."""
        if tool_name in self._tools:
            del self._tools[tool_name]
            
    def get_tool(self, tool_name: str) -> BaseTool | None:
        """Retrieve a tool by name."""
        return self._tools.get(tool_name)
        
    def get_all_tools(self) -> list[BaseTool]:
        """List all registered tools."""
        return list(self._tools.values())
        
    def get_enabled_tools(self) -> list[BaseTool]:
        """List all enabled tools."""
        return [t for t in self._tools.values() if t.is_enabled]
        
    def get_tool_descriptions(self) -> list[dict[str, Any]]:
        """Get schema descriptions for LLM tool selection."""
        return [t.describe() for t in self.get_enabled_tools()]
