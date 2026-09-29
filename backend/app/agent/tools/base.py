"""Base Tool Abstraction for Agent execution."""

from enum import Enum
from typing import Any, Callable, Type
from pydantic import BaseModel, Field


class ToolRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ToolCapability(str, Enum):
    READ = "READ"
    WRITE = "WRITE"
    EXTERNAL_ACTION = "EXTERNAL_ACTION"
    EXTERNAL_READ = "EXTERNAL_READ"
    CALENDAR_WRITE = "CALENDAR_WRITE"
    COMMUNICATION = "COMMUNICATION"
    DESTRUCTIVE = "DESTRUCTIVE"


class ToolObservation(BaseModel):
    """The structured result of a tool execution."""
    tool_call_id: str
    tool_name: str
    status: str
    result_summary: str
    duration_ms: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    is_safe: bool = True # Flag if output guardrails failed
    trust_level: str = "trusted" # "trusted" for internal, "untrusted" for external
    source: str = "internal" # "internal", "web", "calendar", etc.


class RequestContext(BaseModel):
    """Trusted context provided by the backend, not the LLM."""
    user_id: str
    roles: list[str]
    conversation_id: str
    request_id: str


class BaseTool:
    """Abstract base class for all tools."""
    name: str = "base_tool"
    description: str = "Base description"
    version: str = "1.0.0"
    risk_level: ToolRiskLevel = ToolRiskLevel.LOW
    capabilities: list[ToolCapability] = [ToolCapability.READ]
    
    input_schema: Type[BaseModel]
    output_schema: Type[BaseModel]
    
    def __init__(self, **deps):
        """Initialize with necessary backend dependencies."""
        self.deps = deps
        self.is_enabled = True
        
    async def authorize(self, context: RequestContext, arguments: BaseModel) -> bool:
        """Check if the user is authorized to use this tool with these arguments."""
        return True # Default allow, overridden by specific tools or global auth

    async def execute(self, context: RequestContext, arguments: BaseModel) -> BaseModel:
        """Execute the tool logic. Must return an instance of output_schema."""
        raise NotImplementedError("Tool must implement execute()")
        
    def describe(self) -> dict[str, Any]:
        """Return the description and schema for the LLM prompt."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema.model_json_schema()
        }
        
    @staticmethod
    def hash_arguments(arguments: BaseModel | dict[str, Any]) -> str:
        """Create a secure SHA-256 hash of canonicalized arguments."""
        import hashlib
        import json
        
        if isinstance(arguments, BaseModel):
            arg_dict = arguments.model_dump(mode='json')
        else:
            arg_dict = arguments
            
        # Canonicalize: sort keys, strip whitespace
        canonical_str = json.dumps(arg_dict, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical_str.encode('utf-8')).hexdigest()
