"""Calendar Search Tool."""

from typing import Any, List
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, field_validator, ValidationInfo

from app.agent.tools.base import BaseTool, ToolCapability, ToolRiskLevel, RequestContext
from app.services.calendar_provider import get_calendar_provider

class CalendarSearchInput(BaseModel):
    query: str = Field(default="", description="Search query to filter events by title or description.")
    start_time: datetime = Field(description="Start time boundary for the search (ISO 8601).")
    end_time: datetime = Field(description="End time boundary for the search (ISO 8601).")

    @field_validator("query", mode="before")
    @classmethod
    def coerce_query(cls, v):
        if isinstance(v, dict) and not v:
            return ""
        if not isinstance(v, str):
            return str(v)
        return v

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def parse_datetime(cls, v, info: ValidationInfo):
        if not v: # handles empty string, None
            tomorrow = datetime.utcnow() + timedelta(days=1)
            if info.field_name == "start_time":
                return tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
            return tomorrow.replace(hour=23, minute=59, second=59, microsecond=999999)
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                pass
        return v

class CalendarSearchOutput(BaseModel):
    events: List[dict[str, Any]]

class CalendarSearchTool(BaseTool):
    name = "calendar_search"
    description = "Search the user's calendar for events within a time range."
    version = "1.0.0"
    risk_level = ToolRiskLevel.LOW
    capabilities = [ToolCapability.EXTERNAL_READ]
    
    input_schema = CalendarSearchInput
    output_schema = CalendarSearchOutput
    
    async def execute(self, context: RequestContext, arguments: CalendarSearchInput) -> CalendarSearchOutput:
        provider = get_calendar_provider()
        
        results = await provider.search_events(
            query=arguments.query,
            start_time=arguments.start_time,
            end_time=arguments.end_time,
            user_id=context.user_id
        )
        
        return CalendarSearchOutput(events=results)
