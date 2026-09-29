"""Web Search Tool."""

from typing import Any
from pydantic import BaseModel, Field

from app.agent.tools.base import BaseTool, ToolCapability, ToolRiskLevel, RequestContext
from app.core.config import settings
from app.services.web_provider import get_web_provider

class WebSearchInput(BaseModel):
    query: str = Field(description="The search query.")
    max_results: int = Field(default=5, description="Maximum number of results to return.")

class WebSearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    source: str

class WebSearchOutput(BaseModel):
    results: list[WebSearchResult]

class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search external web information. Returns URLs and snippets from the internet."
    version = "1.0.0"
    risk_level = ToolRiskLevel.LOW
    capabilities = [ToolCapability.EXTERNAL_READ]
    
    input_schema = WebSearchInput
    output_schema = WebSearchOutput
    
    async def execute(self, context: RequestContext, arguments: WebSearchInput) -> WebSearchOutput:
        provider = get_web_provider()
        limit = min(arguments.max_results, settings.web_search_max_results)
        
        results_data = await provider.search(query=arguments.query, max_results=limit)
        results = [WebSearchResult(**item) for item in results_data]
        
        return WebSearchOutput(results=results)
