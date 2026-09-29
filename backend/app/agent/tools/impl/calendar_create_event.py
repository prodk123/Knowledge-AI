"""Calendar Create Event Tool."""

from typing import Any, List
from datetime import datetime
from pydantic import BaseModel, Field

from app.agent.tools.base import BaseTool, ToolCapability, ToolRiskLevel, RequestContext
from app.services.calendar_provider import get_calendar_provider

class CalendarCreateEventInput(BaseModel):
    title: str = Field(description="Title of the calendar event.")
    start_time: datetime = Field(description="Start time (ISO 8601).")
    end_time: datetime = Field(description="End time (ISO 8601).")
    description: str = Field(default="", description="Event description or agenda.")
    location: str = Field(default="", description="Event location or virtual link.")
    attendees: List[str] = Field(default_factory=list, description="List of attendee email addresses.")

class CalendarCreateEventOutput(BaseModel):
    status: str
    event_id: str | None = None
    message: str | None = None
    event_details: dict[str, Any] | None = None

class CalendarCreateEventTool(BaseTool):
    name = "calendar_create_event"
    description = "Create a calendar event. HIGH risk, requires approval."
    version = "1.0.0"
    risk_level = ToolRiskLevel.HIGH
    capabilities = [ToolCapability.EXTERNAL_ACTION, ToolCapability.CALENDAR_WRITE]
    
    input_schema = CalendarCreateEventInput
    output_schema = CalendarCreateEventOutput
    
    async def execute(self, context: RequestContext, arguments: CalendarCreateEventInput) -> CalendarCreateEventOutput:
        provider = get_calendar_provider()
        
        try:
            result = await provider.create_event(
                title=arguments.title,
                start_time=arguments.start_time,
                end_time=arguments.end_time,
                description=arguments.description,
                location=arguments.location,
                attendees=arguments.attendees,
                user_id=context.user_id
            )
            return CalendarCreateEventOutput(
                status="CREATED",
                event_id=result.get("event_id"),
                event_details=result
            )
        except Exception as e:
            return CalendarCreateEventOutput(
                status="FAILED",
                message=str(e)
            )
