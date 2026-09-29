"""Web Fetch Tool."""

from pydantic import BaseModel, Field

from app.agent.tools.base import BaseTool, ToolCapability, ToolRiskLevel, RequestContext
from app.services.web_provider import get_web_provider

class WebFetchInput(BaseModel):
    url: str = Field(description="The exact URL to fetch content from.")

class WebFetchOutput(BaseModel):
    url: str
    content: str

class WebFetchTool(BaseTool):
    name = "web_fetch"
    description = "Fetch specific text content from a URL returned by search."
    version = "1.0.0"
    risk_level = ToolRiskLevel.LOW
    capabilities = [ToolCapability.EXTERNAL_READ]
    
    input_schema = WebFetchInput
    output_schema = WebFetchOutput
    
    async def execute(self, context: RequestContext, arguments: WebFetchInput) -> WebFetchOutput:
        provider = get_web_provider()
        
        try:
            content = await provider.fetch(arguments.url)
            return WebFetchOutput(url=arguments.url, content=content)
        except Exception as e:
            return WebFetchOutput(url=arguments.url, content=f"Failed to fetch: {str(e)}")
