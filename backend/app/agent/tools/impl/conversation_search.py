"""Conversation Search Tool."""

from typing import Any
from pydantic import BaseModel, Field

from app.agent.tools.base import BaseTool, RequestContext, ToolRiskLevel, ToolCapability
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.conversation import Conversation, Message


class ConversationSearchInput(BaseModel):
    query: str = Field(..., description="The search query to find in past conversations.")
    limit: int = Field(5, description="Maximum number of past messages to return.")


class ConversationSearchOutput(BaseModel):
    results: str = Field(..., description="The matching past messages.")
    message_count: int = Field(..., description="Number of messages found.")


class ConversationSearchTool(BaseTool):
    name = "conversation_search"
    description = "Search the user's past conversation history. Use this to recall things the user previously told you."
    version = "1.0.0"
    risk_level = ToolRiskLevel.LOW
    capabilities = [ToolCapability.READ]
    
    input_schema = ConversationSearchInput
    output_schema = ConversationSearchOutput
    
    def __init__(self, db_session_maker, **deps):
        super().__init__(**deps)
        self.db_session_maker = db_session_maker
        
    async def execute(self, context: RequestContext, arguments: ConversationSearchInput) -> ConversationSearchOutput:
        async with self.db_session_maker() as db:
            # We enforce ownership securely by joining with the Conversation table and filtering by user_id
            stmt = (
                select(Message)
                .join(Conversation, Message.conversation_id == Conversation.id)
                .where(
                    Conversation.user_id == context.user_id,
                    Message.content.ilike(f"%{arguments.query}%")
                )
                .order_by(Message.created_at.desc())
                .limit(min(arguments.limit, 20)) # Hard bound
            )
            
            result = await db.execute(stmt)
            messages = result.scalars().all()
            
            if not messages:
                return ConversationSearchOutput(results="No matching past conversations found.", message_count=0)
                
            combined_text = []
            for msg in messages:
                combined_text.append(f"[{msg.created_at.isoformat()}] {msg.role}: {msg.content}")
                
            return ConversationSearchOutput(
                results="\n".join(combined_text)[:10000],
                message_count=len(messages)
            )
