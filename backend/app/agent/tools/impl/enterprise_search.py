"""Enterprise Search Tool wrapping existing RAG retrieval."""

from pydantic import BaseModel, Field

from app.agent.tools.base import BaseTool, RequestContext, ToolRiskLevel, ToolCapability
from app.rag.retriever import RetrievalOrchestrator


class EnterpriseSearchInput(BaseModel):
    query: str = Field(..., description="The search query to find in enterprise documents.")


class EnterpriseSearchOutput(BaseModel):
    results: str = Field(..., description="The combined text of retrieved documents.")
    source_count: int = Field(..., description="Number of sources retrieved.")


class EnterpriseSearchTool(BaseTool):
    name = "enterprise_search"
    description = "Search authorized enterprise documents for information. Use this to find company policies, guidelines, and internal knowledge."
    version = "1.0.0"
    risk_level = ToolRiskLevel.LOW
    capabilities = [ToolCapability.READ]
    
    input_schema = EnterpriseSearchInput
    output_schema = EnterpriseSearchOutput
    
    def __init__(self, retrieval_orchestrator: RetrievalOrchestrator, **deps):
        super().__init__(**deps)
        self.retrieval = retrieval_orchestrator
        
    async def execute(self, context: RequestContext, arguments: EnterpriseSearchInput) -> EnterpriseSearchOutput:
        # Pass the allowed roles from the trusted context to ensure RBAC is respected
        chunks = await self.retrieval.retrieve(
            query=arguments.query,
            allowed_roles=context.roles,
            top_k=5
        )
        
        if not chunks:
            return EnterpriseSearchOutput(results="No matching documents found.", source_count=0)
            
        combined_text = []
        for i, chunk in enumerate(chunks, 1):
            combined_text.append(f"--- Document {i} (ID: {chunk.document_id}) ---\n{chunk.content}\n")
            
        return EnterpriseSearchOutput(
            results="\n".join(combined_text)[:15000], # Prevent context flooding (rough bound)
            source_count=len(chunks)
        )
