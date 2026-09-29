"""Document Lookup Tool."""

from typing import Any
from pydantic import BaseModel, Field

from app.agent.tools.base import BaseTool, RequestContext, ToolRiskLevel, ToolCapability
from app.rag.vector_store import QdrantVectorStore
from qdrant_client.models import Filter, FieldCondition, MatchValue

class DocumentLookupInput(BaseModel):
    document_id: str = Field(..., description="The unique identifier (UUID) of the document to retrieve.")


class DocumentLookupOutput(BaseModel):
    document_id: str = Field(..., description="The document identifier.")
    content: str = Field(..., description="The combined text content of the document.")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata associated with the document.")


class DocumentLookupTool(BaseTool):
    name = "document_lookup"
    description = "Lookup the exact content of a specific document by its ID. Requires the exact document ID."
    version = "1.0.0"
    risk_level = ToolRiskLevel.LOW
    capabilities = [ToolCapability.READ]
    
    input_schema = DocumentLookupInput
    output_schema = DocumentLookupOutput
    
    def __init__(self, vector_store: QdrantVectorStore, **deps):
        super().__init__(**deps)
        self.vector_store = vector_store
        
    async def execute(self, context: RequestContext, arguments: DocumentLookupInput) -> DocumentLookupOutput:
        client = self.vector_store.client
        collection_name = self.vector_store.collection_name
        
        records, _ = client.scroll(
            collection_name=collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=arguments.document_id)
                    )
                ]
            ),
            limit=1000  # assuming document has < 1000 chunks
        )
        
        if not records:
            raise ValueError(f"Document {arguments.document_id} not found.")
            
        # RBAC Check (on the first chunk, since they all belong to the same doc)
        first_chunk = records[0]
        chunk_roles = set(first_chunk.payload.get("allowed_roles", [])) if first_chunk.payload else set()
        user_roles = set(context.roles)
        
        if chunk_roles and not chunk_roles.intersection(user_roles) and "admin" not in user_roles:
            raise ValueError(f"Document {arguments.document_id} access denied.")
            
        # Combine content and sort by page/chunk if needed. For now just concatenate.
        combined_content = "\n\n".join([r.payload.get("text", "") for r in records if r.payload])
        
        return DocumentLookupOutput(
            document_id=arguments.document_id,
            content=combined_content,
            metadata=first_chunk.payload or {}
        )
