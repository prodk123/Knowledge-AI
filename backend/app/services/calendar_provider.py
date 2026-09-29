"""Calendar Service Provider."""

import logging
import uuid
from typing import Any, Protocol, List, Dict
from datetime import datetime
from app.core.config import settings

logger = logging.getLogger(__name__)

class CalendarProvider(Protocol):
    async def search_events(self, query: str, start_time: datetime, end_time: datetime, user_id: str) -> List[Dict[str, Any]]:
        ...
        
    async def create_event(self, title: str, start_time: datetime, end_time: datetime, description: str, location: str, attendees: List[str], user_id: str) -> Dict[str, Any]:
        ...

class SandboxCalendarProvider:
    """A safe, sandbox calendar provider (in-memory)."""
    
    def __init__(self):
        self._events: List[Dict[str, Any]] = []

    async def search_events(self, query: str, start_time: datetime, end_time: datetime, user_id: str) -> List[Dict[str, Any]]:
        results = []
        for event in self._events:
            # Basic filtering for sandbox
            if event["user_id"] == user_id:
                if start_time <= event["start_time"] <= end_time or start_time <= event["end_time"] <= end_time:
                    if not query or query.lower() in event["title"].lower() or query.lower() in event["description"].lower():
                        results.append(event)
        return results

    async def create_event(self, title: str, start_time: datetime, end_time: datetime, description: str, location: str, attendees: List[str], user_id: str) -> Dict[str, Any]:
        if len(attendees) > settings.calendar_max_attendees:
            raise ValueError(f"Too many attendees. Max allowed: {settings.calendar_max_attendees}")
            
        duration = (end_time - start_time).total_seconds() / 3600
        if duration > settings.calendar_max_duration_hours:
            raise ValueError(f"Event duration too long. Max allowed: {settings.calendar_max_duration_hours} hours")
            
        if start_time >= end_time:
            raise ValueError("Start time must be before end time")
            
        # Sandbox behavior: simulate API latency
        import asyncio
        await asyncio.sleep(0.5)
        
        event = {
            "event_id": str(uuid.uuid4()),
            "user_id": user_id, # Strict scoping
            "title": title,
            "start_time": start_time,
            "end_time": end_time,
            "description": description,
            "location": location,
            "attendees": attendees,
            "status": "CONFIRMED"
        }
        self._events.append(event)
        logger.info(f"Sandbox created calendar event: {title} for {user_id}")
        return event

# Global instance for stateful sandbox
_sandbox_instance = SandboxCalendarProvider()

def get_calendar_provider() -> CalendarProvider:
    # Always use sandbox for this stage
    return _sandbox_instance
